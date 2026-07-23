## Why

Fase 4 de 7 del feature multi-tenant (fases 0..6). Las Fases 0-3 dejaron la estructura lista: la columna `universidad_id` existe (denormalizada) en las 9 entidades del core, el JWT porta `universidad_activa_id`, `get_universidad_activa` entrega el `ContextoUniversidad` (`universidad_id`, `rol`, `es_superadmin`), y `permissions.py` ya resuelve el rol contra la membresía activa. **Pero la estructura todavía no se USA para filtrar datos**: hoy toda query de listado/búsqueda devuelve registros de TODAS las universidades, y acceder por id a un recurso de otra universidad no está bloqueado. Esta es la fase de **ALTO riesgo**: acá se cierra el aislamiento de datos real. Una sola query sin filtrar = datos de otra universidad expuestos.

El invariante que hace esta fase segura de mergear hoy: con los datos actuales (todo migrado a TUPaD, una sola universidad) el comportamiento observable NO cambia — todos siguen viendo lo que veían. La diferencia se vuelve visible SOLO cuando exista una segunda universidad.

## What Changes

- **Filtrado por `universidad_id` en repositories**: cada método de repositorio que lista/busca/cuenta las 9 entidades scopeadas (`materias`, `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots`) suma un parámetro `universidad_id: int | None` y aplica `WHERE universidad_id = :activa`. El `WHERE` vive en el REPOSITORY (ARCH-001), el service pasa el valor tomado de `ctx.universidad_id`.
- **Check de pertenencia al acceder por id**: al traer un recurso por id (get materia X, entrega Y, corrección Z), validar que `recurso.universidad_id == universidad_activa`. Si no coincide → **404** (no 403: no revelar que el recurso existe en otra universidad). Se reutiliza/generaliza el guard defensivo que dejó Fase 3 (`verificar_materia_universidad_activa` / `materia_pertenece_a_universidad_activa`), pero con semántica 404 para el acceso general por id.
- **Propagación `universidad_id`** router (ya tiene `ctx`) → service → repository, con un patrón mínimo, consistente y keyword-only, calcado del patrón ya existente `comisiones_visibles` en `entrega_repository.get_all`.
- **Bypass de superadmin**: `ctx.universidad_id is None` (superadmin sin universidad activa) ⇒ el repositorio NO aplica el filtro ⇒ ve todas las universidades. Si el superadmin eligió una universidad, `ctx.universidad_id` está seteado y se comporta como cualquier miembro (ver Open Question #2 del design).
- **Cierre de la DEUDA de `comisiones.py`** (arrastrada de Fase 2): `listar_comisiones`, `obtener_comision` y `actualizar_moodle_comision` todavía chequean rol con `current_user.rol` INLINE (rol global viejo) en vez de vía `ctx`. Se migran a `ctx` y se les suma el scoping por universidad.
- **Dashboard / agregaciones**: las métricas de `dashboard.py` / `dashboard_gestores.py` se calculan scopeadas a la universidad activa (ninguna agregación queda global salvo la del superadmin sin universidad activa).
- **Tests de aislamiento con 2 universidades** como corazón de la verificación (gate): un usuario de UniA NO ve NADA de UniB (list vacío / 404 en get), y el superadmin sí ve ambas.

**Fuera de alcance** (para no invadir otras fases): frontend / selector de workspace (Fase 5); eliminación de campos viejos `usuarios.rol` / `usuarios.moodle_*` (Fase 6); re-hacer auth (Fase 1) o la fuente de credenciales Moodle (Fase 3). No se toca la migración de datos (Fase 0). No se crean ni borran columnas: `universidad_id` ya existe.

## Capabilities

### New Capabilities
- `aislamiento-datos-por-universidad`: toda query de datos (listado, búsqueda, conteo, agregación de dashboard) filtra por la universidad activa, y todo acceso por id valida pertenencia a la universidad activa (404 si es de otra). Define el patrón de propagación `ctx.universidad_id` → service → repository, el comportamiento de bypass del superadmin, y los tests de aislamiento con 2 universidades.

### Modified Capabilities
<!-- Ninguna capability existente cambia sus REQUISITOS. La deuda de comisiones.py se
     resuelve como parte de la nueva capability (migrar de current_user.rol a ctx + scoping);
     no altera un requisito ya escrito de permisos-universidad-activa, lo completa hacia el
     aislamiento por universidad, que es el objeto de esta nueva capability. -->

## Impact

- **Riesgo**: ALTO (aislamiento de datos / seguridad multi-tenant). Governance HIGH: proponer artefactos y esperar aprobación humana antes de escribir código.
- **Depende de**: Fase 0 (`universidad_id` denormalizado), Fase 1 (`get_universidad_activa` / `ContextoUniversidad`), Fase 2 (`permissions.py` con `ctx` + `_acceso_total`), Fase 3 (guard defensivo `verificar_materia_universidad_activa`).
- **Código afectado**:
  - Repositories: `materia_repository.py`, `comision_repository.py`, `entrega_repository.py`, `correccion_repository.py`, `unidad_repository.py`, `rubrica_repository.py`, `examen_repository.py`, `cierre_cursada_repository.py`, `avance_repository.py`, `dashboard_repository.py`.
  - Services: los services que consumen esos repositories (`materia_service.py`, `comision_service.py`, `entrega_service.py`, `correccion_service.py`, `unidad_service.py`, `rubrica_service.py`, `examen_service.py`, `cierre_cursada_service.py`, `snapshot_service.py` / `avance`, `dashboard_service.py` / `dashboard_lectura_service.py`) — ganan el parámetro `universidad_id` de paso.
  - Routers: `comisiones.py` (deuda), y cualquier router que hoy pase filtros al service sin `ctx.universidad_id` (`materias.py`, `entregas.py`, `correcciones.py`, `rubricas.py`, `unidades.py`, `examenes.py`, `dashboard.py`, `dashboard_gestores.py`, `cierre_cursada.py`, `avance`).
  - `permissions.py`: se añade/generaliza un check de pertenencia por id con semántica 404 (sin borrar el guard 409 de Fase 3, que sigue sirviendo a los flujos de sync Moodle).
- **Sin cambios de esquema/DB**: `universidad_id` ya existe. No hay migración Alembic en esta fase.
- **Nota sobre `universidad_id` nullable**: hoy la columna es nullable (backfill histórico de Fase 0). El filtro debe decidir explícitamente cómo tratar filas con `universidad_id IS NULL` para preservar el invariante mono-tenant (ver design, Open Question #4).
