## Context

`RubricaIAService.generar_rubrica_desde_pdf` (`backend/app/services/rubrica_ia_service.py`) genera una rúbrica a partir de un PDF llamando a `GeminiCorrectionClient.generar_rubrica`. El cliente detecta errores del proveedor en `_detect_gemini_error` / `_handle_non_200` (`gemini_correction_client.py:140-217`) y lanza cuatro subclases de `GeminiError`: `APIKeyInvalidError`, `QuotaExceededError`, `ModelOverloadedError`, `InsufficientCreditsError`. `GeminiError` hereda de `ActiveIAException`, **no** de `N8NError` (`app/core/exceptions.py:70-97`).

El bloque try/except del servicio (líneas 95-106) solo captura `N8NTimeoutError` y `N8NError`, así que ninguna de las cuatro subclases de `GeminiError` se captura hoy: se propagan y terminan en un HTTP 500 crudo, sin el mensaje accionable del catálogo (`app/core/error_catalog.py`).

El patrón correcto ya existe en `correccion_service.py:195-259`: captura cada subclase, marca la entrega con su `error_code`, marca la API key inválida en DB cuando aplica (`APIKeyInvalidError`), y lanza `HTTPException` con `{error_code, message}` usando `mensaje_error(...)`.

Restricción clave de contexto: `generar_rubrica_desde_pdf` recibe hoy solo `api_key_encrypted` (string), **no** el objeto `Usuario` ni la `AsyncSession`. El router `generar_rubrica_desde_pdf` (`rubricas.py:427`) sí tiene `current_user` y `db`.

**Gobernanza: MEDIA.** Implementar con checkpoints; surgir las decisiones no obvias (especialmente el marcado de la key inválida). Esfuerzo: **S**.

## Goals / Non-Goals

**Goals:**
- Capturar las 4 subclases de `GeminiError` en el flujo de generación de rúbrica y mapearlas a HTTP status + mensaje del catálogo, replicando el estilo de `correccion_service.py`.
- Marcar `gemini_api_key_valid = False` en la DB cuando se produce `APIKeyInvalidError`.
- No introducir regresión en el manejo actual de `N8NTimeoutError` / `N8NError` / `ValidationError`.
- Cubrir con tests unitarios (pytest) que fuercen al menos `APIKeyInvalidError` y `QuotaExceededError` y verifiquen un HTTP útil (no 500 crudo).

**Non-Goals:**
- No se cambia el flujo de corrección de código (`correccion_service.py`), que ya está correcto.
- No se toca la jerarquía de excepciones ni el catálogo de errores.
- No hay cambios de esquema de DB ni migraciones.
- No se refactoriza la lógica de parseo/validación de la rúbrica.

## Decisions

### Decisión 1: Catch explícito por subclase vs. catch-all `GeminiError`

Se capturan las subclases de forma **explícita** (`APIKeyInvalidError`, `InsufficientCreditsError`, `QuotaExceededError`, `ModelOverloadedError`) porque cada una mapea a un HTTP status y `error_code` distinto (402 / 402 / 429 / 503). Esto replica exactamente el estilo de `correccion_service.py`, mantiene la consistencia entre ambos flujos y produce mensajes accionables por caso. Se mantiene `N8NError` como fallback genérico (502) al final, tal como está hoy.

Alternativa considerada: un único `except GeminiError as e` catch-all mapeado a 502. Se descarta porque perdería la distinción de status codes (429/503/402) que el frontend usa para diferenciar rate-limit / overload / key inválida, y porque no permitiría marcar la key inválida solo en el caso correcto.

Orden de los `except`: las subclases específicas van ANTES que `N8NError`. (No hay relación de herencia entre `GeminiError` y `N8NError`, así que el orden entre esas ramas no es crítico por resolución de tipos, pero se ordena de específico a genérico por legibilidad y paridad con `correccion_service.py`.)

### Decisión 2 (checkpoint — decisión no obvia): cómo marcar la API key inválida en DB

El servicio no recibe hoy `Usuario` ni `AsyncSession`, así que no puede marcar la key por sí mismo sin un cambio de contrato. Dos opciones:

- **Opción A (recomendada): threadear contexto al servicio.** Extender la firma de `generar_rubrica_desde_pdf` para recibir el `Usuario` (o `usuario_id` + un `UsuarioRepository`) y la sesión, y marcar `gemini_api_key_valid = False` dentro del `except APIKeyInvalidError`, igual que `correccion_service.py`. Ventaja: la lógica de negocio (marcar key inválida) queda en el service, coherente con Clean Architecture y con el flujo de corrección. Costo: cambio de firma + ajuste del router.

- **Opción B: marcar en el router.** El service relanza `APIKeyInvalidError` (o una `HTTPException 402` con `error_code`), y el router —que ya tiene `current_user` y `db`— hace el marcado. Ventaja: firma del service intacta. Costo: parte la lógica de negocio entre router y service, y el router de rúbricas pasaría a tener lógica de negocio (viola la regla del proyecto "nunca lógica de negocio en Routers").

**Recomendación:** Opción A, por coherencia arquitectónica con `correccion_service.py` y con las reglas del proyecto. **Confirmar con el usuario en el checkpoint de apply** antes de cambiar la firma pública del service, ya que impacta al router y a cualquier otro llamador.

### Decisión 3: fuente de los mensajes

Reusar `app/core/error_catalog.py` (`mensaje_error`, constantes `ERROR_*`) — misma fuente de verdad que `correccion_service.py`. No se crean mensajes nuevos. Provider fijo `"gemini"` (este flujo es Gemini-only, no multi-proveedor como corrección).

### Decisión 4: forma del cuerpo de la HTTPException

Para las subclases de `GeminiError` se usa `detail = {"error_code": <CODE>, "message": mensaje_error(<CODE>)}`, igual que `correccion_service.py`, para que el frontend pueda diferenciar por `error_code`. Se mantiene el `detail` string plano actual para `N8NTimeoutError` / `N8NError` / `ValidationError` (sin regresión).

## Risks / Trade-offs

- **[Cambio de firma del service rompe llamadores]** → El único llamador es el router `rubricas.py:484`. Mitigación: ajustar el router en el mismo change; buscar otros usos de `generar_rubrica_desde_pdf` antes de editar (grep).
- **[Inconsistencia de contrato con el frontend]** → El frontend podría esperar el `detail` string plano en 502 pero un objeto en 402/429/503. Mitigación: replicar exactamente la forma que ya emite `correccion_service.py`, que el frontend ya sabe consumir.
- **[Tests con JSONB/DB en SQLite]** → Marcar la key en DB puede requerir tocar la sesión; el harness es SQLite in-memory y algunos modelos con JSONB no crean tabla. Mitigación: los tests del service mockean el `GeminiCorrectionClient` y, para el marcado de key, mockean el repositorio/usuario en vez de depender de una tabla real (estilo de los tests existentes que no son DB-backed).

## Migration Plan

Sin migración de datos ni de esquema. Despliegue directo del código. Rollback: revertir el commit; no hay estado persistente nuevo.

## Open Questions

- ¿Se confirma la Opción A (threadear `Usuario`/sesión al service) para marcar la key inválida? Es el único punto que cambia la firma pública. A resolver en el checkpoint de apply.
