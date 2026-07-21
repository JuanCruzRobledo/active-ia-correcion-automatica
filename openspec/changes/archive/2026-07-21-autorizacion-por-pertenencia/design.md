## Context

`backend/app/core/permissions.py` contiene hoy dos familias de funciones que no se distinguen por el nombre:

1. **Guards de rol** (sync, sin DB): `require_admin`, `require_coordinador`, `require_tutor`, `require_gestor`, y sus combinaciones. Legítimos: solo miran `user.rol`.
2. **Guards de pertenencia** (async, con DB): `verificar_acceso_materia`, `verificar_acceso_comision`, `verificar_acceso_materia_de_comision`, `verificar_acceso_unidad`, `verificar_acceso_examen`, `verificar_acceso_rubrica`. Funcionan correctamente y ya se usan en `materias.py`, `comisiones.py`, `unidades.py`, `examenes.py`, `cierre_cursada.py`.

Entre las dos hay dos anomalías que este cambio resuelve:

- **`require_any_authenticated(user)` es `return user`** (`permissions.py:236-260`). Es el único guard de los 20 endpoints de `entregas.py`, `correcciones.py` y `documentos.py`. Los docstrings de esos endpoints dicen *"Authorization: Any authenticated user (Admin, Coordinador, Tutor)"* — lo cual es literalmente cierto y es exactamente el bug.
- **`require_coordinador_of_materia` (`:268`) y `require_tutor_of_comision` (`:317`)** parecen guards de pertenencia por el nombre, pero son sync, no reciben `db`, y el chequeo real está comentado como `TODO`. Solo verifican el rol. Son **código muerto**: sus únicas 6 referencias en `app/` son autorreferencias dentro de `permissions.py`.

**El hueco central**: los dos guards de pertenencia que sí funcionan cubren ejes **mutuamente excluyentes**.

| Guard existente | Eje | Consulta |
|---|---|---|
| `verificar_acceso_comision` (`:487`) | tutor asignado | `ComisionTutor` |
| `verificar_acceso_materia_de_comision` (`:438`) | coordinador de la materia | `Comision.materia_id` → `CoordinadorMateria` |

Ninguno expresa la unión. Un coordinador que pasa por `verificar_acceso_comision` recibe 403 aunque coordine la materia; un tutor que pasa por `verificar_acceso_materia_de_comision` recibe 403 aunque esté asignado a la comisión. Los endpoints de corrección necesitan **ambos**, y por eso hay que construir un guard nuevo en lugar de reutilizar uno existente.

Cadena de FKs relevante: `Correccion.entrega_id → Entrega.id` (unique) · `Entrega.comision_id → Comision.id` · `Comision.materia_id → Materia.id`. Tablas puente: `ComisionTutor(comision_id, tutor_id)`, `CoordinadorMateria(materia_id, coordinador_id)`.

Gobernanza del dominio: **CRÍTICA** (Seguridad). La implementación se revisa línea por línea con aprobación humana.

## Goals / Non-Goals

**Goals:**

- Cerrar SEC-001, SEC-002, SEC-004 y SEC-006 con un guard combinado que exprese la unión de los dos ejes de pertenencia.
- Cubrir los 20 endpoints vulnerables sin regresiones funcionales para usuarios correctamente asignados.
- Validar lotes de IDs **sin N+1** y sin cargar columnas `deferred`.
- Dejar cobertura de tests de authz donde hoy no existe ninguna.
- Que las operaciones de lote sean *parcialmente* ejecutables e **informen** lo omitido, en vez de fallar entero o filtrar en silencio.

**Non-Goals:**

- **No** se cambia el modelo de roles ni se agregan roles nuevos.
- **No** se toca la autorización de los endpoints de Moodle (`/correcciones/{id}/moodle*`): ya validan vía `MoodleGradeService`.
- **No** se unifican los guards de pertenencia ya existentes (`verificar_acceso_materia`, `verificar_acceso_unidad`, etc.) ni se refactorizan los routers que los usan.
- **No** se amplía el acceso de `GESTOR`: sigue fuera del flujo de corrección.
- **No** se introduce un sistema de permisos declarativo/genérico (tipo Casbin o dependencias FastAPI parametrizadas). Ver Decisión 1.
- **No** se corrige que `MoodleGradeService` use solo el eje tutor (un coordinador no puede publicar en Moodle). Es comportamiento preexistente, fuera de alcance; queda anotado en *Open Questions*.

## Decisions

### Decisión 1 — El guard va en el router, no en el service

**Elegido: guard en el router**, con llamada explícita `await verificar_acceso_X(db, current_user, id)` como primera sentencia del handler, igual que `materias.py`, `comisiones.py`, `unidades.py`, `examenes.py` y `cierre_cursada.py`.

Rationale:

- **Es el patrón dominante y verificado del repo**: ~24 call sites en routers contra 2 en un único service (`moodle_grade_service.py`). Un guard en el service sería la excepción, no la regla, y haría el código de seguridad menos predecible de auditar.
- **CLAUDE.md** manda que los routers hagan "HTTP handling" y los services "business logic". La autorización aquí es una decisión de acceso HTTP (403/404), no lógica de dominio: pertenece al borde.
- **Auditabilidad**: con el guard como primera línea del handler, `grep` sobre el router responde "¿está protegido este endpoint?" de un vistazo. Es lo que este cambio necesita, dado que el bug original fue justamente un guard vacío que *parecía* protección.

Alternativas consideradas:

- *Guard en el service*: evita duplicación si un service se llama desde varios routers, y es lo que hace `MoodleGradeService`. Rechazado porque contamina la capa de negocio con `HTTPException` y porque los services afectados (`EntregaService`, `CorreccionService`, `PDFService`, `ExcelService`) tienen métodos reutilizados desde background tasks donde no hay usuario, lo que obligaría a un parámetro `usuario: Usuario | None` — y un `None` que salte el guard es exactamente el tipo de agujero que estamos cerrando.
- *Dependencia FastAPI parametrizada* (`Depends(RequireEntregaAccess())`): más declarativo, pero no sirve para los endpoints de lote (el ID no está en el path sino en el body ya parseado) ni para el scoping de `GET /entregas/`. Terminaría siendo dos mecanismos en vez de uno.

**Excepción deliberada**: los 4 endpoints de lote necesitan la partición `(permitidos, denegados)` para construir la respuesta. El guard sigue invocándose desde el router, pero devuelve la partición en lugar de lanzar; el router decide (403 si todo denegado) y pasa al service solo los IDs permitidos. El service nunca ve un ID no autorizado.

### Decisión 2 — Un guard combinado nuevo, no la composición try/except de los existentes

Se agrega a `permissions.py`:

```
verificar_acceso_comision_o_materia(db, usuario, comision_id) -> None
verificar_acceso_entrega(db, usuario, entrega_id) -> None
verificar_acceso_correccion(db, usuario, correccion_id) -> None
```

`verificar_acceso_comision_o_materia` resuelve la unión en **una sola query**: `LEFT JOIN` desde `Comision` a `ComisionTutor` (por `comision_id` + `tutor_id = user.id`) y a `CoordinadorMateria` (por `Comision.materia_id` + `coordinador_id = user.id`), seleccionando solo si existe al menos una de las dos filas. ADMIN retorna antes de consultar. Comisión inexistente → 404; sin pertenencia → 403.

`verificar_acceso_entrega` y `verificar_acceso_correccion` resuelven la cadena hasta `comision_id` y delegan.

Alternativa rechazada: envolver los dos guards existentes en `try/except HTTPException` y permitir si alguno pasa. Es más corto pero (a) duplica round-trips a la DB en el caso coordinador, (b) confunde el 404 de comisión inexistente con el 403 del primer guard, y (c) usa excepciones como control de flujo en el camino caliente de **cada request**.

### Decisión 3 — Nunca cargar la entidad, solo las columnas de clave

`Entrega.contenido_consolidado` y `Entrega.pdf_contenido_b64` son `deferred=True`. Un guard que hiciera `select(Entrega).where(...)` funcionaría, pero cualquier acceso posterior a esos atributos dispararía una carga adicional, y un `selectinload` accidental arrastraría el código fuente completo del alumno en **cada verificación de permisos**.

Regla para todos los guards nuevos: `select(Entrega.id, Entrega.comision_id)` — nunca `select(Entrega)`. Lo mismo para `Correccion` (`select(Correccion.id, Entrega.comision_id).join(Entrega)`) y `Comision` (`select(Comision.materia_id)`).

Esto además hace las queries index-only en la mayoría de los casos.

### Decisión 4 — Validación de lote en una query, con `IN`

Para los 4 endpoints de lote, una única query resuelve la pertenencia de todo el lote:

```
SELECT Entrega.id
FROM entregas
JOIN comisiones ON entregas.comision_id = comisiones.id
LEFT JOIN comision_tutor ON (comision_tutor.comision_id = comisiones.id AND comision_tutor.tutor_id = :uid)
LEFT JOIN coordinador_materia ON (coordinador_materia.materia_id = comisiones.materia_id AND coordinador_materia.coordinador_id = :uid)
WHERE entregas.id IN :ids
  AND (comision_tutor.id IS NOT NULL OR coordinador_materia.id IS NOT NULL)
```

El resultado es el conjunto de permitidos; `denegados = set(ids) - permitidos`. Para ADMIN se saltea la query y `permitidos = ids`.

Los IDs inexistentes caen naturalmente en `denegados`. Esto es **deliberado**: no distinguir "no existe" de "no tenés acceso" en una operación de lote evita convertir el endpoint en un oráculo de enumeración de IDs. Los endpoints de recurso único sí distinguen 404 de 403, porque ahí el 404 ya es observable por otras vías.

El límite de lote es 100 (`min_length=1, max_length=100`), 50 para `correcciones/lote`: un `IN` de ese tamaño es trivial para Postgres.

### Decisión 5 — Cambio de contrato de los 4 endpoints de lote (BREAKING)

Se agrega a las respuestas la información de omitidos. Forma propuesta, consistente entre los 4:

- `EntregaAccionMasivaResponse` (usado por `archivar` y `masivo`): se suman `omitidas: int` y `ids_omitidos: list[int]` a los `procesadas` / `ids` actuales.
- `CorregirLoteAceptadoResponse`: se suman `omitidas: int` y `entrega_ids_omitidos: list[int]`; `mensaje` menciona las omitidas cuando `omitidas > 0`.
- `POST /documentos/pdfs-seleccionados` devuelve un ZIP binario, no JSON. La información de omitidos viaja en un **header de respuesta** (`X-Entregas-Omitidas` con la lista de IDs), que el frontend lee para el toast. Alternativa rechazada: cambiar el endpoint a JSON con el ZIP en base64 — infla la carga útil y rompe la descarga directa.

**Impacto en el frontend** (todo converge en `EntregasPage.tsx`):

| Archivo | Cambio |
|---|---|
| `frontend/src/features/entregas/types/index.ts` | `EntregaAccionMasivaResponse` y `CorregirLoteAceptadoResponse` suman los campos de omitidos |
| `frontend/src/features/entregas/services/entregas-service.ts` | tipos de retorno de `archivar`, `deleteMasivo`, `corregirLote` |
| `frontend/src/features/correcciones/services/correcciones-service.ts` | `descargarPDFsSeleccionados` pasa a leer el header y devolver los omitidos en vez de `Promise<void>` |
| `frontend/src/features/entregas/pages/EntregasPage.tsx` | `runArchivarSeleccionados`, `runEliminarSeleccionados`, `runCorregirMasiva`, `handleDescargarPDFsSeleccionados` — los toasts hoy muestran solo `result.procesadas` / `total_encoladas` y perderían la señal de omitidos |

Para `DELETE /entregas/masivo` el requisito del usuario es reporte **prominente**: cuando `omitidas > 0`, no alcanza un toast de éxito con un número más. La UI debe usar un toast de advertencia (no de éxito) que diga explícitamente cuántas no se borraron y por qué, porque el borrado es irreversible y el operador necesita saber qué quedó vivo.

### Decisión 6 — `GET /entregas/` hace scoping, no 403

Con `comision_id` explícito → guard normal (403 si es ajena). **Sin** `comision_id` → se filtra la query.

Se agrega `comisiones_visibles_para(db, usuario) -> list[int] | None` (`None` = admin, sin filtro), y `EntregaRepository` aplica el filtro con `JOIN`, siguiendo el patrón ya probado de `comision_repository.py:118-124`. El filtro entra **antes** del `count`, para que el total paginado no revele la cantidad global.

Rechazado: filtrar en Python después de traer la página. Rompe la paginación (una página de 20 podría quedar en 3) y sigue leyendo de la DB datos ajenos.

### Decisión 7 — No se agregan índices

Verificado en los modelos:

- `ComisionTutor`: `UniqueConstraint("comision_id", "tutor_id", name="uq_comision_tutor")` → índice compuesto con `comision_id` como columna líder. Cubre el lookup del guard y el `IN` del lote.
- `CoordinadorMateria`: `UniqueConstraint("coordinador_id", "materia_id", name="uq_coordinador_materia")` → índice compuesto con `coordinador_id` líder. El guard filtra por igualdad en **ambas** columnas, así que el índice aplica.

El hallazgo de auditoría "`ComisionTutor.comision_id` no tiene índice propio" es cierto como columna suelta, pero **la unique constraint ya cubre el caso de uso**, porque `comision_id` es su columna líder. Un índice adicional solo sobre `comision_id` sería redundante y costaría escrituras.

**Ninguna migración de esquema en este cambio.** Si el profiling posterior a producción muestra un problema real, se agrega en un cambio propio con evidencia. No se optimiza a ciegas.

## Risks / Trade-offs

- **Usuarios mal asignados en producción pierden acceso de golpe** → Antes de desplegar, correr una query de auditoría que liste usuarios activos no-ADMIN sin ninguna fila en `ComisionTutor` ni en `CoordinadorMateria`: son los que quedarán bloqueados. Corregir asignaciones primero. Es el riesgo más probable de este cambio, y es de datos, no de código.
- **Cambio de contrato rompe el frontend si se despliegan desacoplados** → Los campos nuevos son **aditivos** (no se renombra ni se elimina nada). Un frontend viejo contra un backend nuevo sigue funcionando: ignora los campos y muestra el conteo de procesadas, solo pierde la señal de omitidos. Permite desplegar backend primero.
- **Silencio en las operaciones de lote si el frontend no se actualiza** → Mitigado por lo anterior más la tarea de frontend en el mismo change; el peor caso transitorio es sub-informar, no operar de más.
- **Una query de autorización extra por request** → Es un lookup index-only sobre tablas puente chicas. Se acepta explícitamente: correctitud sobre latencia en un dominio CRÍTICO. Se evita el N+1 en lotes (Decisión 4), que es donde el costo sí sería real.
- **`POST /correcciones/lote` procesa en background** → El filtrado ocurre **antes** de `background_tasks.add_task`, así que la tarea de fondo nunca recibe IDs no autorizados. Es importante no invertir ese orden: el background task no tiene request ni usuario para re-validar.
- **20 endpoints tocados a mano: riesgo de olvidar uno** → El change incluye un test que enumera los endpoints de los 3 routers y falla si alguno no está cubierto por un test de authz. Es la red de seguridad contra el olvido, y contra futuros endpoints agregados sin guard.
- **`require_any_authenticated` sigue existiendo tras el cambio** → Se usa legítimamente en otros routers donde cualquier autenticado sí puede pasar. No se elimina, pero conviene revisar sus call sites restantes en un cambio aparte (fuera de alcance).

## Migration Plan

1. Auditar asignaciones en la DB de producción (query de usuarios sin pertenencia). Corregir datos.
2. Desplegar backend (campos aditivos: compatible con el frontend actual).
3. Desplegar frontend con el reporte de omitidos.
4. Monitorear 403 en los 20 endpoints durante las primeras 48 h. Un pico de 403 en usuarios legítimos indica asignaciones faltantes, no un bug del guard.

**Rollback**: revertir el commit del backend. No hay migración de esquema ni cambio de datos, así que el rollback es limpio y sin pérdida.

## Open Questions

- **`POST /entregas/masiva` y `POST /entregas/`**: el guard valida `comision_id`. ¿Hay que validar además que `rubrica_id` pertenezca a la materia de esa comisión? Hoy no se valida y permitiría corregir con una rúbrica de otra materia. Es un bug distinto (no un IDOR de lectura); se recomienda change aparte.
- **`MoodleGradeService` usa solo el eje tutor** (`verificar_acceso_comision`), así que un coordinador no puede publicar notas en Moodle aunque coordine la materia. Preexistente y fuera de alcance: decidir si es intencional.
- **`X-Entregas-Omitidas` como header**: si la lista de omitidos fuera larga (hasta 100 IDs) el header queda grande pero muy por debajo de cualquier límite razonable (~800 bytes). Confirmar en revisión que no molesta a ningún proxy intermedio.
- **`GET /correcciones/global/progreso` y `POST /correcciones/global`** ya filtran por `current_user.id` vía `get_subidas_ids_by_tutor`, así que no son IDOR. Confirmar en revisión que ese filtro es suficiente para un coordinador (hoy un coordinador probablemente no ve nada ahí).
