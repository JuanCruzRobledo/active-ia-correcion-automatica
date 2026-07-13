## Context

El backend usa Google Gemini para dos cosas: (a) **validar** la API key que el tutor carga en su perfil (health check contra Google AI Studio) y (b) **corregir** entregas y **generar rúbricas** (llamadas reales al modelo). Hoy el nombre del modelo aparece en tres lugares con dos valores distintos:

- `backend/app/core/config.py:78` → `GEMINI_MODEL: str = "gemini-3.5-flash"` — fuente de verdad real; la usan corrección y generación de rúbricas.
- `backend/app/integrations/gemini_studio_client.py:11-14` → literal **hardcodeado** `gemini-2.5-flash` en `_VALIDATION_URL`; la validación de key ignora `settings.GEMINI_MODEL`.
- `backend/app/integrations/gemini_correction_client.py:320` → `getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")`; el default `gemini-2.5-flash` es **código muerto** (el campo Pydantic siempre existe) pero suma confusión.

El desacople entre (a) y (b) produce el bug: la key valida contra `2.5-flash`, pero corrige contra `3.5-flash`. Si `3.5-flash` no existe/no es accesible en el tier de la cuenta, el tutor ve "key válida" y luego **todas** sus correcciones fallan sin causa visible.

Gobernanza del dominio: **MEDIA** (integración con IA). Esfuerzo: **S**. Se implementa con checkpoints; cualquier decisión no obvia (p. ej. si `gemini-3.5-flash` no existiera realmente en la API) se surge al usuario antes de continuar.

## Goals / Non-Goals

**Goals:**
- Una sola fuente de verdad para el nombre de modelo Gemini: `settings.GEMINI_MODEL`.
- La validación de API key usa el mismo modelo que la corrección real: si valida, ese modelo es el que se usará.
- Eliminar el fallback muerto de `gemini_correction_client.py:320`.
- Test de regresión que garantice que la validación referencia `settings.GEMINI_MODEL` y no el literal viejo.

**Non-Goals:**
- No se cambia el **valor** de `GEMINI_MODEL` (queda `gemini-3.5-flash` salvo que la verificación contra la API real demuestre que no existe — en ese caso es decisión del usuario, fuera del scope de este change).
- No se toca la lógica de OpenRouter (`OPENROUTER_MODEL`) ni el proveedor alternativo.
- No se modifica la interfaz pública de `validar_api_key()` ni de `GeminiCorrectionClient`.
- No se refactoriza el manejo de errores/reintentos de las llamadas Gemini.

## Decisions

**D1 — Construir `_VALIDATION_URL` desde `settings.GEMINI_MODEL` en runtime, no como constante de módulo.**
Hoy `_VALIDATION_URL` es una constante evaluada al importar el módulo con el modelo hardcodeado. Se pasa a construir la URL dentro de `validar_api_key` (o vía un helper `_build_validation_url(model)`) leyendo `settings.GEMINI_MODEL`.
- *Por qué*: es la única forma de que la validación siga al modelo real y al override por env var.
- *Alternativa descartada*: mantener la constante pero interpolar `settings.GEMINI_MODEL` a nivel módulo → se congelaría el valor al importar y complicaría el testeo (no permite monkeypatch de `settings`).

**D2 — Extraer un helper puro `construir_url_validacion(model: str) -> str` (o equivalente) testeable sin red.**
El patrón del archivo ya separa helpers puros (`construir_payload_validacion`, `api_key_valida_segun_status`) del wrapper async con I/O. Se sigue ese patrón: un helper puro que arma la URL a partir del modelo, y `validar_api_key` que le pasa `settings.GEMINI_MODEL`.
- *Por qué*: permite el test de regresión sin tocar la red ni mockear httpx; se asegura consistencia de estilo con el archivo existente.

**D3 — `gemini_correction_client.py:320` pasa a `self.model = settings.GEMINI_MODEL` directo (sin `getattr` con default).**
- *Por qué*: `GEMINI_MODEL` es un campo declarado del `Settings` Pydantic, siempre presente; el default `"gemini-2.5-flash"` nunca se dispara y es una fuente de confusión. Mismo tratamiento se aplica a `GEMINI_TIMEOUT_SECONDS` solo si es trivial y no amplía el scope; si genera dudas, se deja como está (no es parte del bug).

**D4 — Verificar contra la API real que el modelo configurado existe y es accesible.**
Como checkpoint de la fase apply (gobernanza MEDIA), se hace una verificación manual/puntual: `GET`/`generateContent` contra `settings.GEMINI_MODEL` con una key real de prueba. Si el modelo no existe (404) se surge al usuario como decisión (¿corregir el valor de `GEMINI_MODEL`?) — NO se decide en automático.

## Risks / Trade-offs

- **[El modelo real (`gemini-3.5-flash`) podría no existir en la API de Google]** → Este change no lo asume resuelto: la verificación D4 lo detecta y lo eleva al usuario. Unificar la fuente de verdad **hace visible** el problema en la validación de key (deja de ser un falso positivo), que es exactamente el objetivo.
- **[Cambiar la constante de módulo a construcción en runtime]** → mínima sobrecarga por request de validación (armar un string); despreciable frente a la llamada de red.
- **[Test acoplado al nombre del literal viejo]** → el test se escribe verificando que la URL contiene `settings.GEMINI_MODEL`, no que *no* contiene un string concreto, para que no se rompa si el valor de `GEMINI_MODEL` cambia legítimamente en el futuro.

## Migration Plan

- Cambio backend-only, sin migración de datos ni de esquema. Deploy = redeploy normal del backend.
- Rollback: revertir el commit; no hay estado persistente afectado.

### Secuenciación con `harden-secret-keys-arranque` (IMPORTANTE)

Este change toca `backend/app/core/config.py` (lectura de `GEMINI_MODEL`, línea 78). El change **`harden-secret-keys-arranque`** toca el MISMO archivo `config.py` en las líneas 53 y 62 (`SECRET_KEY` / `ENCRYPTION_KEY`). **No hay overlap de líneas**, pero para evitar reabrir conflictos de merge en `config.py`:

> La fase de **APPLY** de este change (`unificar-modelo-gemini`) debe ejecutarse **DESPUÉS** de que `harden-secret-keys-arranque` esté mergeado.

Esta dependencia aplica **solo a la fase de apply**. La fase de **propose** (creación de estos artefactos) no tiene ninguna dependencia y puede completarse ahora sin problema. En la práctica este change casi no modifica `config.py` (solo lo lee), así que el riesgo real es bajo; la nota es una precaución de secuenciación.

## Open Questions

- ¿`gemini-3.5-flash` existe y es accesible en la cuenta/tier de Google AI Studio que usan los tutores? → A confirmar en apply (D4). Si no, decisión del usuario sobre el valor correcto de `GEMINI_MODEL`.
