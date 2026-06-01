# Plan técnico — "Por entregar": correcciones pendientes de subir a Moodle

> **Alcance:** una funcionalidad nueva sobre Active-IA. NO es una reescritura. Se monta
> **100% sobre lo ya construido** en la integración bidireccional Moodle (tabla `MoodleSync`,
> `MoodleGradeService.subir_correccion/preview_correccion`, `ComentarioTemplateService`,
> `DevolucionLinkService`, `SubirMoodleModal`). **No requiere migración de base de datos.**
>
> **Estado:** plan de implementación. No incluye código todavía.

---

## 1. Problema y objetivo

La corrección masiva ("Corregir todo") deja todas las entregas **CORREGIDA** en Active-IA, pero
el acto de **devolver al alumno** (publicar nota + feedback en Moodle) sigue siendo manual, TP por
TP, entrega por entrega. El tutor no tiene forma de saber, de un vistazo, **qué corrigió que
todavía no devolvió** — menos aún si son de prácticos y materias distintas.

**Objetivo:** una página nueva **"Por entregar"** que liste TODAS las correcciones hechas en
Active-IA que aún **no fueron subidas a Moodle**, sin importar de qué TP/materia/comisión sean,
con dos formas de subirlas: **individual** (reusando el modal existente) y **"Entregar todos"**
masivo (auto para los que llevan comentario automático).

### Insight clave de diseño

A diferencia de "Pendientes (por corregir)", que **consulta Moodle en vivo** (de ahí el SSE y la
barra de progreso al listar), **esta lista es 100% dato local**. Una corrección está "pendiente de
subir" si:

- su `Entrega` está en estado **`CORREGIDA`**, no archivada;
- la entrega vino de Moodle → **`moodle_user_id IS NOT NULL`**;
- la rúbrica y la materia tienen sus IDs de Moodle configurados (`rubrica.moodle_assign_id`,
  `materia.moodle_course_id`); y
- **NO existe** un `MoodleSync` con `estado=ENVIADO` para esa corrección.

Eso se resuelve con **una query a nuestra propia base** → el listado es **instantáneo**. Solo se
toca Moodle al momento de **subir**.

---

## 2. Decisiones tomadas (confirmadas con el usuario)

| # | Tema | Decisión |
|---|------|----------|
| D1 | **Ubicación UX** | **Página nueva** en el sidebar: "Por entregar" (icono tipo `Send`/`UploadCloud`). Roles `TUTOR`, `ADMIN`. Separada de "Pendientes". |
| D2 | **Alcance de subida** | **Individual + "Entregar todos"**. El masivo auto-sube las que llevan comentario automático (TP); las que requieren comentario del tutor (no-TP) quedan para subir a mano y se reportan como omitidas. |
| D3 | **No vinculadas a Moodle** | **Excluir del listado + contador informativo** ("X correcciones no vinculadas a Moodle"). No se muestran como filas; se cuentan aparte para transparencia (regla "sin caps silenciosos"). |

### Supuestos no bloqueantes (fáciles de cambiar)

- **S1** — La nota mostrada en la lista es **local**: nota cruda 0-100 + etiqueta `Aprobado/Desaprobado`
  para TP calculada con `UMBRAL_APROBACION_TP` (= 60, ya en `core/moodle_config.py`). NO se va a Moodle
  a buscar `grade_config` para listar (eso solo pasa al subir, dentro de `subir_correccion`).
- **S2** — `requiere_comentario_tutor` se deriva del **tipo de rúbrica** (TP → automático; no-TP → manual),
  igual que ya lo decide `ComentarioTemplateService.render`.
- **S3** — Si el último `MoodleSync` de una corrección quedó en **`ERROR`**, la fila sigue apareciendo
  (es "pendiente") pero con un badge "Falló el último intento" + el mensaje, para que el tutor reintente.
- **S4** — El masivo reusa la **idempotencia** y los **permisos** ya existentes en `subir_correccion`
  (salta `ENVIADO` con 409 → se captura y cuenta como "ya enviada"; valida `verificar_acceso_comision`).
- **S5** — Concurrencia del masivo: `asyncio.Semaphore` + sesión por tarea (mismo patrón que
  `procesar_global_background`). Sin cola externa.

---

## 3. Arquitectura por capa

Se respeta `Router → Service → Repository → DB`. **No se crean modelos ni migraciones nuevas.**

```
GET  /api/v1/por-entregar            → lista local (instantánea)
POST /api/v1/por-entregar/entregar/stream → SSE masivo (solo comentario automático)
(individual reusa: GET /correcciones/{id}/moodle/preview + POST /correcciones/{id}/moodle)
```

### 3.1 Backend

| Capa | Archivo | Cambio |
|------|---------|--------|
| Repository | `app/repositories/correccion_repository.py` | **+ `get_pendientes_subida_moodle(tutor_id, es_admin)`** y **+ `contar_no_vinculadas_moodle(tutor_id, es_admin)`** |
| Repository | `app/repositories/moodle_sync_repository.py` | **+ `get_ultimo_estado_por_correcciones(ids)`** → dict `{correccion_id: (estado, mensaje_error)}` para etiquetar filas sin N+1 |
| Service | `app/services/por_entregar_service.py` *(nuevo)* | `listar(usuario)` (arma items + contador) y `entregar_masivo_stream(usuario, base_url)` (async generator SSE) |
| Schema | `app/schemas/por_entregar.py` *(nuevo)* | `CorreccionPorEntregaItem`, `PorEntregarResponse` |
| Router | `app/routers/por_entregar.py` *(nuevo)* | `GET /por-entregar`, `POST /por-entregar/entregar/stream` |
| Main | `app/main.py` | registrar el router nuevo |

### 3.2 Frontend

Nueva feature `frontend/src/features/por-entregar/`:

```
por-entregar/
├── pages/PorEntregarPage.tsx
├── components/
│   ├── PorEntregarTable.tsx       (filas agrupadas por materia/comisión)
│   ├── PorEntregarRow.tsx         (fila + botón "Subir" → abre SubirMoodleModal)
│   └── EntregarTodoButton.tsx     (modal + barra de progreso SSE — patrón ImportarButton)
├── hooks/usePorEntregar.ts        (React Query GET /por-entregar)
├── services/por-entregar.service.ts  (getPorEntregar + entregarTodoStream SSE)
└── types/index.ts
```

Reusos directos:
- **`SubirMoodleModal`** (`features/entregas/components/`) ya recibe `entregaId` → se reusa tal cual para el "Subir" individual de cada fila.
- El patrón **SSE del front** (`importarMoodleStream` + barra de progreso de `ImportarButton`) se replica para "Entregar todos".

Rutas y navegación:
- `frontend/src/app/router.tsx`: **+ ruta `/por-entregar` → `PorEntregarPage`** (lazy).
- `frontend/src/shared/components/layout/Sidebar.tsx`: **+ item "Por entregar"** (roles `TUTOR`, `ADMIN`).

---

## 4. Diseño detallado — Backend

### 4.1 Repository — `correccion_repository.py`

**`get_pendientes_subida_moodle(tutor_id: int, es_admin: bool) -> list[Correccion]`**

```
SELECT Correccion
  JOIN Entrega       ON Entrega.id = Correccion.entrega_id
  JOIN Comision      ON Comision.id = Entrega.comision_id
  JOIN Rubrica       ON Rubrica.id = Entrega.rubrica_id
  JOIN Materia       ON Materia.id = Comision.materia_id
WHERE Entrega.estado = 'CORREGIDA'
  AND Entrega.archivado = false
  AND Entrega.moodle_user_id IS NOT NULL
  AND Rubrica.moodle_assign_id IS NOT NULL
  AND Materia.moodle_course_id IS NOT NULL
  AND NOT EXISTS (
        SELECT 1 FROM moodle_sync ms
        WHERE ms.correccion_id = Correccion.id AND ms.estado = 'ENVIADO')
  AND (:es_admin OR EXISTS (
        SELECT 1 FROM comision_tutor ct
        WHERE ct.comision_id = Comision.id AND ct.tutor_id = :tutor_id))
ORDER BY Materia.nombre, Rubrica.titulo, Entrega.alumno_nombre
```
`selectinload`: `entrega.comision.materia`, `entrega.rubrica`. (Sigue el patrón de `get_all`,
líneas 131-198 del repo.)

**`contar_no_vinculadas_moodle(tutor_id, es_admin) -> int`** — mismo `FROM/JOIN` y filtro de tutor,
pero cuenta las `CORREGIDA` no archivadas, sin `ENVIADO`, que **fallan** alguna condición de
subible (`moodle_user_id IS NULL` OR `rubrica.moodle_assign_id IS NULL` OR `materia.moodle_course_id IS NULL`).

### 4.2 Repository — `moodle_sync_repository.py`

**`get_ultimo_estado_por_correcciones(ids: list[int]) -> dict[int, tuple[MoodleSyncEstado, str | None]]`**
— una sola query con `DISTINCT ON (correccion_id) ... ORDER BY correccion_id, id DESC` (o equivalente
con window) para traer el último estado de cada corrección y evitar N+1 al etiquetar filas con ERROR.

### 4.3 Service — `por_entregar_service.py` (nuevo)

**`listar(usuario) -> PorEntregarResponse`** (todo local, sin Moodle):
1. `es_admin = usuario.rol == ADMIN`.
2. `correcciones = repo.get_pendientes_subida_moodle(usuario.id, es_admin)`.
3. `estados = moodle_sync_repo.get_ultimo_estado_por_correcciones([c.id...])`.
4. Por cada corrección, arma `CorreccionPorEntregaItem`:
   - `nota` (0-100), `etiqueta_nota` (TP → `Aprobado`/`Desaprobado` según `UMBRAL_APROBACION_TP`; no-TP → la nota),
   - `requiere_comentario_tutor` (TP=False, no-TP=True),
   - `estado_ultimo_intento` (`none`/`error`) + `mensaje_error` desde `estados`.
5. `no_vinculadas = repo.contar_no_vinculadas_moodle(...)`.
6. Devuelve `PorEntregarResponse(items, total_pendientes, total_automaticas, total_requieren_comentario, no_vinculadas)`.

**`entregar_masivo_stream(usuario, base_url) -> AsyncIterator[dict]`** (SSE, patrón de
`MoodleImportService.importar_stream` + `procesar_global_background`):
1. Recolecta las pendientes **que NO requieren comentario manual** (TP). Emite `{tipo: inicio, total}`.
2. Las que requieren comentario manual → se cuentan como `omitidas_requieren_comentario` (no se tocan).
3. Para cada TP, con `Semaphore` + sesión propia por tarea:
   - genera el comentario con `ComentarioTemplateService.render(...)` + link de `DevolucionLinkService`,
   - llama `MoodleGradeService.subir_correccion(correccion_id=..., comentario_final=..., usuario, base_url, forzar=False)`,
   - mapea resultado: ENVIADO → `enviadas++`; `HTTPException 409` (ya enviada) → `ya_enviadas++`;
     otro error → `errores.append({alumno, motivo})` (NO aborta el lote).
   - emite `{tipo: progreso, procesadas, total}` con `as_completed`.
4. Emite `{tipo: resumen, enviadas, ya_enviadas, omitidas_requieren_comentario, errores[]}`.

> El masivo **no inventa** lógica de envío: delega en `subir_correccion`, que ya valida permisos,
> credenciales, mapeo de nota y arma el feedback HTML con el cierre "devolución".

### 4.4 Schema — `por_entregar.py` (nuevo)

```
CorreccionPorEntregaItem:
  correccion_id, entrega_id, alumno_nombre,
  materia_id, materia_nombre, comision_id, comision_nombre,
  rubrica_id, rubrica_titulo, tipo_rubrica,
  nota: float, etiqueta_nota: str,
  requiere_comentario_tutor: bool,
  estado_ultimo_intento: 'none' | 'error', mensaje_error: str | None,
  corregido_at: datetime

PorEntregarResponse:
  items: list[CorreccionPorEntregaItem]
  total_pendientes: int
  total_automaticas: int            # TP, suben con "Entregar todos"
  total_requieren_comentario: int   # no-TP, subir a mano
  no_vinculadas: int                # contador informativo (excluidas)
```

### 4.5 Router — `por_entregar.py` (nuevo)

| Método | Path | Permiso | Qué hace |
|--------|------|---------|----------|
| GET | `/por-entregar` | `require_any_authenticated` + filtro por tutor en la query | Lista local (instantánea) |
| POST | `/por-entregar/entregar/stream` | idem (cada subida revalida `verificar_acceso_comision`) | SSE masivo (solo TP) |

`current_user = Depends(get_current_user)`. El SSE devuelve `StreamingResponse(media_type="text/event-stream")`
con header `X-Accel-Buffering: no` (igual que `/moodle/importar/stream`).

---

## 5. Diseño detallado — Frontend

### 5.1 `por-entregar.service.ts`
- `getPorEntregar(): Promise<PorEntregarResponse>` → `GET /por-entregar`.
- `entregarTodoStream(handlers)` → `fetch` POST a `/por-entregar/entregar/stream` con JWT por header
  y lectura por chunks (copia exacta del patrón de `importarMoodleStream`).

### 5.2 `usePorEntregar.ts`
- React Query, key `['por-entregar']`, `staleTime` corto (es dato local; se invalida tras subir).

### 5.3 Componentes
- **`PorEntregarPage`**: StatCards (Pendientes / Automáticas / Requieren comentario) + aviso
  "ⓘ N no vinculadas a Moodle" + `EntregarTodoButton` + `PorEntregarTable`. Estados loading/empty/error.
- **`PorEntregarTable` / `PorEntregarRow`**: filas con alumno, materia, comisión, TP, nota/etiqueta,
  badge de error si corresponde, y botón **"Subir"** → abre `SubirMoodleModal` (reuso) con el `entregaId`.
  Tras éxito, `invalidateQueries(['por-entregar'])`.
- **`EntregarTodoButton`**: modal con barra de progreso SSE (patrón `ImportarButton`); al cerrar,
  invalida `['por-entregar']` y `['entregas']`. Muestra resumen (enviadas / ya enviadas /
  omitidas-requieren-comentario / errores desplegables).

### 5.4 Navegación
- `router.tsx`: ruta `/por-entregar` (lazy).
- `Sidebar.tsx`: item nuevo, roles `TUTOR`, `ADMIN`. Texto sugerido "Por entregar".

---

## 6. Plan de tareas (TDD)

> Estricto TDD donde hay lógica testeable. Recordatorio: el conftest usa SQLite y los modelos usan
> JSONB/ARRAY/enums PG → los tests de repo que tocan esas columnas se marcan/omiten igual que la deuda
> ya documentada; la lógica de service se testea con repos mockeados.

| # | Tarea | Capa | Test primero |
|---|-------|------|--------------|
| T1 | `get_pendientes_subida_moodle` + `contar_no_vinculadas_moodle` | Repo | sí (con datos sembrados) |
| T2 | `get_ultimo_estado_por_correcciones` | Repo | sí |
| T3 | `PorEntregarService.listar` (etiquetas, requiere_comentario, contador) | Service | sí (repo mock) |
| T4 | `PorEntregarService.entregar_masivo_stream` (TP auto, no-TP omitido, 409 ya enviada, error no aborta) | Service | sí (mock `subir_correccion`) |
| T5 | Endpoints `GET /por-entregar` + `POST .../entregar/stream` | Router | sí |
| T6 | `main.py` registra router | Router | — |
| T7 | Frontend: types + service (`getPorEntregar`, `entregarTodoStream`) | FE | — |
| T8 | Frontend: hook + página + tabla + fila (reuso `SubirMoodleModal`) | FE | — |
| T9 | Frontend: `EntregarTodoButton` con barra de progreso | FE | — |
| T10 | Ruta + item de sidebar | FE | — |

---

## 7. Criterios de aceptación

| # | Criterio |
|---|----------|
| CA1 | La página "Por entregar" lista **instantáneamente** (sin tocar Moodle) las correcciones `CORREGIDA` del tutor que aún no fueron subidas (`ENVIADO`), de **todas** las materias/TP juntas. |
| CA2 | El tutor solo ve correcciones de **sus** comisiones; ADMIN ve todas. |
| CA3 | Las correcciones **no vinculadas** a Moodle NO aparecen como filas, pero se muestra el **contador**. |
| CA4 | Cada fila tiene "Subir" que abre el modal existente y, al enviar, **desaparece de la lista** (se creó `MoodleSync ENVIADO`). |
| CA5 | "Entregar todos" sube en bloque solo las de **comentario automático** (TP), con barra de progreso, sin abortar el lote ante un error puntual; reporta enviadas / ya enviadas / omitidas-requieren-comentario / errores. |
| CA6 | Una corrección cuyo último intento fue **ERROR** sigue listada con badge y mensaje, y se puede reintentar. |
| CA7 | Idempotencia: subir dos veces no duplica; la segunda informa "ya enviada" (salvo `forzar`). |
| CA8 | No se introduce ninguna migración ni modelo nuevo. |

---

## 8. Lo que NO entra en este alcance

- Adjuntar el PDF de devolución como archivo en Moodle (sigue siendo link "devolución" en el feedback).
- Subida masiva de no-TP con comentario manual (por diseño: requieren texto del tutor → individual).
- Re-sincronización automática de re-entregas posteriores a un envío.
- Notificaciones/push al alumno más allá de lo que Moodle haga al calificar.
