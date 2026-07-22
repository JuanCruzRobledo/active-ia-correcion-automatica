## Why

`RubricaIAService.generar_rubrica_desde_pdf` llama a `GeminiCorrectionClient.generar_rubrica`, pero solo captura `N8NTimeoutError` y `N8NError` (`rubrica_ia_service.py:97-106`). El cliente puede lanzar cuatro excepciones de la jerarquía `GeminiError` (`APIKeyInvalidError`, `QuotaExceededError`, `ModelOverloadedError`, `InsufficientCreditsError`), que heredan de `ActiveIAException` — **no** de `N8NError` — por lo que hoy se propagan sin manejar y terminan en un HTTP 500 crudo, sin el mensaje accionable del catálogo. Es el hallazgo ERR-001 de la auditoría (severidad crítica). La ruta de corrección de código (`correccion_service.py`) ya maneja estas excepciones correctamente; la generación de rúbrica quedó atrás.

## What Changes

- Capturar la jerarquía `GeminiError` en `generar_rubrica_desde_pdf` y mapear cada subclase a su HTTP status + mensaje del catálogo de errores (`app/core/error_catalog.py`), replicando el estilo ya usado en `correccion_service.py`:
  - `APIKeyInvalidError` → 402 con `ERROR_API_KEY_INVALID`
  - `InsufficientCreditsError` → 402 con `ERROR_SIN_CREDITOS`
  - `QuotaExceededError` → 429 con `ERROR_RATE_LIMIT`
  - `ModelOverloadedError` → 503 con `ERROR_OVERLOADED`
  - `N8NError` (fallback genérico) → se mantiene el 502 actual
- Marcar la API key de Gemini del usuario como inválida en la DB cuando se produce `APIKeyInvalidError` (mismo comportamiento que `correccion_service.py`).
- Agregar tests unitarios que fuercen `APIKeyInvalidError` y `QuotaExceededError` desde el cliente mockeado y verifiquen que el servicio devuelve un HTTP útil (no un 500 crudo).

## Capabilities

### New Capabilities
- `manejo-errores-generacion-rubrica-ia`: manejo de las excepciones del proveedor de IA (jerarquía `GeminiError`) en el flujo de generación de rúbrica desde PDF, traduciéndolas a respuestas HTTP con mensajes accionables del catálogo, y marcado de la API key como inválida cuando corresponde.

### Modified Capabilities
<!-- Sin specs previas para el flujo de generación de rúbrica IA; no hay requerimientos existentes que cambien. -->

## Impact

- **Código afectado**:
  - `backend/app/services/rubrica_ia_service.py` — imports + bloque try/except (líneas ~16, 95-106). Posible cambio de firma para recibir contexto de usuario/DB (decisión en design.md).
  - `backend/app/routers/rubricas.py` — endpoint `generar_rubrica_desde_pdf` (línea ~427), si el marcado de key inválida se resuelve threadeando el usuario/DB a través del router.
- **Tests**: nuevo archivo en `backend/tests/unit/services/`.
- **Sin cambios de esquema de DB ni migraciones.**
- **Gobernanza: MEDIA** — manejo de errores en un service de negocio (no toca auth/billing/security core). Implementar con checkpoints y surgir decisiones no obvias. Esfuerzo estimado: **S**.
