## Context

El backend ya no usa N8N: la corrección de código llama directo a la IA (rama `feat/remove-n8n-direct-ai`, `backend/app` sin llamadas funcionales a n8n). Pero la capa de infraestructura y las docs de deploy quedaron desincronizadas. Estado actual verificado en el repo:

- `docker-compose.prod.yml`: 23 líneas mencionan n8n — comentario de cabecera, 5 env vars `N8N_*` al backend, `depends_on: n8n` (backend y nginx), servicio `n8n` completo (imagen `juancruzrobledo/n8n-active-ia:latest`), bind mount a `./n8n/workflows` (que **no existe en el repo**) y volumen `n8n_data`.
- `docker-compose.easypanel.yml`: 20 líneas — servicio `n8n` completo, 5 env vars `N8N_*` al backend, `depends_on: n8n`, volumen `n8n_data`, y `N8N_BASIC_AUTH_PASSWORD: ${N8N_BASIC_AUTH_PASSWORD:?...}`, cuya sintaxis `:?` **aborta** `docker compose up` si la var no está seteada.
- `nginx/nginx.conf`: 9 líneas — `upstream n8n { server n8n:5678; }`, `location /n8n/`, y el bloque HTTPS comentado equivalente. Con nginx, un `upstream` apuntando a un host que ya no existe en la red de compose puede impedir el arranque del proxy ("host not found in upstream").
- `openspec/specs/docker-local-env/spec.md`: describe un contenedor `active-ia-n8n` en el compose local. `docker-compose.local.yml` y `docker-compose.yml` están confirmados limpios (0 referencias a n8n).
- Docs de deploy con pasos de configurar/verificar/backupear N8N: `DEPLOYMENT.md`, `EASYPANEL_DEPLOY.md`, `DEPLOY_QUICKSTART.md`, `docs/DEPLOY.md`.
- `backend/Dockerfile` y `frontend/Dockerfile`: 0 referencias a n8n (verificado).

**Topología de deploy real (confirmada por el usuario):** el backend en producción se despliega directo desde `backend/Dockerfile` (EasyPanel app service), no necesariamente vía el stack completo de docker-compose.prod/easypanel. El frontend se despliega en **Vercel**, que no usa Docker en absoluto. Los composes de prod/easypanel pueden quedar como alternativa self-hosted documentada, pero no son el flujo vigente.

**Gobernanza: ALTA.** Se modifican archivos de infraestructura de deploy compartida (docker-compose de producción, nginx). Regla del nivel ALTO: *"Propose and wait for review before writing."* La aprobación del proposal NO alcanza como autorización para escribir la infra.

## Goals / Non-Goals

**Goals:**
- Dejar `docker-compose.prod.yml`, `docker-compose.easypanel.yml` y `nginx/nginx.conf` sin ninguna referencia a n8n, en un cambio atómico que no rompa el arranque de compose ni de nginx.
- Sincronizar la spec `docker-local-env` con la realidad del compose local (sin n8n).
- Dejar la documentación de deploy correcta: sin pasos de N8N y con la topología real (backend vía Dockerfile/EasyPanel, frontend vía Vercel) documentada.
- Validar el resultado de forma objetiva: `docker compose ... config` sin errores y `grep -ri n8n` sin resultados en los 3 archivos de infra.

**Non-Goals:**
- NO renombrar ni tocar `N8NError`/`N8NTimeoutError` (`exceptions.py`) ni `ERROR_N8N*` (`error_catalog.py`) — hallazgo DOC-013, cosmético, fuera de scope.
- NO tocar `backend/app` (ya migrado), ni lógica de negocio, endpoints o modelos.
- NO tocar `docker-compose.local.yml` ni `docker-compose.yml` (ya limpios).
- NO modificar `backend/Dockerfile` ni `frontend/Dockerfile` (ya limpios) — solo se verifican.
- NO migrar datos ni desplegar; este change edita archivos de configuración y docs.

## Decisions

### Decisión 1: Un único cambio atómico sobre los 3 archivos de infra (no incremental)
Borrar el servicio `n8n` de un compose SIN borrar en el mismo paso su `depends_on`, su `upstream` en nginx y su volumen dejaría el stack en un estado que no arranca. Por eso todas las referencias a n8n de un mismo archivo se eliminan juntas, y los 3 archivos se validan antes de dar por cerrada la tarea.
- **Alternativa descartada:** limpiar archivo por archivo y en varias tandas. Aumenta la ventana en la que compose/nginx quedan inconsistentes y es más difícil de revisar como una sola unidad.

### Decisión 2: Gate de revisión humana ANTES de escribir la infra (gobernanza ALTA)
La fase de APPLY DEBE, para `docker-compose.prod.yml`, `docker-compose.easypanel.yml` y `nginx/nginx.conf`:
1. Mostrar al usuario el **diff completo propuesto** de cada archivo.
2. **Esperar aprobación explícita** del usuario ANTES de escribir cualquier cambio en esos archivos.
3. Recién con el OK, aplicar y luego correr las validaciones.

La aprobación general del proposal NO es suficiente. Las ediciones de spec y docs (`docker-local-env`, `DEPLOYMENT.md`, etc.) son de menor riesgo y pueden aplicarse tras la aprobación general, pero conviene incluirlas en el mismo diff para revisión.
- **Alternativa descartada:** aplicar autónomamente porque el backend ya está migrado. Rechazada: el riesgo no está en el backend sino en que prod/nginx no levanten; el dominio es ALTO por definición.

### Decisión 3: Documentar la topología real en vez de solo borrar
Al remover los pasos de N8N de las docs, se agrega una sección que describe el flujo vigente (backend `backend/Dockerfile` en EasyPanel app service; frontend en Vercel sin Docker; composes prod/easypanel como alternativa self-hosted). Así la limpieza no deja un vacío que reintroduzca confusión.

### Decisión 4: Validación objetiva como criterio de done
- `docker compose -f docker-compose.prod.yml config` y `-f docker-compose.easypanel.yml config` deben resolver sin errores (prueba de que no quedaron `depends_on`/volúmenes colgados).
- `grep -ri n8n` sobre `docker-compose.prod.yml`, `docker-compose.easypanel.yml` y `nginx/nginx.conf` debe devolver 0 resultados.

## Risks / Trade-offs

- **Quitar el servicio n8n pero dejar un `depends_on: n8n` o `upstream n8n`** → compose/nginx no arrancan. Mitigación: cambio atómico por archivo + `docker compose config` + `grep -ri n8n` como gates de la tarea.
- **`N8N_BASIC_AUTH_PASSWORD: ${...:?...}` en easypanel** aborta `docker compose up` incluso ahora. Mitigación: se elimina junto con el servicio; la validación `config` lo confirma.
- **Perder documentación útil de una eventual reinstalación self-hosted de n8n** → aceptado: n8n ya no es parte de la arquitectura; si en el futuro se reintroduce, se documentará entonces. Git conserva el historial.
- **Escribir infra sin revisión humana (violación de gobernanza ALTA)** → Mitigación: gate explícito de diff + aprobación en APPLY (Decisión 2), reflejado como tareas bloqueantes en tasks.md.
- **`docker compose config` puede requerir variables de entorno** (por los `${VAR}`) y fallar por eso y no por n8n. Mitigación: correrlo con un `.env` de ejemplo o exportando placeholders; interpretar el error correctamente (falta de var ≠ referencia colgante a n8n).

## Migration Plan

1. (APPLY) Preparar los diffs de los 3 archivos de infra y presentarlos al usuario. **Esperar OK explícito.**
2. Aplicar la limpieza de infra aprobada (composes + nginx).
3. Aplicar la corrección de la spec `docker-local-env` y de las 4 docs de deploy.
4. Validar: `docker compose ... config` (ambos) + `grep -ri n8n` (3 archivos) = limpio.
5. Verificar (solo lectura) que `backend/Dockerfile` y `frontend/Dockerfile` siguen sin n8n.

**Rollback:** `git checkout -- <archivo>` de los archivos afectados; el change no borra datos ni recursos vivos, solo configuración declarativa y texto.

## Open Questions

- ¿Los composes `prod`/`easypanel` se conservan como alternativa self-hosted documentada, o se marcan como deprecados dado que el flujo real es EasyPanel app + Vercel? (No bloquea la limpieza de n8n; se resuelve al redactar las docs.)
