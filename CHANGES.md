# CHANGES.md — Quick wins de la auditoría (2026-07-12)

> Roadmap operativo de los 7 "quick wins" identificados en `docs/auditoria/00-RESUMEN-EJECUTIVO.md` (sección 3). Son fixes puntuales sobre código/infra existente — no hay feature nueva, por eso este mapa se armó a mano en vez de vía `kb-creator` + `roadmap-generator` (ese flujo aplica cuando hace falta una knowledge-base completa; acá no era necesario). Cada change vive en `openspec/changes/<nombre>/` con `proposal.md` + `design.md` + `specs/` + `tasks.md`, ya creados y validados (`openspec validate` → 8/8 passed, incluye `moodle-live-pendientes` que es un change preexistente sin relación).

## Índice

| # | Change | Hallazgo(s) | Gobernanza | Esfuerzo | Depende de |
|---|--------|-------------|:----------:|:--------:|:----------:|
| 1 | [`harden-secret-keys-arranque`](openspec/changes/harden-secret-keys-arranque/) | SEC-003 | 🔴 CRÍTICA | S | — |
| 2 | [`unificar-modelo-gemini`](openspec/changes/unificar-modelo-gemini/) | BUG-001 / IA-006 | 🟡 MEDIA | S | #1 |
| 3 | [`limpiar-n8n-deploy`](openspec/changes/limpiar-n8n-deploy/) | DOC-004 / DOC-005 | 🟠 ALTA | S | — |
| 4 | [`confirmar-eliminar-usuario`](openspec/changes/confirmar-eliminar-usuario/) | UI-001 | 🟢 BAJA | S | — |
| 5 | [`capturar-errores-gemini-rubrica-ia`](openspec/changes/capturar-errores-gemini-rubrica-ia/) | ERR-001 | 🟡 MEDIA | S | — |
| 6 | [`no-expirar-sesion-en-login`](openspec/changes/no-expirar-sesion-en-login/) | ERR-004 | 🟡 MEDIA | S | — |
| 7 | [`limitar-tamano-uploads-y-zip-bomb`](openspec/changes/limitar-tamano-uploads-y-zip-bomb/) | PERF-008 / SEC-005 | 🟡 MEDIA | S/M | — |

**Gobernanza** (modelo JR Stack): 🔴 CRÍTICA = analysis-only, aprobación humana explícita línea por línea antes de escribir código · 🟠 ALTA = proponer y esperar revisión antes de escribir · 🟡 MEDIA = implementar con checkpoints, surfacear decisiones no obvias · 🟢 BAJA = autonomía completa si los tests pasan (TDD).

## Grafo de dependencias y paralelismo

Único edge real de archivo compartido: **#1 → #2** (ambos tocan `backend/app/core/config.py` — SECRET_KEY/ENCRYPTION_KEY vs GEMINI_MODEL, secciones distintas sin overlap de líneas, pero se serializan para no reabrir contexto en el mismo archivo).

Los changes **#3, #4, #5, #6, #7 son 100% paralelizables** entre sí y con el bloque #1→#2 — no comparten ningún archivo.

```
#1 harden-secret-keys-arranque ──▶ #2 unificar-modelo-gemini
#3 limpiar-n8n-deploy                              (independiente)
#4 confirmar-eliminar-usuario                       (independiente)
#5 capturar-errores-gemini-rubrica-ia               (independiente)
#6 no-expirar-sesion-en-login                       (independiente)
#7 limitar-tamano-uploads-y-zip-bomb                (independiente)
```

**Plan multi-agente** (si se trabaja en paralelo): track A (`#1→#2`, backend `config.py`), track B (`#3`, infra — gate de revisión ALTA), track C (`#4` y `#6`, frontend), track D (`#5` y `#7`, backend servicios). Único punto de sincronización: no aplicar `#2` antes de que `#1` esté mergeado.

## Critical path / orden de ataque

Orden acordado, por prioridad de riesgo (igual que el resumen ejecutivo de la auditoría):

**1 → 2 → 3 → 4 → 5 → 6 → 7**

- **#1** (`harden-secret-keys-arranque`) va primero: es la prioridad #1 de toda la auditoría (neutraliza forja de JWT ADMIN + descifrado de API keys). Gobernanza CRÍTICA: la fase de apply NO es autónoma, cada línea se muestra y se espera aprobación explícita antes de escribirla.
- **#2** inmediatamente después, mismo archivo que #1.
- **#3** (`limpiar-n8n-deploy`) — gobernanza ALTA: mostrar el diff completo de los 3 archivos de infra afectados y esperar OK explícito antes de aplicar.
- **#4, #5, #6** — gobernanza BAJA/MEDIA, se pueden aplicar con más autonomía (TDD + checkpoints puntuales).
- **#7** (`limitar-tamano-uploads-y-zip-bomb`) va último por ser el más grande de los 7 (2 servicios + 2 endpoints), no por prioridad baja.

## Detalle por change

### 1. `harden-secret-keys-arranque` — SEC-003 🔴 CRÍTICA
Validador que aborta el arranque si `DEBUG=False` y `SECRET_KEY`/`ENCRYPTION_KEY` siguen siendo los defaults hardcodeados del repo. Archivos: `backend/app/core/config.py:53,62`. Leer antes: `proposal.md`, `design.md` (nota de gobernanza crítica explícita en ambos).

### 2. `unificar-modelo-gemini` — BUG-001 / IA-006 🟡 MEDIA
Una sola fuente de verdad para el modelo Gemini: la validación de API key debe usar `settings.GEMINI_MODEL` en vez del literal hardcodeado `gemini-2.5-flash`. Archivos: `backend/app/core/config.py:78`, `backend/app/integrations/gemini_studio_client.py:11-14`, `backend/app/integrations/gemini_correction_client.py:320`. **Depende de #1** (mismo archivo `config.py`).

### 3. `limpiar-n8n-deploy` — DOC-004 / DOC-005 🟠 ALTA
Elimina el servicio `n8n`, env vars `N8N_*`, `depends_on` y volumen muertos de `docker-compose.prod.yml` y `docker-compose.easypanel.yml`, y el `upstream n8n`/`location /n8n/` de `nginx/nginx.conf`, en un solo cambio atómico. Corrige también `openspec/specs/docker-local-env/spec.md` y documenta la topología real de deploy (backend vía `backend/Dockerfile`, frontend vía Vercel sin Docker) en `DEPLOYMENT.md`/`EASYPANEL_DEPLOY.md`/`DEPLOY_QUICKSTART.md`/`docs/DEPLOY.md`.

### 4. `confirmar-eliminar-usuario` — UI-001 🟢 BAJA
Agrega `ConfirmDialog` + `onError`/`onSuccess` con toast al borrado de usuarios, replicando el patrón ya validado de `useDeleteEntregasMasivo`/`EntregasPage`. Archivos: `frontend/src/features/usuarios/pages/UsuariosPage.tsx:147-149`, `frontend/src/features/usuarios/hooks/useUsuarios.ts:91-101`. Nota: requiere agregar infra de testing React (jsdom + Testing Library) al frontend, que hoy no está configurada.

### 5. `capturar-errores-gemini-rubrica-ia` — ERR-001 🟡 MEDIA
`rubrica_ia_service.py` solo captura `N8NError`/`N8NTimeoutError`; agrega captura de `GeminiError` y sus 4 subclases (`APIKeyInvalidError`, `QuotaExceededError`, `ModelOverloadedError`, `InsufficientCreditsError`), replicando el patrón ya correcto de `correccion_service.py`. Archivos: `backend/app/services/rubrica_ia_service.py:16,95-106`.

### 6. `no-expirar-sesion-en-login` — ERR-004 🟡 MEDIA
El interceptor de axios trata todo 401 como "sesión expirada", incluso el de credenciales inválidas en `/auth/login`. Excluye las URLs de auth del tratamiento de logout/redirect y muestra el mensaje real del backend. Archivo: `frontend/src/shared/services/api-client.ts:96-105`.

### 7. `limitar-tamano-uploads-y-zip-bomb` — PERF-008 / SEC-005 🟡 MEDIA (S/M)
Aplica `MAX_UPLOAD_SIZE` (ya definido, nunca usado) a los endpoints de subida individual y masiva, y agrega límite anti ZIP-bomb (tamaño descomprimido acumulado + cantidad de entries) al consolidar ZIPs. Archivos: `backend/app/services/entrega_service.py:136-137,732,738-820`, `backend/app/services/consolidacion_service.py:240-288`.

## Verificación general al cerrar las 7

- Backend: `pytest` completo sin regresiones (Strict TDD Mode: safety net → RED → GREEN → triangulate → refactor por cada change).
- Frontend: `npm run test` (vitest) y `npm run typecheck` sin regresiones.
- Infra: `docker compose -f docker-compose.prod.yml config` y `-f docker-compose.easypanel.yml config` sin errores; `grep -ri n8n` sobre los archivos de infra sin resultados.
- Cada change se archiva (`openspec archive`) al terminar, moviendo su carpeta a `openspec/changes/archive/`.
