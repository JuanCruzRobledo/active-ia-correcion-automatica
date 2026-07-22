## ADDED Requirements

### Requirement: Peso por subcriterio en la rúbrica

Un `Subcriterio` de una rúbrica SHALL poder tener un campo `peso` entero, expresado en puntos absolutos que suman al `peso` de su criterio contenedor. La semántica SHALL ser análoga a la de los criterios (que suman 100): en una rúbrica versión 2, `sum(subcriterio.peso)` de un criterio SHALL ser exactamente igual al `peso` de ese criterio.

#### Scenario: Subcriterios cuya suma coincide con el peso del criterio (v2)
- **WHEN** se crea o actualiza una rúbrica `schema_version = 2` cuyos subcriterios de cada criterio suman exactamente el `peso` de ese criterio
- **THEN** la rúbrica se valida y persiste correctamente

#### Scenario: Subcriterios cuya suma no coincide con el peso del criterio (v2)
- **WHEN** se crea o actualiza una rúbrica `schema_version = 2` en la que los subcriterios de algún criterio no suman el `peso` de ese criterio
- **THEN** el sistema rechaza la operación con un error de validación que indica el criterio y la discrepancia

#### Scenario: Subcriterio sin peso en v2
- **WHEN** se crea o actualiza una rúbrica `schema_version = 2` con algún subcriterio sin `peso` (o con `peso` inválido, fuera de 1-100)
- **THEN** el sistema rechaza la operación con un error de validación

### Requirement: Versionado de rúbricas mediante schema_version

La entidad `Rubrica` SHALL tener una columna `schema_version` entera, `NOT NULL`, con `server_default '1'`. Las rúbricas existentes al aplicar la migración SHALL quedar en versión 1. El sistema SHALL exponer `schema_version` en las respuestas de detalle y de listado de rúbricas.

#### Scenario: Rúbricas existentes quedan en v1 tras la migración
- **WHEN** se aplica la migración que agrega `schema_version`
- **THEN** todas las rúbricas preexistentes tienen `schema_version = 1` sin backfill manual

#### Scenario: schema_version disponible para el frontend
- **WHEN** el frontend solicita el detalle o el listado de una rúbrica
- **THEN** la respuesta incluye el campo `schema_version`

### Requirement: Compatibilidad total de rúbricas v1

Las rúbricas `schema_version = 1` SHALL seguir siendo válidas, editables y corregibles exactamente igual que antes de este cambio. El sistema SHALL NO exigir `peso` en los subcriterios de una rúbrica v1, y SHALL NO bloquear la corrección de rúbricas v1.

#### Scenario: Validación de rúbrica v1 sin peso en subcriterios
- **WHEN** se crea o actualiza una rúbrica `schema_version = 1` cuyos subcriterios no tienen `peso`
- **THEN** la rúbrica se valida y persiste correctamente, sin exigir peso por subcriterio

#### Scenario: Corrección de rúbrica v1 no se bloquea
- **WHEN** se corrige una entrega asociada a una rúbrica `schema_version = 1`
- **THEN** la corrección se procesa con el comportamiento previo (reparto implícito, sin desglose por subcriterio)

### Requirement: Pre-carga de pesos iguales con suma exacta

Al migrar una rúbrica de v1 a v2, el frontend SHALL pre-cargar como punto de partida un reparto de pesos iguales entre los subcriterios de cada criterio, calculado de forma que la suma cierre exactamente al `peso` del criterio (método del resto mayor: `base = floor(peso/n)`, y los primeros `resto = peso - base*n` subcriterios reciben `base + 1`). El reparto pre-cargado SHALL ser editable por el docente antes de guardar.

#### Scenario: Reparto no divisible exacto
- **WHEN** el docente migra un criterio de peso 25 con 3 subcriterios
- **THEN** el pre-cargado asigna pesos 9, 8, 8 (o equivalente) cuya suma es exactamente 25, editables

#### Scenario: El docente ajusta el reparto pre-cargado
- **WHEN** el docente edita los pesos pre-cargados de subcriterios manteniendo la suma igual al peso del criterio
- **THEN** la validación en vivo indica que el reparto es válido y permite guardar como v2

### Requirement: Indicador de rúbrica desactualizada

El frontend SHALL mostrar un indicador visible ("Rúbrica desactualizada — actualizar al nuevo modelo") en la lista de rúbricas y en el editor cuando `schema_version < 2`, junto con una acción para iniciar la migración al nuevo modelo. El indicador SHALL NO impedir corregir con esa rúbrica.

#### Scenario: Badge en rúbrica v1
- **WHEN** se muestra en la lista o el editor una rúbrica con `schema_version < 2`
- **THEN** aparece el indicador de "desactualizada" y un botón para migrar al nuevo modelo

#### Scenario: Rúbrica v2 sin badge
- **WHEN** se muestra una rúbrica con `schema_version = 2`
- **THEN** no aparece el indicador de "desactualizada"
