## ADDED Requirements

### Requirement: Levantamiento Unificado de Servicios
El sistema MUST permitir levantar todos los servicios necesarios para el desarrollo local (PostgreSQL, FastAPI Backend, React Frontend y n8n) utilizando un único comando de Docker Compose.

#### Scenario: Levantamiento exitoso del entorno
- **WHEN** el usuario ejecuta `docker-compose -f docker-compose.local.yml up -d`
- **THEN** los contenedores `active-ia-postgres`, `active-ia-backend`, `active-ia-frontend` y `active-ia-n8n` se inician correctamente y pasan sus healthchecks.

### Requirement: Conectividad Interna de Red
Los servicios MUST ser capaces de comunicarse entre sí utilizando los nombres de servicio definidos en el archivo de orquestación como hostnames, dentro de una red aislada de Docker.

#### Scenario: Comunicación Backend-Base de Datos
- **WHEN** el backend intenta conectarse a la base de datos usando `postgres:5432`
- **THEN** la conexión se establece exitosamente sin necesidad de exponer puertos al host para esta comunicación interna.

### Requirement: Persistencia de Datos Locales
El sistema MUST asegurar que los datos de la base de datos, los archivos subidos al backend y las configuraciones de n8n persistan incluso si los contenedores son eliminados o reiniciados.

#### Scenario: Persistencia de datos en Postgres
- **WHEN** se crea una tabla en la base de datos y luego se ejecuta `docker-compose down` y `docker-compose up`
- **THEN** los datos creados anteriormente siguen estando disponibles en la base de datos.

### Requirement: Configuración vía Variables de Entorno
El sistema MUST cargar y aplicar las configuraciones definidas en el archivo `.env` del proyecto para parametrizar el comportamiento de los contenedores (puertos, claves, URLs).


#### Scenario: Cambio de puerto del frontend
- **WHEN** el usuario cambia `FRONTEND_PORT` en el archivo `.env` y reinicia el servicio
- **THEN** el servicio frontend es accesible en el nuevo puerto especificado desde el host.
