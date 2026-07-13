# 📨 Auditoría — Errores Mal Transmitidos (dimensión 05)

Auditoría del viaje del error de punta a punta en Active-IA: desde el proveedor de IA / la base de datos / Moodle, pasando por servicios y routers de FastAPI, hasta el toast que ve el tutor en el frontend.

## Alcance

Se auditó:

- **Backend**: `app/core/{exceptions.py,error_catalog.py}`, `app/main.py`, `app/integrations/*` (Gemini Studio, OpenRouter, cliente de corrección), `app/services/{correccion_service,rubrica_ia_service,consolidacion_service,entrega_service,moodle_grade_service}.py`, routers `correcciones`, `rubricas`, `perfil`, `entregas`, `cierre_cursada`, `app/core/dependencies.py`.
- **Frontend**: interceptor axios global (`shared/services/api-client.ts`), `shared/types/index.ts` (`getErrorMessage`), hooks y services de `correcciones`, `entregas`, `auth`, `dashboard` (corrección global), y `EntregasPage.tsx` (polling de lote).

### El viaje del error hoy (diagrama)

```
Google AI Studio / OpenRouter
        │  HTTP != 200
        ▼
_handle_non_200 / _detect_*_error          ← mapea a excepciones de dominio
(gemini_correction_client, openrouter)       (APIKeyInvalid, Quota, Overloaded,
        │                                     InsufficientCredits, N8NError*)
        ▼
CorreccionService.corregir_individual      ← catch por tipo → marca entrega ERROR
        │                                    (error_code + mensaje_error() catálogo)
        │                                    → HTTPException 402/429/502/503
        │
RubricaIAService.generar_rubrica_desde_pdf ← ⚠️ SOLO catchea N8NError/Timeout:
        │                                    el resto EXPLOTA como 500 crudo
        ▼
FastAPI (main.py)                          ← ⚠️ SIN exception handlers globales:
        │                                    ActiveIAException sin traducir = 500
        ▼
axios interceptor (api-client.ts)          ← toasts por status; ⚠️ no entiende
        │                                    detail objeto {error_code, message}
        ▼
hooks React Query (onError)                ← re-toastean (⚠️ doble toast) o
        │                                    tragan el error (⚠️ null silencioso)
        ▼
Usuario (toast / badge ERROR con error_mensaje persistido)
```

**Lo que está bien** (y conviene preservar): el catálogo `error_catalog.py` como fuente única de mensajes provider-aware; la persistencia de `error_code/error_mensaje/error_at` en la entrega (el badge de la tabla muestra el motivo real); el corte del lote en 402/429 con backoff; la auditoría de fallos de Moodle en `MoodleSync` con códigos 424/502/422/409 bien diferenciados; el resumen de errores por código en `CorregirTodoButton`.

## Índice

| ID | Título | Severidad |
|----|--------|-----------|
| ERR-001 | Key inválida / rate limit al generar rúbrica → 500 crudo | 🔴 Crítica |
| ERR-002 | Sin exception handler global: excepciones de dominio desconectadas del HTTP | 🟠 Alta |
| ERR-003 | Entregas colgadas en PENDIENTE para siempre, sin reconciliación | 🟠 Alta |
| ERR-004 | Login fallido tratado como "Sesión expirada"; el detail real nunca llega | 🟠 Alta |
| ERR-005 | `detail` objeto `{error_code, message}` no lo parsea ni el interceptor ni `getErrorMessage` | 🟠 Alta |
| ERR-006 | `getCorreccionByEntregaId` traga TODO error y devuelve `null` | 🟠 Alta |
| ERR-007 | Fuga de internals (body crudo del proveedor, errores de crypto) al cliente | 🟡 Media |
| ERR-008 | Error de red del servidor reportado al usuario como "API Key inválida" | 🟡 Media |
| ERR-009 | 500s lanzados sin log — contrato "500 + log detallado" incumplido | 🟡 Media |
| ERR-010 | Doble toast (interceptor + hook) en errores de corrección | 🟡 Media |
| ERR-011 | Código muerto roto: servicio de lote apunta a un endpoint que no existe | 🟡 Media |
| ERR-012 | Toast del lote genérico y hardcodeado a "Gemini" pese a tener el error real persistido | 🟡 Media |
| ERR-013 | Carga masiva devuelve `str(e)` crudo por alumno, sin traceback en logs | 🟡 Media |
| ERR-014 | Semántica HTTP propia (402/429/503) no documentada + naming "N8N" fantasma | 🟢 Baja |
| ERR-015 | Logs imprecisos: todo 402 = "key inválida"; auth opcional traga errores de DB | 🟢 Baja |

**Totales**: 1 Crítica · 5 Altas · 7 Medias · 2 Bajas

---

### [CRÍTICA] Key inválida / rate limit al generar rúbrica → 500 crudo

- **ID**: ERR-001
- **Ubicación**: `backend/app/services/rubrica_ia_service.py:95-106` (+ `backend/app/routers/rubricas.py:483-484`, `backend/app/core/exceptions.py:55-97`)
- **Severidad**: 🔴 Crítica
- **Dimensión**: Errores
- **Descripción**: `generar_rubrica_desde_pdf` solo captura `N8NTimeoutError` y `N8NError`. Pero el cliente (`gemini_correction_client._handle_non_200` / `_detect_gemini_error`, líneas 135-217) lanza `APIKeyInvalidError`, `QuotaExceededError`, `ModelOverloadedError` e `InsufficientCreditsError`, que heredan de `GeminiError` → `ActiveIAException`, **una rama de herencia distinta a `N8NError`**. Ninguna capa las captura (el router `rubricas.py` llama al service sin try/except y `main.py` no registra handlers), así que suben como excepción no manejada.
- **Evidencia**: `exceptions.py:55` (`class N8NError(ActiveIAException)`) vs `exceptions.py:70-97` (`class GeminiError(ActiveIAException)` y sus 4 hijas). `rubrica_ia_service.py:97-106` solo tiene `except N8NTimeoutError` y `except N8NError`. Contraste: `correccion_service.py:195-270` sí captura las 6 explícitamente.
- **Impacto**: el caso MÁS probable de fallo (key de Gemini expirada, rate limit del free tier, modelo sobrecargado) al generar una rúbrica desde PDF devuelve **500 Internal Server Error** genérico. El usuario ve "Error del servidor. Por favor, intenta nuevamente más tarde" (toast del interceptor, caso 500) sin ninguna pista de que su key expiró. Además, a diferencia del flujo de corrección (`correccion_service.py:206-215`), NO se marca `gemini_api_key_valid = False` en la DB, así que el perfil sigue mostrando la key como válida.
- **Reproducción**: configurar una API key de Gemini que luego expire → `POST /api/v1/rubricas/generar-desde-pdf` con cualquier PDF → 500 en vez de 402 con mensaje del catálogo.
- **Fix propuesto**: capturar en `rubrica_ia_service` el mismo set de excepciones que `correccion_service` (o mejor: resolver ERR-002 con un handler global de `ActiveIAException` que traduzca cada tipo a su status + mensaje de catálogo, y deduplicar el mapeo hoy copiado en `correccion_service`). Marcar la key inválida en DB también en este flujo.
- **Esfuerzo estimado**: S

---

### [ALTA] Sin exception handler global: excepciones de dominio desconectadas del HTTP

- **ID**: ERR-002
- **Ubicación**: `backend/app/main.py:54-83` (ausencia) + `backend/app/core/exceptions.py:20-49`
- **Severidad**: 🟠 Alta
- **Dimensión**: Errores
- **Descripción**: `main.py` no registra ningún `app.add_exception_handler(...)`. El proyecto define un catálogo prolijo de excepciones de dominio (`ValidationError`, `UnauthorizedError`, `ForbiddenError`, `NotFoundError`, `ConflictError`, `ExternalServiceError`) pero no existe NINGUNA traducción centralizada a HTTP. Consecuencias: (a) toda excepción de dominio que se escape de un try/except local = 500 crudo (ERR-001 es exactamente eso); (b) los services compensan lanzando `HTTPException` directamente (`correccion_service`, `moodle_grade_service`, `consolidacion_service`...), acoplando la capa de negocio al transporte HTTP; (c) `UnauthorizedError`, `ForbiddenError`, `NotFoundError` y `ConflictError` son código muerto — un grep muestra que solo `ValidationError` se lanza en todo el backend.
- **Evidencia**: grep de `add_exception_handler|exception_handler` en `backend/` → 0 resultados. Grep de `raise (NotFoundError|ConflictError|ForbiddenError|UnauthorizedError)` → 0 resultados. `ValidationError` se lanza solo en `correccion_service.py:727,740` y `rubrica_ia_service.py` (17 sitios), siempre capturada localmente.
- **Impacto**: cada fuga futura de una excepción de dominio será un 500 sin mensaje; la traducción error→HTTP está duplicada en cada service (el bloque de 75 líneas de `corregir_individual` habría que copiarlo en cualquier flujo IA nuevo — y en `rubrica_ia_service` ya se olvidaron, ver ERR-001).
- **Fix propuesto**: registrar un handler global para `ActiveIAException` con un mapeo tipo→(status, error_code, mensaje de catálogo) + log automático. Migrar gradualmente los services a lanzar excepciones de dominio en vez de `HTTPException` (alineado con Clean Architecture del CLAUDE.md). Borrar o empezar a usar las excepciones muertas.
- **Esfuerzo estimado**: M

---

### [ALTA] Entregas colgadas en PENDIENTE para siempre, sin reconciliación

- **ID**: ERR-003
- **Ubicación**: `backend/app/services/correccion_service.py:185-187` (+ `272-352`, `frontend/src/features/entregas/pages/EntregasPage.tsx:190-205`)
- **Severidad**: 🟠 Alta
- **Dimensión**: Errores
- **Descripción**: `corregir_individual` pone `entrega.estado = PENDIENTE` **antes** de llamar a la IA. Los fallos de IA están bien cubiertos (pasan a `ERROR` con código), pero: (a) si falla cualquier cosa DESPUÉS de la respuesta exitosa de la IA — el hard-delete de la corrección previa (línea 290), `correccion_repo.create` (línea 344), la construcción del response — la entrega queda en `PENDIENTE` sin marca de error; (b) si el proceso muere (deploy, OOM, restart) durante un lote background (`procesar_lote_background` corre en `BackgroundTasks`, muere con el proceso), TODAS las entregas en vuelo quedan `PENDIENTE`. No existe ningún job de reconciliación ni timeout que las rescate.
- **Evidencia**: no hay `except Exception` alrededor del bloque de persistencia post-IA (líneas 283-352); el estado `PENDIENTE` solo sale por éxito (`CORREGIDA`, línea 347) o por las 6 excepciones IA capturadas. El frontend (`EntregasPage.tsx:197-205`) hace polling cada 10s **mientras haya PENDIENTE** — con una entrega colgada, el polling no termina nunca.
- **Impacto**: estado ambiguo permanente: el tutor ve "PENDIENTE" eterno, el botón de corregir puede quedar bloqueado por UI, el polling queda activo para siempre, y la única salida es tocar la DB a mano. En la masiva global (`/correcciones/global`) las PENDIENTE colgadas ni siquiera re-entran al lote (solo toma `SUBIDA`, `entrega_repo.get_subidas_ids_by_tutor`).
- **Reproducción**: matar el proceso uvicorn en medio de un lote de 50 → las entregas en curso quedan PENDIENTE para siempre.
- **Fix propuesto**: (1) envolver la persistencia post-IA en try/except que marque `ERROR` con un código nuevo del catálogo; (2) job de arranque o cron que pase a `ERROR` (o de vuelta a `SUBIDA`) toda entrega en `PENDIENTE` hace más de N minutos; (3) considerar que la masiva global también re-tome `PENDIENTE` viejas.
- **Esfuerzo estimado**: M

---

### [ALTA] Login fallido tratado como "Sesión expirada"; el detail real nunca llega

- **ID**: ERR-004
- **Ubicación**: `frontend/src/shared/services/api-client.ts:96-105` (+ `frontend/src/features/auth/pages/LoginPage.tsx:82-86`, `backend/app/services/auth_service.py:92-96`)
- **Severidad**: 🟠 Alta
- **Dimensión**: Errores
- **Descripción**: el interceptor global trata TODO 401 como sesión expirada: toast "Sesión expirada. Por favor, inicia sesión nuevamente.", borra `localStorage` y fuerza `window.location.href = '/login'` a los 1.5s. Pero el backend devuelve 401 también para credenciales incorrectas en el propio login, incluyendo información valiosa: `"Credenciales inválidas. {N} intentos restantes."` (hay lockout por intentos). Ese detail muere: el interceptor no lo muestra, y `LoginPage` renderiza `loginMutation.error.message`, que para un `AxiosError` es el texto técnico `"Request failed with status code 401"`.
- **Evidencia**: `auth_service.py:94-96` arma el detail con intentos restantes; `api-client.ts:98` toastea el texto hardcodeado sin usar `message`; `LoginPage.tsx:84-85` muestra `error.message` de Axios; `useLogin.ts:67-72` solo hace `console.error`.
- **Impacto**: quien se equivoca de contraseña ve un mensaje absurdo ("Sesión expirada") + un reload completo de la página de login que le borra el form, y NUNCA se entera de que le quedan 2 intentos antes del bloqueo de cuenta. Cuando se bloquea, tampoco entiende por qué.
- **Reproducción**: ir a /login, poner contraseña incorrecta → toast "Sesión expirada..." y reload.
- **Fix propuesto**: en el interceptor, exceptuar del tratamiento de 401 a las URLs de auth (`/auth/login`, `/auth/change-password`) y dejar que el caller muestre el detail real; en `LoginPage`, extraer el detail del `AxiosError` (usar el `getErrorMessage` compartido, no `error.message`).
- **Esfuerzo estimado**: S

---

### [ALTA] `detail` objeto `{error_code, message}` no lo parsea ni el interceptor ni `getErrorMessage`

- **ID**: ERR-005
- **Ubicación**: `frontend/src/shared/services/api-client.ts:85-92` + `frontend/src/shared/types/index.ts:278-296`
- **Severidad**: 🟠 Alta
- **Dimensión**: Errores
- **Descripción**: el backend responde los errores IA "ricos" con `detail = {error_code, message}` (402 key inválida, 402 sin créditos, 429 rate limit, 503 sobrecargado — `correccion_service.py:216-263`). Pero las DOS rutinas genéricas de extracción de mensaje del frontend solo entienden `detail` string o array de Pydantic: el interceptor (`api-client.ts:85-92`) y el `getErrorMessage` compartido (`shared/types/index.ts:280-288`). Solo los hooks de correcciones/entregas tienen su `getErrorMessage` local que sí lee `detail.message` (`useCorrecciones.ts:71-77`).
- **Evidencia**: para un 503 sobrecargado, el interceptor cae en `message === undefined` → toast genérico "Error del servidor. Por favor, intenta nuevamente más tarde." aunque el backend mandó "El modelo de Gemini está sobrecargado en este momento. Reintentá en unos minutos.". Para 402/429 el interceptor deliberadamente no toastea ("handled by specific hooks", líneas 127-133) — pero `CorregirTodoButton.tsx:60` maneja su `onError` con el `getErrorMessage` COMPARTIDO, que ante detail-objeto devuelve `error.message` de Axios ("Request failed with status code 402") o el fallback genérico. El mensaje claro del catálogo, que existe justamente para esto, muere en el JSON.
- **Impacto**: mensajes accionables del catálogo (esperá unos minutos / cargá créditos / renová tu key) se degradan a genéricos o a jerga técnica según qué ruta del frontend los toque. Inconsistencia: el mismo error se ve distinto en pantallas distintas.
- **Fix propuesto**: unificar la extracción en UNA función compartida que contemple `detail` string | array | `{error_code, message}`, y usarla tanto en el interceptor como en todos los hooks. Los checks de `error_code` (`isGeminiApiKeyError`, etc.) también deberían vivir en shared — hoy están copiados en `useCorrecciones.ts:21-42` y `useEntregas.ts:46-66`.
- **Esfuerzo estimado**: S

---

### [ALTA] `getCorreccionByEntregaId` traga TODO error y devuelve `null`

- **ID**: ERR-006
- **Ubicación**: `frontend/src/features/correcciones/services/correcciones-service.ts:60-69`
- **Severidad**: 🟠 Alta
- **Dimensión**: Errores
- **Descripción**: el catch pretende mapear "404 = no hay corrección todavía" a `null`, pero captura **cualquier** error (500, 403, timeout, red caída) y devuelve `null` igual, sin siquiera `console.error`. `useCorreccionByEntrega` y el modal de corrección de `EntregasPage` consumen ese `null` como "esta entrega no tiene corrección".
- **Evidencia**: `catch (error) { // Si no existe corrección, retornar null \n return null; }` — sin chequeo de `error.response?.status === 404`. Además `descargarPDFCorreccion` (líneas 159-162) usa esta función: ante un 500 del backend lanza "No se encontró corrección para esta entrega", un mensaje FALSO.
- **Impacto**: un error real del backend se disfraza de estado de negocio válido: el tutor ve el modal vacío o "no hay corrección" para una entrega CORREGIDA, y no hay ningún rastro del error ni en consola. Debugging imposible desde el cliente.
- **Reproducción**: apagar el backend con el modal por abrirse → "no hay corrección" en vez de error de conexión.
- **Fix propuesto**: devolver `null` SOLO si `AxiosError` con status 404; re-lanzar todo lo demás para que React Query lo exponga como `isError` y la UI distinga "sin corrección" de "no pude consultar".
- **Esfuerzo estimado**: S

---

### [MEDIA] Fuga de internals (body crudo del proveedor, errores de crypto) al cliente

- **ID**: ERR-007
- **Ubicación**: `backend/app/integrations/gemini_correction_client.py:215-217` (+ `correccion_service.py:173-176,269,280`, `rubrica_ia_service.py:63-67,105`, `perfil.py:169-173`, `openrouter_client.py:82`)
- **Severidad**: 🟡 Media
- **Dimensión**: Errores
- **Descripción**: varios paths concatenan internals directo al `detail` HTTP que llega al toast del usuario:
  - `_handle_non_200` arma `N8NError(f"Error HTTP {status}: {response.text[:500]}")` → 500 caracteres del body crudo de Google/OpenRouter; `correccion_service.py:269` lo re-expone: `detail=f"{mensaje_error(...)} ({str(e)})"`; ídem `rubrica_ia_service.py:105`.
  - `Error al desencriptar API Key: {str(e)}` (`correccion_service.py:175`, `rubrica_ia_service.py:66`) filtra detalles de la capa crypto en un 400 — y encima es un error de configuración del SERVIDOR (`ENCRYPTION_KEY` rotada), no culpa del usuario: correspondería 500 con log, no 400.
  - `perfil.py:172`: `Error al guardar API Key: {str(e)}` → internals de DB en un 500.
  - `correccion_service.py:280`: el error de validación Pydantic completo (potencialmente enorme) viaja en el detail del 502.
- **Evidencia**: ver líneas citadas. ⚠️ A confirmar: la key de Gemini viaja en la query string (`?key=...`, `gemini_correction_client.py:32-38`); si algún `str(e)` de `httpx.RequestError` o log llegara a incluir la URL completa, la key quedaría expuesta en mensajes/logs — no se verificó un caso concreto donde ocurra, pero el patrón lo habilita.
- **Impacto**: mensajes crípticos y potencialmente sensibles en toasts de usuario final; superficie de información para un atacante (versiones, estructura de errores del proveedor, detalles de la capa de cifrado).
- **Fix propuesto**: el `detail` HTTP lleva SOLO el mensaje del catálogo + `error_code`; el `str(e)` completo va a `logger.error/exception`. Para la desencriptación fallida: 500 + log + mensaje "Reconfigurá tu API key en el perfil".
- **Esfuerzo estimado**: S

---

### [MEDIA] Error de red del servidor reportado al usuario como "API Key inválida"

- **ID**: ERR-008
- **Ubicación**: `backend/app/integrations/gemini_studio_client.py:47-50` + `backend/app/integrations/openrouter_client.py:277-281` (+ `perfil.py:142-148`)
- **Severidad**: 🟡 Media
- **Dimensión**: Errores
- **Descripción**: ambos `validar_api_key` terminan en `except Exception: return False` sin log. Un timeout, un DNS caído o un problema de salida a internet del servidor se vuelven `is_valid = False`, y `perfil.py:144-148` le dice al usuario "API Key inválida o sin permisos". El error real no queda registrado en ningún lado (ni log, ni respuesta).
- **Evidencia**: `gemini_studio_client.py:47-50` (`except httpx.TimeoutException: return False` / `except Exception: return False`); `openrouter_client.py:277-281` idéntico.
- **Impacto**: el tutor con una key perfectamente válida entra en un loop de frustración regenerando keys en Google AI Studio, cuando el problema era del servidor. Soporte no puede diagnosticar porque no hay log.
- **Reproducción**: cortar la salida a internet del backend → `POST /perfil/api-key` con una key válida → "API Key inválida o sin permisos".
- **Fix propuesto**: distinguir tres resultados en la validación (válida / inválida / no se pudo validar). Ante error de red devolver 502/503 con mensaje "No pudimos validar tu key en este momento, reintentá" + `logger.warning` con la causa.
- **Esfuerzo estimado**: S

---

### [MEDIA] 500s lanzados sin log — contrato "500 + log detallado" incumplido

- **ID**: ERR-009
- **Ubicación**: `backend/app/services/consolidacion_service.py:250-254,317-321,381-385` (+ `perfil.py:169-173`, `correccion_service.py:195-201,264-270`)
- **Severidad**: 🟡 Media
- **Dimensión**: Errores
- **Descripción**: el contrato del proyecto (CLAUDE.md) pide "Internal → HTTPException 500 + detailed log". Pero los `except Exception → HTTPException(500, detail=str(e))` de consolidación y perfil NO llaman a ningún logger, y FastAPI no loguea traceback de `HTTPException` (las trata como respuestas intencionales). El traceback se pierde para siempre; solo sobrevive el `str(e)` de una línea… en el toast del usuario (ERR-007). Lo mismo pasa en el flujo IA individual: las ramas `N8NTimeoutError` (líneas 195-201) y `N8NError` (264-270) de `corregir_individual` levantan 502 sin loguear nada — el resto de las ramas sí loguea (`logger.warning`, líneas 213, 228, 241, 254).
- **Evidencia**: líneas citadas; grep de `logger` en `consolidacion_service.py` → 0 usos.
- **Impacto**: los errores más raros (justo los que necesitás traza para diagnosticar: encoding exótico en ZIP, fallo de crypto, body inesperado del proveedor) son los que menos evidencia dejan en el servidor.
- **Fix propuesto**: `logger.exception(...)` antes de cada `HTTPException(500/502)` construida desde un `except Exception`; idealmente resolverlo de una vez en el handler global de ERR-002.
- **Esfuerzo estimado**: S

---

### [MEDIA] Doble toast (interceptor + hook) en errores de corrección

- **ID**: ERR-010
- **Ubicación**: `frontend/src/shared/services/api-client.ts:135-141` + `frontend/src/features/correcciones/hooks/useCorrecciones.ts:157-159` (y `useEntregas.ts:277-279,309-311`)
- **Severidad**: 🟡 Media
- **Dimensión**: Errores
- **Descripción**: para 500/502/503 el interceptor global ya dispara un toast, y después el `onError` del hook dispara OTRO. Con 502 (detail string) el usuario ve dos toasts con el mismo texto; con 503 (detail objeto) ve uno genérico ("Error del servidor…") y uno específico ("El modelo está sobrecargado…"), contradictorios entre sí. Lo mismo con 404/403/409 en hooks que además toastean (`useUpdateCorreccion` toastea genérico sobre el toast específico del interceptor).
- **Evidencia**: interceptor `case 500/502/503 → toast.error(...)`; `useCorrecciones.ts:159 → toast.error(msg)` para el mismo error. No hay ningún mecanismo de "ya se mostró este error".
- **Impacto**: UX ruidosa e inconsistente; en el caso 503 los dos mensajes se contradicen (uno dice "error del servidor", el otro "esperá unos minutos").
- **Fix propuesto**: definir un dueño único del toast por status: o el interceptor maneja SOLO los transversales (401/red) y los hooks el resto, o el interceptor marca el error como "toasted" (flag en el objeto error) y los hooks lo respetan.
- **Esfuerzo estimado**: S

---

### [MEDIA] Código muerto roto: servicio de lote apunta a un endpoint que no existe

- **ID**: ERR-011
- **Ubicación**: `frontend/src/features/correcciones/services/correcciones-service.ts:31-38` (+ `hooks/useCorrecciones.ts:171-210`, `hooks/index.ts:10`)
- **Severidad**: 🟡 Media
- **Dimensión**: Errores
- **Descripción**: `corregirEntregasLote` hace `POST /entregas/corregir-lote` — endpoint que NO existe en el backend (el router de entregas solo expone `POST /` y `POST /masiva`; el lote real es `POST /correcciones/lote`, `routers/correcciones.py:154-199`). Además tipa la respuesta como `Correccion[]` cuando el endpoint real devuelve 202 con `{mensaje, total_encoladas, entrega_ids}`. Su hook `useCorregirEntregasLote` festeja "N entrega(s) corregida(s) exitosamente" iterando ese array inexistente. Hoy ningún componente lo usa (el flujo vivo es `useCorregirEntregaMasiva` de `features/entregas`, que apunta bien), pero está **exportado en el barrel** `hooks/index.ts` como API pública del feature.
- **Evidencia**: grep de `corregir-lote` en backend → 0 endpoints; grep de `useCorregirEntregasLote` en `.tsx` → 0 usos.
- **Impacto**: trampa cargada: el próximo dev que importe el hook "oficial" del feature correcciones obtiene un 404 instantáneo y un success-handler que miente sobre el contrato (dice "corregidas" cuando el backend solo encola). Duplica además toda la lógica de error de `useEntregas`, que ya divergió.
- **Fix propuesto**: eliminar `corregirEntregasLote` + `useCorregirEntregasLote` (y su export), dejando un único camino para el lote.
- **Esfuerzo estimado**: S

---

### [MEDIA] Toast del lote genérico y hardcodeado a "Gemini" pese a tener el error real persistido

- **ID**: ERR-012
- **Ubicación**: `frontend/src/features/entregas/pages/EntregasPage.tsx:234-247` (+ `backend/app/services/correccion_service.py:837-872`)
- **Severidad**: 🟡 Media
- **Dimensión**: Errores
- **Descripción**: cuando el polling detecta errores nuevos en el lote, el toast dice siempre: "…Revisá si tu API Key de Gemini es válida o esperá unos minutos si se alcanzó el límite de uso". Dos problemas: (a) el motivo REAL está disponible — cada entrega fallida tiene `error_code`/`error_mensaje` persistidos y provider-aware (el backend se tomó el trabajo de armar el catálogo justamente para esto; hasta existe `shared/utils/erroresResumen.ts` que la corrección global SÍ usa) — pero el lote lo ignora y adivina; (b) nombra "Gemini" hardcodeado aunque el usuario esté en modo OpenRouter. Además el toast siempre dice "la corrección en lote se detuvo… N sin procesar", pero el backend solo corta el lote en 402/429 (`correccion_service.py:838-866`); con errores genéricos (502) el lote SIGUE, así que el conteo "sin procesar" puede ser falso.
- **Evidencia**: texto hardcodeado en `EntregasPage.tsx:240-245`; corte selectivo del lote en `correccion_service.py:837-866` (los `HTTPException` 502 caen al `break` del ítem pero no setean `stop_batch`).
- **Impacto**: el usuario recibe un diagnóstico especulativo cuando el sistema ya sabe el diagnóstico exacto; en modo OpenRouter el mensaje es directamente incorrecto (le pide revisar una key que no está usando).
- **Fix propuesto**: al cerrar el lote, agrupar los `error_code` de las entregas fallidas del batch (mismo patrón que `resumenErrores` de la corrección global) y armar el toast con esos mensajes; condicionar el texto "se detuvo / sin procesar" a que efectivamente haya habido corte.
- **Esfuerzo estimado**: S

---

### [MEDIA] Carga masiva devuelve `str(e)` crudo por alumno, sin traceback en logs

- **ID**: ERR-013
- **Ubicación**: `backend/app/services/entrega_service.py:933-948` (+ `305-309`)
- **Severidad**: 🟡 Media
- **Dimensión**: Errores
- **Descripción**: en la carga masiva de entregas, el catch-all por alumno está bien pensado (un alumno roto no aborta el lote, y hasta hace rollback de la sesión — 👏), pero reporta `error=str(e)` directo al cliente: para errores de DB eso es jerga SQLAlchemy ("(psycopg2.errors...)…null bytes…") ilegible para un tutor. Y no hay `logger.exception`, así que el traceback que explicaría el fallo no queda en el servidor. Mismo patrón en `crear_entrega_desde_moodle` (línea 309).
- **Evidencia**: `errores.append(EntregaError(..., error=str(e)))` sin log previo.
- **Impacto**: el tutor ve errores crípticos por alumno en el resumen de importación; soporte no tiene traza para reproducir.
- **Fix propuesto**: `logger.exception` con contexto (alumno, archivo) + mensaje traducido al cliente ("No se pudo procesar la entrega de X: contenido inválido"), reservando `str(e)` para el log.
- **Esfuerzo estimado**: S

---

### [BAJA] Semántica HTTP propia (402/429/503) no documentada + naming "N8N" fantasma

- **ID**: ERR-014
- **Ubicación**: `backend/app/services/correccion_service.py:216-263` (+ `core/exceptions.py:52-64`, `correccion_service.py:725-730`)
- **Severidad**: 🟢 Baja
- **Dimensión**: Errores
- **Descripción**: el contrato documentado del proyecto es "400/404/403/502+retry/500". Pero el flujo IA usa además: **402** para key inválida Y para sin-créditos (semánticamente discutible — 402 es "Payment Required", una key inválida sería 401/400), **429** para rate limit y **503** para modelo sobrecargado. Es una convención interna coherente (el corte del lote y el frontend dependen de distinguirlas) pero no está documentada en CLAUDE.md ni en el catálogo, y un dev nuevo que respete el contrato oficial la rompería. Aparte, todo el naming sigue siendo "N8N" (`N8NError`, `N8NTimeoutError`, `ERROR_N8N`, "N8N retornó error") cuando N8N ya no existe en el sistema; ese texto puede llegarle al usuario: `_parse_gemini_response` (línea 727) arma `"N8N retornó error: ..."` que viaja en el detail del 502 (línea 280).
- **Evidencia**: líneas citadas; comparar con la tabla de error handling de `CLAUDE.md`.
- **Impacto**: deuda de coherencia; mensajes con tecnología fantasma confunden a usuarios y devs.
- **Fix propuesto**: documentar la tabla real de códigos del flujo IA en CLAUDE.md / catálogo; renombrar `N8N*` → `IAProvider*` (los códigos persistidos pueden mantener alias por retrocompat, como ya hace el catálogo con los `GEMINI_*`).
- **Esfuerzo estimado**: M

---

### [BAJA] Logs imprecisos: todo 402 = "key inválida"; auth opcional traga errores de DB

- **ID**: ERR-015
- **Ubicación**: `backend/app/services/correccion_service.py:838-846` + `backend/app/core/dependencies.py:209-210`
- **Severidad**: 🟢 Baja
- **Dimensión**: Errores
- **Descripción**: (a) en `procesar_lote_background`, cualquier 402 corta el lote con el log "[BG] API Key inválida. Deteniendo lote." — pero 402 también es `SIN_CREDITOS` (OpenRouter): el log miente sobre la causa y confunde el diagnóstico de corridas masivas. (b) `get_current_user_optional` hace `except (JWTError, Exception): return None` — un error de DB durante la resolución del usuario se degrada silenciosamente a "anónimo", sin log; además `(JWTError, Exception)` es redundante (Exception ya incluye a JWTError).
- **Evidencia**: líneas citadas.
- **Impacto**: bajo — afecta diagnóstico por logs, no al usuario final directo.
- **Fix propuesto**: (a) loguear el `error_code` real del detail en el corte del lote; (b) capturar `JWTError → None` y loguear el resto antes de devolver None.
- **Esfuerzo estimado**: S
