# Auditoría — 📄 Documentación Desactualizada

## Alcance

Auditoría de divergencias doc-vs-código en Active-IA (`active-ia-correcion-automatica`), con foco en la migración **N8N → corrección IA nativa en backend** (`backend/app/integrations/`: `gemini_studio_client.py`, `openrouter_client.py`, `ia_provider.py`, `gemini_correction_client.py`). El código es la fuente de verdad. Se revisaron: `CLAUDE.md`, `AGENTS.md` (raíz, backend, frontend), `docs/` completo (incl. `docs/specs/`), `skills/`, `docker-compose*.yml`, `nginx/nginx.conf`, `openspec/specs/`, guías de deploy, `backend/app/core/config.py` y comentarios/docstrings en código backend y frontend. **No se modificó ningún archivo existente** — este informe es el único entregable.

Fecha: 2026-07-12 · Branch: `main` @ `17b4061`

---

## Índice

| ID | Título | Severidad |
|----|--------|-----------|
| DOC-001 | CLAUDE.md describe el flujo de corrección vía N8N que ya no existe | 🟠 Alta |
| DOC-002 | Modelo IA documentado (`gemini-2.0-flash`) no coincide con el stack real | 🟠 Alta |
| DOC-003 | Variables de entorno: `.env.example` no existe y CLAUDE.md documenta vars fantasma / omite las reales | 🟠 Alta |
| DOC-004 | docker-compose.prod.yml levanta un servicio n8n removido y nginx.conf lo exige como upstream | 🔴 Crítica |
| DOC-005 | docker-compose.easypanel.yml exige `N8N_BASIC_AUTH_PASSWORD` para un servicio que ya no se usa | 🔴 Crítica |
| DOC-006 | Guías de deploy instruyen configurar, verificar y backupear N8N | 🟠 Alta |
| DOC-007 | Skills auto-invocadas enseñan a implementar contra `N8NClient` inexistente | 🟠 Alta |
| DOC-008 | docs/specs/ describe N8N como intermediario de IA en toda la especificación | 🟠 Alta |
| DOC-009 | backend/AGENTS.md lista archivos inexistentes (`n8n_client.py`, `app/config.py`) | 🟠 Alta |
| DOC-010 | docs/README.md: stack con N8N y links muertos a ESTADO.md / ROADMAP.md | 🟡 Media |
| DOC-011 | Spec OpenSpec `docker-local-env` exige un contenedor n8n que el compose local ya no define | 🟡 Media |
| DOC-012 | Documentos históricos de N8N sin marca de obsolescencia | 🟡 Media |
| DOC-013 | Comentarios, docstrings y nombres N8N engañosos en código vivo | 🟡 Media |
| DOC-014 | `n8n_client.cpython-313.pyc` (módulo borrado) versionado en git | 🟢 Baja |

**Conteo:** 🔴 2 · 🟠 7 · 🟡 4 · 🟢 1 — Total: 14

---

### [ALTA] CLAUDE.md describe el flujo de corrección vía N8N que ya no existe

- **ID**: DOC-001
- **Ubicación**: `CLAUDE.md:7`, `CLAUDE.md:73-78`, `CLAUDE.md:104`
- **Severidad**: 🟠 Alta
- **Dimensión**: Docs
- **Descripción**: El entry point para agentes IA afirma que el sistema "integrates with N8N workflows" y que el flujo de corrección pasa por un webhook de N8N corriendo en `http://n8n:5678`. En el código, N8N fue removido: la corrección se hace con llamadas HTTP directas desde el backend a Gemini/OpenRouter vía `backend/app/integrations/`.
- **Evidencia**:
  - Doc — `CLAUDE.md:74`: `→ N8N webhook → Gemini API (model: gemini-2.0-flash)` y `CLAUDE.md:78`: `N8N runs at http://n8n:5678`.
  - Código — `backend/app/integrations/gemini_correction_client.py:4`: `"Replaces the N8N proxy layer — calls Gemini directly with httpx."` y `:317`: `"""Direct Gemini API client — replaces N8N as AI intermediary."""`. Además existe `backend/app/integrations/ia_provider.py` que rutea entre `"gemini"` (Studio) y `"openrouter"` — no existe ningún cliente N8N (`backend/app/integrations/` contiene solo `gemini_correction_client.py`, `gemini_studio_client.py`, `ia_provider.py`, `openrouter_client.py`).
  - Nota: la tabla de errores `CLAUDE.md:104` ("AI/N8N error → 502 + retry") sigue siendo funcionalmente correcta pero con nombre engañoso (ver DOC-013).
  - Lo que SÍ está bien: la estructura frontend descripta en `CLAUDE.md:61-66` (features con `components/hooks/services/types/pages`) coincide con `frontend/src/features/` real (auth, correcciones, entregas, rubricas, etc.) — verificado, sin hallazgo.
- **Impacto**: CLAUDE.md es lo primero que lee cualquier agente IA (Claude Code, Cursor, etc.) y cualquier dev nuevo. Un agente que siga esta doc va a buscar el webhook de N8N, intentar debuggear conectividad con `n8n:5678` o proponer cambios en "workflows" que no existen. Es la desactualización de mayor radio de daño del repo.
- **Fix propuesto**: Reescribir la sección "AI Correction Flow" describiendo el flujo real: `Entrega → consolidación → ia_provider.py (gemini | openrouter) → cliente HTTP directo → Correccion`. Eliminar toda mención a N8N o marcarla como histórica.
- **Esfuerzo estimado**: S

---

### [ALTA] Modelo IA documentado (`gemini-2.0-flash`) no coincide con el stack real

- **ID**: DOC-002
- **Ubicación**: `CLAUDE.md:74`; `docs/specs/10-INTEGRACIONES.md:18,73,268,308,378,397,533,543-545,578,856`; `docs/specs/05-ARQUITECTURA-STACK.md:375`; `docs/specs/06-MODELO-DATOS.md:685`; `docs/specs/14-GLOSARIO-REFERENCIAS.md:119`; `docs/specs/PLAN.md:483`; `skills/correccion-ia/SKILL.md:155`; `skills/rubricas/SKILL.md:376`
- **Severidad**: 🟠 Alta
- **Dimensión**: Docs
- **Descripción**: Toda la documentación fija `gemini-2.0-flash` como modelo del sistema (incluso `10-INTEGRACIONES.md:543-545` recomienda `gemini-2.0-flash-thinking` y `gemini-1.5-pro` como alternativas). El código real usa otra cosa, y ni siquiera es un único valor:
- **Evidencia**:
  - Doc — `docs/specs/10-INTEGRACIONES.md:18`: `| **Modelo IA** | gemini-2.0-flash (predeterminado) |`; `docs/specs/14-GLOSARIO-REFERENCIAS.md:119`: "Específicamente se usa `gemini-2.0-flash`".
  - Código — `backend/app/core/config.py:78`: `GEMINI_MODEL: str = "gemini-3.5-flash"`; `config.py:87`: `OPENROUTER_MODEL: str = "google/gemini-3.5-flash"`; `backend/app/integrations/gemini_studio_client.py:13`: hardcodea `"gemini-2.5-flash:generateContent"`; `backend/app/integrations/gemini_correction_client.py:320`: `self.model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")` (fallback distinto del default de config); `backend/app/routers/perfil.py:132`: validación de key con `gemini-2.5-flash`.
  - El propio repo ya lo reconoce en un doc suelto: `fix-workflow-correccion-active-ia.md:18-20` ("Modelos Gemini desalineados: producción usa gemini-3.5-flash... Conviene unificar (decisión pendiente)"). Y `PLAN_FEAT.md:353` avisa que "Los gemini-2.0-* se apagan 2026-06-01" — o sea que el modelo documentado **ya está apagado** a la fecha de esta auditoría.
- **Impacto**: Un dev/agente que copie `gemini-2.0-flash` de la doc (p. ej. del snippet de `10-INTEGRACIONES.md:578`) obtiene errores de la API de Google porque el modelo fue discontinuado. Además la doc esconde que hay 3 valores distintos conviviendo en el código (`3.5-flash` en config, `2.5-flash` hardcodeado en studio client y en el fallback), lo cual es en sí una deuda que la doc debería exponer, no tapar.
- **Reproducción**: Llamar a `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent` (URL literal de `10-INTEGRACIONES.md:578`) con una key válida → 404 del modelo.
- **Fix propuesto**: Documentar los modelos reales por proveedor (Gemini Studio: `GEMINI_MODEL`, hoy `gemini-3.5-flash` con hardcode `gemini-2.5-flash` en `gemini_studio_client.py`; OpenRouter: `google/gemini-3.5-flash`) y de paso abrir un issue para unificar el hardcode del studio client con la setting.
- **Esfuerzo estimado**: M

---

### [ALTA] Variables de entorno: `.env.example` no existe y CLAUDE.md documenta vars fantasma / omite las reales

- **ID**: DOC-003
- **Ubicación**: `CLAUDE.md:127-135` vs `backend/app/core/config.py:17-135`
- **Severidad**: 🟠 Alta
- **Dimensión**: Docs
- **Descripción**: `CLAUDE.md:129` dice "Key vars from `.env.example`" pero **no existe ningún `.env.example` en todo el repo** (verificado con glob `**/.env*` y `**/*.env*`: cero resultados; `.gitignore:6-13` solo ignora `.env` reales, no el example). Además, la lista de vars mezcla una variable que no existe en el código, con omisiones groseras y un dato técnico incorrecto.
- **Evidencia**:
  - Doc — `CLAUDE.md:133`: `N8N_WEBHOOK_URL — N8N service URL`. Código — `backend/app/core/config.py` no define `N8N_WEBHOOK_URL` ni ninguna variable `N8N_*` (grep sobre el archivo: cero matches). Con `extra="ignore"` (`config.py:30`), setearla es un no-op silencioso.
  - Doc — `CLAUDE.md:132`: `ENCRYPTION_KEY — AES-256 key ... (exactly 32 chars)`. Código — `config.py:60-62`: es una **Fernet key** ("Generar con: `Fernet.generate_key()`"), que es un string base64 de 44 caracteres, no 32. Seguir la doc al pie de la letra genera una key inválida y el backend no arranca.
  - Vars reales del código que NO están documentadas en ningún lado (ni CLAUDE.md ni `backend/SETUP.md:169-176`, que solo lista `DATABASE_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`): `GEMINI_MODEL` y `GEMINI_TIMEOUT_SECONDS` (`config.py:78-79`), `OPENROUTER_BASE_URL` y `OPENROUTER_MODEL` (`config.py:86-87`), `RESEND_API_KEY`, `EMAIL_REMITENTE`, `EMAIL_RATE_POR_SEGUNDO` (`config.py:131-135`), `ALLOW_HARD_DELETE` (`config.py:125`), `MAX_LOGIN_ATTEMPTS` / `LOCKOUT_DURATION_MINUTES` (`config.py:67-68`), rate limits (`config.py:112-117`), pool de BD (`config.py:46-48`).
- **Impacto**: Onboarding roto: el primer paso de setup ("copiá el .env.example") es imposible. Deploys nuevos no se enteran de que existen las settings de OpenRouter y de email/Resend. Y quien genere la `ENCRYPTION_KEY` "de 32 chars" según la doc rompe el arranque del backend.
- **Reproducción**: `ls .env.example` en la raíz o en `backend/` → no existe.
- **Fix propuesto**: Crear `backend/.env.example` generado desde `config.py` (una línea por setting con comentario), corregir la sección Environment Variables de CLAUDE.md (sacar `N8N_WEBHOOK_URL`, corregir la descripción de `ENCRYPTION_KEY`, agregar las vars de IA/email) y actualizar `backend/SETUP.md`.
- **Esfuerzo estimado**: M

---

### [CRÍTICA] docker-compose.prod.yml levanta un servicio n8n removido y nginx.conf lo exige como upstream

- **ID**: DOC-004
- **Ubicación**: `docker-compose.prod.yml:5,60-65,84,124-151,184,201-202`; `nginx/nginx.conf:37-38,75-88`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Docs
- **Descripción**: El compose de producción sigue definiendo el servicio `n8n` completo (imagen `juancruzrobledo/n8n-active-ia:latest`, basic auth, volumen `n8n_data`), el backend recibe cinco variables `N8N_*` que `config.py` ignora por completo, y `nginx` declara `depends_on: n8n` más un `upstream n8n { server n8n:5678; }`. Todo eso es infraestructura muerta: el backend ya no le pega a N8N para nada.
- **Evidencia**:
  - Doc/infra — `docker-compose.prod.yml:61-65`: `N8N_BASE_URL: http://n8n:5678`, `N8N_WEBHOOK_CORRECCION: http://n8n:5678/webhook/corregir`, etc. (inyectadas al backend); `:126-151`: servicio `n8n` con `volumes: - ./n8n/workflows:/workflows:ro`; `nginx/nginx.conf:37-38`: `upstream n8n { server n8n:5678; }` y `:76-77`: `location /n8n/ { proxy_pass http://n8n/; }`.
  - Código — `backend/app/core/config.py`: cero settings `N8N_*` (con `extra="ignore"`, `config.py:30`, se descartan en silencio). No existe cliente N8N en `backend/app/integrations/`. Y **no existe el directorio `n8n/` en el repo** (`git ls-files` no trackea nada bajo `n8n/`), así que el mount `./n8n/workflows` de la línea 151 apunta a una carpeta inexistente.
- **Impacto**: Rompe/degrada el deploy real, por eso 🔴: (a) si alguien "limpia" el servicio n8n del compose sin tocar `nginx.conf`, nginx **no arranca** (`host not found in upstream "n8n"`) y se cae todo el sitio; (b) tal como está hoy, el deploy levanta un contenedor N8N público en `/n8n/` (superficie de ataque + RAM/CPU gastados) que ningún componente usa; (c) el bind mount de `./n8n/workflows` inexistente crea un directorio vacío fantasma en el host.
- **Reproducción**: `docker compose -f docker-compose.prod.yml config` → muestra el servicio n8n y las vars N8N_* inyectadas al backend. Comentar el servicio n8n y levantar → nginx entra en crash-loop por el upstream.
- **Fix propuesto**: Eliminar en el mismo cambio: servicio `n8n`, volumen `n8n_data`, vars `N8N_*` del backend, `depends_on: n8n` del nginx, y el bloque `upstream n8n` + `location /n8n/` de `nginx/nginx.conf` (incluido el bloque comentado de HTTPS, `nginx.conf:138-140`). Nota: `docker-compose.yml` y `docker-compose.local.yml` ya están limpios (verificado: solo postgres/backend/frontend) — sirven de referencia.
- **Esfuerzo estimado**: M

---

### [CRÍTICA] docker-compose.easypanel.yml exige `N8N_BASIC_AUTH_PASSWORD` para un servicio que ya no se usa

- **ID**: DOC-005
- **Ubicación**: `docker-compose.easypanel.yml:31-63,82-86,100,149`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Docs
- **Descripción**: Igual que DOC-004 pero peor: la variable usa la sintaxis obligatoria de compose, así que el deploy en EasyPanel **falla directamente** si el operador (razonablemente) no define una contraseña para un servicio que ya no existe en la arquitectura.
- **Evidencia**:
  - Doc/infra — `docker-compose.easypanel.yml:41`: `N8N_BASIC_AUTH_PASSWORD: ${N8N_BASIC_AUTH_PASSWORD:?N8N_BASIC_AUTH_PASSWORD requerido}` (el modificador `:?` aborta el `docker compose up` si la var no está seteada); `:82-86`: el backend recibe `N8N_BASE_URL`, `N8N_WEBHOOK_CORRECCION`, `N8N_WEBHOOK_RUBRICA`, `N8N_WEBHOOK_HEALTH`, `N8N_TIMEOUT_SECONDS`; `:100`: `depends_on: n8n`.
  - Código — `backend/app/core/config.py`: ninguna de esas vars existe; el flujo IA es directo desde el backend.
- **Impacto**: Deploy nuevo en EasyPanel siguiendo el archivo tal cual: o falla el `up` por la var requerida, o el operador inventa una password y levanta un N8N público inútil ruteado por Traefik en `/n8n` (`:62-63`). En ambos casos la doc-infra errada rompe o compromete el deploy → 🔴.
- **Reproducción**: `docker compose -f docker-compose.easypanel.yml config` sin `N8N_BASIC_AUTH_PASSWORD` en el entorno → `error: N8N_BASIC_AUTH_PASSWORD requerido`.
- **Fix propuesto**: Remover servicio `n8n`, volumen `n8n_data` (`:149`), labels de Traefik para `/n8n`, `depends_on: n8n` y las 5 vars `N8N_*` del backend.
- **Esfuerzo estimado**: S

---

### [ALTA] Guías de deploy instruyen configurar, verificar y backupear N8N

- **ID**: DOC-006
- **Ubicación**: `DEPLOYMENT.md:132-137,168,184,196-204,390-396,453`; `DEPLOY_QUICKSTART.md:32,59`; `EASYPANEL_DEPLOY.md:21-32,71,106,120,199,213,228`; `docs/DEPLOY.md:34,64-65,93-121,164-165,203,241-242,275-317,412-422`
- **Severidad**: 🟠 Alta
- **Dimensión**: Docs
- **Descripción**: Las cuatro guías de deploy tratan a N8N como componente de primera clase: piden setear credenciales, verificar `curl http://localhost/n8n/healthz`, importar workflows desde `n8n/workflows/` (carpeta que ni existe en el repo), hacer backup/restore del volumen `n8n_data`, e incluyen troubleshooting "N8N no responde". Checklists finales exigen "[ ] N8N accesible y configurado".
- **Evidencia**:
  - Doc — `DEPLOYMENT.md:453`: `- [ ] N8N accesible y configurado`; `docs/DEPLOY.md:110-114`: "Paso 6: Configurar N8N ... Importar workflows desde `n8n/workflows/` (si existen)"; `EASYPANEL_DEPLOY.md:213`: `- [ ] N8N accesible en /n8n/`.
  - Código — no hay integración N8N en el backend (`backend/app/integrations/` = 4 clientes IA directos) y no existe directorio `n8n/` trackeado en git.
- **Impacto**: Quien deploya siguiendo la guía pierde tiempo configurando, "verificando" y backupeando un servicio inerte; el troubleshooting manda a mirar logs de n8n ante errores de corrección que hoy se resuelven en el backend (logs de `correccion_service` / API key del proveedor). Confunde tanto a humanos como a agentes que ejecutan runbooks.
- **Fix propuesto**: Purgar las secciones N8N de las 4 guías y reemplazar el troubleshooting de corrección por: revisar logs del backend, `error_code` de la entrega y validez de la API key Gemini/OpenRouter del usuario.
- **Esfuerzo estimado**: M

---

### [ALTA] Skills auto-invocadas enseñan a implementar contra `N8NClient` inexistente

- **ID**: DOC-007
- **Ubicación**: `skills/correccion-ia/SKILL.md:4,15,23,32,46-47,95,118-127,144,206-259,287,432-438,518`; `skills/rubricas/SKILL.md:372-385`
- **Severidad**: 🟠 Alta
- **Dimensión**: Docs
- **Descripción**: `CLAUDE.md:143-144` auto-invoca estas skills para "Implementing correction flow" y "Managing rubrics/criteria". Ambas contienen código de ejemplo completo contra una arquitectura removida: `from app.integrations.n8n_client import N8NClient`, `self.base_url = settings.N8N_WEBHOOK_URL`, payloads `"model": "gemini-2.0-flash"`, y hasta redefinen `N8NError`/`N8NTimeoutError` como si fueran el patrón a seguir.
- **Evidencia**:
  - Doc — `skills/correccion-ia/SKILL.md:209-219`: `# integrations/n8n_client.py ... class N8NClient: def __init__(self): self.base_url = settings.N8N_WEBHOOK_URL`; `skills/rubricas/SKILL.md:382`: `n8n_client = N8NClient()` con `:376`: `"model": "gemini-2.0-flash"`.
  - Código — `backend/app/integrations/n8n_client.py` no existe (solo queda su `.pyc`, ver DOC-014); `settings.N8N_WEBHOOK_URL` no existe en `config.py`. El flujo real usa `ia_provider.py` + `gemini_correction_client.py`/`openrouter_client.py`.
- **Impacto**: Este es el caso más peligroso para agentes IA: las skills son *instrucciones ejecutables* que CLAUDE.md carga automáticamente al tocar corrección o rúbricas. Un agente obediente va a recrear `n8n_client.py`, agregar `N8N_WEBHOOK_URL` a config y "restaurar" la arquitectura vieja creyendo que sigue el estándar del proyecto.
- **Fix propuesto**: Reescribir ambas skills contra el código real (`ia_provider.resolver_proveedor`, `GeminiCorrectionClient`, `OpenRouterClient`, catálogo `error_catalog.py`) o, mínimo, ponerles un banner "OBSOLETO — N8N removido, ver backend/app/integrations/" hasta reescribirlas.
- **Esfuerzo estimado**: L

---

### [ALTA] docs/specs/ describe N8N como intermediario de IA en toda la especificación

- **ID**: DOC-008
- **Ubicación**: `docs/specs/10-INTEGRACIONES.md` (documento completo; p. ej. `:73,268,308,378,397`); `docs/specs/13-INFRAESTRUCTURA-DEPLOY.md:34,53,67,102,121,155-177,223-247,303-315,500-537,663,719,773-779,885-943`; `docs/specs/01-VISION-OBJETIVOS.md:46,79,126,167,268`; `docs/specs/03-REQUISITOS-FUNCIONALES.md:298,432-436`; `docs/specs/04-REQUISITOS-NO-FUNCIONALES.md:267,402`; `docs/specs/05-ARQUITECTURA-STACK.md:375`; `docs/specs/14-GLOSARIO-REFERENCIAS.md:181,321-324,392`; `docs/specs/PLAN.md:139,180,316,481,518,573,580`
- **Severidad**: 🟠 Alta
- **Dimensión**: Docs
- **Descripción**: La especificación formal del sistema (14 documentos) tiene a N8N incrustado en la visión ("N8N como intermediario permite modificar prompts sin redeployear", `01-VISION-OBJETIVOS.md:167`), los requisitos funcionales ("Sistema envía a N8N → Gemini", `03-REQUISITOS-FUNCIONALES.md:298`), la infraestructura (Dockerfile preconfigurado de N8N, variables `N8N_WEBHOOK_BASE_URL`, healthcheck `/healthz`, `13-INFRAESTRUCTURA-DEPLOY.md:500-537`) y el glosario. Nada de eso describe el sistema actual.
- **Evidencia**:
  - Doc — `docs/specs/10-INTEGRACIONES.md:73`: diagrama `Modelo: gemini-2.0-flash` dentro del flujo vía N8N; `13-INFRAESTRUCTURA-DEPLOY.md:313-315`: `N8N_WEBHOOK_BASE_URL=http://n8n:5678`, `N8N_CORRECTION_WEBHOOK=/webhook/corregir-individual` (endpoints que además ya eran los "viejos" según `DOCKER-COMPOSE-FIXES.md:17-19` — doble capa de desactualización).
  - Código — el flujo real es backend→Gemini/OpenRouter directo. Ironía: `backend/app/core/config.py:6-7` referencia estas mismas specs como fuente (`Ref: docs/specs/05-ARQUITECTURA-STACK.md seccion 11.1`), o sea que el propio código apunta a doc que lo contradice.
- **Impacto**: Las specs son la referencia de diseño que `docs/README.md:22` manda a consultar "cuando implementes corrección IA". Un dev que arranque por ahí modela el sistema equivocado. Como el código las cita como "Ref:", la contradicción erosiona la confianza en TODA la carpeta specs.
- **Fix propuesto**: Actualizar en serio `10-INTEGRACIONES.md` (el más citado) al flujo `ia_provider` + clientes directos, y en el resto agregar una nota de cabecera "⚠️ Sección N8N obsoleta desde la migración a corrección nativa (ver backend/app/integrations/)" hasta poder reescribirlos.
- **Esfuerzo estimado**: L

---

### [ALTA] backend/AGENTS.md lista archivos inexistentes (`n8n_client.py`, `app/config.py`)

- **ID**: DOC-009
- **Ubicación**: `backend/AGENTS.md:47-48,107-110`
- **Severidad**: 🟠 Alta
- **Dimensión**: Docs
- **Descripción**: El árbol de estructura que guía a los agentes en el backend lista `integrations/n8n_client.py # N8N webhook client` y `integrations/gemini_validator.py`, ninguno de los cuales existe; omite los 4 módulos reales. También ubica `config.py` y `database.py` directo bajo `app/`, cuando en realidad están en `app/core/config.py` y `app/db/` respectivamente.
- **Evidencia**:
  - Doc — `backend/AGENTS.md:107-110`: `└── integrations/ ... ├── n8n_client.py # N8N webhook client └── gemini_validator.py # API key validator`; `:47`: `├── config.py # Configuración (env vars)` bajo `app/`.
  - Código — `backend/app/integrations/` contiene `gemini_correction_client.py`, `gemini_studio_client.py`, `ia_provider.py`, `openrouter_client.py`; `backend/app/config.py` y `backend/app/database.py` no existen (verificado con `ls`: "No such file or directory"); la config real es `backend/app/core/config.py`.
- **Impacto**: Los agentes usan este árbol para decidir dónde crear/buscar código. Resultado típico: imports rotos (`from app.config import settings` — nótese que el ejemplo de `backend/AGENTS.md:374` usa exactamente ese import inexistente) o recrear `n8n_client.py` "porque falta".
- **Fix propuesto**: Regenerar el árbol desde el filesystem real y corregir los imports de los ejemplos (`from app.core.config import settings`).
- **Esfuerzo estimado**: S

---

### [MEDIA] docs/README.md: stack con N8N y links muertos a ESTADO.md / ROADMAP.md

- **ID**: DOC-010
- **Ubicación**: `docs/README.md:22,48-49,91,102,106`
- **Severidad**: 🟡 Media
- **Dimensión**: Docs
- **Descripción**: El índice de documentación declara `Integracion IA | N8N + Google Gemini API` en el stack (`:91`), promociona `10-INTEGRACIONES.md` como la guía de "N8N, Gemini, prompts" (`:22`), y linkea documentos operativos `../ESTADO.md` y `../ROADMAP.md` (`:48-49`) que no existen en el repo (única mención a esos archivos en todo el codebase). Última actualización declarada: 2026-01-26 (`:106`), previa a la migración.
- **Evidencia**:
  - Doc — `docs/README.md:91`: `| Integracion IA | N8N + Google Gemini API |`.
  - Código — stack real: backend→Gemini Studio/OpenRouter directo (`backend/app/integrations/ia_provider.py:5`). `ESTADO.md`/`ROADMAP.md`: grep en todo el repo → solo aparecen citados en este README.
- **Impacto**: Es la puerta de entrada a `docs/` — manda al lector directo a la doc más desactualizada (DOC-008) y a dos archivos inexistentes.
- **Fix propuesto**: Corregir la fila de stack, quitar los links muertos y refrescar la fecha.
- **Esfuerzo estimado**: S

---

### [MEDIA] Spec OpenSpec `docker-local-env` exige un contenedor n8n que el compose local ya no define

- **ID**: DOC-011
- **Ubicación**: `openspec/specs/docker-local-env/spec.md:7,11,21` vs `docker-compose.local.yml`
- **Severidad**: 🟡 Media
- **Dimensión**: Docs
- **Descripción**: La spec principal (fuente de verdad del flujo OpenSpec, sincronizada desde el change archivado `2026-05-07-docker-local-setup`) requiere que el entorno local levante `active-ia-n8n` y persista "las configuraciones de n8n". El compose local real ya no tiene ese servicio.
- **Evidencia**:
  - Doc — `openspec/specs/docker-local-env/spec.md:11`: `**THEN** los contenedores active-ia-postgres, active-ia-backend, active-ia-frontend y active-ia-n8n se inician correctamente y pasan sus healthchecks.`
  - Código/infra — `docker-compose.local.yml` define solo `postgres` (`:15`), `backend` (`:38`) y `frontend` (`:92`); cero menciones a n8n en el archivo.
- **Impacto**: Cualquier `/opsx:verify` o validación contra esta spec da falso negativo ("falta el contenedor n8n"), y un agente aplicando un change sobre `docker-local-env` podría "arreglar" el compose re-agregando n8n para cumplir la spec.
- **Fix propuesto**: Crear un change OpenSpec chico que actualice el delta de `docker-local-env` removiendo el requisito de n8n, y sincronizarlo (`/opsx:sync`).
- **Esfuerzo estimado**: S

---

### [MEDIA] Documentos históricos de N8N sin marca de obsolescencia

- **ID**: DOC-012
- **Ubicación**: `docs/INTEGRACION-N8N-RESUMEN.md:1-8`; `fix-workflow-correccion-active-ia.md:5-10,106-111`; `DOCKER-COMPOSE-FIXES.md:5,17-29,192-207`; `docs/PLAN-SOPORTE-PDF-ENTREGAS.md:558`; `docs/PLAN-MIGRACION-RUBRICA-V2.md:112,242`
- **Severidad**: 🟡 Media
- **Dimensión**: Docs
- **Descripción**: Varios documentos de trabajo quedaron congelados en la era N8N y se leen como vigentes: `INTEGRACION-N8N-RESUMEN.md` declara "**Estado:** ✅ **COMPLETADO** — Todos los workflows de N8N han sido creados y son compatibles con el backend existente" (`:6-8`); `fix-workflow-correccion-active-ia.md` deja **tareas pendientes abiertas** ("⬜ Re-importar manualmente el workflow en la instancia de n8n", `:106`) que ya no tienen sentido; `DOCKER-COMPOSE-FIXES.md` documenta como "corregidas" variables `N8N_*` que hoy ni existen en config.
- **Evidencia**:
  - Doc — `fix-workflow-correccion-active-ia.md:5-6`: "FALTA re-importar a la instancia de n8n (paso manual — ver abajo). Producción NO cambia hasta que se re-importe."
  - Código — no hay instancia de n8n que importar: el flujo vive en `backend/app/integrations/gemini_correction_client.py` (cuyos docstrings confirman: "Prompts and generationConfig are identical to the former N8N workflows", `:5`).
- **Impacto**: Un lector (o agente buscando "pendientes") encuentra checklists abiertos que lo mandan a operar una instancia de n8n inexistente. Confunde el estado real del proyecto.
- **Fix propuesto**: Banner de cabecera en cada uno: "📜 HISTÓRICO — N8N fue removido en <fecha/PR>; la corrección es nativa en backend/app/integrations/. Este doc se conserva solo como registro." Opcional: moverlos a `docs/archive/`.
- **Esfuerzo estimado**: S

---

### [MEDIA] Comentarios, docstrings y nombres N8N engañosos en código vivo

- **ID**: DOC-013
- **Ubicación**: `backend/app/core/exceptions.py:52-64`; `backend/app/core/error_catalog.py:5,19-20,58-61`; `backend/app/services/correccion_service.py:6,118,126,178,529-582,621-729`; `backend/app/services/rubrica_ia_service.py:6,51,136-180`; `backend/app/services/entrega_service.py:1024`; `backend/app/routers/correcciones.py:49,91,100`; `backend/app/routers/rubricas.py:439`; `backend/app/main.py:109`; `backend/requirements.txt:36`; `frontend/src/features/correcciones/services/correcciones-service.ts:93-97`; `frontend/src/shared/utils/erroresResumen.ts:12-13`
- **Severidad**: 🟡 Media
- **Dimensión**: Docs (documentación embebida en código)
- **Descripción**: La migración renombró la infraestructura pero no la "doc en código". Dos capas distintas:
  1. **Docstrings/comentarios lisa y llanamente falsos**: `correccion_service.py:118` ("al webhook de n8n correspondiente"), `:529` ("Build payload for N8N text correction webhook (/webhook/corregir)"), `routers/correcciones.py:91` ("3. Sends to N8N → Gemini for evaluation") y `:100` ("Timeout: 90 seconds (configurable in N8N)" — hoy es `GEMINI_TIMEOUT_SECONDS`, `config.py:79`), `rubricas.py:439`, `main.py:109` ("Estado de conexion a N8N"), `requirements.txt:36` ("HTTP Client (for N8N integration)"), y en frontend `correcciones-service.ts:93` ("Si N8N falla...").
  2. **Identificadores en uso con nombre engañoso** (no son código muerto — se lanzan/persisten hoy): `N8NError`/`N8NTimeoutError` (`exceptions.py:55-62`) son las excepciones que levantan los clientes Gemini/OpenRouter actuales (`gemini_correction_client.py:195,494`; `openrouter_client.py:82,246`); los códigos `N8N_TIMEOUT`/`N8N_ERROR` (`error_catalog.py:19-20`) se **persisten en `entrega.error_code`** y el frontend los mapea (`erroresResumen.ts:12-13`). El propio catálogo documenta el criterio para el caso análogo GEMINI_: "Se mantienen los nombres históricos... para no romper datos ya guardados" (`error_catalog.py:13-14`).
- **Evidencia**: citada arriba; contraste con el código real: `gemini_correction_client.py:4`: "Replaces the N8N proxy layer — calls Gemini directly with httpx."
- **Impacto**: Quien debuggea una corrección fallida ve `N8N_TIMEOUT` en la BD o `raise N8NError` en el stack trace y sale a buscar un servicio N8N que no existe. Los docstrings falsos además envenenan a los agentes IA que leen el código como contexto.
- **Fix propuesto**: (a) Corregir docstrings/comentarios — costo cero, sin riesgo. (b) Para los identificadores: renombrar excepciones a `IAProviderError`/`IAProviderTimeoutError` con alias `N8NError = IAProviderError` deprecado; los códigos persistidos (`N8N_TIMEOUT`/`N8N_ERROR`) conviene NO renombrarlos en datos (mismo criterio que el prefijo GEMINI_) pero sí documentar en `error_catalog.py` que son nombres históricos, como ya se hizo con los otros.
- **Esfuerzo estimado**: M

---

### [BAJA] `n8n_client.cpython-313.pyc` (módulo borrado) versionado en git

- **ID**: DOC-014
- **Ubicación**: `backend/app/integrations/__pycache__/n8n_client.cpython-313.pyc`
- **Severidad**: 🟢 Baja
- **Dimensión**: Docs (resto arqueológico / higiene de repo)
- **Descripción**: El `.py` de `n8n_client` fue borrado pero su bytecode compilado sigue **trackeado en git** (verificado con `git ls-files`). No es solo residuo local: el repo versiona ~60 archivos `.pyc` bajo `__pycache__/` (commiteados antes de que `.gitignore:22` agregara `__pycache__/` — gitignore no destrackea lo ya commiteado).
- **Evidencia**: `git ls-files | rg n8n` → `backend/app/integrations/__pycache__/n8n_client.cpython-313.pyc`; `backend/app/integrations/n8n_client.py` no existe.
- **Impacto**: Ruido en grep/auditorías (aparece "n8n_client" como si existiera), bytecode obsoleto distribuido a todos los clones, y en teoría Python podría importar un `.pyc` huérfano en escenarios sin source-check. Menor, pero es el fósil literal de la migración.
- **Reproducción**: `git ls-files backend/app/integrations/__pycache__/`
- **Fix propuesto**: `git rm -r --cached` de todos los `__pycache__/` trackeados (el `.gitignore` ya los cubre hacia adelante) en un commit `chore` aparte.
- **Esfuerzo estimado**: S

---

## Resumen

La migración N8N → backend nativo se hizo bien en el código (los clientes nuevos hasta documentan que replican los workflows viejos), pero **ningún documento acompañó el cambio**: el entry point de agentes (CLAUDE.md), las skills auto-invocadas, las 4 guías de deploy, la spec completa de `docs/specs/`, los AGENTS.md y dos de los cuatro docker-compose siguen describiendo (o levantando) la arquitectura anterior. Los dos hallazgos críticos son de infra-como-doc: los compose de prod/easypanel despliegan un N8N muerto y el de EasyPanel directamente falla si no le das una password para ese servicio fantasma.
