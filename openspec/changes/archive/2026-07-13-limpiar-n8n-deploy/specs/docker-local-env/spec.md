## MODIFIED Requirements

### Requirement: Levantamiento Unificado de Servicios
El sistema MUST permitir levantar todos los servicios necesarios para el desarrollo local (PostgreSQL, FastAPI Backend y React Frontend) utilizando un único comando de Docker Compose.

#### Scenario: Levantamiento exitoso del entorno
- **WHEN** el usuario ejecuta `docker-compose -f docker-compose.local.yml up -d`
- **THEN** los contenedores `active-ia-postgres`, `active-ia-backend` y `active-ia-frontend` se inician correctamente y pasan sus healthchecks.

### Requirement: Persistencia de Datos Locales
El sistema MUST asegurar que los datos de la base de datos y los archivos subidos al backend persistan incluso si los contenedores son eliminados o reiniciados.

#### Scenario: Persistencia de datos en Postgres
- **WHEN** se crea una tabla en la base de datos y luego se ejecuta `docker-compose down` y `docker-compose up`
- **THEN** los datos creados anteriormente siguen estando disponibles en la base de datos.
