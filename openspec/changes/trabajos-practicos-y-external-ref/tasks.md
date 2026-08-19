> **Gobernanza: 🟡 MEDIA.** Implementar con checkpoints. La migración se genera y aplica **únicamente** vía `docker-compose -f docker-compose.local.yml`. El paso 2.4 (reemplazo del constraint de rúbricas) es el único no aditivo del change y tiene gate propio.

## 1. Backend — Modelos nuevos

- [ ] 1.1 (RED) Test: `TrabajoPractico` se instancia con materia, título, `external_ref`, `universidad_id` y `deleted_at` nulo.
- [ ] 1.2 Crear `app/models/trabajo_practico.py` con `SoftDeleteMixin`, `TimestampMixin`, `universidad_id` denormalizado e índice único parcial sobre `(materia_id, external_ref)` con `postgresql_where=text("deleted_at IS NULL")`.
- [ ] 1.3 (RED) Test: `Ejercicio` valida `peso > 0`, hereda `materia_id` y `universidad_id`, y ordena por `orden` dentro del TP.
- [ ] 1.4 Crear `app/models/ejercicio.py` con `trabajo_practico_id`, `materia_id` denormalizado, `universidad_id`, `orden`, `titulo`, `enunciado_md`, `peso` (`Numeric(5,2)`, default 1), `test_cases` (JSONB) e índice único parcial sobre `(materia_id, external_ref)`.
- [ ] 1.5 Registrar ambos modelos en `app/models/__init__.py` y definir las relaciones (`TrabajoPractico.ejercicios`, `Ejercicio.trabajo_practico`, `Ejercicio.rubrica` con `uselist=False`).
- [ ] CHECKPOINT: modelos instanciables y relaciones navegables en tests.

## 2. Backend — Cambios sobre modelos existentes y migración

- [ ] 2.1 Agregar `external_ref` a `app/models/materia.py` (`String(64)`, nullable) con índice único parcial sobre `(universidad_id, external_ref)`.
- [ ] 2.2 Agregar `ejercicio_id` a `app/models/rubrica.py` (`Integer | None`, FK a `ejercicios.id`, índice único) y la relación inversa.
- [ ] 2.3 (RED) Test: cuatro rúbricas con la misma `(materia_id, tipo, numero, anio)`, cada una con su `ejercicio_id`, se persisten sin conflicto.
- [ ] 2.4 Reemplazar el `UniqueConstraint("materia_id","tipo","numero","anio")` de `rubricas` por un `Index(..., unique=True, postgresql_where=text("ejercicio_id IS NULL"))`, replicando el patrón de `uq_entrega_rubrica_alumno`.
- [ ] 2.5 (TRIANGULATE) Test de caracterización: dos rúbricas SIN ejercicio con la misma clave siguen siendo rechazadas, igual que antes del change.
- [ ] 2.6 Verificar contra un dump de producción que no existen filas de `rubricas` que violarían el índice parcial antes de crearlo.
- [ ] 2.7 Generar la migración Alembic con los cinco pasos del plan del design, y escribir a mano el `downgrade` que restituye el `UniqueConstraint` original.
- [ ] 2.8 Aplicar `alembic upgrade head` en el entorno dockerizado local; correr `downgrade` y volver a `upgrade` para verificar la reversibilidad.
- [ ] 🛑 CHECKPOINT: el paso 2.4 es el único no aditivo. Mostrar el SQL generado (up y down) y confirmar antes de dar por cerrada la migración.

## 3. Backend — Schemas y validación

- [ ] 3.1 (RED) Tests de `test_cases`: tipo desconocido falla; caso sin id o sin nombre falla; ids duplicados dentro del ejercicio fallan.
- [ ] 3.2 (RED) Tests de casos ocultos: caso no público con `salida_esperada` → **rechazo** con el id del caso en el mensaje; con `asercion` → rechazo; caso no público correcto → se persiste solo con id, nombre, tipo y visibilidad.
- [ ] 3.3 (RED) Tests de tipo vs. campos: `pytest_assert`/`junit_assert` con entrada o salida → rechazo; `stdin_stdout` con aserción → rechazo.
- [ ] 3.4 Implementar `TestCase` y su validador en `app/schemas/ejercicio.py`.
- [ ] 3.5 Implementar `TrabajoPracticoCreate/Update/Response` y `EjercicioCreate/Update/Response` en `app/schemas/`, con `external_ref` obligatorio y `peso > 0`.
- [ ] 3.6 (TRIANGULATE) Test: los pesos de los ejercicios de un TP **no** se validan contra ningún total (cuatro ejercicios de peso 1 es válido).
- [ ] CHECKPOINT: el contrato de escritura rechaza lo que tiene que rechazar, y rechaza fuerte — nada de descarte silencioso.

## 4. Backend — Repositorios y resolución por `external_ref`

- [ ] 4.1 (RED) Tests de resolución: por `external_ref` vigente devuelve el registro; inexistente devuelve `None`; dado de baja devuelve `None`; de otra universidad devuelve `None`.
- [ ] 4.2 Crear `app/repositories/trabajo_practico_repository.py` y `app/repositories/ejercicio_repository.py` con `get_by_external_ref`, scopeados por universidad activa y filtrando `deleted_at IS NULL`.
- [ ] 4.3 Agregar `get_by_external_ref` al repositorio de materias.
- [ ] 4.4 (TRIANGULATE) Test: mismo `external_ref` en dos materias distintas resuelve correctamente a cada una.
- [ ] CHECKPOINT: la resolución por identificador externo es la única vía de cruce y está scopeada.

## 5. Backend — Servicio y baja lógica en cascada

- [ ] 5.1 (RED) Test: dar de baja un ejercicio marca también su rúbrica como borrada, en la misma operación.
- [ ] 5.2 (RED) Test: ninguna operación de baja elimina filas físicamente.
- [ ] 5.3 Crear `app/services/trabajo_practico_service.py` con alta de TP con ejercicios anidados, alta de la rúbrica por ejercicio, y baja lógica en cascada.
- [ ] 5.4 Mapear los criterios que llegan del cliente a `criterios_json` con el schema de rúbrica existente, derivando `tipo`, `numero` y `anio` del TP.
- [ ] 5.5 (TRIANGULATE) Test: reutilizar el `external_ref` de un TP dado de baja es válido.
- [ ] CHECKPOINT: un TP con cuatro ejercicios se crea completo, con sus cuatro rúbricas, en una sola operación.

## 6. Backend — Permisos y aislamiento

- [ ] 6.1 (RED) Tests: usuario de otra universidad no accede; usuario sin acceso a la materia no accede.
- [ ] 6.2 Implementar `verificar_acceso_trabajo_practico` y `verificar_acceso_ejercicio` en `app/core/permissions.py`, resolviendo por la materia (patrón de `verificar_acceso_rubrica`).
- [ ] 6.3 (TRIANGULATE) Test: el mensaje de error no revela si el recurso existe en otra universidad.
- [ ] CHECKPOINT: scoping multi-tenant verificado en las dos entidades nuevas.

## 7. Verificación y cierre

- [ ] 7.1 `pytest` completo en el backend, sin regresiones.
- [ ] 7.2 Test de no regresión del flujo de Moodle: importar, corregir y devolver una entrega por el camino existente, sin tocar TPs ni ejercicios.
- [ ] 7.3 Verificar que una rúbrica de Moodle sigue cruzándose por su identificador de actividad, sin cambios.
- [ ] 7.4 Documentar en `docs/specs/06-MODELO-DATOS.md` las dos entidades nuevas y el cambio de constraint.
- [ ] 7.5 `openspec validate trabajos-practicos-y-external-ref --strict`.
