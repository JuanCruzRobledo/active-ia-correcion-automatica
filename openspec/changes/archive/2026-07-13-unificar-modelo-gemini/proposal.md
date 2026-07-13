## Why

Hoy conviven **tres nombres de modelo Gemini** distintos en el backend, y la validación de la API key del tutor usa uno **hardcodeado** (`gemini-2.5-flash`) que ignora por completo el modelo real configurado (`settings.GEMINI_MODEL = "gemini-3.5-flash"`). Consecuencia: una key puede "validar OK" en el perfil del tutor (contra 2.5-flash) y luego fallar **toda** corrección real (contra 3.5-flash) si ese modelo no existe/no es accesible en la cuenta o tier de la API — un error silencioso, imposible de diagnosticar para el usuario. Es el hallazgo de auditoría BUG-001 (crítico) / IA-006 (alto).

Gobernanza: **MEDIA** (bug de integración con IA — implementar con checkpoints, surgir decisiones no obvias). Esfuerzo: **S**.

## What Changes

- La validación de API key en `gemini_studio_client.py` deja de pegar contra el literal hardcodeado `gemini-2.5-flash` y pasa a usar **`settings.GEMINI_MODEL`** — la misma fuente de verdad que usan las correcciones reales y la generación de rúbricas. La URL de validación se construye dinámicamente a partir del modelo configurado.
- Se elimina el fallback muerto `getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")` en `gemini_correction_client.py:320`, dejando `self.model = settings.GEMINI_MODEL` directo. (`GEMINI_MODEL` siempre existe como campo Pydantic; ese default nunca se dispara y es una segunda fuente de confusión.)
- Queda **una sola fuente de verdad** para el modelo Gemini: `settings.GEMINI_MODEL`. Validación de key y corrección real usan exactamente el mismo modelo.
- Se agrega verificación (test) de que la validación de key referencia `settings.GEMINI_MODEL` y ya no el literal viejo, para evitar regresión.

No hay cambios breaking: la interfaz pública de `validar_api_key()` y de `GeminiCorrectionClient` no cambia; solo cambia contra qué modelo se hace el health check y de dónde sale el nombre.

## Capabilities

### New Capabilities
- `gemini-model-config`: Fuente única del nombre de modelo Gemini (`settings.GEMINI_MODEL`) usada de forma consistente en la validación de API key y en la corrección real, de modo que si una key valida, el modelo también sea el que efectivamente se usa al corregir.

### Modified Capabilities
<!-- Sin capabilities de spec existentes que cambien sus requisitos: no hay spec previa que cubra la integración Gemini. -->

## Impact

- **Código afectado**:
  - `backend/app/integrations/gemini_studio_client.py` (líneas 10-14 y `validar_api_key`): construir la URL de validación desde `settings.GEMINI_MODEL`.
  - `backend/app/integrations/gemini_correction_client.py:320`: quitar el `getattr` con default muerto.
  - `backend/app/core/config.py:78` (`GEMINI_MODEL`): solo lectura — no se modifica el valor; se usa como fuente de verdad. **Nota de secuenciación**: mismo archivo que el change `harden-secret-keys-arranque` (líneas 53/62) — sin overlap de líneas, ver `design.md`.
- **Tests**: nuevo test en `backend/tests/unit/integrations/` que verifica que la validación usa `settings.GEMINI_MODEL` y no el literal `gemini-2.5-flash`.
- **Comportamiento de usuario**: la validación de key en el perfil del tutor pasa a reflejar el modelo real; se elimina el falso positivo donde una key validaba pero luego toda corrección fallaba.
- **Config/entorno**: `GEMINI_MODEL` es overrideable por env var — a partir de este change, ese override aplica también a la validación de key (antes quedaba desacoplada).
