## 1. Gate de gobernanza ALTA (bloqueante — antes de escribir infra)

- [x] 1.1 Preparar el diff completo propuesto de `docker-compose.prod.yml`, `docker-compose.easypanel.yml` y `nginx/nginx.conf` (sin escribir todavía).
- [x] 1.2 Presentar esos diffs al usuario y ESPERAR aprobación explícita antes de modificar cualquier archivo de infraestructura. La aprobación del proposal NO alcanza (gobernanza ALTA: "Propose and wait for review before writing").

## 2. Limpieza de docker-compose.prod.yml

- [x] 2.1 Eliminar la mención a n8n del comentario de cabecera.
- [x] 2.2 Eliminar las 5 env vars `N8N_*` inyectadas al servicio backend.
- [x] 2.3 Eliminar el `depends_on: n8n` del backend.
- [x] 2.4 Eliminar el servicio `n8n` completo (imagen `juancruzrobledo/n8n-active-ia:latest`), incluido el bind mount muerto a `./n8n/workflows`.
- [x] 2.5 Eliminar el `depends_on: n8n` de nginx.
- [x] 2.6 Eliminar el volumen `n8n_data`.

## 3. Limpieza de docker-compose.easypanel.yml

- [x] 3.1 Eliminar el servicio `n8n` completo, incluida la línea `N8N_BASIC_AUTH_PASSWORD: ${N8N_BASIC_AUTH_PASSWORD:?...}` (la sintaxis `:?` aborta `docker compose up`).
- [x] 3.2 Eliminar las 5 env vars `N8N_*` del servicio backend.
- [x] 3.3 Eliminar el `depends_on: n8n`.
- [x] 3.4 Eliminar el volumen `n8n_data`.

## 4. Limpieza de nginx/nginx.conf

- [x] 4.1 Eliminar el bloque `upstream n8n { server n8n:5678; }`.
- [x] 4.2 Eliminar el bloque `location /n8n/ { proxy_pass http://n8n/; ... }`.
- [x] 4.3 Eliminar el bloque HTTPS comentado equivalente (mismo patrón `location /n8n/`).

## 5. Corrección de la spec docker-local-env

- [x] 5.1 Editar `openspec/specs/docker-local-env/spec.md`: quitar `active-ia-n8n` del escenario de "Levantamiento Unificado" y toda mención a persistencia de configuraciones de n8n en "Persistencia de Datos Locales" (según el delta en `specs/docker-local-env/spec.md` de este change).

## 6. Actualización de documentación de deploy

- [x] 6.1 `DEPLOYMENT.md`: remover pasos de configurar/verificar/backupear N8N (líneas aprox. 132-137, 168, 184, 196-204, 390-396, 453).
- [x] 6.2 `EASYPANEL_DEPLOY.md`: remover pasos de N8N (líneas aprox. 21-32, 71, 106, 120, 199, 213, 228).
- [x] 6.3 `DEPLOY_QUICKSTART.md`: remover pasos de N8N (líneas aprox. 32, 59).
- [x] 6.4 `docs/DEPLOY.md`: remover pasos de N8N (líneas aprox. 34, 64-65, 93-121, 164-165, 203, 241-242, 275-317, 412-422).
- [x] 6.5 En esas docs, documentar la topología de deploy real vigente: backend desde `backend/Dockerfile` (EasyPanel app service) y frontend en Vercel sin Docker; composes prod/easypanel como alternativa self-hosted.

## 7. Verificación (solo lectura, no modifica código)

- [x] 7.1 Verificar que `backend/Dockerfile` no contiene referencias a n8n (`grep -i n8n backend/Dockerfile` → 0 resultados). Ya confirmado; dejar registrado.
- [x] 7.2 Verificar que `frontend/Dockerfile` no contiene referencias a n8n (`grep -i n8n frontend/Dockerfile` → 0 resultados). Ya confirmado; dejar registrado.

## 8. Validación objetiva (criterio de done)

- [x] 8.1 `docker compose -f docker-compose.prod.yml config` resuelve sin errores (no quedan `depends_on`/volúmenes colgados).
- [x] 8.2 `docker compose -f docker-compose.easypanel.yml config` resuelve sin errores.
- [x] 8.3 `grep -ri n8n docker-compose.prod.yml docker-compose.easypanel.yml nginx/nginx.conf` devuelve 0 resultados.
