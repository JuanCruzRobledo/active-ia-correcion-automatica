## 1. Preparación / Checkpoint

- [ ] 1.1 Correr el suite existente de `backend/tests/unit/services/` (safety net) y capturar baseline "N tests passing" antes de tocar nada; si hay fallas previas, reportarlas como pre-existentes (no arreglarlas).
- [ ] 1.2 CHECKPOINT (gobernanza MEDIA): confirmar con el usuario la Opción A del design (threadear `Usuario`/sesión al service para marcar la key inválida) vs. Opción B (marcar en el router). No cambiar la firma pública del service sin confirmación.
- [ ] 1.3 Grep de todos los llamadores de `generar_rubrica_desde_pdf` para dimensionar el impacto de un eventual cambio de firma (esperado: solo `backend/app/routers/rubricas.py`).

## 2. Tests (RED — escribir primero)

- [ ] 2.1 Crear `backend/tests/unit/services/test_rubrica_ia_service_errores.py` siguiendo el estilo de `test_rubrica_service.py` / `test_rubrica_obtener_response.py`, con el `GeminiCorrectionClient` mockeado (patch de `generar_rubrica`).
- [ ] 2.2 RED: test que fuerza `APIKeyInvalidError` desde el cliente mockeado y verifica que el service levanta `HTTPException` con status 402 y `detail` con `error_code == "GEMINI_API_KEY_INVALID"` y el mensaje del catálogo (NO un 500 crudo).
- [ ] 2.3 RED: test que fuerza `QuotaExceededError` y verifica `HTTPException` 429 con `error_code == "GEMINI_RATE_LIMIT"`.
- [ ] 2.4 TRIANGULATE: agregar tests para `ModelOverloadedError` (503 / `GEMINI_OVERLOADED`) e `InsufficientCreditsError` (402 / `SIN_CREDITOS`).
- [ ] 2.5 TRIANGULATE (no-regresión): test que confirma que `N8NTimeoutError` y `N8NError` siguen mapeando a 502 como hoy.
- [ ] 2.6 Si se elige Opción A: test que verifica que ante `APIKeyInvalidError` se marca `gemini_api_key_valid = False` (mockeando usuario/repositorio, sin depender de tabla DB real).

## 3. Implementación (GREEN)

- [ ] 3.1 En `rubrica_ia_service.py`: importar desde `app.core.exceptions` las 4 subclases (`APIKeyInvalidError`, `QuotaExceededError`, `ModelOverloadedError`, `InsufficientCreditsError`) y desde `app.core.error_catalog` las constantes `ERROR_*` + `mensaje_error`.
- [ ] 3.2 Agregar los `except` por subclase en el bloque de la línea ~95-106, ANTES del `except N8NError` genérico, mapeando cada uno a su `HTTPException` con `detail = {"error_code", "message": mensaje_error(...)}` (402/402/429/503) replicando el estilo de `correccion_service.py`.
- [ ] 3.3 Si Opción A: extender la firma de `generar_rubrica_desde_pdf` para recibir el contexto de usuario/sesión y marcar `gemini_api_key_valid = False` dentro del `except APIKeyInvalidError`; ajustar el llamador en `rubricas.py` (~línea 484).
- [ ] 3.4 Ejecutar los tests → todos en verde. Confirmar que ya NO hay 500 crudo para las 4 excepciones.

## 4. Refactor y verificación

- [ ] 4.1 REFACTOR: revisar duplicación entre los nuevos `except` y considerar un helper compartido con `correccion_service.py` solo si queda limpio (sin cambiar comportamiento); re-correr tests tras cada cambio.
- [ ] 4.2 Correr `pytest` completo del backend + verificar que el baseline de 1.1 no empeoró.
- [ ] 4.3 Verificar que `<= 500 LOC` en `rubrica_ia_service.py` y que no se metió lógica de negocio en el router (regla del proyecto).
