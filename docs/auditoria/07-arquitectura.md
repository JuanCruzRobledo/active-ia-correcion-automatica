# 🏛️ Auditoría de Arquitectura — Active-IA

**Dimensión**: Violaciones de Arquitectura
**Fecha**: 2026-07-12
**Alcance**: `backend/app/` (Clean Architecture: Routers → Services → Repositories → DB), `frontend/src/` (feature-based modules), estructura del repo y código muerto post-migración N8N → Gemini directo.
**Fuera de alcance**: componentes frontend >200 LOC (auditor UI/UX), menciones a N8N en documentación (auditor de docs), seguridad, performance.

---

## Índice de hallazgos

| ID | Título | Severidad |
|----|--------|-----------|
| ARCH-001 | Services que ejecutan SQLAlchemy directo, salteando Repositories | 🔴 Crítica |
| ARCH-002 | Routers que instancian Repositories directo, salteando Services | 🟠 Alta |
| ARCH-003 | 13 archivos backend superan el límite de 500 LOC | 🟠 Alta |
| ARCH-004 | `moodle_service.py` como god-service: hub de 7 services y cadenas frágiles | 🟠 Alta |
| ARCH-005 | Código zombie de N8N: excepciones, catálogo de errores, compose y `.pyc` huérfano | 🟠 Alta |
| ARCH-006 | `HTTPException` masivo en la capa de Services (311 ocurrencias) | 🟡 Media |
| ARCH-007 | `core/permissions.py` ejecuta queries SQLAlchemy directo | 🟡 Media |
| ARCH-008 | Imports cruzados entre features del frontend sin frontera definida | 🟡 Media |
| ARCH-009 | Lógica de negocio leve en router `correcciones.py` | 🟡 Media |
| ARCH-010 | Estructura muerta `backend/app/api/v1/routers/` | 🟢 Baja |
| ARCH-011 | `fetch` crudo con manejo manual de JWT duplicado en 4 services del front | 🟢 Baja |
| ARCH-012 | Imports inline repetidos dentro de métodos de `correccion_repository.py` | 🟢 Baja |

---

### [CRÍTICA] Services que ejecutan SQLAlchemy directo, salteando Repositories

- **ID**: ARCH-001
- **Ubicación**: `backend/app/services/dashboard_service.py:46-234`, `backend/app/services/auth_service.py:63-64`, `backend/app/services/moodle_service.py:1284-1340`, `backend/app/services/moodle_import_service.py:364-394`, `backend/app/services/excel_service.py:79-86`, `backend/app/services/notificacion_config_service.py:28-37`, `backend/app/services/snapshot_config_service.py:28-35`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Arquitectura
- **Descripción**: La regla dura del proyecto es explícita: "never access DB directly from Services — Repositories (all SQLAlchemy queries)". Sin embargo, al menos 7 services construyen y ejecutan statements SQLAlchemy directo contra la sesión (`select(...)`, `db.execute(...)`, `db.add(...)`, `db.commit(...)`).
- **Evidencia**:
  - `dashboard_service.py` es el caso más grave: **todo el service** son queries crudas. Ej: línea 46-48 `await db.scalar(select(func.count(Materia.id)).where(Matería.activa == True))`, líneas 86-145 arma queries con joins y agregaciones para stats de coordinador, líneas 179-234 lo mismo para tutor. No existe un `dashboard_repository`.
  - `auth_service.py:63-64`: `stmt = select(Usuario).where(Usuario.username == data.username)` + `await self.db.execute(stmt)` — existiendo `usuario_repository.py` con exactamente ese tipo de query. Además hace `db.commit()` directo en líneas 174, 193 y 208.
  - `moodle_service.py:1284-1340`: tres bloques `select(Comision)`, `select(Rubrica)`, `select(Materia)` ejecutados con `self.db.execute`.
  - `notificacion_config_service.py:28-37` y `snapshot_config_service.py:28-35`: `select(...)` + `db.add(config)` + `db.commit()` — persistencia completa hecha en el service.
  - `excel_service.py:79-86` y `moodle_import_service.py:364-394`: queries de `Entrega`, `Comision`, `Rubrica` y `Materia` armadas inline.
  - Grep total: 55 ocurrencias de `db.execute|select(|db.add|db.commit` en 14 archivos de `services/` (algunas son docstrings; las de arriba son código real verificado).
- **Impacto**: La capa Repository deja de ser el único punto de acceso a datos: las reglas de soft-delete, filtros por permisos y paginación quedan duplicadas o inconsistentes según el camino que tome el request. Testear estos services exige DB real o mocks de sesión (en vez de mockear un repo). La arquitectura declarada en `CLAUDE.md` y la real divergen — el próximo dev no sabe cuál imitar.
- **Reproducción**: `rg "select\(|db\.execute|db\.add|db\.commit" backend/app/services/`
- **Fix propuesto**: Extraer las queries a repositories existentes o nuevos (`DashboardRepository`, `ConfigRepository`); `auth_service` debe consumir `UsuarioRepository`. El commit/rollback debería quedar en un único lugar (unit of work o el propio repo/dependencia de sesión), no esparcido en services.
- **Esfuerzo estimado**: L

---

### [ALTA] Routers que instancian Repositories directo, salteando Services

- **ID**: ARCH-002
- **Ubicación**: `backend/app/routers/correcciones.py:34,396-397,427-435`, `backend/app/routers/cierre_cursada.py:19`, `backend/app/routers/perfil.py:19`, `backend/app/routers/notificaciones.py:28`, `backend/app/routers/documentos.py:68`
- **Severidad**: 🟠 Alta
- **Dimensión**: Arquitectura
- **Descripción**: El flujo obligatorio es Router → Service → Repository. Cinco routers importan e instancian repositories directo, cortocircuitando la capa de Services.
- **Evidencia**:
  - `correcciones.py:396-397`: `entrega_repo = EntregaRepository(db)` + `ids = await entrega_repo.get_subidas_ids_by_tutor(...)` dentro del endpoint `corregir_global`. Y en `progreso_global` (427-435) el router consulta el repo y **calcula el agregado de negocio** (`total = subidas + pendientes + corregidas + error`) inline.
  - `cierre_cursada.py:19`, `perfil.py:19`, `notificaciones.py:28` importan repositories a nivel módulo; `documentos.py:68` lo hace inline dentro de un handler.
- **Impacto**: La lógica que debería vivir en un service (qué entregas encolar, cómo se compone el progreso) queda repartida entre router y repo. Cualquier regla nueva (p. ej. filtrar por comisión activa) hay que aplicarla en dos capas. Rompe la testeabilidad por capas: para testear el endpoint hay que mockear repos, no services.
- **Reproducción**: `rg "from app.repositories" backend/app/routers/`
- **Fix propuesto**: Mover esas llamadas a métodos del service correspondiente (`CorreccionService.iniciar_global()`, `CorreccionService.progreso_global()`, etc.) y que el router solo delegue.
- **Esfuerzo estimado**: M

---

### [ALTA] 13 archivos backend superan el límite de 500 LOC

- **ID**: ARCH-003
- **Ubicación**: `backend/app/` (varios — ver evidencia)
- **Severidad**: 🟠 Alta
- **Dimensión**: Arquitectura
- **Descripción**: La regla del proyecto es "Max 500 LOC per file" en backend. Hay 13 archivos que la violan, dos de ellos por márgenes enormes.
- **Evidencia** (LOC medidas con `wc -l`):
  | Archivo | LOC | Exceso |
  |---------|-----|--------|
  | `backend/app/services/pdf_service.py` | 2417 | +383% (una sola clase `PDFService`) |
  | `backend/app/services/moodle_service.py` | 1543 | +209% |
  | `backend/app/services/entrega_service.py` | 1031 | +106% |
  | `backend/app/services/correccion_service.py` | 954 | +91% |
  | `backend/app/integrations/gemini_correction_client.py` | 927 | +85% |
  | `backend/app/services/consolidacion_service.py` | 714 | +43% |
  | `backend/app/schemas/rubrica.py` | 626 | +25% |
  | `backend/app/services/rubrica_service.py` | 583 | +17% |
  | `backend/app/repositories/materia_repository.py` | 557 | +11% |
  | `backend/app/services/moodle_import_service.py` | 546 | +9% |
  | `backend/app/services/comision_service.py` | 543 | +9% |
  | `backend/app/services/excel_service.py` | 517 | +3% |
  | `backend/app/core/permissions.py` | 516 | +3% |
- **Impacto**: `pdf_service.py` con 2417 LOC en una sola clase es inmantenible: cada cambio de layout de PDF toca un archivo gigante con alto riesgo de regresión y merge conflicts. Los archivos >900 LOC concentran los flujos más críticos del negocio (corrección IA, Moodle, entregas), justo donde más duele.
- **Reproducción**: `wc -l backend/app/**/*.py | sort -rn`
- **Fix propuesto**: Partir por responsabilidad: `pdf_service` en módulos por tipo de documento/render; `moodle_service` en cliente API + parsing + sincronización (ya existen `moodle_bulk_parser`, `moodle_url_parser` — seguir ese patrón); `correccion_service` separando los workers de background (`procesar_lote_background`, `procesar_global_background`, líneas 790 y 890) a un módulo de tasks.
- **Esfuerzo estimado**: L

---

### [ALTA] `moodle_service.py` como god-service: hub de 7 services y cadenas frágiles

- **ID**: ARCH-004
- **Ubicación**: `backend/app/services/moodle_service.py` (1543 LOC); importadores: `cierre_cursada_service.py:36`, `gestion_service.py:37`, `moodle_grade_service.py:32`, `moodle_import_service.py:36`, `por_entregar_service.py:35`, `snapshot_service.py:39`, `unidad_service.py:42`
- **Severidad**: 🟠 Alta
- **Dimensión**: Arquitectura
- **Descripción**: `MoodleService` es dependencia directa de 7 services distintos, y varios de ellos se encadenan entre sí formando grafos de acoplamiento service→service de 3+ niveles sin interfaz intermedia.
- **Evidencia**:
  - Cadenas verificadas por imports:
    - `por_entregar_service` → `moodle_grade_service` → `moodle_service` (+ `comentario_template_service`, `devolucion_link_service`)
    - `moodle_import_service` → `entrega_service` → `consolidacion_service` + `historial_service`
    - `notificacion_service` → `snapshot_service` → `moodle_service` (+ `email_service`, `notificacion_config_service`, `actividad_service`)
    - `gestion_service` → `excel_service` + `moodle_service`
  - `actividad_service` (audit log) es importado por 8 services — aceptable como cross-cutting, pero suma al grafo.
- **Impacto**: Cualquier cambio de firma o comportamiento en `moodle_service` tiene radio de explosión sobre media capa de negocio. Instanciar un service en tests arrastra la cadena completa (Moodle + email + snapshots). Es el terreno típico donde aparecen los import cycles: hoy se salva porque `moodle_service` solo importa `usuario_repository` (línea 33), pero un import inverso lo rompe.
- **Reproducción**: `rg "^from app.services" backend/app/services/`
- **Fix propuesto**: Separar `moodle_service` en un cliente de integración (candidato a `app/integrations/moodle_client.py` — hoy la integración HTTP con Moodle vive en `services/`, inconsistente con Gemini/OpenRouter que sí están en `integrations/`) y services de dominio finos. Para las cadenas, invertir dependencias con protocolos/interfaces o componer en el router vía DI, no service-dentro-de-service.
- **Esfuerzo estimado**: L

---

### [ALTA] Código zombie de N8N: excepciones, catálogo de errores, compose y `.pyc` huérfano

- **ID**: ARCH-005
- **Ubicación**: `backend/app/integrations/__pycache__/n8n_client.cpython-313.pyc`, `backend/app/core/exceptions.py:52-62`, `backend/app/core/error_catalog.py:19-20,58-61`, `docker-compose.easypanel.yml:31-100`, `backend/requirements.txt:36`, `backend/app/main.py:109`, `backend/app/routers/correcciones.py:49,91,100`
- **Severidad**: 🟠 Alta
- **Dimensión**: Arquitectura
- **Descripción**: N8N fue removido del flujo de corrección (reemplazado por `gemini_correction_client.py`, que lo declara en su docstring: "Replaces the N8N proxy layer"), pero quedaron restos estructurales en cuatro niveles: artefacto compilado huérfano, taxonomía de excepciones, infraestructura de deploy y comentarios/docstrings que mienten sobre el flujo actual.
- **Evidencia**:
  - `backend/app/integrations/__pycache__/n8n_client.cpython-313.pyc` existe sin su `.py` fuente — confirma que `n8n_client.py` fue borrado pero el `__pycache__` está commiteado/presente. ⚠️ A confirmar si `__pycache__` está versionado en git o solo local.
  - `core/exceptions.py:55-62`: `N8NError` y `N8NTimeoutError` siguen definidas y son las excepciones que levanta el **cliente Gemini directo** (`gemini_correction_client.py:195,215,224,232,487,494`) — semántica engañosa: un timeout de Gemini se reporta como error de un sistema que ya no existe.
  - `core/error_catalog.py:19-20`: códigos `N8N_TIMEOUT` / `N8N_ERROR` siguen siendo los códigos técnicos persistidos en las entregas con error (`correccion_service.py:196` los marca hoy).
  - `docker-compose.easypanel.yml:31-100`: levanta el servicio `n8n` completo (imagen, auth, volumen `n8n_data`, labels de Traefik) y le pasa al backend env vars `N8N_BASE_URL`, `N8N_WEBHOOK_CORRECCION`, `N8N_WEBHOOK_RUBRICA`, `N8N_WEBHOOK_HEALTH`, `N8N_TIMEOUT_SECONDS` (líneas 82-86) que **ningún código lee**: `core/config.py` no tiene ninguna referencia a N8N. El backend además declara `depends_on: n8n` (línea 100) — el deploy espera un servicio inútil.
  - `requirements.txt:36`: comentario "HTTP Client (for N8N integration)" justificando httpx.
  - Docstrings desactualizados que describen el flujo viejo: `routers/correcciones.py:49` ("a qué workflow de n8n se rutea"), `:91` ("Sends to N8N → Gemini"), `:100` ("Timeout: 90 seconds (configurable in N8N)"), `main.py:109` ("Estado de conexion a N8N").
- **Impacto**: El deploy de producción (easypanel) arranca y monitorea un contenedor N8N que no participa del flujo — costo de recursos, superficie de ataque (basic auth expuesta por Traefik) y confusión operativa. Los códigos de error `N8N_*` persistidos contaminan datos y métricas con semántica falsa. Un dev nuevo que lea `correcciones.py` va a buscar workflows de N8N que no existen.
- **Reproducción**: `rg -i "n8n" backend/ docker-compose.easypanel.yml`
- **Fix propuesto**: Renombrar `N8NError`/`N8NTimeoutError` → `IAProviderError`/`IAProviderTimeoutError` (con alias temporal si hay datos persistidos con código `N8N_*`, definir migración de códigos); eliminar el servicio n8n y sus env vars del compose de easypanel; borrar el `.pyc` huérfano y asegurar `__pycache__/` en `.gitignore`; actualizar docstrings.
- **Esfuerzo estimado**: M

---

### [MEDIA] `HTTPException` masivo en la capa de Services

- **ID**: ARCH-006
- **Ubicación**: `backend/app/services/` (26 archivos — ej. `rubrica_service.py` con 37 ocurrencias, `entrega_service.py` con 32, `comision_service.py` con 31, `materia_service.py` con 29)
- **Severidad**: 🟡 Media
- **Dimensión**: Arquitectura
- **Descripción**: Hay 311 `raise HTTPException` distribuidos en 26 archivos de `services/`. La capa de negocio está acoplada al transporte HTTP de FastAPI, a pesar de que existe `app/core/exceptions.py` con una jerarquía de excepciones de dominio (`ActiveIAException` y derivadas) que está subutilizada.
- **Evidencia**: `rg -c "HTTPException" backend/app/services/` → 311 en 26 archivos. Ejemplo: `auth_service.py:68-71` levanta `HTTPException 401` por credenciales inválidas — decisión de dominio expresada en vocabulario HTTP.
- **Impacto**: Los services no son reutilizables fuera de un request HTTP (jobs de scheduler, CLI, tests) sin arrastrar FastAPI. El mapeo dominio→status code queda esparcido en 26 archivos en vez de centralizado en un exception handler. Nota: los workers de background (`procesar_lote_background`) ya tienen que capturar `HTTPException` fuera de contexto HTTP.
- **Reproducción**: `rg -c "HTTPException" backend/app/services/`
- **Fix propuesto**: Usar las excepciones de dominio de `core/exceptions.py` en services y mapearlas a HTTP en un `exception_handler` global de FastAPI. Migración incremental, empezando por los services que también corren en background.
- **Esfuerzo estimado**: L

---

### [MEDIA] `core/permissions.py` ejecuta queries SQLAlchemy directo

- **ID**: ARCH-007
- **Ubicación**: `backend/app/core/permissions.py:383-384, 407-408, 427-428, 456-457, 476-477, 503-504`
- **Severidad**: 🟡 Media
- **Dimensión**: Arquitectura
- **Descripción**: El módulo de permisos (capa `core`, que debería ser transversal y sin conocimiento de persistencia) ejecuta 6 queries `select(...)` directas sobre `CoordinadorMateria`, `Unidad`, `ExamenMateria`, `Comision`, `Rubrica` y `ComisionTutor` para resolver ownership.
- **Evidencia**: `permissions.py:383-384`: `result = await db.execute(select(CoordinadorMateria.id)...)`; ídem en las otras 5 ubicaciones listadas.
- **Impacto**: `core` pasa a depender de 6 modelos de dominio y de la sesión — invierte la dirección de dependencias (core debería ser lo más abajo del grafo). Las reglas de "a qué materia pertenece X" quedan duplicadas respecto de los repositories que ya saben resolverlas.
- **Reproducción**: `rg "db.execute|select\(" backend/app/core/`
- **Fix propuesto**: Delegar la resolución de ownership a métodos de repository (`materia_repository.usuario_es_coordinador()`, etc.) y que `permissions.py` solo componga la decisión, o mover estos checks a un `PermissionService`.
- **Esfuerzo estimado**: M

---

### [MEDIA] Imports cruzados entre features del frontend sin frontera definida

- **ID**: ARCH-008
- **Ubicación**: `frontend/src/features/` — 30+ ocurrencias. Ejemplos representativos: `entregas/pages/EntregasPage.tsx:17-44` (importa de 5 features: comisiones, rubricas, correcciones, auth, perfil), `por-entregar/components/PorEntregarTable.tsx:3` (importa `SubirMoodleModal` de `entregas/components`), `pendientes/pages/PendientesPage.tsx:4` y `por-entregar/pages/PorEntregarPage.tsx:3` (importan `StatCard` desde `dashboard/components`)
- **Severidad**: 🟡 Media
- **Dimensión**: Arquitectura
- **Descripción**: La arquitectura declarada es feature-based con `shared/` para lo reusable. En la práctica las features se importan entre sí libremente: componentes de una feature usados como si fueran shared (`StatCard`, `SubirMoodleModal`), hooks y services cruzados (`useAuth`, `useProfile`, `invalidateStoredApiKey` consumidos desde entregas/correcciones/dashboard).
- **Evidencia**: `rg "from '@/features/" frontend/src/features/` → 30+ matches cruzando límites de feature. Los casos de `auth` y `perfil` son semi-legítimos (cross-cutting), pero `dashboard/components/StatCard` importado por 2 features ajenas y `entregas/components/SubirMoodleModal` importado por `por-entregar` son componentes compartidos viviendo en la feature equivocada.
- **Impacto**: Las features dejan de ser unidades independientes: no se puede tocar/borrar `dashboard` sin romper `pendientes` y `por-entregar`. El grafo de dependencias entre features es implícito y sin regla de lint que lo controle, así que solo va a crecer.
- **Reproducción**: `rg "from '@/features/" frontend/src/features/ | rg -v "features/([a-z-]+)/.*@/features/\1"`
- **Fix propuesto**: Promover a `shared/` los componentes usados por 2+ features (`StatCard`, `SubirMoodleModal`); definir qué features son cross-cutting permitidas (auth, perfil) y encodear la regla con `eslint-plugin-boundaries` o similar.
- **Esfuerzo estimado**: M

---

### [MEDIA] Lógica de negocio leve en router `correcciones.py`

- **ID**: ARCH-009
- **Ubicación**: `backend/app/routers/correcciones.py:45-67, 388-394, 427-442`
- **Severidad**: 🟡 Media
- **Dimensión**: Arquitectura
- **Descripción**: El router de correcciones toma decisiones de dominio que corresponden al service: resolución de credenciales/proveedor de IA, gate de "API key paga" y armado del agregado de progreso.
- **Evidencia**:
  - `_resolver_credenciales_ia()` (líneas 45-67): función a nivel de módulo del router que decide qué API key usar según `correction_provider` del usuario — regla de negocio del flujo de corrección.
  - Líneas 388-394: la regla "la corrección global con Gemini requiere key paga, OpenRouter no" (incluida la justificación de negocio en el comentario) está implementada en el endpoint.
  - Líneas 427-442: el endpoint `progreso_global` compone el resultado de negocio (`total = subidas + pendientes + corregidas + error`, decide cuándo consultar `errores_por_codigo`).
- **Impacto**: Estas reglas no son testeables sin levantar el router, y no se reutilizan: si mañana el scheduler quiere disparar corrección global, hay que duplicar el gate de key paga. Combinado con ARCH-002 (el mismo endpoint usa `EntregaRepository` directo), `corregir_global` es el endpoint que más viola el layering del proyecto.
- **Reproducción**: Leer `backend/app/routers/correcciones.py:366-443`.
- **Fix propuesto**: Mover `_resolver_credenciales_ia` y el gate de key paga a `CorreccionService` (o a `ia_provider`), y que `progreso_global` devuelva un DTO ya compuesto por el service.
- **Esfuerzo estimado**: S

---

### [BAJA] Estructura muerta `backend/app/api/v1/routers/`

- **ID**: ARCH-010
- **Ubicación**: `backend/app/api/__init__.py`, `backend/app/api/v1/__init__.py`, `backend/app/api/v1/routers/__init__.py`
- **Severidad**: 🟢 Baja
- **Dimensión**: Arquitectura
- **Descripción**: Existe un árbol de paquetes `app/api/v1/routers/` completamente vacío (solo `__init__.py`), mientras los routers reales viven en `app/routers/` y el prefijo `/api/v1` se aplica a mano en cada `include_router` de `main.py` (líneas 121, 126, 131, 136...).
- **Evidencia**: Los tres paquetes no contienen ningún módulo. Ningún import en el codebase apunta a `app.api`.
- **Impacto**: Estructura zombie que sugiere una migración a versionado de API que nunca se hizo. Confunde: hay dos lugares candidatos para crear un router nuevo. Además el prefijo `/api/v1` repetido N veces en `main.py` es el síntoma de que el paquete versionado nunca se adoptó.
- **Reproducción**: `eza backend/app/api/v1/routers/`
- **Fix propuesto**: Decidir: o se borra el árbol `app/api/` (opción barata), o se completa la migración moviendo routers ahí con un `api_router` agregador que centralice el prefijo. No dejar el limbo actual.
- **Esfuerzo estimado**: S

---

### [BAJA] `fetch` crudo con manejo manual de JWT duplicado en 4 services del front

- **ID**: ARCH-011
- **Ubicación**: `frontend/src/features/pendientes/services/pendientes.service.ts:42-53`, `frontend/src/features/por-entregar/services/por-entregar.service.ts:22-26`, `frontend/src/features/notificaciones/services/notificaciones.service.ts:60`, `frontend/src/features/cron-config/services/cron-config.service.ts:70`
- **Severidad**: 🟢 Baja
- **Dimensión**: Arquitectura
- **Descripción**: Cuatro services usan `fetch` crudo en vez del `apiClient` compartido. La justificación es válida (streaming SSE, que axios no maneja bien, documentado en `pendientes.service.ts:35`), y están correctamente en la capa `services/` — no hay fetch en componentes ni pages (verificado). Pero cada uno re-implementa a mano la obtención del token (`localStorage.getItem('auth_token')`), la base URL y el manejo de errores que el interceptor de `api-client.ts` ya centraliza.
- **Evidencia**: `pendientes.service.ts:41-52` y `por-entregar.service.ts:22-26` duplican el bloque token+headers; si mañana cambia el storage del token (p. ej. a cookie), hay 4+ lugares para tocar además del interceptor.
- **Impacto**: Deriva silenciosa: los flujos SSE quedan fuera del manejo centralizado de 401/refresh del interceptor de axios. Bug latente si cambia la estrategia de auth.
- **Reproducción**: `rg "fetch\(" frontend/src/features/`
- **Fix propuesto**: Extraer un helper compartido `shared/services/sse-client.ts` (o `fetchWithAuth`) que resuelva token + baseURL + errores en un solo lugar, y que los 4 services lo consuman.
- **Esfuerzo estimado**: S

---

### [BAJA] Imports inline repetidos dentro de métodos de `correccion_repository.py`

- **ID**: ARCH-012
- **Ubicación**: `backend/app/repositories/correccion_repository.py:69-70, 117-118, 156-159, 273, 310-311, 345-350, 412-417, 473-475`
- **Severidad**: 🟢 Baja
- **Dimensión**: Arquitectura
- **Descripción**: El repository importa `Entrega`, `Comision`, `Materia`, `Rubrica`, `MoodleSync` y enums **dentro de cada método**, repetido en 8+ lugares, en vez de a nivel módulo. Es el patrón típico de workaround de import circular — pero acá no se justifica: otros repositories (p. ej. `cohorte_repository.py:15-16`) importan los mismos modelos a nivel módulo sin problema.
- **Evidencia**: `correccion_repository.py:345-350` importa 6 módulos dentro de un método; el mismo set se re-importa en las líneas 412-417.
- **Impacto**: Ruido y sospecha falsa de circularidad para quien lee; oculta el grafo real de dependencias del módulo. ⚠️ A confirmar si en algún momento hubo un ciclo real `models ↔ repositories` que motivó esto — hoy no se detecta ninguno.
- **Reproducción**: `rg -n "^\s+from app.models" backend/app/repositories/correccion_repository.py`
- **Fix propuesto**: Subir los imports al nivel de módulo y deduplicar. Si aparece un ciclo real, resolverlo en los modelos (p. ej. `TYPE_CHECKING`), no escondiéndolo en los métodos.
- **Esfuerzo estimado**: S

---

## Notas de cierre

- **Lo que está bien** (para calibrar señal): los routers en general son finos y delegan correctamente (verificado en `rubricas.py`, `correcciones.py` salvo lo señalado); no hay `fetch`/`axios` en componentes ni pages del front; los repositories no contienen lógica de negocio ni importan services; no se detectaron ciclos de import reales en backend; los schemas Pydantic se usan como DTOs de borde, no como modelos de dominio (los services operan sobre modelos SQLAlchemy).
- **Patrón transversal**: las violaciones se concentran en el subsistema Moodle/corrección masiva (agregado más tarde al proyecto) — `moodle_service`, `moodle_import_service`, `correcciones.py` router y los 4 services SSE del front. El código "fase 1-3" respeta mucho mejor el layering que el "fase 4+".
