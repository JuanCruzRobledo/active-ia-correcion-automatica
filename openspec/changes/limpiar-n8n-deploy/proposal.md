## Why

El proyecto migró de N8N a llamadas directas a IA (rama `feat/remove-n8n-direct-ai`) y el backend ya está 100% migrado (cero llamadas funcionales a n8n en `backend/app`). Sin embargo, la infraestructura de deploy y la documentación todavía arrastran restos muertos de N8N que son un riesgo operativo real: un servicio `n8n` fantasma en los composes de producción, un `upstream n8n` en nginx que puede impedir el arranque del proxy ("host not found in upstream"), una variable con sintaxis `:?` que aborta `docker compose up` si no se setea, un bind mount a `./n8n/workflows` que ni siquiera existe en el repo, y docs que instruyen configurar/verificar/backupear un N8N inexistente. Hallazgos de auditoría DOC-004 y DOC-005, ambos clasificados **críticos**.

## What Changes

- **BREAKING (infra)**: Eliminar el servicio `n8n` completo de `docker-compose.prod.yml` y `docker-compose.easypanel.yml`, junto con TODO lo que lo referencia, en un único cambio atómico para no romper el arranque de nginx ni de compose:
  - Las 5 variables de entorno `N8N_*` inyectadas al backend (que `config.py` ya ignora).
  - Los `depends_on: n8n` (backend y nginx).
  - El volumen `n8n_data`.
  - En easypanel, la variable `N8N_BASIC_AUTH_PASSWORD: ${...:?...}` cuya sintaxis `:?` aborta `docker compose up` para un servicio ya inútil.
  - El bind mount muerto a `./n8n/workflows`.
- Eliminar de `nginx/nginx.conf` el bloque `upstream n8n { server n8n:5678; }`, el `location /n8n/ { proxy_pass ... }` y el bloque HTTPS comentado equivalente.
- Corregir la spec `docker-local-env` para que deje de describir un contenedor `active-ia-n8n` que ya no existe en el compose local (`docker-compose.local.yml` confirmado limpio: solo postgres/backend/frontend).
- Actualizar la documentación de deploy (`DEPLOYMENT.md`, `EASYPANEL_DEPLOY.md`, `DEPLOY_QUICKSTART.md`, `docs/DEPLOY.md`): remover pasos de configurar/verificar/backupear N8N y **documentar la topología de deploy real vigente**: backend desplegado directo desde `backend/Dockerfile` (EasyPanel app service), frontend en Vercel sin Docker.
- Verificar (sin modificar) que `backend/Dockerfile` y `frontend/Dockerfile` no contienen referencias a n8n. Ya confirmado: cero referencias en ambos.

**Fuera de scope (hallazgo distinto, DOC-013, cosmético):** los nombres de excepciones `N8NError`/`N8NTimeoutError` en `backend/app/core/exceptions.py` y los códigos `ERROR_N8N_TIMEOUT`/`ERROR_N8N` en `error_catalog.py`. No rompen nada y no forman parte de este change.

## Capabilities

### New Capabilities
<!-- Ninguna. Este change es de limpieza de infra + docs, no introduce comportamiento nuevo. -->

### Modified Capabilities
- `docker-local-env`: se corrige la descripción del entorno local para que refleje que `docker-compose.local.yml` levanta únicamente PostgreSQL, Backend FastAPI y Frontend React. Se elimina toda mención al contenedor `active-ia-n8n` y a la persistencia de configuraciones de n8n de los requisitos y escenarios de la spec (el comportamiento descripto ya no coincide con la realidad del repo).

## Impact

- **Archivos de infraestructura (gobernanza ALTA — deploy compartido):** `docker-compose.prod.yml`, `docker-compose.easypanel.yml`, `nginx/nginx.conf`. Un error aquí puede impedir que producción levante. La fase de APPLY DEBE mostrar el diff completo de estos tres archivos y esperar aprobación explícita del usuario ANTES de escribir (ver design.md).
- **Spec OpenSpec:** `openspec/specs/docker-local-env/spec.md`.
- **Documentación de deploy:** `DEPLOYMENT.md`, `EASYPANEL_DEPLOY.md`, `DEPLOY_QUICKSTART.md`, `docs/DEPLOY.md`.
- **Sin impacto en código de aplicación:** `backend/app` ya está migrado; no se toca lógica de negocio, endpoints ni modelos.
- **Riesgo mitigado:** eliminar el servicio n8n SIN eliminar su `upstream`/`depends_on` en el mismo cambio dejaría nginx y compose sin poder arrancar; de ahí que todo se haga atómicamente y se valide con `docker compose ... config`.
