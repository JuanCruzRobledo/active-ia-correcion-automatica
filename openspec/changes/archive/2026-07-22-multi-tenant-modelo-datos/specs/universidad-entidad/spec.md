## ADDED Requirements

### Requirement: Entidad Universidad como tenant de primer nivel

El sistema SHALL introducir una tabla `universidades` que representa a una universidad/tenant. Cada fila SHALL tener: `id` (PK), `nombre` (String, **unique**, NOT NULL), `moodle_host` (String, **nullable** — el campus puede configurarse después), `activa` (Boolean, NOT NULL, default `true`) y las columnas de timestamps del `TimestampMixin` del proyecto (`created_at`, `updated_at`). El modelo `Universidad` SHALL vivir en `app/models/universidad.py` y registrarse en `app/models/__init__.py`.

Este change introduce ÚNICAMENTE el modelo y su migración; el CRUD/endpoint de universidades es de una fase posterior y NO forma parte de este spec.

#### Scenario: Se crea la tabla universidades con sus columnas

- **WHEN** se aplica la migración que crea `universidades`
- **THEN** la tabla existe con columnas `id`, `nombre`, `moodle_host`, `activa`, `created_at`, `updated_at`
- **THEN** `nombre` es NOT NULL y tiene una restricción de unicidad
- **THEN** `moodle_host` es nullable y `activa` tiene default `true`

#### Scenario: Dos universidades no pueden compartir nombre

- **WHEN** ya existe una universidad con `nombre = "TUPaD"` y se intenta insertar otra con el mismo `nombre`
- **THEN** la base de datos SHALL rechazar el insert por violación del unique de `nombre`

#### Scenario: Una universidad puede crearse sin moodle_host

- **WHEN** se inserta una universidad con `moodle_host = NULL`
- **THEN** el insert es válido (el campus se puede configurar más tarde)

#### Scenario: La migración es reversible

- **WHEN** se ejecuta el downgrade de la revisión que crea `universidades`
- **THEN** la tabla `universidades` se elimina sin dejar objetos huérfanos (respetando el orden inverso de las FKs que la referencian)
