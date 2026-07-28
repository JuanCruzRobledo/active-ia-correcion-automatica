## ADDED Requirements

### Requirement: Columna universidad_id denormalizada en el árbol de Materia

El sistema SHALL agregar una columna `universidad_id` (FK → `universidades.id`) a **todas** las tablas que cuelgan del árbol de `Materia`. Las tablas alcanzadas por este change SHALL ser: `materias`, `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs` y `avance_snapshots`. La columna es **denormalizada en cascada** (decisión de producto): cada registro guarda su `universidad_id` directamente en vez de derivarlo por JOIN hasta `materias`. En cada tabla, `universidad_id` SHALL introducirse primero **nullable** (para permitir el backfill) y quedar **NOT NULL** solo después de backfillear todos los datos existentes.

#### Scenario: Cada tabla del árbol recibe universidad_id

- **WHEN** se aplica la migración de columnas
- **THEN** cada una de `materias`, `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots` tiene una columna `universidad_id` que es FK a `universidades.id`

#### Scenario: universidad_id se agrega nullable antes del backfill

- **WHEN** se agrega `universidad_id` a una tabla con datos existentes
- **THEN** la columna se crea como nullable, de modo que las filas existentes no violen la restricción antes del backfill

#### Scenario: universidad_id pasa a NOT NULL después del backfill

- **WHEN** el backfill dejó cero filas con `universidad_id IS NULL` en una tabla
- **THEN** la migración SHALL alterar esa columna a NOT NULL
- **THEN** si quedara alguna fila con `universidad_id IS NULL`, el `ALTER ... SET NOT NULL` SHALL fallar y detener la migración (no dejar la tabla en estado inconsistente)

### Requirement: Invariante de coherencia de universidad_id con el padre

El `universidad_id` denormalizado de un registro SHALL coincidir siempre con el `universidad_id` de su registro padre en el árbol (una `comision` con el de su `materia`, una `entrega` con el de su `comision`, una `correccion` con el de su `entrega`, etc.). Este change NO impone una constraint cross-table en la base para ello; la coherencia SHALL validarse en la capa de servicio al crear/mover registros (regla a implementar cuando el scoping real de queries entre en vigor, Fase 4). En esta fase, el backfill SHALL producir un estado 100% coherente propagando el valor desde el padre.

#### Scenario: El backfill deja el árbol coherente

- **WHEN** finaliza el backfill de todas las tablas
- **THEN** para toda `comision`, `comision.universidad_id == comision.materia.universidad_id`
- **THEN** para toda `entrega`, `entrega.universidad_id == entrega.comision.universidad_id`
- **THEN** para toda `correccion`, `correccion.universidad_id == correccion.entrega.universidad_id`
- **THEN** para toda `unidad`/`rubrica`/`examen_materia`/`cierre_cursada_run`/`avance_snapshot`, su `universidad_id` es el de su `materia`

### Requirement: Unicidad de código de materia scopeada por universidad

El sistema SHALL reemplazar el unique global de `materias.codigo` por un `UniqueConstraint(universidad_id, codigo)`. Dos universidades distintas SHALL poder tener cada una una materia con el mismo `codigo`; dentro de una misma universidad el `codigo` SHALL seguir siendo único. Este cambio de constraint SHALL aplicarse recién después del backfill (cuando `universidad_id` ya no es nullable).

#### Scenario: Se elimina el unique global de codigo y se crea el compuesto

- **WHEN** se aplica la migración de constraints (post-backfill)
- **THEN** ya no existe el índice/constraint unique global sobre `materias.codigo`
- **THEN** existe un `UniqueConstraint(universidad_id, codigo)` sobre `materias`

#### Scenario: Mismo código en dos universidades es válido

- **WHEN** la universidad A tiene una materia con `codigo = "PROG1"` y se crea una materia con `codigo = "PROG1"` en la universidad B
- **THEN** el insert es válido

#### Scenario: Código duplicado dentro de la misma universidad se rechaza

- **WHEN** la universidad A ya tiene una materia con `codigo = "PROG1"` y se intenta crear otra con `codigo = "PROG1"` en la universidad A
- **THEN** la base de datos SHALL rechazar el insert por el `UniqueConstraint(universidad_id, codigo)`
