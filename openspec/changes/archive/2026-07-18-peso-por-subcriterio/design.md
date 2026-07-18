## Context

Active-IA corrige TPs con IA (Gemini directo y OpenRouter) contra rúbricas jerárquicas guardadas en JSONB. Estado actual verificado en el código:

- `Subcriterio` (`app/schemas/rubrica.py`, L28-66) tiene `id`, `descripcion`, `evidencias[]`. **No tiene peso.**
- `Criterio` (L69-123) tiene `peso: int (1-100)`, `instrucciones_puntuacion` opcional, `subcriterios[]`, y `validar_subcriterio_ids_unicos`.
- `CriteriosStructure.validar_suma_pesos` (L240-248) valida `sum(criterio.peso) == 100`. **Este es el patrón exacto a replicar un nivel abajo.**
- La validación de la estructura se dispara en `RubricaCreate.validar_estructura_completa` (L359-376) y `RubricaUpdate.validar_estructura_si_presente` (L426-444), que construyen `CriteriosStructure(...)` a partir de los `*_json`.
- Los builders de prompt `_build_criterios_texto` (gemini_correction_client L45-67) y `_build_criterios_pdf_texto` (L70-89) listan los subcriterios como checklist de evidencias, sin puntos. Los **comparten ambos proveedores**: `openrouter_client.corregir()` importa `_build_criterios_texto` (L100/110); el payload de rúbrica lo arma `correccion_service._build_correction_payload` (L546) y `_build_pdf_correction_payload` (L586).
- Los response schemas `_SCHEMA_CORRECCION_CODIGO` (L251) y `_SCHEMA_CORRECCION_PDF` (L282) definen `criterios[]` sin nivel de subcriterios. `CriterioGeminiSchema`/`CriterioEvaluado` (correccion.py L36-60) tampoco.
- `criterios_json` es JSONB (`app/models/rubrica.py` L81; corrección: `data_dict['criterios_json'] = {"criterios": [...]}` en `correccion_service` L339) → **agregar `subcriterios_evaluados` NO requiere migración de esa tabla**.
- Frontend: la validación 100-suma existe en DOS lugares Zod independientes — `criteriosStructureSchema.superRefine` (schema file) y `rubricaFormSchema.refine` (RubricaEditor). `criterioSchema` se reusa en ambos, así que una `.superRefine` en `criterioSchema` propaga a los dos.

Restricciones del proyecto: Clean Architecture (Routers → Services → Repositories); nada de lógica de negocio en routers; Services no acceden a DB directo; máx 500 LOC/archivo; soft delete; permisos por rol por endpoint; migraciones SOLO vía `docker-compose -f docker-compose.local.yml`; frontend sin `any`, API solo en `services/`, React Query + RHF + Zod, componentes < 200 LOC. Governance: **MEDIUM** (business logic + integración IA), implementar con checkpoints.

## Goals / Non-Goals

**Goals:**
- Permitir que el docente asigne peso por subcriterio (puntos absolutos que suman al peso del criterio).
- Que la IA devuelva y persista puntaje desglosado por subcriterio en rúbricas v2.
- Compatibilidad hacia atrás **total**: rúbricas v1 corrigen exactamente igual que hoy; correcciones viejas se muestran sin romper.
- Aplicar el cambio de prompt/schema a ambos proveedores (Gemini y OpenRouter) sin duplicar lógica.
- UI clara para migrar rúbricas v1 → v2 con pesos iguales precargados y editables.

**Non-Goals:**
- No se migran automáticamente las rúbricas existentes a v2 (quedan en v1 hasta que el docente las edite/migre).
- No se recalculan correcciones ya hechas.
- No se deprecia `instrucciones_puntuacion`.
- No se bloquea la corrección de rúbricas v1.
- No se cambia la semántica de penalizaciones ni de condiciones de desaprobación.

## Decisions

### D1. Semántica del peso de subcriterio: puntos absolutos que suman al peso del criterio

`sum(subcriterio.peso) == criterio.peso` (mismo patrón que "criterios suman 100"), no porcentaje relativo. Rationale: consistencia conceptual con el nivel superior; el `puntaje_maximo` del subcriterio evaluado sale directo del peso; la nota del criterio es la suma de sus subcriterios.
Alternativa descartada: peso porcentual relativo al criterio (0-100 que suman 100 dentro del criterio) — añade una conversión mental y rompe la analogía con el nivel criterio.

### D2. Versionado con columna `schema_version` (Opción A)

Columna `schema_version int NOT NULL server_default '1'` en `rubricas`. Migración Alembic con `server_default='1'` para que las filas existentes queden en v1 sin backfill manual.
- v1 = comportamiento actual (no exige peso en subcriterios, reparto implícito, prompt y schema actuales).
- v2 = exige peso por subcriterio, prompt y schema nuevos con desglose.
Rationale: una sola columna versiona el contrato de toda la estructura JSONB sin tocar el shape del JSONB para rúbricas viejas; permite evolucionar el schema en el futuro (v3...).
Alternativa descartada: inferir la versión sniffeando si los subcriterios traen `peso` — frágil (una rúbrica v2 a medio editar podría tener subcriterios sin peso y confundir el branch). La versión explícita es la fuente de verdad.

### D3. Validación condicional por versión SIN plumbing de context de Pydantic

**Punto no trivial.** `Subcriterio`/`Criterio`/`CriteriosStructure` no conocen la versión; solo `RubricaCreate`/`RubricaUpdate` la conocen. Decisión:

1. `Subcriterio.peso` se declara **opcional a nivel modelo**: `peso: int | None = Field(default=None, ge=1, le=100)`. Así los dicts v1 (sin `peso`) siguen parseando.
2. Los validadores existentes de `Criterio`/`CriteriosStructure` quedan **version-agnósticos** (no se toca el camino v1).
3. Se agrega un helper de validación de pesos de subcriterio que corre **solo cuando `schema_version >= 2`**, invocado desde `RubricaCreate.validar_estructura_completa` y `RubricaUpdate.validar_estructura_si_presente` (que sí tienen `schema_version` como campo plano). El helper verifica, por cada criterio: (a) todos los subcriterios tienen `peso` no nulo; (b) `sum(sub.peso) == criterio.peso`. Mensajes de error análogos a `validar_suma_pesos`.

Rationale: evita plumbing invasivo de `model_validate(..., context=...)` en todos los call sites (la estructura hoy se valida dentro de un `model_validator` interno, no vía `model_validate` externo). La versión es un campo plano donde ya se conoce; el chequeo condicional vive ahí.
Alternativa descartada: `info.context` de Pydantic v2 — requeriría cambiar cómo se construye `CriteriosStructure` internamente y propagar context desde cada endpoint; más superficie de cambio y más frágil.

`schema_version` en los schemas: `RubricaCreate.schema_version: int = Field(default=1, ge=1)`, `RubricaUpdate.schema_version: int | None`, y `RubricaResponse`/`RubricaListItem.schema_version: int`. El default 1 en create preserva el comportamiento de cualquier cliente que no lo mande.

### D4. Redondeo de pesos iguales (suma exacta con enteros) — método del resto mayor

**Punto no trivial.** `peso_criterio / n` puede no ser entero (ej. 25/3). Regla (Hamilton / largest remainder), usada por el pre-cargado de "pesos iguales" del frontend:
```
base = floor(peso_criterio / n)
resto = peso_criterio - base * n           # 0 <= resto < n
# los primeros `resto` subcriterios reciben base+1; el resto, base
pesos[i] = base + 1 if i < resto else base
```
Garantiza: todos enteros ≥ 1 (si `peso_criterio >= n`), difieren a lo sumo en 1, y `sum(pesos) == peso_criterio` exacto. El validador (backend y Zod) solo chequea la **suma exacta**; no impone cómo se distribuye, así el docente puede reajustar a mano siempre que la suma cierre. Caso borde `peso_criterio < n` (más subcriterios que puntos): no se puede dar ≥1 a todos; el pre-cargado deja el reparto de resto mayor (algunos en 0) y la validación v2 exige `peso >= 1`, forzando al docente a corregir — se documenta como validación que puede fallar y guía al usuario, no como auto-fix silencioso.

### D5. Branch v1/v2 en el prompt-builder (compartido por ambos proveedores)

Los builders `_build_criterios_texto` y `_build_criterios_pdf_texto` reciben `schema_version` (nuevo parámetro, default 1). `correccion_service._build_correction_payload`/`_build_pdf_correction_payload` inyectan `"schema_version": rubrica.schema_version` en el dict de rúbrica; Gemini y OpenRouter lo pasan al builder.
- **v1**: salida EXACTAMENTE actual (subcriterios como checklist de evidencias, sin puntos; instrucciones y response schema actuales). El camino v1 no se toca.
- **v2**: cada subcriterio se imprime como `[C2.1] (10 pts) <descripción>` seguido de sus evidencias; las instrucciones de scoring indican asignar puntaje POR subcriterio y que `puntaje_obtenido` del criterio = suma de sus subcriterios; el response schema gana el nivel anidado `subcriterios_evaluados[]` (`id, puntaje_obtenido, puntaje_maximo, estado, feedback`). Se agregan `_SCHEMA_CORRECCION_CODIGO_V2` y `_SCHEMA_CORRECCION_PDF_V2` (o el schema se construye condicionalmente); Gemini selecciona por versión; OpenRouter replica en su `response_format`.
Rationale: un solo lugar (builders compartidos) ramifica ambos proveedores; el default 1 y el branch garantizan que cualquier llamada sin versión cae en v1.

### D6. Persistencia y schema de respuesta

- `CriterioGeminiSchema` y `CriterioEvaluado` ganan `subcriterios_evaluados: list[SubcriterioEvaluado] | None = None`. `SubcriterioEvaluado`: `id: str`, `puntaje_obtenido`, `puntaje_maximo`, `estado: Literal["OK","WARNING","ERROR"]`, `feedback: str`. Coherencia de tipos como en el nivel criterio: `CriterioGeminiSchema` usa `RoundedInt` (Gemini a veces devuelve floats), `CriterioEvaluado` usa `Decimal`.
- `correccion_service` persiste `subcriterios_evaluados` dentro de cada criterio en `criterios_json` (JSONB, sin migración de tabla). Al leer, `CorreccionResponse.model_validate` ya reconstruye desde `criterios_json`; se propaga el campo opcional.
- `GeminiResponse.validate_nota_sum` (autocorrige `nota` a la suma de criterios cuando no hay CD/penalización) se mantiene intacto: la nota sigue siendo suma de `puntaje_obtenido` de criterios; los subcriterios no cambian el cálculo de la nota, solo lo desglosan.
- `CorreccionUpdate.criterios` acepta `subcriterios_evaluados` para no perderlos en ediciones manuales.

### D7. Frontend: validación, badge y migración

- `Subcriterio` (TS) y `subcriterioSchema` (Zod) ganan `peso`. La validación "suma subcriterios == peso criterio" se agrega como `.superRefine` en `criterioSchema` (se reusa en `criteriosStructureSchema` y en `rubricaFormSchema` del editor, así propaga a ambos). Condicionada a v2: en el editor, cuando la rúbrica se está guardando/editando como v2.
- `RubricaManualMode`: input de peso por subcriterio (patrón idéntico al peso de criterio, L127-136) + display de suma en vivo por criterio (réplica del "Total: X%" de criterios, L288-315, comparando contra `criterio.peso`). Los defaults de subcriterio nuevo (RubricaManualMode L175-179 y los tres de RubricaEditor) suman `peso`.
- `schema_version` se agrega a los tipos `Rubrica`/`RubricaListItem`/`RubricaCreate`/`RubricaUpdate` (pass-through por el service). El editor setea `schema_version: 2` al guardar con pesos por subcriterio.
- Badge "Rúbrica desactualizada" cuando `schema_version < 2`: en la fila de `RubricasPage` y en el header del editor. Botón "Migrar al nuevo modelo": pre-carga pesos iguales (D4) vía `setValue('criterios', migrated)` y marca la rúbrica como v2 (borrador editable, no guarda hasta que el docente confirme).

### D8. Frontend correcciones: display tolerante

`CriterioEvaluado` (TS) y `CorreccionUpdate` ganan `subcriterios_evaluados?`. `CriterioCard` (CorreccionViewEditModal) renderiza el desglose por subcriterio **solo si** `criterio.subcriterios_evaluados?.length`, con la misma defensividad (`|| []`, optional chaining) ya usada para correcciones viejas. Correcciones sin el campo (viejas o v1) se muestran igual que hoy.

## Risks / Trade-offs

- [La IA v2 podría devolver subcriterios cuya suma no coincida con `puntaje_obtenido` del criterio] → El prompt lo exige explícitamente y `validate_nota_sum` sigue anclando la nota a la suma de criterios; el desglose es informativo. No se hace hard-fail por descuadre de subcriterios (evita romper correcciones por ruido del modelo); se documenta como tolerancia.
- [Dos definiciones Zod de la suma-100 en el front] → Se centraliza la nueva validación en `criterioSchema` para que ambas la hereden y no divergir.
- [Migración con `peso_criterio < n`] → El pre-cargado no puede dar ≥1 a todos; la validación v2 obliga al docente a ajustar. Se documenta; no se auto-corrige en silencio.
- [Regresión del camino v1] → Mitigación: el branch v1 no toca ninguna línea del path actual; tests de caracterización sobre builders/validación v1 antes de tocar (Safety Net del modo TDD en apply).
- [OpenRouter y Gemini divergen en formato de response schema] → Se implementa el nivel anidado en ambos y se cubre con tests de cada cliente.
- [`schema_version` no expuesto por el service rompe el badge] → Tarea explícita de agregarlo a los tipos y verificar que el backend lo serializa en list y detail.

## Migration Plan

1. Backend: agregar columna `schema_version` (modelo + migración Alembic vía docker compose local) con `server_default '1'`. Aplicar `alembic upgrade head` en el entorno local dockerizado.
2. Backend: schemas de rúbrica (peso opcional + validación condicional v2 + `schema_version` en create/update/response).
3. Backend: schemas de corrección (`subcriterios_evaluados`) + builders v1/v2 + response schemas v2 (Gemini y OpenRouter) + inyección de `schema_version` y persistencia en `correccion_service`.
4. Frontend: tipos + Zod + editor (input/validación/badge/migrar) + display de correcciones.
5. Docs: `docs/specs/Rubrica.md`.

**Rollback**: como v1 es el default y el server_default es '1', revertir el código deja las rúbricas existentes intactas. La columna `schema_version` puede quedar sin uso sin efectos (downgrade de Alembic la elimina si se requiere). Correcciones v2 ya persistidas conservan `subcriterios_evaluados` en JSONB; el front viejo simplemente los ignora.

## Open Questions

- ¿La migración v1→v2 debe forzar recorrección de entregas ya corregidas de esa rúbrica, o solo aplica a nuevas correcciones? (Asunción actual: solo nuevas; correcciones viejas quedan como están.)
- ¿El badge "desactualizada" debe aparecer también en el dashboard de gestores o solo en la lista/editor de rúbricas? (Asunción: lista + editor.)
