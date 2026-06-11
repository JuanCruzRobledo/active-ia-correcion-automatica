# PLAN — Refactor de obtención de datos de Moodle: de N+1 a carga masiva

> **Origen:** incidente del 2026-06-08. El snapshot le pegaba a Moodle `1 + 2N`
> requests por materia (1 enrolled + N completion + N grades). Para 100 alumnos =
> **201 requests** con timeout de 30s c/u. El admin de Moodle lo leyó como un
> scraping/ataque y amenazó con bloquear nuestra IP.
>
> **Objetivo:** que la generación de un snapshot le pegue a Moodle un número
> **CONSTANTE** de veces (~3-4), independiente de la cantidad de alumnos.

---

## 1. Decisión de arquitectura (validada en spike R0, 2026-06-08)

> ⚠️ **REVISIÓN tras el spike R0:** la idea inicial era bajar las notas con el WS
> `gradereport_user_get_grade_items?userid=0`. **El spike demostró que NO es viable**
> a esta escala: para el curso de Prog1 (772 alumnos) la respuesta pesa ~37 MB y tarda
> >520s → **ReadTimeout, muere**. Un solo grupo de 62 alumnos ya devuelve 3 MB en 42s.
> El WS de notas es obeso (mucha metadata por item × alumno). **Se descarta el WS para
> notas.** La idea ORIGINAL del usuario (bajar el export del calificador) resultó ser
> la correcta: el export TXT del mismo curso pesa **282 KB** y baja en 1 request.

| Dato | Mecanismo validado en R0 | Hits a Moodle |
|------|--------------------------|---------------|
| Login de sesión (cookie `MoodleSession`) | POST `/login/index.php` con credenciales **ya cifradas** (reusa `moodle_username`/`moodle_password_encrypted`) | 1 / corrida |
| **Notas** de TODOS los alumnos | POST `/grade/export/txt/export.php` (export del calificador, formato comma) → CSV ~282 KB | 1 / materia |
| **Seguimiento** (completion) de TODOS | GET `/report/progress/index.php?course=X&format=csv` → CSV | 1 / materia |
| Mapa nombre-actividad → cmid (para parsear ambos CSV) | `core_course_get_contents(course_id)` (WS liviano, **ya existe, cacheado**) | 1 / materia |

**Total: ~3-4 requests por materia, sin importar N alumnos.** (Antes: `1 + 2N` = 201 para 100 alumnos.)

### El hallazgo clave (revisado)
**Un solo mecanismo de auth (sesión web) sirve para las dos descargas masivas.** El
login programático funciona con las credenciales que el sistema YA guarda cifradas
(las mismas que sacan el token WS). Tanto el export del calificador como el reporte de
finalización se sirven por sesión y devuelven **un archivo compacto con todos los
alumnos**. No hay que guardar credenciales nuevas (R4 se cae).

### El detalle honesto
El export del calificador trae **solo notas**; el reporte de finalización trae **solo
completion**. Por eso se necesitan los DOS: las actividades por `CALIFICACION` (TP) salen
del calificador; las de `SEGUIMIENTO` (CIERRE/AUTOEVALUACION, marcar-como-hecha sin nota)
salen del CSV de finalización. **Ambos archivos keyean por NOMBRE de actividad, no por
cmid** → el puente es `core_course_get_contents` (nombre → cmid).

### Lo que NO se toca (Clean Architecture)
`avance_mapper.py` (lógica pura) queda **intacto**. `calcular_avance_alumno` y
`calcular_deudas_y_alcance` ya reciben `completion_statuses` + `notas_tp` +
`unidades_config`. Solo cambia el **origen** de esos dos primeros, no el cálculo.

---

## 2. Autenticación de las descargas — RESUELTO en R0

> ✅ **Decidido tras el spike:** las descargas van por **sesión web** (cookie
> `MoodleSession`), obtenida con **login programático reusando las credenciales que el
> sistema YA guarda cifradas** (`usuario.moodle_username` + `moodle_password_encrypted`,
> AES-256 vía `app/core/security.decrypt_api_key`). **No se almacenan credenciales
> nuevas → R4 ya no es necesario.** Flujo validado: GET `/login/index.php` (extraer
> `logintoken`) → POST credenciales → cookie `MoodleSession` → descargas.

<details><summary>Análisis previo (histórico) de opciones de auth</summary>

El reporte `report/progress/index.php?course=X&format=csv` se sirve por **sesión web
(cookie `MoodleSession`)**, NO por token. Opciones evaluadas:

| Opción | Cómo | Pro | Contra | Governance |
|--------|------|-----|--------|------------|
| **A. Login programático (Recomendado)** | Guardar credenciales Moodle (user/pass) **cifradas AES-256** (mismo patrón que las API keys de Gemini), hacer POST a `/login/index.php` con `logintoken` → obtener cookie → GET del CSV | Automatizable en el cron; sin pasos manuales | Hay que almacenar credenciales (riesgo) | **HIGH** — almacenamiento de credenciales |
| **B. Subida manual del CSV** | El gestor baja el CSV de la UI de Moodle y lo sube a Active-IA | Cero credenciales almacenadas; cero hit automático | No sirve para el cron diario; paso manual | LOW |
| **C. Híbrido** | Manual para el arranque, login programático cuando se valide | — | Más trabajo | HIGH |

> **Recomendación (histórica):** empezar por **A**. El spike R0 confirmó que A funciona
> con las credenciales ya guardadas → es la opción definitiva.

</details>

### Resultados del spike R0 (2026-06-08, curso Prog1 id=38, 772 alumnos)

| Probe | Resultado |
|-------|-----------|
| WS `gradereport_user_get_grade_items?userid=0` | ❌ **ReadTimeout** (>180s). 1 grupo de 62 = 3 MB/42s → 772 ≈ 37 MB/520s. **Descartado.** |
| Chunking por grupo | ❌ El curso tiene **548 grupos** → 548 llamadas. **Descartado.** |
| Login programático (credenciales cifradas) | ✅ cookie `MoodleSession` OK |
| `report/progress?course=38&format=csv` (completion) | ✅ HTTP 200, text/csv, **774 líneas** en 1 GET |
| POST `grade/export/txt/export.php` (notas) | ✅ HTTP 200, application/download, **282 KB, 774 líneas** |

**Estructura del CSV de finalización:** col0=nombre, col1="Dirección de correo", luego
**pares** `[estado, fecha]` por actividad (header de la fecha vacío). Estados (es):
`"Finalizado"`, `"Finalizado (ha alcanzado la califiación de aprobado)"` [sic, typo de
Moodle], vacío/`"No finalizado"`.

**Estructura del export del calificador:** col0-5 = Nombre, Apellido(s), Número de ID,
Institución, Departamento, Dirección de correo; luego **una columna por item**, header
`"<Tipo>:<Nombre actividad> (Real)"` (ej. `"Cuestionario:... (Real)"`); valores numéricos
(`10.00`) o de escala (`Aprobado`/`Desaprobado`). El form requiere `sesskey` + los 132
`itemids[...]` (extraídos del HTML) en el POST.

---

## 3. Presupuesto de requests — antes vs después

```
ANTES (por materia, N alumnos):
  1 × core_enrol_get_enrolled_users
  N × core_completion_get_activities_completion_status   (30s c/u)
  N × gradereport_user_get_grade_items                   (30s c/u)
  = 1 + 2N         →  100 alumnos = 201 requests

DESPUÉS (por materia, cualquier N) — validado en R0:
  1 × login de sesión                      (1 por corrida, no por materia)
  1 × core_enrol_get_enrolled_users        (WS, cacheado)
  1 × core_course_get_contents             (WS, cacheado, para nombre→cmid)
  1 × POST grade/export/txt/export.php      (notas, ~282 KB)
  1 × GET report/progress?format=csv        (completion)
  = ~5 requests CONSTANTES   →  100 o 3000 alumnos = los mismos ~5 requests
```

---

## 4. Fases de implementación

> Convención del proyecto: TDD estricto en lógica pura, migraciones SIEMPRE dentro de
> `docker-compose.local.yml`, sin `Co-Authored-By`. Cada fase deja tests verdes.

### R0 — Spike de validación contra Moodle real ✅ COMPLETADO (2026-06-08)
- Script `backend/scripts/spike_moodle_bulk.py`. Resultados en §2 ("Resultados del spike R0").
- **Conclusión:** WS `userid=0` descartado (37 MB/timeout). Camino definitivo = **2 descargas
  por sesión web** (export calificador TXT + CSV de finalización), reusando credenciales
  cifradas existentes. Contratos de R1/R2 ajustados abajo.

### R1 — `moodle_service`: sesión + export del calificador (notas) `[Governance: MEDIUM]`
- **I/O sesión:** `abrir_sesion_moodle(usuario|user/pass, host) -> httpx.AsyncClient`
  (GET `/login/index.php` → extraer `logintoken` con regex tolerante a orden de atributos
  y a `M.cfg`; POST credenciales; verificar cookie `MoodleSession`). User-Agent custom
  `Active-IA/1.0 (integración académica TUD)`.
- **I/O notas:** `descargar_export_calificador(client, host, course_id) -> str`
  (GET `/grade/export/txt/index.php?id=X` → extraer `sesskey` + todos los `itemids[...]`;
  POST a `/grade/export/txt/export.php` con `separator=comma`, `display[real]=1`,
  `export_onlyactive=1`, todos los itemids → CSV).
- **Pure (TDD):** `parsear_export_calificador(csv_text, nombre_a_cmid, email_a_uid) -> dict[int, dict[int, str]]`
  → `{moodle_user_id: {cmid: gradeformatted}}`. Col0-5 fijas (Nombre, Apellido(s), Número
  de ID, Institución, Departamento, Dirección de correo); de col6 = una por item con header
  `"<Tipo>:<Nombre> (Real)"`. Tests: normalizar header (quitar prefijo `Tipo:` y sufijo
  ` (Real)`) → match nombre→cmid; valor numérico (`"10.00"`) y de escala (`"Aprobado"`/
  `"Desaprobado"`/`"-"`) → pasa tal cual a `estado_tp`; match fila→alumno por email; item
  sin match de nombre se ignora con log.

### R2 — `moodle_service`: CSV de finalización (completion) `[Governance: MEDIUM]`
- **I/O:** `descargar_reporte_finalizacion_csv(client, host, course_id) -> str`
  (GET `/report/progress/index.php?course=X&format=csv`, reusa el client con sesión de R1).
- **Pure (TDD):** `parsear_csv_finalizacion(csv_text, nombre_a_cmid, email_a_uid) -> dict[int, list[dict]]`
  → `{moodle_user_id: [{cmid, state}]}` (shape que ya consume el mapper). El CSV trae
  **pares** `[estado, fecha]` por actividad (header de la fecha vacío → se saltea esa
  columna). Texto→state: `"Finalizado (ha alcanzado...)"`→2, `"Finalizado (no ha
  alcanzado...)"`→3, `"Finalizado"`→1, vacío/`"No finalizado"`→0. Match fila→alumno por
  email. Tests con la muestra real de R0 (acentos, emojis en nombres, typo "califiación").
- ⚠️ **Riesgo (ambos parsers):** keyean por **nombre** de actividad, no cmid → join vía
  `core_course_get_contents`. Nombres duplicados/sin match → log + se omite.

### R3 — `snapshot_service.generar()`: orquestación masiva `[Governance: MEDIUM]`
- Reescribir el cuerpo de `generar()`:
  1. `client = abrir_sesion_moodle(usuario, host)`  (1 login)
  2. `enrolled = get_enrolled_users_full(course_id)` → `email_a_uid` + datos de alumno  (1 WS)
  3. `contents = get_course_contents(course_id)` → `nombre_a_cmid`  (1 WS)
  4. `notas_por_uid = parsear_export_calificador(descargar_export_calificador(...), ...)`  (1 descarga)
  5. `completion_por_uid = parsear_csv_finalizacion(descargar_reporte_finalizacion_csv(...), ...)`  (1 descarga)
  6. **Loop en memoria** por alumno: `calcular_avance_alumno(completion_por_uid.get(uid, []), notas_por_uid.get(uid, {}), unidades_config, unidad_actual=...)` — **CERO requests a Moodle en el loop.**
- **Eliminar:** el `asyncio.Semaphore(concurrencia)`, las llamadas per-alumno
  (`get_activities_completion`, `get_grade_items`), el param `concurrencia`.
- `on_progress(p, t)` ahora refleja el procesamiento **en memoria** (instantáneo).
- `calcular_avance_alumno` **NO se modifica.**

### R4 — ~~Persistencia de credenciales Moodle~~ NO NECESARIO
- ✅ Las credenciales ya existen cifradas (`usuario.moodle_username` +
  `moodle_password_encrypted`). R1 las reusa vía `decrypt_api_key`. **Fase eliminada.**

### R5 — Tests + verificación de paridad `[Governance: MEDIUM]`
- Unit verdes (los 3 errores de colección pre-existentes son AJENOS: `CriterioSchema`,
  `CargaMasivaRequest`).
- Adaptar `test_snapshot_service.py` a los nuevos mocks (bulk + CSV en vez de per-alumno).
- **Paridad:** comparar un snapshot generado al modo viejo vs nuevo para 3-5 alumnos
  conocidos (mismo `unidad_alcanzada`, `estado`, `deudas`). Es la prueba de que no
  rompimos nada.

### R6 — Defensa y limpieza `[Governance: LOW]`
- Circuit breaker simple en `_ws_get_json` (abortar la corrida si N errores seguidos,
  para no martillar a Moodle caído).
- Borrar el código muerto del path per-alumno.
- Actualizar docstrings + `CLAUDE.md` (sección "AI Correction Flow" / snapshot) y este plan.
- (Proceso, fuera de código) coordinar con el admin de Moodle el whitelisting de la IP
  de Active-IA y avisar el horario del cron.

---

## 5. Orden sugerido y dependencias

```
R0 (spike) ✅ HECHO
   │
   ├──► R1 (sesión + export calificador)  ─┐
   └──► R2 (CSV completion)               ─┤
                                           ▼
                            R3 (orquestación) ──► R5 (paridad) ──► R6 (defensa/limpieza)
```

- **R1 y R2 son paralelizables** (módulos independientes en `moodle_service`). Sus
  **parsers puros** se pueden desarrollar con TDD usando las muestras reales de R0.
- **R4 eliminado** (credenciales ya existen).

---

## 5.bis Estado de implementación (2026-06-08) ✅ NÚCLEO COMPLETO

| Fase | Estado |
|------|--------|
| R0 spike | ✅ validado contra Moodle real |
| R1 sesión + export calificador (`moodle_service` + `moodle_bulk_parser`) | ✅ |
| R2 CSV finalización + parser | ✅ |
| R3 `snapshot_service.generar()` orquestación masiva | ✅ (firma: `usuario=` + `sesion=`) |
| R4 credenciales | ✅ eliminado (ya existen) |
| R5 tests + paridad | ✅ 339 unit verdes; **paridad 6/6 idéntica vs flujo viejo** contra Moodle real |
| R6 defensa/limpieza | ✅ User-Agent ASCII; métodos per-alumno marcados legacy (los usan scripts) |

**Bug encontrado y corregido por R5:** el User-Agent con acentos (`integración`) rompía
`httpx` (headers solo ASCII) → habría tirado el snapshot en producción. Ahora es ASCII.

**Matiz a confirmar:** en el curso 38, `enrolled`=831 vs notas/completion=773 uids. La
diferencia (~58) son alumnos suspendidos/sin email (el export usa `export_onlyactive=1`).
Para esos, el modo nuevo da SIN_ACTIVIDAD. Decidir si se incluyen (`onlyactive=0`) o si es
el comportamiento deseado. La muestra de 6 alumnos activos dio paridad perfecta.

Archivos: `app/services/moodle_bulk_parser.py` (nuevo, puro), `app/services/moodle_service.py`
(sesión + 2 descargas), `app/services/snapshot_service.py` (orquestación), routers
`dashboard_gestores.py`, tests `test_moodle_bulk_parser.py` + `test_snapshot_service.py`,
scripts `spike_moodle_bulk.py` + `verify_refactor_paridad.py`.

---

## 6. Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Headers de ambos CSV por **nombre** de actividad (no cmid) → ambigüedad/renombres | Join vía `course_contents` con normalización; log y omisión de duplicados/sin-match. Es el riesgo principal |
| El form del export cambia de campos (`sesskey`/`itemids`) entre versiones de Moodle | Extracción robusta del HTML; si falla, log claro y abortar la materia sin romper el resto |
| La sesión web expira / login falla | Verificar cookie `MoodleSession`; reintentar login 1 vez; si falla, error claro por materia |
| Notas de escala salen como índice numérico en vez de texto | Validado en R0 que `display[real]` da el texto; `estado_tp` ya tolera numérico y texto |
| Romper paridad con el cálculo actual | R5 compara viejo vs nuevo antes de mergear |
```
