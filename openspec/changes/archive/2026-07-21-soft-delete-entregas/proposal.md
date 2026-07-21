## Why

Hoy `Entrega` y `Correccion` se borran **físicamente** siempre: `EntregaService.eliminar_entrega` y `eliminar_entregas_masivo` llaman `db.delete()` de forma incondicional, sin mirar `ALLOW_HARD_DELETE` y sin registrar ninguna `Actividad`. Esto viola la regla dura del proyecto ("soft delete SIEMPRE, nunca borrado físico, por auditoría") y produce una pérdida irreversible del trabajo del alumno y de su nota, sin huella de quién borró ni cuándo (CRUD-001, 🔴 crítica, `docs/auditoria/02-cruds.md`).

## What Changes

- `Entrega` pasa a heredar `SoftDeleteMixin` (ya existe en `app/models/base.py`), sumando la columna `deleted_at: datetime | None`. El borrado por defecto deja de ser físico y pasa a ser una baja lógica (`deleted_at = utcnow()`).
- `EntregaService.eliminar_entrega` y `eliminar_entregas_masivo` bifurcan según `settings.ALLOW_HARD_DELETE`, idéntico al patrón ya establecido en `MateriaService.eliminar_materia`: flag `False` (default) → soft delete; flag `True` → hard delete físico con cascada (comportamiento actual preservado).
- El borrado (soft o hard) y la restauración registran una `Actividad` de auditoría. Se agrega el tipo `ENTREGA_ELIMINADA` (y el de restauración) a `TipoActividadEnum` — hoy no existe **ningún** tipo de eliminación.
- Las queries de listado/lectura/export (`get_all`, `get_by_id`, `get_all_for_export`) excluyen por defecto las entregas con `deleted_at IS NOT NULL`, sumándose a la lista `conditions` compartida entre datos y count (no filtrar rompería el aislamiento del total paginado de SEC-002).
- Nuevo endpoint `POST /entregas/{id}/restore` (patrón ya existente en materias/comisiones/rúbricas/usuarios) que revierte `deleted_at = NULL`, con guard de pertenencia que **sí** puede ver entregas borradas.
- Migración Alembic (down_revision `b9c4d1e5f3a6`) que agrega la columna `deleted_at` a `entregas`.
- La `Correccion` 1:1 **no se toca** en el soft delete: al no ejecutar `db.delete()`, la cascada `all, delete-orphan` no dispara y la corrección queda preservada colgando de la entrega oculta; al restaurar, vuelve con su nota intacta.

## Capabilities

### New Capabilities
- `entregas-soft-delete`: baja lógica reversible de entregas (individual y masiva) con `deleted_at`, respetando `ALLOW_HARD_DELETE`, con registro de auditoría en borrado y restauración, exclusión de borradas en los listados, y endpoint de restauración.

### Modified Capabilities
<!-- No hay specs formales previas en openspec/specs/ para entregas; el comportamiento se define como capability nueva. Sin deltas. -->

## Impact

- **Modelos**: `app/models/entrega.py` (hereda `SoftDeleteMixin`); `app/models/enums.py` (`TipoActividadEnum` +2 tipos).
- **Migración**: nueva revisión Alembic sobre `b9c4d1e5f3a6` que agrega `entregas.deleted_at`.
- **Repositorio**: `app/repositories/entrega_repository.py` — nuevos `soft_delete` / `restore` / `hard_delete` (renombra la semántica actual), filtro `deleted_at IS NULL` en `get_all` / `get_by_id` / `get_all_for_export`, y capacidad de leer una entrega borrada para el restore.
- **Servicio**: `app/services/entrega_service.py` — `eliminar_entrega` / `eliminar_entregas_masivo` bifurcan por `ALLOW_HARD_DELETE` + `restaurar_entrega`; instancian `ActividadService`.
- **Router**: `app/routers/entregas.py` — nuevo `POST /{id}/restore`; el DELETE existente conserva su contrato HTTP (la UX del frontend no cambia).
- **Permisos**: reutiliza `verificar_acceso_entrega` (`app/core/permissions.py`); el restore necesita un guard que no trate a la entrega borrada como "no encontrada".
- **Frontend**: sin cambios funcionales obligatorios (la entrega desaparece del listado igual); UI de papelera/restore queda como follow-up documentado.
- **Fuera de alcance**: CRUD-003 (versionar corrección en recorrección), CRUD-002 (rediseño de `ALLOW_HARD_DELETE`), columna de soft delete propia en `Correccion`.
