## Why

Hoy los subcriterios de una rúbrica no tienen peso propio: solo el `Criterio` tiene `peso` (porcentual, suma 100 entre criterios) y sus subcriterios son descripción + checklist de evidencias, sin puntaje asociado. Consecuencias verificadas contra el código:

1. Al armar el prompt para la IA, el criterio se pasa con su peso total y los subcriterios como mero checklist; la IA reparte el puntaje implícitamente (casi siempre asumiendo pesos iguales), cuando en la realidad los subcriterios no pesan lo mismo. El docente no tiene forma de expresar ese reparto.
2. El output de la corrección tampoco desglosa por subcriterio: `CriterioGeminiSchema`/`CriterioEvaluado` solo tienen score a nivel criterio. Los subcriterios son puramente decorativos, sin trazabilidad de por qué el criterio obtuvo esa nota.

Esto reduce la fidelidad de la corrección automática y la transparencia del feedback hacia el alumno.

## What Changes

- **Peso por subcriterio (rúbrica)**: `Subcriterio` gana un campo `peso` (puntos absolutos que suman al peso de su criterio, mismo patrón que "los criterios suman 100"). Nuevo validador: `sum(subcriterio.peso) == criterio.peso`.
- **Versionado de rúbricas (`schema_version`)**: nueva columna `schema_version int NOT NULL server_default '1'` en `rubricas`. Rúbricas existentes quedan en **v1** (corrigen EXACTAMENTE igual que hoy, reparto implícito, sin exigir peso en subcriterios). Rúbricas nuevas o editadas con pesos por subcriterio se guardan como **v2**. La validación y el prompt se ramifican por versión.
- **Validación condicional por versión** (Pydantic): el `peso` de subcriterio es obligatorio y su suma se valida SOLO en v2. v1 sigue aceptando subcriterios sin peso.
- **Desglose por subcriterio en la corrección (IA)**: la IA DEBE devolver puntaje por subcriterio en v2. Se extiende el prompt-builder, el JSON schema de `generationConfig`/`response_format`, el schema de respuesta (`subcriterios_evaluados`), la persistencia en `criterios_json` (JSONB, sin migración de tabla) y la visualización en el front de correcciones.
- **Multi-proveedor**: el cambio del prompt-builder y del response schema aplica a AMBOS caminos (Gemini y OpenRouter), que comparten los builders.
- **Frontend rúbricas**: input de peso por subcriterio + validación en vivo (suma == peso del criterio), badge/banner "Rúbrica desactualizada — actualizar al nuevo modelo" cuando `schema_version < 2`, y botón "migrar" que pre-carga pesos iguales entre subcriterios (`peso_criterio / n` con redondeo de resto mayor) como punto de partida editable. NO se bloquea la corrección de rúbricas v1.
- **Frontend correcciones**: mostrar el desglose por subcriterio cuando exista `subcriterios_evaluados`, tolerando su ausencia en correcciones viejas.
- `instrucciones_puntuacion` NO se deprecia: se mantiene como nota complementaria no vinculante.
- **BREAKING**: ninguno para datos existentes. Compatibilidad hacia atrás total (v1 intacto).

## Capabilities

### New Capabilities

- `rubrica-peso-subcriterio`: peso por subcriterio en la rúbrica, versionado `schema_version`, validación condicional por versión, pre-carga de pesos iguales con redondeo exacto, y UI de edición + badge/migración en el frontend de rúbricas.
- `correccion-desglose-subcriterio`: desglose de puntaje por subcriterio en la corrección con IA — ramificación v1/v2 del prompt-builder y del response schema (Gemini y OpenRouter), persistencia en `criterios_json`, y visualización tolerante a ausencia en el frontend de correcciones.

### Modified Capabilities

<!-- No hay specs previas de rúbrica ni corrección en openspec/specs/. Ambas capabilities son nuevas. -->

## Impact

**Backend**
- `app/schemas/rubrica.py` — `Subcriterio.peso` (opcional a nivel modelo; exigido en v2), validación condicional en `RubricaCreate`/`RubricaUpdate`, `schema_version` en create/update/response.
- `app/models/rubrica.py` — columna `schema_version`.
- `alembic/versions/` — migración `schema_version int NOT NULL server_default '1'` (vía docker compose local).
- `app/schemas/correccion.py` — `subcriterios_evaluados` opcional en `CriterioGeminiSchema`/`CriterioEvaluado`/`CorreccionResponse`/`CorreccionUpdate`.
- `app/integrations/gemini_correction_client.py` — builders `_build_criterios_texto`/`_build_criterios_pdf_texto` con branch por `schema_version`; response schemas v2.
- `app/integrations/openrouter_client.py` — reusa los builders; response_format v2.
- `app/services/correccion_service.py` — inyectar `schema_version` en el payload de rúbrica (`_build_correction_payload`, `_build_pdf_correction_payload`) y persistir `subcriterios_evaluados` en `criterios_json`.

**Frontend**
- `features/rubricas/`: `schemas/rubrica-schema.ts`, `types/index.ts`, `components/RubricaManualMode.tsx`, `components/RubricaEditor.tsx`, `services/rubricas-service.ts` (pass-through), `hooks/useRubricas.ts`, `pages/RubricasPage.tsx` (badge en tabla).
- `features/correcciones/`: `types/index.ts`, `components/CorreccionViewEditModal.tsx` (`CriterioCard`).

**Docs**
- `docs/specs/Rubrica.md` — actualizar a la nueva versión del schema.
