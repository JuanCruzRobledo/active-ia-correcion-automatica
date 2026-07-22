## 1. Backend — Modelo y migración (schema_version)

- [x] 1.1 Agregar columna `schema_version: Mapped[int]` (`Integer`, `nullable=False`, `default=1`, `server_default=text("1")`) a `app/models/rubrica.py`.
- [x] 1.2 Generar la migración Alembic vía docker compose local (`docker-compose -f docker-compose.local.yml`) que agrega `schema_version int NOT NULL server_default '1'` a `rubricas`; verificar el `downgrade` que la elimina.
- [x] 1.3 Aplicar `alembic upgrade head` en el entorno dockerizado local y verificar que las rúbricas existentes quedan en `schema_version = 1`.
- [x] CHECKPOINT: confirmar migración aplicada y filas existentes en v1 antes de seguir.

## 2. Backend — Schemas de rúbrica (peso + validación condicional)

- [x] 2.1 (RED) Test: `Subcriterio` acepta dict sin `peso` (v1) y con `peso` válido (v2); `peso` inválido (0, >100) falla.
- [x] 2.2 Agregar `peso: int | None = Field(default=None, ge=1, le=100, ...)` a `Subcriterio` en `app/schemas/rubrica.py` (opcional a nivel modelo).
- [x] 2.3 (RED) Test: helper de validación v2 — rúbrica v2 con `sum(sub.peso) == criterio.peso` pasa; con descuadre falla; con subcriterio sin peso falla; rúbrica v1 sin peso pasa.
- [x] 2.4 Implementar helper `_validar_pesos_subcriterios_v2(criterios)` (réplica de `validar_suma_pesos` un nivel abajo) e invocarlo SOLO cuando `schema_version >= 2` desde `RubricaCreate.validar_estructura_completa` y `RubricaUpdate.validar_estructura_si_presente`.
- [x] 2.5 Agregar `schema_version` a `RubricaCreate` (`int = Field(default=1, ge=1)`), `RubricaUpdate` (`int | None`), `RubricaResponse` y `RubricaListItem` (`int`).
- [x] 2.6 (TRIANGULATE) Tests de caracterización v1: rúbrica v1 valida igual que antes (peso ausente en subcriterios no rompe); confirmar que el camino v1 no cambió.
- [x] 2.7 Verificar que el repositorio/servicio de rúbrica persiste y devuelve `schema_version` en create, update, detail y list.
- [x] CHECKPOINT: validación condicional por versión funcionando; v1 intacto.

## 3. Backend — Schemas de corrección (subcriterios_evaluados)

- [x] 3.1 (RED) Test: `SubcriterioEvaluado` parsea con enteros redondeados (patrón `RoundedInt`) y con floats de Gemini.
- [x] 3.2 Definir `SubcriterioEvaluado` (`id`, `puntaje_obtenido`, `puntaje_maximo`, `estado`, `feedback`) en `app/schemas/correccion.py` con la dualidad `RoundedInt` (parseo IA) / `Decimal` (respuesta API) coherente con el nivel criterio.
- [x] 3.3 Agregar `subcriterios_evaluados: list[...] | None = None` a `CriterioGeminiSchema`, `CriterioEvaluado`, y propagarlo en `CorreccionResponse.model_validate` y `CorreccionUpdate`/`CorreccionCreate`.
- [x] 3.4 (RED) Test: `GeminiResponse` con `subcriterios_evaluados` presente y ausente parsea sin error y `validate_nota_sum` sigue anclando la nota a la suma de criterios (sin cambio).
- [x] 3.5 (TRIANGULATE) Test: respuesta sin el campo (v1) sigue parseando idéntico a hoy.
- [x] CHECKPOINT: schemas de corrección aceptan y omiten el desglose sin regresión.

## 4. Backend — Prompt-builder y response schema (branch v1/v2, multi-proveedor)

- [x] 4.1 (RED) Test de caracterización de `_build_criterios_texto`/`_build_criterios_pdf_texto` en v1 (salida byte-a-byte actual) para blindar el camino v1.
- [x] 4.2 (RED) Test: builders con `schema_version=2` imprimen cada subcriterio como `[C2.1] (N pts) ...` + evidencias, e instrucciones de scoring por subcriterio.
- [x] 4.3 Agregar parámetro `schema_version` (default 1) a `_build_criterios_texto` y `_build_criterios_pdf_texto` con branch; v1 no toca ninguna línea del path actual.
- [x] 4.4 Definir response schemas v2 (`_SCHEMA_CORRECCION_CODIGO_V2`, `_SCHEMA_CORRECCION_PDF_V2`) con el nivel anidado `subcriterios_evaluados`; seleccionar por versión en `corregir_codigo`/`corregir_pdf`.
- [x] 4.5 Inyectar `"schema_version": rubrica.schema_version` en el dict de rúbrica de `correccion_service._build_correction_payload` y `_build_pdf_correction_payload`.
- [x] 4.6 Propagar el branch v1/v2 y el response_format v2 al proveedor OpenRouter (`openrouter_client.corregir`), que reusa los builders compartidos.
- [x] 4.7 (TRIANGULATE) Tests por proveedor: Gemini y OpenRouter en v1 (sin cambios) y v2 (con desglose).
- [x] CHECKPOINT: ambos proveedores ramifican por versión; v1 verificado sin regresión.

## 5. Backend — Persistencia del desglose

- [x] 5.1 (RED) Test: `correccion_service` persiste `subcriterios_evaluados` dentro de cada criterio en `criterios_json` (JSONB) para una corrección v2.
- [x] 5.2 Implementar la serialización de `subcriterios_evaluados` en el armado de `criterios_json` (creación y update de corrección), sin migración de tabla.
- [x] 5.3 (TRIANGULATE) Test: corrección v1/vieja sin el campo persiste y se lee igual que hoy; la nota sigue siendo suma de criterios.
- [x] CHECKPOINT: desglose persistido en JSONB; nota sin cambios.

## 6. Frontend — Tipos y Zod (peso de subcriterio + schema_version)

- [x] 6.1 Agregar `peso` a la interfaz `Subcriterio` y `schema_version` a `Rubrica`/`RubricaListItem`/`RubricaCreate`/`RubricaUpdate` en `features/rubricas/types/index.ts` (sin `any`).
- [x] 6.2 (RED) Test Zod: `criterioSchema` con `.superRefine` que exige `sum(subcriterio.peso) == criterio.peso`; casos válido/ inválido; verificar que propaga a `criteriosStructureSchema` y a `rubricaFormSchema`.
- [x] 6.3 Agregar `peso` a `subcriterioSchema` y la `.superRefine` de suma en `criterioSchema` (condicionada a v2) en `features/rubricas/schemas/rubrica-schema.ts`.
- [x] CHECKPOINT: tipos y validación Zod alineados con backend.

## 7. Frontend — Editor de rúbricas (input, validación en vivo, badge, migrar)

- [x] 7.1 Agregar input de peso por subcriterio en `RubricaManualMode` (patrón del peso de criterio) y actualizar los defaults de subcriterio nuevo (RubricaManualMode + los tres de RubricaEditor) con `peso`.
- [x] 7.2 Mostrar suma en vivo por criterio (réplica del "Total: X%" de criterios, comparando contra `criterio.peso`) con color de estado.
- [x] 7.3 Setear `schema_version: 2` en el submit de `RubricaEditor` cuando la rúbrica se guarda con pesos por subcriterio.
- [x] 7.4 Badge "Rúbrica desactualizada" en la fila de `RubricasPage` y en el header del editor cuando `schema_version < 2`.
- [x] 7.5 Botón "Migrar al nuevo modelo": pre-cargar pesos iguales con método del resto mayor (`base = floor(peso/n)`, primeros `resto` reciben +1) vía `setValue('criterios', migrated)`, editable, sin guardar hasta confirmar.
- [x] 7.6 Manejar loading y error states; componentes < 200 LOC. (Nota: RubricaEditor/RubricaManualMode/RubricasPage ya excedían 200 LOC antes de este cambio; no se refactorizó su tamaño para no ampliar el alcance — ver desvíos en el reporte de apply.)
- [x] CHECKPOINT: edición y migración v1→v2 funcionando end-to-end en el editor.

## 8. Frontend — Display de correcciones (desglose tolerante)

- [x] 8.1 Agregar `subcriterios_evaluados?` a `CriterioEvaluado` y `CorreccionUpdate` en `features/correcciones/types/index.ts`. (`CorreccionUpdate.criterios` ya tipa con `CriterioEvaluado[]`, así que hereda el campo automáticamente — no requirió tocar la interfaz por separado.)
- [x] 8.2 Renderizar el desglose por subcriterio en `CriterioCard` (CorreccionViewEditModal) solo si `criterio.subcriterios_evaluados?.length`, tolerando ausencia (correcciones viejas/v1). (`CorreccionDetailModal` es un componente huérfano sin imports activos — no se tocó, fuera de alcance.)
- [x] 8.3 Verificar que las ediciones manuales preservan `subcriterios_evaluados` en el payload de `CorreccionUpdate`. (El estado `criterios` en `CorreccionViewEditModal` spreadea `...c` antes de sobreescribir puntajes, preservando el campo sin cambios de código.)
- [x] CHECKPOINT: correcciones viejas se muestran sin romper; nuevas muestran desglose.

## 9. Docs y cierre

- [x] 9.1 Actualizar `docs/specs/Rubrica.md` con el nuevo schema (peso por subcriterio, `schema_version`, semántica de suma).
- [x] 9.2 Frontend: `npm run lint` (73 problemas — todos pre-existentes al branch, verificado por línea contra `git show HEAD:...`; ninguno introducido por fases 6-9) y `npx tsc -b` (0 errores, ejecutado como equivalente — el repo no tiene script `npm run typecheck` pese a mencionarlo CLAUDE.md). `pytest` backend NO se re-corrió acá: el usuario confirmó 926 tests passing antes de delegar el frontend, y el mandato explícito de esta tarea fue "NO toques backend".
- [ ] 9.3 Verificación end-to-end: crear rúbrica v2, corregir una entrega (Gemini y OpenRouter) y ver el desglose; corregir una rúbrica v1 y confirmar comportamiento idéntico al previo. PENDIENTE: requiere entorno dockerizado local con DB + credenciales de IA reales, fuera del alcance de este apply frontend-only. Recomendado como siguiente paso antes de archivar el change (posiblemente vía `openspec-verify` o manual).
