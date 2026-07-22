# entregas-soft-delete Specification

## Purpose
TBD - created by archiving change soft-delete-entregas. Update Purpose after archive.
## Requirements
### Requirement: Baja lógica de entrega individual

El sistema SHALL borrar una `Entrega` de forma lógica (soft delete) por defecto, seteando `deleted_at` al timestamp actual en lugar de eliminarla físicamente, preservando la fila y su `Correccion` asociada para auditoría. El comportamiento SHALL bifurcar según `settings.ALLOW_HARD_DELETE`: con el flag en `False` (default) hace baja lógica; con el flag en `True` mantiene el borrado físico con cascada.

#### Scenario: Borrado por defecto es lógico
- **WHEN** un usuario con permiso elimina una entrega existente y `ALLOW_HARD_DELETE` es `False`
- **THEN** la entrega queda con `deleted_at` seteado (no NULL), la fila sigue en la base de datos, y su `Correccion` 1:1 se conserva sin cambios

#### Scenario: Borrado físico bajo flag explícito
- **WHEN** un usuario con permiso elimina una entrega existente y `ALLOW_HARD_DELETE` es `True`
- **THEN** la entrega y su `Correccion` se eliminan físicamente con la cascada actual (comportamiento previo preservado)

#### Scenario: Entrega inexistente
- **WHEN** se solicita eliminar una entrega cuyo id no existe
- **THEN** el sistema responde `404 Not Found` y no modifica ningún registro

#### Scenario: Doble borrado lógico es idempotente en efecto
- **WHEN** se elimina lógicamente una entrega que ya tiene `deleted_at` seteado
- **THEN** el sistema responde con un error de validación (`400`) indicando que la entrega ya está eliminada, sin alterar el `deleted_at` original

### Requirement: Baja lógica masiva respetando permisos

El sistema SHALL soportar el borrado lógico masivo de entregas, borrando lógicamente solo las entregas a las que el usuario tiene acceso (partición por `filtrar_entregas_accesibles`, SEC-002) y devolviendo cuáles fueron procesadas y cuáles omitidas. La bifurcación por `ALLOW_HARD_DELETE` SHALL aplicar igual que en el borrado individual.

#### Scenario: Borrado masivo lógico de las permitidas
- **WHEN** un usuario solicita borrar un lote de ids y `ALLOW_HARD_DELETE` es `False`
- **THEN** el sistema setea `deleted_at` solo en las entregas permitidas, deja intactas las no permitidas o inexistentes, y devuelve la lista de procesadas y de omitidas

#### Scenario: Borrado masivo físico bajo flag
- **WHEN** un usuario solicita borrar un lote de ids y `ALLOW_HARD_DELETE` es `True`
- **THEN** el sistema borra físicamente con cascada solo las entregas permitidas y devuelve procesadas/omitidas

### Requirement: Restauración de entrega borrada

El sistema SHALL exponer `POST /entregas/{id}/restore` que revierte la baja lógica seteando `deleted_at = NULL`. El guard de acceso SHALL poder resolver una entrega borrada (una entrega con `deleted_at` seteado NO se considera "no encontrada" para el restore) y validar la pertenencia del usuario a su comisión/materia.

#### Scenario: Restauración exitosa
- **WHEN** un usuario con acceso restaura una entrega que tiene `deleted_at` seteado
- **THEN** el sistema pone `deleted_at = NULL`, la entrega vuelve a aparecer en los listados, y su `Correccion` sigue asociada con su nota intacta

#### Scenario: Restaurar una entrega no borrada
- **WHEN** se solicita restaurar una entrega cuyo `deleted_at` ya es NULL
- **THEN** el sistema responde `400 Bad Request` indicando que la entrega no está eliminada

#### Scenario: Restore sin permiso sobre la comisión
- **WHEN** un usuario sin pertenencia a la comisión/materia de la entrega intenta restaurarla
- **THEN** el sistema responde `403 Forbidden` y no modifica el registro

#### Scenario: Restore de id inexistente
- **WHEN** se solicita restaurar un id que nunca existió
- **THEN** el sistema responde `404 Not Found`

### Requirement: Los listados y exports excluyen entregas borradas

El sistema SHALL excluir por defecto las entregas con `deleted_at IS NOT NULL` de las lecturas: `get_all` (listado paginado), `get_by_id` (detalle) y `get_all_for_export`. El filtro `deleted_at IS NULL` SHALL sumarse a la lista `conditions` compartida entre la query de datos y la de count, de modo que el total paginado no revele la existencia de entregas borradas. El eje `deleted_at` SHALL ser ortogonal al flag `archivado`: el listado default excluye ambos (archivadas y borradas).

#### Scenario: Listado por defecto oculta borradas
- **WHEN** se listan entregas de una comisión que contiene entregas borradas y no borradas
- **THEN** la respuesta incluye solo las no borradas y el total refleja únicamente las no borradas

#### Scenario: Detalle de entrega borrada no accesible por la vía normal
- **WHEN** se solicita `get_by_id` de una entrega con `deleted_at` seteado
- **THEN** la consulta normal no la devuelve (se comporta como no encontrada para el flujo de detalle)

#### Scenario: Export excluye borradas
- **WHEN** se exportan las entregas con filtros
- **THEN** el export no incluye ninguna entrega con `deleted_at` seteado

#### Scenario: Ortogonalidad archivado vs borrado
- **WHEN** una entrega está archivada (`archivado = True`) pero no borrada (`deleted_at IS NULL`)
- **THEN** su visibilidad se rige por los filtros de archivado existentes, independientemente del filtro de borrado

### Requirement: Auditoría de borrado y restauración

El sistema SHALL registrar una `Actividad` de auditoría cada vez que una entrega se borra (lógica o físicamente) y cada vez que se restaura, usando `ActividadService.registrar_actividad`. `TipoActividadEnum` SHALL incluir un tipo para la eliminación de entrega y otro para la restauración. El registro SHALL incluir el `entidad_id` de la entrega y el `usuario_id` del actor cuando esté disponible.

#### Scenario: Borrado registra actividad
- **WHEN** se elimina una entrega (lógica o físicamente)
- **THEN** se crea una `Actividad` con el tipo de eliminación de entrega, el id de la entrega y el usuario que ejecutó la acción

#### Scenario: Restauración registra actividad
- **WHEN** se restaura una entrega borrada
- **THEN** se crea una `Actividad` con el tipo de restauración de entrega, el id de la entrega y el usuario que ejecutó la acción

#### Scenario: Borrado masivo registra por entrega procesada
- **WHEN** se borran lógicamente N entregas en un lote
- **THEN** se registra una `Actividad` de eliminación por cada entrega efectivamente procesada (no por las omitidas)

