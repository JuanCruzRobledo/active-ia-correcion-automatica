# historial-correcciones Specification

## Purpose
TBD - created by archiving change historial-correcciones. Update Purpose after archive.
## Requirements
### Requirement: Snapshot de la corrección saliente en cada recorrección

Cuando una entrega que YA tiene una corrección es recorregida, el sistema SHALL persistir un snapshot inmutable y completo de la corrección saliente en la tabla `correccion_historial` ANTES de borrarla físicamente. El snapshot SHALL preservar: `nota`, `criterios_json`, `fortalezas`, `recomendaciones`, `comentario_general`, `nota_antes_penalizaciones`, `condicion_desaprobacion_aplicada`, `penalizaciones_aplicadas`, `editado_manualmente`, `corregido_por_id` (autor de la corrección saliente), `raw_response`, `correccion_creada_en` (el `created_at` original de la corrección saliente), `reemplazada_en` (timestamp de la recorrección) y `reemplazada_por_id` (usuario que disparó la recorrección).

El snapshot SHALL capturarse leyendo la corrección saliente completa, incluida la columna `raw_response` (que es `deferred=True` y por tanto debe cargarse explícitamente antes del borrado).

#### Scenario: Recorrección preserva la corrección anterior

- **WHEN** una entrega con una corrección existente (nota 8.00) es recorregida y obtiene una nueva nota (4.00)
- **THEN** existe una fila en `correccion_historial` para esa entrega con `nota = 8.00` y el resto de los campos de la corrección saliente
- **AND** la tabla `correcciones` conserva una única corrección vigente para la entrega, con la nueva nota (4.00)

#### Scenario: Se preserva la edición manual del tutor

- **WHEN** la corrección saliente tenía `editado_manualmente = true` (un tutor ajustó la nota a mano) y la entrega es recorregida
- **THEN** el snapshot en `correccion_historial` conserva `editado_manualmente = true`

#### Scenario: Se preserva el raw_response deferred

- **WHEN** la corrección saliente tenía un `raw_response` no nulo y la entrega es recorregida
- **THEN** el snapshot en `correccion_historial` conserva ese `raw_response` intacto

#### Scenario: La primera corrección no genera snapshot

- **WHEN** una entrega sin corrección previa es corregida por primera vez
- **THEN** NO se crea ninguna fila en `correccion_historial`
- **AND** la entrega queda en estado CORREGIDA con su corrección vigente

### Requirement: Registro de actividad de la recorrección

Cuando una recorrección reemplaza una corrección existente, el sistema SHALL registrar una `Actividad` de tipo `CORRECCION_RECORREGIDA` asociada a la entrega afectada, con el `usuario_id` del actor que disparó la recorrección. Este es el registro de auditoría del borrado, que hoy no existe.

#### Scenario: La recorrección queda auditada

- **WHEN** una entrega con corrección existente es recorregida por un usuario
- **THEN** se registra una `Actividad` de tipo `CORRECCION_RECORREGIDA` con `entidad_id` = id de la entrega y `usuario_id` = actor de la recorrección

#### Scenario: La primera corrección no genera actividad de recorrección

- **WHEN** una entrega es corregida por primera vez (sin corrección previa)
- **THEN** NO se registra ninguna `Actividad` de tipo `CORRECCION_RECORREGIDA`

### Requirement: Consulta del historial de correcciones de una entrega

El sistema SHALL exponer un endpoint de solo lectura (`GET`) que devuelva el historial de correcciones reemplazadas de una entrega, ordenado de la reemplazada más reciente a la más antigua. La respuesta SHALL incluir, por cada versión: `id`, `nota`, `editado_manualmente`, nombre del autor de la corrección saliente, `correccion_creada_en`, `reemplazada_en` y nombre de quien disparó la recorrección. El campo `raw_response` (grande, forense) NO SHALL incluirse en el listado.

#### Scenario: Listar el historial de una entrega recorregida

- **WHEN** un usuario autorizado consulta el historial de una entrega que fue recorregida dos veces
- **THEN** la respuesta contiene dos versiones ordenadas de la más reciente a la más antigua
- **AND** ninguna versión incluye el `raw_response`

#### Scenario: Entrega sin recorrecciones

- **WHEN** un usuario autorizado consulta el historial de una entrega que nunca fue recorregida
- **THEN** la respuesta es una lista vacía (total 0), no un error

### Requirement: Autorización del historial por pertenencia

El endpoint de consulta del historial SHALL validar el acceso mediante el guard `verificar_acceso_entrega`: sólo un ADMIN, un tutor asignado a la comisión de la entrega, o el coordinador de su materia pueden verlo. Un usuario sin acceso a la entrega SHALL recibir 403.

#### Scenario: Usuario sin acceso a la entrega

- **WHEN** un tutor NO asignado a la comisión de la entrega consulta su historial de correcciones
- **THEN** el sistema responde 403 Forbidden

#### Scenario: Historial de una entrega eliminada (soft delete) es consultable

- **WHEN** un usuario autorizado consulta el historial de una entrega que fue borrada por soft delete (`deleted_at` no nulo)
- **THEN** el sistema devuelve el historial de correcciones normalmente (el guard no filtra por `deleted_at`)

