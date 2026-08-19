## Context

Estado verificado en el código al 2026-08-19:

- `Rubrica` (`app/models/rubrica.py`) ya es la unidad de corrección completa: `criterios_json` jerárquico (criterio → subcriterio → evidencias) con peso por subcriterio desde `schema_version = 2`, `penalizaciones_json`, `condiciones_desaprobacion_json`, `puntaje_maximo`, `metadata_json`, `modo_consolidacion`.
- `Rubrica.moodle_assign_id` (L116, `Integer | None`) es el único vínculo con una actividad externa, y es el `cmid` de Moodle. Se setea a mano vía `PUT /api/v1/rubricas/{id}`.
- `Rubrica.__table_args__` (L155-163) declara `UniqueConstraint("materia_id", "tipo", "numero", "anio", name="uq_rubrica_materia_tipo_numero_anio")`.
- `Entrega.__table_args__` (`app/models/entrega.py:133-141`) ya usa el patrón de **índice parcial**: `Index("uq_entrega_rubrica_alumno", "rubrica_id", "alumno_nombre", unique=True, postgresql_where=text("deleted_at IS NULL"))`.
- `Materia` (`app/models/materia.py`) tiene `codigo`, `nombre`, `universidad_id`, `moodle_course_id`, y un `UniqueConstraint` sobre el código.
- El proyecto denormaliza `universidad_id` en toda entidad scopeada (patrón multi-tenant Fase 0: `rubricas`, `entregas`, `correcciones`).
- `SoftDeleteMixin` (`app/models/base.py:65-83`) aporta `deleted_at`. Regla dura del proyecto: los DELETE son siempre soft.

Governance: **MEDIA** — modelo de datos y lógica de dominio. Implementar con checkpoints; la migración se genera y aplica únicamente vía `docker-compose -f docker-compose.local.yml`.

## Goals / Non-Goals

**Goals**

- Poder corregir de a un ejercicio, que es lo que desactiva el modo de fallo "presencia, no vínculo".
- Cruzar entidades por un identificador que el cliente controla, sin depender de Moodle.
- Reutilizar íntegramente el motor de corrección existente.
- No romper absolutamente nada del flujo de Moodle.

**Non-Goals**

- No se exponen endpoints públicos en este change (van en `api-escritura-trabajos-practicos`).
- No se corrige por ejercicio todavía (va en `correccion-por-ejercicio-con-tests`).
- Active-IA **no** ejecuta código ni tests. Nunca.
- No se calcula la nota final del TP: Active-IA devuelve nota por ejercicio, el promedio ponderado lo hace el cliente.
- No se migra ninguna rúbrica existente de Moodle a la estructura nueva.

## Decisions

### D1. Un ejercicio es dueño de una `Rubrica` existente, no de un modelo nuevo

El documento de AI-Native dibuja `ejercicio → rubrica` como si la rúbrica fuera una estructura nueva a crear. No lo es: la `Rubrica` de Active-IA ya tiene criterios jerárquicos con peso, subcriterios con peso propio, penalizaciones y condiciones de desaprobación. Es estrictamente más expresiva que el `{ criterios: [{ nombre, descripcion, puntaje_max }] }` que ellos mandan.

Decisión: `Ejercicio` **1:1** con `Rubrica`. Los criterios que llegan del cliente se mapean a `criterios_json` con el schema existente.

Rationale: el motor de corrección, el generador de PDF, el historial de correcciones, el cálculo determinístico de la nota y todo el frontend de correcciones siguen funcionando sin tocar una línea. Duplicar el modelo de rúbrica significaría duplicar los seis.

Alternativa descartada: `Ejercicio` con sus propios criterios en JSONB. Más fiel al dibujo del documento, pero obliga a bifurcar el motor en dos caminos que hay que mantener sincronizados para siempre — y a reimplementar el desglose por subcriterio, las penalizaciones y el PDF.

### D2. La FK del vínculo va en `rubricas`, no en `ejercicios`

`rubricas.ejercicio_id`: `Integer | None`, FK a `ejercicios.id`, con **índice único** para forzar el 1:1.

Rationale: es lo que permite D3. Poniendo la FK del lado de la rúbrica, la condición del índice parcial (`ejercicio_id IS NULL`) se evalúa sobre la propia tabla `rubricas`, sin joins. Con la FK del lado de `ejercicios` habría que denormalizar un flag en `rubricas` para lograr lo mismo, que es peor.

La navegación `ejercicio.rubrica` se resuelve con `relationship(uselist=False)`.

### D3. `uq_rubrica_materia_tipo_numero_anio` pasa a ser un índice parcial

**Este es el punto no obvio del change.** Cuatro ejercicios del "TP 2" de una materia necesitan cuatro rúbricas, y las cuatro tendrían `materia_id`, `tipo=TP`, `numero=2`, `anio=2026` idénticos. El `UniqueConstraint` actual **lo impide**: la segunda rúbrica del TP falla al insertarse.

Decisión: reemplazar el `UniqueConstraint` por un índice único parcial:

```python
Index(
    "uq_rubrica_materia_tipo_numero_anio",
    "materia_id", "tipo", "numero", "anio",
    unique=True,
    postgresql_where=text("ejercicio_id IS NULL"),
)
```

Rationale: las rúbricas de Moodle (`ejercicio_id IS NULL`) mantienen **exactamente** la unicidad que tienen hoy — cero cambio de comportamiento para el flujo existente. Las rúbricas que pertenecen a un ejercicio quedan exentas, y su unicidad la garantiza el `external_ref` del ejercicio. Y el patrón ya está establecido en el repo (`uq_entrega_rubrica_alumno`).

`tipo`, `numero` y `anio` siguen siendo `NOT NULL`, así que las rúbricas de ejercicio se crean con valores derivados del TP (`tipo=TP`, `numero` del TP, `anio` en curso). Dejan de ser una clave, pasan a ser metadata.

### D4. `external_ref` es único por materia, y la materia lo es por universidad

- `materias.external_ref`: `String(64) | None`, único por `(universidad_id, external_ref)`.
- `trabajos_practicos.external_ref`: `String(64)`, único por `(materia_id, external_ref)`.
- `ejercicios.external_ref`: `String(64)`, único por `(materia_id, external_ref)`.

`Ejercicio` **denormaliza `materia_id`** además de su `trabajo_practico_id`. Rationale: el documento pide `external_ref` "único por materia", y sin la denormalización esa unicidad requeriría un join en cada validación. El proyecto ya denormaliza por esta misma razón (`universidad_id` en `rubricas`, `entregas`, `correcciones`), así que es el idioma de la casa.

Los tres índices son **parciales sobre `deleted_at IS NULL`**: un TP borrado no debe bloquear la republicación de otro con el mismo `external_ref`.

`external_ref` es nullable en `Materia` (las materias existentes de Moodle no tienen ninguno) y **no nullable** en las dos entidades nuevas (nacen de la integración; sin identificador externo no tienen para qué existir).

**Formato**: `String(64)`, no `UUID` nativo. AI-Native manda UUIDs, pero atarse al tipo `UUID` de Postgres cierra la puerta a otro cliente que use otro formato de identificador. El campo es opaco para Active-IA: se guarda y se compara, no se interpreta.

### D5. `cmid` no se toca

`rubricas.moodle_assign_id` queda exactamente como está. Una rúbrica de Moodle se cruza por `cmid`; una rúbrica de ejercicio se cruza por el `external_ref` de su ejercicio. Son dos caminos independientes que conviven, y ninguna rúbrica usa los dos.

### D6. `test_cases` es JSONB con validación de shape, y los ocultos se guardan mutilados a propósito

`ejercicios.test_cases`: JSONB, lista de objetos `{ id, nombre, tipo, entrada?, salida_esperada?, asercion?, es_publico }`, con `tipo` en `stdin_stdout` / `pytest_assert` / `junit_assert`.

Regla dura: **si `es_publico` es falso, `salida_esperada` y `asercion` NO se almacenan.** El schema rechaza el alta si vienen. Los casos ocultos guardan solo `id`, `nombre`, `tipo` y `es_publico`, para que el motor sepa que existen, cuántos son y qué evalúan.

Rationale, y es del cliente, no nuestro: el PDF de devolución se le entrega al alumno. **Lo que el motor nunca recibió no lo puede citar.** Pedirle por escrito que no lo cite sería depender de que honre una regla declarada — y de este motor ya está medido que no lo hace (el 2026-08-17 la rúbrica pedía una penalización del 30% y aplicó 0%). Un caso oculto que aparezca en una devolución deja de estar oculto para toda la cohorte.

**Rechazo en lugar de descarte silencioso**: si el cliente manda `salida_esperada` en un caso oculto, la operación falla con error de validación. Falla en el momento más barato — el docente publicando el TP — y no en el momento caro, con un alumno esperando su corrección. Descartar en silencio dejaría al cliente creyendo que su contrato se respeta cuando en realidad se le está limpiando el payload.

Para `pytest_assert` y `junit_assert` el código **es** el criterio (`assert suma(2,3) == 5`), así que va en `asercion` y no en `entrada`/`salida_esperada`, y solo si el caso es público.

### D7. `peso` es relativo dentro del TP y no se valida contra 100

`ejercicios.peso`: `Numeric(5,2)`, default `1.00`, mayor que 0.

Rationale: el cliente dice explícitamente que **no** pide que Active-IA calcule la nota final del TP — el promedio ponderado lo hace él. Entonces el peso acá es metadata de contexto, no un input de cálculo. Validar que sume 100 impondría una restricción que el consumidor no pidió y que rompería pushes legítimos.

### D8. Soft delete y scoping multi-tenant en las dos entidades nuevas

Ambas heredan `SoftDeleteMixin` y llevan `universidad_id` denormalizado, indexado, propagado desde la materia. Los repositorios filtran por universidad activa como el resto del proyecto, y `verificar_acceso_trabajo_practico` / `verificar_acceso_ejercicio` resuelven la pertenencia vía la materia (patrón de `verificar_acceso_rubrica`).

## Risks / Trade-offs

- **La migración toca un constraint de una tabla con datos de producción.** Es la parte delicada: hay que dropear `uq_rubrica_materia_tipo_numero_anio` y crear el índice parcial. Si hubiera filas que hoy violan la unicidad (no debería, el constraint las impide), la creación del índice falla. Mitigación: verificar duplicados antes en un dump, y `downgrade` probado que restituye el constraint original.
- **`Ejercicio` denormaliza `materia_id`.** Si un TP se moviera de materia, habría que propagar. Mitigación: mover un TP de materia no es una operación soportada; el `external_ref` la haría ambigua de todos modos.
- **1:1 ejercicio-rúbrica significa que borrar un ejercicio deja una rúbrica huérfana.** Mitigación: el soft delete del ejercicio soft-deletea su rúbrica en la misma operación de servicio.
- **`String(64)` puede quedar corto** si un cliente futuro usa identificadores más largos. Es un `ALTER TYPE` barato si pasa.

## Migration Plan

Una sola migración Alembic, generada y aplicada vía `docker-compose -f docker-compose.local.yml`:

1. `CREATE TABLE trabajos_practicos` y `CREATE TABLE ejercicios`.
2. `ALTER TABLE materias ADD COLUMN external_ref VARCHAR(64) NULL` + índice único parcial.
3. `ALTER TABLE rubricas ADD COLUMN ejercicio_id INTEGER NULL` + FK + índice único.
4. `DROP CONSTRAINT uq_rubrica_materia_tipo_numero_anio` + `CREATE UNIQUE INDEX ... WHERE ejercicio_id IS NULL`.
5. `downgrade` que revierte los cuatro pasos, restituyendo el `UniqueConstraint` original.

Todo aditivo salvo el paso 4, que preserva la semántica para las filas existentes. Ninguna fila se modifica ni se backfillea.

## Open Questions

- ¿`Materia.external_ref` lo setea un admin a mano una vez por materia del piloto, o se expone un endpoint? La propuesta asume **a mano** (son pocas materias y es una operación de configuración inicial). Si el piloto escala a muchas materias, conviene un endpoint.
- ¿Un `TrabajoPractico` debería poder vincularse también a una `Unidad` existente, para que aparezca en el Dashboard de Gestores? Queda fuera de alcance; se anota porque `rubricas.unidad_id` ya existe y podría heredarse.
