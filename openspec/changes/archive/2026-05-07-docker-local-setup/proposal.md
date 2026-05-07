## Why

El usuario necesita ejecutar el entorno completo (backend, frontend, base de datos y n8n) de forma local utilizando Docker Compose para facilitar el desarrollo, asegurar la consistencia entre ambientes y simplificar la configuración inicial de nuevos desarrolladores.

## What Changes

- Verificación y ajuste de `docker-compose.local.yml` para asegurar que todos los servicios (postgres, backend, frontend, n8n) se comuniquen correctamente.
- Configuración de variables de entorno en `.env` para apuntar a los servicios locales de Docker.
- Asegurar que los `Dockerfile` en `backend/` y `frontend/` estén optimizados para desarrollo local (hot reload opcional en backend).
- Documentación del proceso de levantamiento en el README o AGENTS.md.

## Capabilities

### New Capabilities
- `docker-local-env`: Capacidad de levantar y gestionar el entorno de desarrollo completo usando Docker Compose de forma local.

### Modified Capabilities
<!-- None -->

## Impact

- `docker-compose.local.yml`: Archivo principal de orquestación local.
- `.env`: Configuración de variables de entorno locales.
- `backend/Dockerfile`: Definición de imagen para el servicio FastAPI.
- `frontend/Dockerfile`: Definición de imagen para el servicio React.
- `n8n/`: Montaje de workflows locales.
