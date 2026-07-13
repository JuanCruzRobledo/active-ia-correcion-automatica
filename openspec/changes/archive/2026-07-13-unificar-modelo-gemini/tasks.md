## 0. Precondición de secuenciación (leer antes de aplicar)

- [x] 0.1 Confirmar que el change `harden-secret-keys-arranque` está mergeado antes de empezar el apply (ambos tocan `backend/app/core/config.py`; ver `design.md` → Migration Plan). Si aún no está mergeado, esperar.

## 1. Safety net (baseline TDD)

- [x] 1.1 Correr los tests existentes de integraciones Gemini y capturar baseline verde: `cd backend && pytest tests/unit/integrations/ -q`. Si algo falla de antes, reportarlo como pre-existing failure y NO arreglarlo acá.

## 2. RED — Test de regresión de la validación de key

- [x] 2.1 Escribir en `backend/tests/unit/integrations/test_gemini_studio_client.py` (o nuevo `test_gemini_model_source.py` en el mismo dir) un test que verifique que la URL de validación se construye a partir de `settings.GEMINI_MODEL` y contiene ese valor. El test debe referenciar el helper/URL de validación que todavía no lee `settings` → debe FALLAR (RED).
- [x] 2.2 Segundo caso (triangulación): monkeypatch de `settings.GEMINI_MODEL` a un valor distinto (p. ej. `"gemini-x-test"`) y verificar que la URL de validación refleja ESE valor y no un literal fijo. Confirma que no hay hardcodeo.

## 3. GREEN — Unificar la fuente de verdad

- [x] 3.1 En `backend/app/integrations/gemini_studio_client.py`: reemplazar la constante `_VALIDATION_URL` con el modelo hardcodeado por un helper puro (p. ej. `construir_url_validacion(model: str) -> str`) que arme la URL a partir del modelo recibido (patrón de helpers puros ya usado en el archivo).
- [x] 3.2 En el mismo archivo, hacer que `validar_api_key` construya la URL usando `settings.GEMINI_MODEL` (importar `settings` desde `app.core.config`). Eliminar por completo el literal `gemini-2.5-flash`.
- [x] 3.3 Correr los tests de 2.1 y 2.2 → deben pasar (GREEN).

## 4. Limpiar fallback muerto en el cliente de corrección

- [x] 4.1 En `backend/app/integrations/gemini_correction_client.py:320`: cambiar `self.model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")` por `self.model = settings.GEMINI_MODEL` (sin default muerto).
- [x] 4.2 Verificar que no queda ningún otro literal `gemini-2.5-flash` en `backend/app/` (buscar con grep). Si aparece otro, evaluar caso por caso.

## 5. REFACTOR y verificación

- [x] 5.1 Revisar nombres/imports y consistencia de estilo con el resto del archivo; correr toda la suite de integraciones: `cd backend && pytest tests/unit/integrations/ -q` (debe seguir verde).
- [ ] 5.2 CHECKPOINT (gobernanza MEDIA): verificar contra la API real de Google que `settings.GEMINI_MODEL` (`gemini-3.5-flash` u otro) existe y es accesible con una key de prueba. Si devuelve 404/modelo inexistente, SURGIR al usuario la decisión sobre el valor correcto de `GEMINI_MODEL` — no cambiarlo en automático.
- [x] 5.3 Marcar el change listo para archivar una vez confirmado que validación de key y corrección real usan el mismo modelo.
