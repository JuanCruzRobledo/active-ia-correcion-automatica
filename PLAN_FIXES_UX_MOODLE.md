# Plan de implementación — Fixes UX + Moodle (correcciones / entregas / rúbricas)

> Rama base: `feat/moodle-bidireccional`. Stack: FastAPI (Clean Arch) + React/TS (React Query, RHF+Zod, Tailwind).
> TDD obligatorio. Migraciones SIEMPRE con `docker compose -f docker-compose.local.yml`. Conventional commits, sin `Co-Authored-By`.

Este plan cubre 7 pedidos. Están **reordenados por dependencia y riesgo** (no por el orden en que llegaron), porque varios comparten infraestructura: los items 1 y 7 comparten la persistencia de errores; los 4 y 5 comparten el helper de URL de Moodle; el sub-bug de "pendientes no refresca" del item 3 es en realidad del item 2.

---

## Orden propuesto (olas)

| Ola | Items | Por qué juntos | Riesgo (governance) |
|-----|-------|----------------|---------------------|
| **1** | #6 Moodle id vacío en rúbrica | Aislado, quick win, desbloquea higiene de pendientes | LOW |
| **2** | #2 Estados/refresh + sub-bug pendientes | Frontend transversal, base de UX para el resto | MEDIUM |
| **3** | #1 Errores n8n claros · #7 Re-corregir errores | Ambos necesitan persistir el error en la entrega | MEDIUM |
| **4** | #4 URL manual a Moodle · #5 Link a entrega Moodle | Comparten construir/parsear URL de Moodle | MEDIUM |
| **5** | #3 Último archivo + nota de re-entrega | Toca import + grading (la más delicada) | HIGH |

---

## Item #6 — Moodle id vacío en una rúbrica (Ola 1, LOW)

**Problema (verificado):** no se puede dejar vacío `moodle_assign_id` ni borrarlo.
- Frontend Zod: `RubricaEditor.tsx:30-68` ya es `.positive().nullable().optional()`, pero el input en `RubricaGeneralInfo.tsx:124-134` solo aparece en **edición** y el `setValueAs` ya mapea `'' → null`. El problema real es de **envío**: `RubricaEditor.tsx:386,408` hace `data.moodle_assign_id ?? undefined`, así que **un `null` explícito se transforma en `undefined` y no viaja** → el backend nunca recibe la orden de borrar.
- Backend `RubricaUpdate` (`schemas/rubrica.py:379-440`) acepta `int | None`, **pero no distingue "no enviado" de "enviado null"**. Hay que asegurar que `null` se persista como `NULL`.
- Modelo `rubrica.py:109` ya es `nullable=True`. La columna está OK.

**Causa raíz:** el `?? undefined` del front colapsa el `null` y, si se arregla eso, falta confirmar que el service de update setee `NULL` cuando llega `null` (y no lo ignore por un patrón "solo campos presentes").

**Solución:**
- Frontend: en update/create enviar `moodle_assign_id: data.moodle_assign_id ?? null` (no `undefined`). Mostrar el campo también en alta si el rol corresponde.
- Backend: en `RubricaService.update`, usar `model_dump(exclude_unset=True)` para distinguir ausente de `null`, y permitir setear `NULL` explícito. Validar `gt=0` cuando **sí** viene número (`Field(None, gt=0)`).
- Relación con pendientes: con `moodle_assign_id = NULL`, `moodle_service.get_pendientes` ya filtra `Rubrica.moodle_assign_id.isnot(None)` → la rúbrica **deja de aparecer en pendientes** automáticamente. ✔️ Es justo lo que pide el usuario.

**Archivos:** `frontend/.../rubricas/components/RubricaEditor.tsx`, `RubricaGeneralInfo.tsx`; `backend/app/schemas/rubrica.py`, `backend/app/services/rubrica_service.py`.
**Tests (TDD):** unit del service — update con `moodle_assign_id=None` borra el valor; update sin la clave no lo toca; create/update con `0` o negativo → 422.
**Migración:** ninguna (ya es nullable).

---

## Item #2 — Estados actualizados / cache / botón refresh (Ola 2, MEDIUM)

**Problema (verificado):**
- React Query global (`app/providers.tsx:4-16`): `staleTime 5min`, `refetchOnWindowFocus:false`. Datos cacheados hasta 5min o invalidación explícita.
- **Falta invalidación cruzada:** crear/editar rúbrica con `moodle_assign_id` no invalida `['pendientes-moodle']` → hay que cerrar sesión o esperar. (`useRubricas.ts` invalida solo `rubricasKeys`.)
- **Sub-bug pendientes (viene del item 3):** el botón "Actualizar" (`PendientesPage.tsx:104-112` → `usePendientesMoodle.ts:8-36`) usa `queryClient.removeQueries(...)` en vez de `refetchQueries(...)`. Por eso necesita F5: `removeQueries` borra del cache pero no fuerza el refetch inmediato; depende de que el componente vuelva a montar la query.

**Solución (dos capas):**

**Capa A — MUST (resuelve el 90%, barato):**
1. Cambiar el refresh de pendientes a `queryClient.refetchQueries({ queryKey: ['pendientes-moodle'] })` (refetch explícito, spinner correcto).
2. Completar invalidaciones faltantes: `useCreateRubrica`/`useUpdateRubrica`/`useDeleteRubrica` invalidan también `['pendientes-moodle']` y `['entregas']` cuando cambia `moodle_assign_id`.
3. Componente compartido `<RefreshButton/>` (extraer del de pendientes, que al usuario le gusta) y colocarlo en las pantallas con datos vivos: Pendientes, Entregas, Rúbricas, Dashboard. Cada uno hace `refetchQueries` de su key.

**Capa B — IMPLEMENTADA (detección de cambios, "hay novedades"):**
> Nota de implementación: el token de versión (`GET /sync/version` → `{entregas, rubricas}` = `MAX(updated_at)|COUNT`) es un HINT **global** (no scopeado por usuario): puede sobre-disparar (un cambio de otro tutor avisa igual), pero nunca pierde un cambio. El refresco real lo hace la query de la pantalla; el banner solo decide cuándo ofrecer actualizar. Mensaje por rol vía `mensajeNovedades(rol)`. Poolea cada 45s, no en background.

- El pedido "cuando haya un cambio en el backend… con un mensaje según el rol" implica detección de cambios. Sin WebSocket, lo barato es **polling liviano** de un endpoint `GET /<recurso>/version` (devuelve un `updated_at`/contador máximo). Si el valor cambió respecto al que tengo, muestro un banner "Hay datos nuevos — Actualizar".
- **Mensaje por rol** (`useAuth.ts` da `user.rol`): TUTOR → "Hay entregas nuevas para corregir"; COORDINADOR/GESTOR → "Hay datos actualizados"; ADMIN → idem genérico. Sin filtrar info de más.

> **DECIDIDO (2026-06-24):** se hacen **Capa A + Capa B**. Banner de novedades con polling y mensaje por rol.

**Archivos:** `frontend/src/app/providers.tsx`, `features/pendientes/hooks/usePendientesMoodle.ts`, `features/rubricas/hooks/useRubricas.ts`, nuevo `shared/components/RefreshButton.tsx`; (Capa B) routers backend con endpoint `version`.
**Tests:** hook test del refresh (refetch llamado), invalidación cruzada al crear rúbrica.
**Migración:** ninguna (Capa A). Capa B: ninguna si se usa `MAX(updated_at)`.

---

## Item #1 — Errores de n8n/Gemini con texto claro (Ola 3, MEDIUM)

**Problema (verificado):** el backend YA clasifica los errores (`n8n_client.py:249-338`: `APIKeyInvalidError`/402, `QuotaExceededError`/429, `N8NError`/502, `N8NTimeoutError`/502) y el front ya distingue 402/429 (`useEntregas.ts:47-68`). **Pero el detalle no se persiste:** `Entrega` no tiene campos de error (`models/entrega.py`), así que una entrega en ERROR no sabe *por qué* falló. El mensaje al usuario es genérico y se pierde al recargar.

**Solución:**
1. **Persistir el error en la entrega** (habilita también el item #7). Migración: agregar a `Entrega`:
   - `error_code: str | None` (ej. `GEMINI_RATE_LIMIT`, `GEMINI_API_KEY_INVALID`, `GEMINI_OVERLOADED`, `N8N_TIMEOUT`, `IA_RESPUESTA_INVALIDA`).
   - `error_mensaje: str | None` (texto humano corto, ya traducido).
   - `error_at: datetime | None`.
2. **Diccionario de traducción** central (nuevo `app/core/error_catalog.py`): mapea `error_code` → mensaje claro en español:
   - 429 → "Gemini saturado / superaste tu límite de uso. Esperá unos minutos."
   - 503/“overloaded”/“high demand” → "El modelo de Gemini está sobrecargado. Reintentá en un rato."
   - API key inválida → "Tu API Key de Gemini no es válida o expiró. Revisala en tu perfil."
   - timeout → "El servicio de IA tardó demasiado. Reintentá."
3. **Detectar 503/overloaded:** hoy `_check_response_body_for_errors` cubre 429 y API key; agregar rama para `status==503` o `message` con "overloaded"/"high demand" → nuevo `ModelOverloadedError` (502/503) con su code.
4. En `correccion_service.py:147-214`, cada `except` setea `entrega.error_code/error_mensaje/error_at` antes del `update`.
5. Schema de respuesta de Entrega incluye los 3 campos; front los muestra en toast + tooltip/badge en la tabla (`EntregasPage.tsx`).

**Archivos:** `backend/app/models/entrega.py`, nueva migración Alembic, `app/integrations/n8n_client.py`, `app/core/exceptions.py`, nuevo `app/core/error_catalog.py`, `app/services/correccion_service.py`, `app/schemas/entrega.py`; front `features/entregas/...`.
**Tests (TDD):** `error_catalog` mapea cada code → texto; `n8n_client` clasifica 503/overloaded; service setea `error_code` correcto por cada excepción.
**Migración:** SÍ (3 columnas nullable). Con docker compose local.

---

## Item #7 — Entregas en ERROR vuelven a corrección masiva + resumen (Ola 3, MEDIUM)

**Problema (verificado):**
- Masiva **global** (`procesar_global_background`) toma `entrega_repo.get_subidas_ids_by_tutor()` que filtra **solo `SUBIDA`** → las `ERROR` quedan atrapadas, nunca se reintentan.
- No hay resumen persistente de la corrida (el front infiere por polling en `EntregasPage.tsx:199-240`, pero si te vas de la pantalla se pierde).

**Solución:**
1. **Incluir ERROR como recorregibles:** `get_subidas_ids_by_tutor` (y el filtro del lote/global) acepta `estado IN (SUBIDA, ERROR)`. Para la global, agregar parámetro `incluir_errores: bool = True`.
2. **Frontend:** en Entregas, permitir filtrar y seleccionar las `ERROR` para "Re-corregir seleccionadas"; el botón de masiva global por defecto las incluye. Mostrar el `error_mensaje` (item #1) como motivo.
3. **Resumen de la corrida:** al terminar la masiva, modal/banner con conteo por tipo, usando el `error_code` persistido:
   ```
   ✅ 42 corregidas
   ❌ 8 con error: 5 rate limit · 2 sobrecarga · 1 API key
   [Re-corregir las 8 con error]
   ```
   El endpoint `GET /correcciones/global/progreso` (`correcciones.py:401-421`) ya devuelve `{subidas,pendientes,corregidas,error,total}`; extenderlo con desglose por `error_code` (agregación en `contar_estados_by_tutor`).

**Archivos:** `backend/app/repositories/entrega_repository.py`, `app/services/correccion_service.py`, `app/routers/correcciones.py`; front `features/entregas/...`, `features/dashboard/...`.
**Tests (TDD):** repo incluye ERROR en el set recorregible; agregación de progreso desglosa por code; reintento de una ERROR la vuelve a SUBIDA/PENDIENTE.
**Migración:** ninguna nueva (usa columnas del item #1). **Depende de #1.**

---

## Item #4 — Corrección manual con subida a Moodle vía URL de la entrega (Ola 4, MEDIUM)

**Problema (verificado):** una entrega manual (`routers/entregas.py:87-144`) se guarda con `moodle_user_id = NULL`. Subir a Moodle exige `moodle_user_id` (`moodle_grade_service.py:98-105`) → el botón "Subir a Moodle" siempre falla con 400. No hay forma de vincular una entrega manual a su submission de Moodle.

**Solución:**
1. **Campo URL en el alta manual:** input opcional "URL de la entrega en Moodle" (ej. `https://host/mod/assign/view.php?id=<cmid>&userid=<userid>`).
2. **Parser** (`app/services/moodle_url_parser.py`, puro): extrae `cmid` (param `id`) y `userid` de la URL. Con esos datos:
   - `userid` → `entrega.moodle_user_id`.
   - `cmid` se valida/contrasta contra `rubrica.moodle_assign_id` (si difieren, avisar; el cmid manda la rúbrica).
3. Guardado el `moodle_user_id`, el botón "Subir a Moodle" funciona sin tocar `moodle_grade_service`.
4. (Opcional) persistir la URL cruda en `entrega.moodle_submission_url` para mostrarla luego.

> **Decisión menor:** ¿guardar la URL cruda además del `moodle_user_id`? Recomiendo **sí** (barato, sirve para el item #5 y auditoría).

**Archivos:** front form de alta (`features/entregas/components/CargaEntregaModal.tsx`), `backend/app/routers/entregas.py`, `app/services/entrega_service.py`, nuevo `app/services/moodle_url_parser.py`, posible migración (`moodle_submission_url`).
**Tests (TDD):** parser con URLs válidas/ruidosas/sin params → cmid+userid o error claro; alta manual con URL puebla `moodle_user_id`.
**Migración:** opcional (1 columna nullable) si se persiste la URL.

---

## Item #5 — Link directo a la entrega de Moodle cuando "no hay archivos" (Ola 4, LOW/MEDIUM)

**Problema (verificado):** cuando el alumno entregó pero sin archivos válidos, el import suma `resumen.sin_archivos` (`moodle_import_service.py:241-243`) y el front lo muestra como número seco. No hay link para ir a avisarle al alumno.

**Solución:**
1. **Helper compartido** (reusa el parser/constructor del item #4): `construir_url_entrega(host, cmid, userid)` → `https://host/mod/assign/view.php?id=<cmid>&userid=<userid>`. Datos disponibles: `host`=`usuario.moodle_host`, `cmid`=`rubrica.moodle_assign_id`, `userid`=`sub.userid`.
2. **Enriquecer el resumen del import:** que `sin_archivos` deje de ser un contador y pase a ser una **lista** `[{alumno, url_moodle}]` (cambio en el `ImportResumen` y en el `yield` de `moodle_import_service`).
3. **Frontend:** en el resultado del import, sección "Entregaron sin archivos" con el nombre + botón "Ver en Moodle" (abre la URL) para mandarle el aviso.

**Archivos:** `backend/app/services/moodle_import_service.py` (dataclass resumen + loop `sin_archivos` en `:241-243`), helper URL compartido, front `features/pendientes/components/ImportarButton.tsx`.
**Tests (TDD):** el import arma la lista con URL correcta para las submissions sin archivos.
**Migración:** ninguna (se calcula on-the-fly).

---

## Item #3 — Usar el último archivo del alumno + nota de re-entrega (Ola 5, HIGH)

**Esta es la más delicada: toca import Y grading. Governance HIGH → implementar por pasos y mostrar decisiones.**

### 3a) Bug "detecta el primer archivo" (CAUSA RAÍZ CONFIRMADA)
En `moodle_service.py:918-961`, `get_submissions_with_files` agrega **un `MoodleSubmission` por cada registro** de `assignment["submissions"]`. Cuando hay reintentos, Moodle devuelve un registro por `attemptnumber` → pueden quedar el intento viejo y el nuevo, y el pipeline procesa cualquiera (a menudo el primero). `timemodified` y `attemptnumber` están disponibles pero **no se usan para deduplicar**.

**Solución:** deduplicar por `userid` quedándose con el de **mayor `attemptnumber`** (desempate por `timemodified`). Un solo `MoodleSubmission` por alumno = el más reciente. Punto exacto: antes de construir `result` (o justo después), colapsar por `userid`.

> Nota: dentro de UNA submission, `_obtener_bytes` (`moodle_import_service.py:509-522`) ya consolida todos sus archivos en ZIP — eso está bien; el problema era *entre* intentos, no dentro de uno.

### 3b) Subir la nueva nota aunque ya esté en Moodle ("Ya estaban en Moodle")
Hoy `subir_correccion` (`moodle_grade_service.py:119-163`) bloquea con 409 si `get_ultimo_enviado` existe o si ya está calificada en Moodle, salvo `forzar=True`. Tras una re-entrega, la nota nueva debe subir igual.

**Solución:**
- Detectar re-entrega de forma robusta: ya existe `_es_reentrega(sub, correccion_actualizada_en)` (`moodle_import_service.py:525`). Al re-importar una re-entrega, marcar la entrega/corrección como "re-entregada pendiente de re-publicar".
- En `subir_correccion`, si la corrección corresponde a una re-entrega **posterior** al último `moodle_sync` ENVIADO, devolver una señal de "re-entrega detectada" para que el front **pida confirmación** al tutor (DECIDIDO 2026-06-24: NO reenvío automático). Recién con `forzar=True` se reenvía. `save_grade` ya usa `attemptnumber:-1` (último intento), así que sobrescribe la nota del intento vigente correctamente.
- Mantener el anti-pisado para notas puestas a mano fuera de Active-IA salvo que sea claramente una re-entrega nuestra.

### 3c) Sub-bug del botón "Actualizar" en pendientes
Ya cubierto y resuelto en el **item #2 Capa A** (cambiar `removeQueries`→`refetchQueries`).

**Archivos:** `backend/app/services/moodle_service.py` (dedup en `get_submissions_with_files`), `app/services/moodle_grade_service.py` (excepción de re-entrega a la idempotencia), `app/services/moodle_import_service.py` (marcar re-entrega), posible flag en `Correccion`/`Entrega`.
**Tests (TDD):**
- `get_submissions_with_files` con 2 intentos del mismo user → devuelve solo el de mayor `attemptnumber`.
- `subir_correccion`: re-entrega posterior al último ENVIADO → reenvía sin 409; sin re-entrega → mantiene 409.
**Migración:** posible (flag de re-entrega), evaluar si alcanza con timestamps existentes.

---

## Resumen de migraciones (todas con docker compose local)

| Item | Migración |
|------|-----------|
| #6 | — |
| #2 | — (A); — (B con MAX(updated_at)) |
| #1 | `entrega.error_code`, `error_mensaje`, `error_at` (nullable) |
| #7 | — (reusa #1) |
| #4 | opcional `entrega.moodle_submission_url` (nullable) |
| #5 | — |
| #3 | posible flag de re-entrega (a confirmar) |

## Verificación final por ola
`pytest` (backend) + `npm run typecheck && npm run build && npm run lint` (front). Ignorar los 5 tests pre-existentes rotos (consolidacion/entrega/rubrica service ImportError, pendientes aiosqlite). Validar con datos reales antes de cerrar cada ola.

## Decisiones tomadas (2026-06-24)
1. **Item #2:** Capa A **+ Capa B** (banner "hay novedades" con polling y mensaje por rol). ✔️
2. **Item #3b:** **Pedir confirmación** al tutor antes de pisar una nota ya publicada en Moodle (no reenvío automático). ✔️
3. **Item #4:** persistir la URL cruda de Moodle además del `moodle_user_id` (recomendado, a confirmar al llegar a la Ola 4).
