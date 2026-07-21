## Context

`Entrega` (`app/models/entrega.py:26`) hereda solo `TimestampMixin` y no tiene baja lógica. Su flag `archivado` (`:90`) es UI (ocultar del listado), **no** borrado. `Correccion` (`app/models/correccion.py`) tampoco tiene baja lógica. Al borrar, `EntregaService.eliminar_entrega` (`:567-585`) y `eliminar_entregas_masivo` (`:617-643`) hacen `db.delete()` físico **incondicional**: no miran `ALLOW_HARD_DELETE` y no registran `Actividad`. Los repos `EntregaRepository.delete` (`:339-347`) y `delete_by_ids` (`:383-409`) son físicos. Como `Entrega.correccion` (1:1) y `Entrega.historial` tienen `cascade="all, delete-orphan"`, el borrado físico arrastra la nota del alumno de forma irreversible.

El proyecto ya tiene todas las piezas del patrón de soft delete:
- `SoftDeleteMixin` (`app/models/base.py:65-83`): aporta `deleted_at: Mapped[datetime|None]` (default `None`) y `is_deleted`. Hoy solo lo usa `TutorNexo`.
- El patrón a replicar es `MateriaService.eliminar_materia` (`materia_service.py:324-364`): bifurca `if settings.ALLOW_HARD_DELETE: hard_delete_with_cascade() else: soft_delete()`. `MateriaRepository.soft_delete` (`:288-302`) setea el flag + `updated_at` + commit + refresh; `restore` (`:304-318`) es el inverso. Mismo patrón en comisión/rúbrica/usuario.
- Endpoints `POST /{id}/restore` ya existen (materias/comisiones/rúbricas/usuarios, solo admin, ej. `routers/materias.py:149`).
- `ActividadService.registrar_actividad(...)` (`actividad_service.py:28-58`) ya existe; hoy **ningún** borrado registra actividad y `TipoActividadEnum` (`enums.py:57-70`) solo tiene tipos `_CREADO`/`_CREADA`.
- Post-SEC-002, el borrado masivo particiona por `filtrar_entregas_accesibles` (`permissions.py:546`) y el guard de recurso único es `verificar_acceso_entrega` (`permissions.py:491-517`).

Alembic head actual: `b9c4d1e5f3a6` (DB en sync).

**Gobernanza: CRÍTICA** (borrado de datos de alumnos / auditoría). Este change entrega SOLO los artefactos OpenSpec; el código se implementa después con aprobación humana línea por línea.

## Goals / Non-Goals

**Goals:**
- Que el borrado de `Entrega` (individual y masivo) sea baja lógica por defecto (`deleted_at`), reversible y auditado, respetando `ALLOW_HARD_DELETE`.
- Excluir las entregas borradas de listados, detalle y export sin romper el aislamiento del total paginado (SEC-002).
- Endpoint `POST /entregas/{id}/restore` con guard de pertenencia que pueda ver entregas borradas.
- Migración Alembic aditiva sobre `b9c4d1e5f3a6`.
- Convivir con `archivado` (ejes ortogonales) y con la partición por permisos del borrado masivo.

**Non-Goals:**
- **CRUD-003** (versionar la corrección en la recorrección): choca con `Correccion.entrega_id UNIQUE`; es otro problema y otro change.
- **CRUD-002** (rediseño de `ALLOW_HARD_DELETE` como "bomba de config").
- Columna de soft delete propia en `Correccion`: innecesaria — al soft-deletear la entrega no se llama `db.delete`, la cascada no dispara y la corrección queda preservada colgando de la entrega oculta.
- UI de papelera/restore en el frontend (follow-up; ver Decisiones).

## Decisions

### 1. Mecanismo: `deleted_at` timestamp vía `SoftDeleteMixin` (no booleano)
`Entrega` pasa a `class Entrega(Base, TimestampMixin, SoftDeleteMixin)`. Soft delete = `entrega.deleted_at = datetime.utcnow()`; restore = `deleted_at = None`. Las queries default filtran `WHERE deleted_at IS NULL`.
- **Por qué timestamp y no `activo` booleano**: decisión del usuario. El timestamp además deja huella temporal (cuándo se borró) útil para auditoría, sin costo extra frente a un bool. `SoftDeleteMixin` ya existe y ya modela exactamente esto.
- **Alternativa descartada**: un flag `activo`/`eliminado` booleano — pierde la marca temporal y duplicaría lo que el mixin ya provee.

### 2. Bifurcación por `ALLOW_HARD_DELETE`, calcado de Materia
El service replica `MateriaService.eliminar_materia`: `if settings.ALLOW_HARD_DELETE: hard_delete() else: soft_delete()`. Default (flag `False`) = soft; flag `True` = físico con cascada (comportamiento actual, preservado).
- **Por qué**: consistencia con el resto del sistema; el operador que ya activa hard delete para materias espera el mismo interruptor para entregas.

### 3. Repositorio: renombrar semántica y centralizar el filtro
- `delete`/`delete_by_ids` actuales pasan a ser el camino **hard** (renombrar a `hard_delete`/`hard_delete_by_ids` o dejarlos como el brazo físico explícito). Nuevos: `soft_delete(entrega)`, `soft_delete_by_ids(ids)`, `restore(entrega)`.
- Filtro `Entrega.deleted_at.is_(None)` se agrega a la lista `conditions` de `get_all` (`:140`), y a `get_by_id` (`:99-102`) y `get_all_for_export` (`:201+`). Va a la **misma** lista compartida datos+count, igual que search y el scoping de SEC-002 (`:149-150`) — no filtrar rompería el aislamiento del total paginado.
- **Lectura de borradas para el restore**: `get_by_id` filtra borradas, así que el restore necesita un camino que las vea. Decisión: un parámetro `include_deleted: bool = False` en `get_by_id` (o un `get_by_id_incluyendo_borradas`) que el service de restore usa. Mantiene una sola fuente de verdad de la query.

### 4. Guard del restore ve entregas borradas
`verificar_acceso_entrega` (`permissions.py:491-517`) hace su **propia** query `select(Entrega.id, Entrega.comision_id).where(Entrega.id == entrega_id)` sin filtro de `deleted_at` → **ya encuentra** entregas borradas y resuelve la pertenencia correctamente. No hay que tocar el guard: sirve tal cual para el restore. El 404 "no encontrada" de una entrega borrada NO ocurre en el guard; el que debe distinguir "borrada vs inexistente" es el service de restore, leyendo con `include_deleted=True`.
- **Trade-off**: el guard, al no filtrar borrados, permite validar permisos sobre entregas borradas también en el DELETE — inocuo, porque el DELETE de una entrega ya borrada devuelve `400` por la vía del service (escenario idempotencia del spec).

### 5. Auditoría: dos tipos nuevos en `TipoActividadEnum`
Agregar `ENTREGA_ELIMINADA` y `ENTREGA_RESTAURADA`. El service instancia `ActividadService(self.db)` y llama `registrar_actividad` en borrado (soft y hard) y en restore, con `entidad_id`, `entidad_nombre` (ej. nombre del alumno) y `usuario_id` del actor. En masivo, se registra una actividad por entrega efectivamente procesada.
- **Por qué el tipo nuevo**: hoy no existe ningún tipo de eliminación; sin él no se puede tipar el evento de auditoría.

### 6. Índice sobre `deleted_at`: NO (o índice parcial opcional)
La columna es `NULL` en la fila común (el 99% de las entregas no están borradas). Un B-tree sobre una columna mayormente NULL aporta poco al filtro `deleted_at IS NULL` (que matchea casi todo, el planner prefiere seq/scan existente). La migración **no agrega índice**. Si el volumen de borradas creciera, un índice **parcial** `WHERE deleted_at IS NOT NULL` sería lo indicado para consultar la papelera — se deja anotado, fuera de alcance.
- **Por qué**: evitar un índice que no paga su costo de escritura. Las queries de listado ya filtran primero por `comision_id`/scoping, que son los selectivos.

### 7. Frontend: mínimo viable = solo backend, papelera como follow-up
El botón "eliminar" del frontend ya llama al DELETE masivo. Con soft delete la UX **no cambia**: la entrega desaparece del listado igual, pero ahora es recuperable vía backend. Decisión: entregar el `POST /restore` en el backend y **dejar la UI de papelera/restore como follow-up documentado**. Un admin puede restaurar por API mientras tanto; no se bloquea el valor (dejar de perder datos) esperando UI.
- **Alternativa descartada**: construir papelera completa ahora — infla el scope de un change cuyo objetivo es cerrar la pérdida irreversible de datos.

## Risks / Trade-offs

- **[Migración sobre datos existentes]** → La columna se agrega `nullable=True` con default `NULL`; todas las filas actuales quedan como "no borradas". Aditiva, sin backfill, sin downtime.
- **[Corrección huérfana visible]** → Al soft-deletear la entrega, su `Correccion` sigue en la DB. Si alguna query de correcciones no pasa por la entrega, podría mostrar una corrección de entrega borrada. Mitigación: la corrección se accede vía la entrega (1:1); documentar y verificar en tests que los flujos de listado de correcciones no la expongan. No se agrega filtro en `Correccion` (fuera de alcance), pero se anota como área a revisar.
- **[Cascada dispara en hard delete bajo flag]** → Cuando `ALLOW_HARD_DELETE=True`, el borrado físico sigue arrastrando la corrección por cascada. Es el comportamiento deseado y explícito del flag; sin cambios.
- **[Filtro olvidado en alguna query]** → Si una lectura nueva no agrega `deleted_at IS NULL`, expone borradas. Mitigación: centralizar el filtro en los métodos del repo y cubrir con tests los tres puntos (`get_all`, `get_by_id`, `get_all_for_export`).
- **[Doble registro de auditoría en masivo]** → Registrar por entrega puede generar N inserts. Aceptable para el volumen esperado; si fuera problema, batch de actividades sería una optimización posterior.

## Migration Plan

1. Agregar la columna con Alembic: nueva revisión con `down_revision = "b9c4d1e5f3a6"`, `op.add_column("entregas", sa.Column("deleted_at", sa.DateTime(), nullable=True))`. `downgrade` hace `op.drop_column("entregas", "deleted_at")`.
2. `alembic upgrade head` en cada entorno. Aditivo y reversible; sin backfill (todas las filas quedan `deleted_at = NULL` = no borradas).
3. Rollback: `alembic downgrade -1` elimina la columna. Como no se escribe `deleted_at` hasta que el código nuevo esté desplegado, el orden de despliegue (migración antes que código) no rompe nada; y desplegar código sin migración fallaría al escribir la columna, por eso migración primero.

## Open Questions

- ¿El borrado masivo debe registrar una `Actividad` por entrega o una sola agregada por lote? El spec asume una por entrega procesada; a confirmar en apply si el volumen lo hace costoso.
- ¿El restore debe ser solo-admin (como los otros `POST /restore`) o abierto a coordinador/tutor con pertenencia? El resto del sistema usa solo-admin; a decidir con el usuario en apply — el spec deja el guard de pertenencia como piso, la restricción a admin sería un endurecimiento.
