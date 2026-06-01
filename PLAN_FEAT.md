# Plan técnico — Integración bidireccional Moodle + clasificación de API Key Gemini

> **Alcance:** 3 funcionalidades sobre Active-IA. NO es una reescritura. Se apoya en los
> patrones existentes (Clean Architecture, `MoodleService`, `EntregaService`,
> `CorreccionService`, feature modules + TanStack Query).
>
> **Estado:** plan de implementación. No incluye código todavía.

---

## 1. Supuestos y ambigüedades a confirmar

Estos puntos cambian el diseño según la respuesta. **Hay que cerrarlos antes de codear.**

### 1.1 Bloqueantes (afectan arquitectura)

| # | Tema | Ambigüedad | Supuesto por defecto del plan |
|---|------|-----------|-------------------------------|
| A1 | **Descarga de archivos Moodle** | El código actual de `mod_assign_get_submissions` sólo cuenta; no extrae `fileurls`. | ✅ **CONFIRMADO (Fase 0)** contra `tup.sied.utn.edu.ar`. La submission expone `plugins[type=file].fileareas[].files[].fileurl`; la descarga con `?token=` devuelve HTTP 200 + bytes. Keys útiles de la submission: `userid` (→ A4 `moodle_user_id`), `attemptnumber` (→ re-entregas), `gradingstatus`, `timemodified`. El nombre del alumno se resuelve por `userid`→`core_enrol`, NO del filename. |
| A2 | **Clasificación API key paga/gratuita** | El criterio "Pro responde ⇒ paga" es frágil. | ❌ **REFUTADO empíricamente (Fase 0):** en la 1ª corrida Pro devolvió **429 RESOURCE_EXHAUSTED** (rate limit, NO falta de acceso) → la heurística marcó "GRATUITA" sin fundamento. **La API de Gemini no expone el tier de billing.** Decisión revisada: clasificación automática sólo informativa (ACCESIBLE / RATE_LIMITED / INVÁLIDA), y "Corregir todo" se gatea por un **toggle manual "key paga"** declarado por el tutor (ver §8). |
| A3 | **Escala cualitativa en Moodle (Aprobado/Desaprobado)** | Tipo de escala por assignment + textos/orden de la escala. | ✅ **CONFIRMADO TOTAL (Fase 0):** TP = cualitativos (`grade=-5`, scale_id=5); exámenes = numéricos (`grade=100`); Trabajo Integrador = numérico **máx 10** (¡no 100!). Escala 5: **`índice 1='Aprobado'`, `índice 2='Desaprobado'` (orden invertido)**. Reglas firmes en §7. |
| A4 | **Mapeo `alumno_nombre` ↔ `moodle_user_id`** | Para subir nota a Moodle se necesita el `userid` de Moodle, pero `Entrega` sólo guarda `alumno_nombre`. | Se agrega columna `moodle_user_id` (nullable) a `Entrega`, poblada en la importación. Para entregas cargadas manualmente se resuelve por `fullname` con fallback y error si es ambiguo. |
| A5 | **Accesibilidad del PDF de devolución para el alumno** | El endpoint actual `/documentos/correcciones/{id}/pdf` exige JWT de Active-IA → un alumno de Moodle no puede abrirlo. | Endpoint público con **token firmado** (HMAC sobre `correccion_id` + expiración), sin sesión. Evolución futura: adjuntar el PDF como `assignfeedback_file` en Moodle. |

### 1.2 No bloqueantes (se asumen, fáciles de cambiar)

- **A6** — Re-entregas Moodle: NO se sobrescriben automáticamente entregas ya `CORREGIDA`. Se reportan en categoría aparte `reentrega` y el tutor decide.
- **A7** — Permisos: hoy los endpoints de entregas/correcciones **no validan que el tutor esté asignado a la comisión** (cualquier autenticado accede). Para las funciones nuevas se agrega validación de pertenencia (`ComisionTutor`) + bypass para ADMIN. Se recomienda extender esa validación a los endpoints existentes (fuera de alcance estricto, pero anotado).
- **A8** — Concurrencia de corrección paga: se usa `asyncio.Semaphore` con concurrencia configurable, en lugar del `sleep(7)` secuencial. Sin cola externa (Celery/Redis): los jobs viven en el proceso (riesgo documentado en §12).
- **A9** — Plantillas de comentario TP: se guardan **configurables** (tabla/JSON), con los textos del prompt como seed por defecto. Escala 0-100, `>= 60` aprueba.

---

## 2. Arquitectura por capa

### 2.1 Backend (FastAPI, Clean Architecture)

Se respeta `Router → Service → Repository → DB`. Se **extiende** `MoodleService` (lectura) y se crean servicios nuevos para la escritura.

```
Routers nuevos/extendidos
├── routers/moodle_import.py      (NUEVO)  importar pendientes
├── routers/correcciones.py       (EXT)    + subir a Moodle, + corrección global
├── routers/perfil.py             (EXT)    clasificación tipo API key
└── routers/public_docs.py        (NUEVO)  PDF público con token firmado

Services
├── services/moodle_service.py            (EXT)  + descarga archivos, + map userid/fullname
├── services/moodle_grade_service.py      (NUEVO) subir nota+feedback a Moodle, mapeo escala
├── services/moodle_import_service.py     (NUEVO) orquesta descarga → EntregaService
├── services/entrega_service.py           (EXT)  método interno que acepta bytes (no sólo UploadFile)
├── services/correccion_service.py        (EXT)  corrección global (cross-rubrica) + concurrencia
├── services/gemini_classifier_service.py (NUEVO) clasificación paga/gratuita/error
├── services/comentario_template_service.py (NUEVO) render de plantillas por tipo de rúbrica
└── services/devolucion_link_service.py   (NUEVO) genera/valida token firmado del PDF

Repositories
├── repositories/moodle_sync_repository.py (NUEVO) auditoría de sincronización
├── repositories/entrega_repository.py     (EXT)  query: SUBIDA del tutor cross-comisión
└── repositories/correccion_repository.py  (EXT)  estado de sync
```

**Regla clave:** `moodle_import_service` y `moodle_grade_service` NO acceden a DB directo; usan repositories y reutilizan `EntregaService`. Los routers sólo validan permisos + delegan.

### 2.2 Frontend (React + TS strict + Tailwind + TanStack Query)

```
features/pendientes/        (EXT)
├── components/ComisionRow.tsx      + botón "Importar pendientes"
├── components/MateriaBlock.tsx     + botón "Importar materia"
├── components/ImportarModal.tsx    (NUEVO) progreso + resumen
└── hooks/useImportarMoodle.ts      (NUEVO)

features/entregas/          (EXT)
├── pages/EntregasPage.tsx          + acción "Subir corrección a Moodle"
├── components/SubirMoodleModal.tsx (NUEVO) nota + comentario editable + link devolución
└── hooks/useSubirCorreccionMoodle.ts (NUEVO)

features/dashboard/         (EXT)
└── components/DashboardTutor.tsx   + botón "Corregir todo (API Key paga)"

features/perfil/            (EXT)
└── PerfilPage.tsx                  + badge tipo de key (Paga/Gratuita/Inválida)
```

### 2.3 Integraciones

- **Moodle WS** (lectura): `mod_assign_get_submissions` (extendido para extraer files), `core_enrol_get_enrolled_users` (extendido para `fullname`), `pluginfile.php` (descarga).
- **Moodle WS** (escritura): `mod_assign_save_grade`, `mod_assign_get_assignments` (campo `grade` para detectar escala).
- **Gemini REST**: `:generateContent` con modelos configurables para clasificación.
- **N8N**: sin cambios en el webhook; sólo cambia cómo se orquesta el lote.

---

## 3. Modelo de datos y migraciones

Todas las columnas nuevas son **nullable** → migraciones sin backfill, sin breaking changes.

### 3.1 `Entrega` — nuevo campo

| Campo | Tipo | Nullable | Motivo |
|-------|------|----------|--------|
| `moodle_user_id` | `Integer` | sí | Mapeo directo a Moodle para subir nota (A4). Poblado en importación. |

### 3.2 Nueva tabla `moodle_sync` (auditoría + idempotencia)

Relación con `Correccion` (N:1 para historial de intentos).

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | PK | |
| `correccion_id` | FK → correcciones.id | |
| `estado` | Enum `MoodleSyncEstado` | `PENDIENTE` / `ENVIADO` / `ERROR` |
| `nota_enviada` | `Numeric(5,2)` o `String` | numérica o "Aprobado"/"Desaprobado" |
| `comentario_enviado` | `Text` | el feedback final publicado |
| `moodle_assignment_id` | `Integer` | instance id usado |
| `moodle_user_id` | `Integer` | |
| `mensaje_error` | `Text` nullable | |
| `intento` | `Integer` | nº de intento |
| `enviado_por_id` | FK → usuarios.id | |
| `created_at` / `updated_at` | timestamp | |

**Idempotencia / anti doble-envío:** antes de enviar se consulta si existe `moodle_sync` con `estado=ENVIADO` para esa corrección → se bloquea salvo `forzar=true` explícito.

### 3.3 Plantillas de comentario (A9)

**Decisión confirmada:** plantillas en **JSON/config en código** (no tabla DB). Sin migración.

Estructura (constante en `app/core/comentario_templates.py` o en `settings`):
```python
COMENTARIO_TEMPLATES = {
  "TP": [
    {"min": 90, "max": 100, "texto": "Excelente {nombre_alumno}!\nTe dejo tu devolución: {link_devolucion}"},
    {"min": 81, "max": 89,  "texto": "Muy bien {nombre_alumno}!\nTe dejo tu devolución: {link_devolucion}"},
    {"min": 71, "max": 80,  "texto": "Bien {nombre_alumno}!\nTe dejo tu devolución: {link_devolucion}"},
    {"min": 60, "max": 70,  "texto": "Bien {nombre_alumno}! Revisá con detalle tu entrega PDF.\nTe dejo tu devolución: {link_devolucion}"},
    {"min": 0,  "max": 59,  "texto": "Hola {nombre_alumno}, revisá tu entrega PDF para poder realizar la reentrega del TP.\nTe dejo tu devolución: {link_devolucion}"},
  ],
  "DEFAULT": {"requiere_comentario_tutor": True, "cierre": "Te dejo tu devolución: {link_devolucion}"},
}
```

> **Trade-off aceptado:** cambiar un texto requiere deploy. A cambio, cero migraciones y validación estática.

### 3.4 `Usuario` — key paga (toggle manual, decisión confirmada)

| Campo | Tipo | Notas |
|-------|------|-------|
| `gemini_api_key_paga` | `Boolean` default `False` | **Toggle manual** declarado por el tutor ("mi key tiene billing"). Gatea "Corregir todo". |

`gemini_api_key_valid` (existente) se sigue usando para validación funcional de la key.
**No** se agrega enum de tier: la Fase 0 demostró que el tier no es detectable vía API.

### 3.5 Migraciones Alembic (orden)

1. `add_moodle_user_id_to_entrega`
2. `create_moodle_sync_table` (+ enum)
3. `add_gemini_tier_to_usuario` (+ enum)

> Las plantillas de comentario NO requieren migración (van en JSON/config — §3.3).

---

## 4. Endpoints

### 4.1 Nuevos

| Método | Ruta | Descripción | Permiso |
|--------|------|-------------|---------|
| `POST` | `/api/moodle/importar` | Importa pendientes a Active-IA según scope | Tutor de la comisión / Admin |
| `POST` | `/api/correcciones/{id}/moodle` | Sube nota + feedback a Moodle | Tutor de la comisión / Admin |
| `GET` | `/api/correcciones/{id}/moodle/preview` | Devuelve nota a enviar + comentario sugerido + link devolución | Tutor / Admin |
| `POST` | `/api/correcciones/global` | Corrige todos los `SUBIDA` del tutor (cross-rubrica) | Tutor (con key) / Admin |
| `GET` | `/api/correcciones/global/progreso` | Conteo de estados para feedback de progreso | Tutor / Admin |
| `GET` | `/api/public/devoluciones/{token}` | PDF público vía token firmado (sin JWT) | Público (token válido) |

**Request `POST /api/moodle/importar`** (scope flexible, un solo endpoint):
```jsonc
{
  "scope": "comision_unidad" | "materia" | "tutor",
  "rubrica_id": 12,      // requerido si scope=comision_unidad
  "comision_id": 5,      // requerido si scope=comision_unidad
  "materia_id": 3        // requerido si scope=materia
}
```
**Response (resumen):**
```jsonc
{
  "descargadas": 50, "cargadas": 44,
  "omitidas_ya_corregidas": 4, "duplicadas": 1,
  "reentregas": 1, "errores": [{ "alumno": "...", "motivo": "..." }],
  "detalle_por_rubrica": [ { "rubrica_id": 12, "cargadas": 10, ... } ]
}
```

### 4.2 Modificados

- `POST /api/correcciones/lote` — sin cambios (se mantiene límite 50 para flujo manual).
- `POST /api/perfil/api-key` — valida la key (flash) y guarda `gemini_api_key_valid`.
- `PATCH /api/perfil/key-paga` — setea el toggle manual `gemini_api_key_paga`.
- `GET /api/perfil` — expone `gemini_api_key_valid` y `gemini_api_key_paga`.

---

## 5. Servicios / repositories a crear o extender

### 5.1 `MoodleService` (extender)

- `get_submissions_with_files(token, host, assignment_instance_id, group_member_ids) -> list[SubmissionFile]`
  Extrae `userid`, `fullname`, `status`, `timemodified`, lista de `fileurl`. Reutiliza el cache de token y de miembros, pero **el cache de miembros pasa a guardar `{userid: fullname}`** (hoy guarda sólo `set[userid]`).
- `download_submission_file(token, fileurl) -> bytes` — `GET {fileurl}` agregando `token={wstoken}`. Manejo de timeout/404.
- `get_assignment_grade_config(token, host, course_id, cmid) -> {tipo: "numerica"|"escala", scale_id, max}` — usa el campo `grade` de `mod_assign_get_assignments` (ya cacheado).

**Seguridad:** la password Moodle se descifra sólo dentro de `get_token` (ya implementado). **Nunca** loguear token, password ni `fileurl` con token.

### 5.2 `MoodleImportService` (nuevo)

Orquesta: resolver scope → para cada (rubrica, comisión) con IDs Moodle → traer submissions con files → por alumno descargar → delegar a `EntregaService`. Clasifica resultado (cargada/omitida/duplicada/reentrega/error).

### 5.3 `EntregaService` (extender)

- Refactor: extraer `_crear_desde_bytes(comision_id, rubrica_id, alumno_nombre, filename, contenido_bytes, moodle_user_id, ...)` que reciba **bytes + filename** en lugar de `UploadFile`. El método público actual `crear_entrega_individual(UploadFile)` se reescribe para leer bytes y llamar al interno. Así la importación reutiliza consolidación/PDF base64/idempotencia/historial **sin duplicar lógica**.
- Reusa la regla existente: si la entrega ya tiene `correccion` → no sobrescribe (se reporta `omitida_ya_corregida`).

### 5.4 `MoodleGradeService` (nuevo)

- `subir_correccion(correccion_id, comentario_final, nota_override, usuario, forzar=False)`:
  1. Carga corrección + entrega + rúbrica + comisión + materia.
  2. Resuelve `moodle_user_id` (de `Entrega` o por `fullname`).
  3. Mapea nota según tipo de rúbrica y escala del assignment (§7).
  4. Verifica idempotencia (`moodle_sync` ENVIADO) salvo `forzar`.
  5. Llama `mod_assign_save_grade` con `plugindata[assignfeedbackcomments_editor]`.
  6. Registra `moodle_sync` (ENVIADO / ERROR + mensaje).

### 5.5 Validación de key Gemini (extender perfil existente)

`validar(api_key) -> bool` con un modelo flash barato → actualiza `gemini_api_key_valid`. El toggle
`gemini_api_key_paga` es declarado por el tutor (no se infiere). Nunca loguea la key. No hay servicio de "tier".

### 5.6 `ComentarioTemplateService` (nuevo)

`render(tipo_rubrica, nota, nombre_alumno, link_devolucion) -> {comentario, requiere_comentario_tutor}` según §7. Lee de `COMENTARIO_TEMPLATES` (JSON/config, §3.3) — sin acceso a DB.

### 5.7 `DevolucionLinkService` (nuevo)

- `generar(correccion_id, ttl_dias) -> str` (token HMAC firmado con `SECRET_KEY`).
- `validar(token) -> correccion_id` (verifica firma + expiración).

### 5.8 Repositories

- `MoodleSyncRepository` (CRUD + `get_ultimo_por_correccion`).
- `EntregaRepository.get_subidas_by_tutor(tutor_id) -> list[Entrega]` (join `ComisionTutor`, estado `SUBIDA`, no archivadas) para corrección global.

---

## 6. Flujo de importación desde Moodle (paso a paso)

1. **Tutor** en `/pendientes` clickea "Importar" en una comisión/unidad (o "Importar materia" / "Importar todo").
2. Frontend → `POST /api/moodle/importar` con el scope.
3. Router valida: usuario autenticado + (tutor asignado a la comisión **o** admin). Si no → 403.
4. `MoodleImportService` resuelve el scope a una lista de `(rubrica, comisión)` con IDs Moodle configurados (ignora las que no tienen, igual que el endpoint de pendientes).
5. Para cada par: token (cache) → `cmid→instance_id` (cache) → miembros del grupo `{userid: fullname}` (cache).
6. `get_submissions_with_files`: filtra `status=submitted` y pendientes de corrección (misma lógica de "espera" del conteo actual).
7. Por alumno pendiente:
   - Resolver `alumno_nombre` desde `fullname` (normalizado title-case, consistente con carga masiva).
   - ¿Existe `Entrega` por `(rubrica_id, alumno_nombre)`?
     - **Sí + tiene corrección** → `omitida_ya_corregida` (o `reentrega` si `timemodified` Moodle > fecha corrección).
     - **Sí + sin corrección** → `duplicada` (no se re-descarga salvo flag futuro).
     - **No** → descargar archivo(s) → `EntregaService._crear_desde_bytes(...)` con `estado=SUBIDA` + `moodle_user_id`.
   - Si la descarga falla (timeout/404) → `error` con motivo.
8. `MoodleImportService` arma el resumen y lo devuelve.
9. Frontend muestra `ImportarModal` con el resumen (cargadas/omitidas/duplicadas/reentregas/errores) e invalida `['pendientes-moodle']` y `['entregas']`.

**Multi-archivo por alumno:** si Moodle devuelve varios files, se consolidan en un ZIP en memoria y se delega igual que la carga masiva actual.

---

## 7. Flujo de subida de corrección a Moodle (paso a paso)

1. En `EntregasPage`, para una entrega `CORREGIDA`, el dropdown muestra **"Subir corrección a Moodle"**.
2. Click → `GET /api/correcciones/{id}/moodle/preview` → devuelve:
   - `nota_a_enviar` (ya mapeada: numérica o Aprobado/Desaprobado).
   - `comentario_sugerido` (render de plantilla).
   - `requiere_comentario_tutor` (true para no-TP).
   - `link_devolucion` (token firmado).
3. Se abre `SubirMoodleModal`:
   - Muestra la nota final.
   - Textarea editable con el comentario sugerido (incluye `Te dejo tu devolución: {link}`).
   - Si `requiere_comentario_tutor` y el textarea está vacío → botón "Enviar" deshabilitado.
4. "Enviar corrección" → `POST /api/correcciones/{id}/moodle` con `{ comentario, forzar?: bool }`.
5. `MoodleGradeService`:
   - Mapeo de nota (**leer SIEMPRE el campo `grade` del assignment vía `mod_assign_get_assignments`, nunca asumir**):
     - **TP / assignment cualitativo** (`grade < 0`): `nota >= 60 ⇒ "Aprobado"`, `< 60 ⇒ "Desaprobado"`. Se envía el **índice 1-based** del ítem en scale_id=`abs(grade)` (mapeo configurable, ver §7.4). Confirmado en TUP: TP usan scale_id=5.
     - **No-TP / assignment numérico** (`grade > 0`): se envía la nota **numérica vigente** en Active-IA **escalada al máximo real del assignment**: `grade_moodle = nota_active_ia / 100 * grade_max`. Confirmado en TUP: parciales `grade_max=100` (queda igual) pero el Trabajo Integrador `grade_max=10` (ej. 90 → 9.0). **No asumir 100.**
   - Validación de escala: si el tipo real del assignment no coincide con lo esperado para el tipo de rúbrica → error 422 con mensaje claro (no se envía a ciegas).
   - Idempotencia: si ya hay `moodle_sync=ENVIADO` y no `forzar` → 409 "Ya fue enviada".
   - `mod_assign_save_grade` con `plugindata[assignfeedbackcomments_editor][text]=comentario` (HTML, format=1).
   - Registra `moodle_sync`.
6. Frontend muestra éxito/error y marca visualmente la entrega como "sincronizada" (badge a partir del estado de `moodle_sync`).

### 7.1 Plantillas TP (escala 0-100, seed por defecto)

| Banda | Comentario |
|-------|-----------|
| `>= 90` | `Excelente {nombre_alumno}!` + `Te dejo tu devolución: {link_devolucion}` |
| `81–89` | `Muy bien {nombre_alumno}!` + link |
| `71–80` | `Bien {nombre_alumno}!` + link |
| `60–70` | `Bien {nombre_alumno}! Revisá con detalle tu entrega PDF.` + link |
| `< 60` | `Hola {nombre_alumno}, revisá tu entrega PDF para poder realizar la reentrega del TP.` + link |

### 7.2 Plantillas no-TP (`PARCIAL_*`, `RECUPERATORIO_*`, `FINAL`, `GLOBAL`)

- Sin comentario de evaluación predeterminado.
- Puede aparecer sólo el cierre: `Te dejo tu devolución: {link_devolucion}`.
- **El tutor debe escribir un comentario propio** antes de enviar (`requiere_comentario_tutor=true`).

### 7.3 Link de devolución (A5)

- Token firmado HMAC (`SECRET_KEY`) que codifica `correccion_id` + `exp`.
- `GET /api/public/devoluciones/{token}` valida firma+exp y hace stream del PDF (reutiliza `PDFService.generar_pdf_devolucion`). **No** expone otros alumnos: el token mapea a una sola corrección.
- TTL configurable (default 90 días). Sin JWT.

### 7.4 Mapeo de escalas Moodle (config) — confirmado en TUP

Las escalas cualitativas no tienen WS simple para leer sus textos, así que el índice va en **config** (junto a los modelos Gemini, §8.1). Estructura:
```python
MOODLE_SCALE_MAP = {
  # scale_id: índice 1-based de cada resultado. ⚠️ El orden NO es intuitivo (ver abajo).
  5: {"aprobado": 1, "desaprobado": 2, "items": ["Aprobado", "Desaprobado"]},
}
```
- `mod_assign_save_grade` recibe el **índice** (`grade=<indice>.0`), no el texto.
- ⚠️ **CONFIRMADO Fase 0 (scale_id=5):** `índice 1 = 'Aprobado'`, `índice 2 = 'Desaprobado'`.
  El orden está **invertido** respecto a lo intuitivo (1 NO es el reprobado). Asumir lo contrario
  habría desaprobado a todos los aprobados. Por eso el índice va en config explícita, nunca hardcodeado por "lógica".
- Regla TP: `nota >= 60 ⇒ grade=1` (Aprobado); `nota < 60 ⇒ grade=2` (Desaprobado).
- Si un assignment usa un `scale_id` que no está en `MOODLE_SCALE_MAP` → 422 "escala no mapeada" (no se envía).

---

## 8. Clasificación de API Key Gemini + corrección masiva global

### 8.1 Estado de la API key (REVISADO tras refutar A2 en Fase 0)

Modelos **configurables por entorno**. ✅ **Confirmado en Fase 0 (ListModels):** los alias `-latest`
del prompt SÍ existen en la API (no estaban en la doc, pero la key los expone). Se usan como defaults
por ser auto-actualizables:
```
GEMINI_MODEL_PRO=gemini-pro-latest          # existe. Versionado predecible: gemini-2.5-pro
GEMINI_MODEL_FLASH=gemini-flash-lite-latest # existe. Versionado predecible: gemini-2.5-flash-lite
```
> Trade-off: `-latest` se actualiza solo (menos mantenimiento) pero puede cambiar de comportamiento sin
> aviso; para producción podría preferirse versionar. Por eso es env. Los `gemini-2.0-*` se apagan 2026-06-01.

**Clasificación: NO se infiere "PAGA" automáticamente.** En Fase 0, Pro devolvió `429 RESOURCE_EXHAUSTED`
(rate limit, no falta de acceso) → la heurística "Pro responde ⇒ paga" marcó "GRATUITA" sin fundamento.
**La API de Gemini no expone el tier de billing.** El clasificador queda **sólo informativo**:
1. `POST :generateContent` sobre `GEMINI_MODEL_FLASH` (barato) → valida que la key **funciona**.
2. Estado: `ACCESIBLE` (200) / `RATE_LIMITED` (429, reintentable) / `INVALIDA` (400/403 API key).
3. Se guarda como dato informativo en el perfil; **no** gatea funcionalidad crítica.

> Decisión confirmada: la validación sólo actualiza `gemini_api_key_valid` (ya existe). La habilitación
> de "Corregir todo" se decide por **toggle manual** `gemini_api_key_paga` (§8.2). Sin badge de tier ni enum nuevo.

### 8.2 Corrección masiva global (key paga)

- Endpoint `POST /api/correcciones/global` reúne **todos** los `SUBIDA` del tutor (cross-materia/comisión/rúbrica) vía `EntregaRepository.get_subidas_by_tutor`.
- Reutiliza `corregir_individual` (ya lee la rúbrica de **cada** entrega → respeta la rúbrica correcta).
- **Diferencia con el lote actual** (límite 50, secuencial, `sleep(7)`):
  - Sin límite 50 (configurable `GLOBAL_BATCH_MAX`, ej. 200).
  - Concurrencia con `asyncio.Semaphore(GEMINI_PAID_CONCURRENCY)` (ej. 5–8) en vez de secuencial.
  - `sleep` reducido/condicional según tier.
  - Manejo 429: backoff exponencial; si persiste, baja concurrencia a 1 y continúa (no aborta todo).
  - 402 (key inválida): aborta y marca `gemini_api_key_valid=False`.
- **Progreso:** `GET /api/correcciones/global/progreso` devuelve `{ total, subidas, pendientes, corregidas, error }` del tutor. El frontend hace polling (reutiliza patrón existente de `EntregasPage`, generalizado para no filtrar por comisión/rúbrica).
- Dashboard tutor: en el banner amarillo, botón **"Corregir todo (API Key paga)"** visible sólo si `gemini_api_key_paga=True` (toggle manual) y `subidas > 0`. Muestra `Pendientes: N por corregir`.

> **No se rompe el flujo actual:** `/lote` queda intacto para correcciones manuales por rúbrica.

---

## 9. Estados de UI, modales, botones, errores

### 9.1 Importar pendientes
- Botones "Importar" (comisión), "Importar materia", "Importar todo" (dashboard/pendientes).
- `ImportarModal`: estado `idle → importando (spinner + texto) → resumen`.
- Resumen con contadores y lista colapsable de errores (patrón de `UploadResultView`).
- Errores: 403 (no asignado), 424 (sin credenciales Moodle → CTA a `/perfil`), 502 (Moodle offline).

### 9.2 Subir corrección a Moodle
- Acción en dropdown de entrega `CORREGIDA`.
- `SubirMoodleModal`: nota (readonly), comentario (editable), link devolución (readonly, copiable).
- Botón "Enviar" deshabilitado si no-TP y comentario vacío.
- Estados: enviando → éxito (badge "Sincronizado") / error (toast + detalle).
- 409 "Ya enviada" → ofrece "Reenviar" (forzar).

### 9.3 Perfil
- Estado de la key: **Configurada/válida** (verde) o **Inválida** (rojo) — validación funcional existente.
- **Toggle** "Mi API key tiene facturación habilitada (paga)" con texto aclaratorio: "Actívalo sólo si habilitaste billing en Google Cloud; habilita la corrección masiva 'Corregir todo'." Sin detección automática.

### 9.4 Dashboard tutor
- Banner amarillo existente + `Pendientes: N por corregir` + botón "Corregir todo (API Key paga)" (condicional).
- Barra/contador de progreso durante la corrección global.

---

## 10. Idempotencia, reintentos y errores

| Área | Estrategia |
|------|-----------|
| Importación | Índice único `(rubrica_id, alumno_nombre)`; no re-descarga duplicadas; no sobrescribe corregidas. |
| Subida a Moodle | `moodle_sync=ENVIADO` bloquea reenvío salvo `forzar`. Cada intento queda auditado. |
| Descarga archivos | Reintento con backoff ante timeout; 404 → marca error por alumno y continúa. |
| Corrección global | Reusa transición SUBIDA→PENDIENTE→CORREGIDA/ERROR; 429 backoff + degradación; 402 aborta. |
| Token PDF | Firma HMAC + expiración; token inválido/expirado → 404/410. |
| Moodle offline / token vencido / permisos | Excepciones tipadas (`MoodleAuthError`, `MoodleConnectionError`) → 424/502 con mensaje claro. |
| Escala no coincide | 422 con detalle; no se envía nota a ciegas. |

---

## 11. Testing

### Backend (pytest, async)
- **Unit**: `ComentarioTemplateService` (todas las bandas TP + no-TP), `DevolucionLinkService` (firma válida/alterada/expirada), mapeo de nota numérica vs escala, `GeminiClassifierService` (Pro ok / Pro falla+Flash ok / ambos fallan) con httpx mockeado.
- **Service**: `MoodleImportService` con `MoodleService` mockeado → verifica clasificación de resultados (cargada/omitida/duplicada/reentrega/error) e idempotencia. `MoodleGradeService` → idempotencia (no doble envío), payload correcto a `mod_assign_save_grade`.
- **Integración (router)**: permisos (tutor no asignado → 403; admin ok), 424 sin credenciales, 409 reenvío.
- Mockear **toda** llamada externa a Moodle/Gemini (httpx). Nunca pegar a la red en tests.

### Frontend (Vitest + RTL)
- `ImportarModal`: idle/loading/resumen/errores.
- `SubirMoodleModal`: botón deshabilitado si no-TP sin comentario; envío ok/error.
- Badge de tier en perfil.
- Hooks: estados de mutation y manejo 402/429/409.

---

## 12. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|-----------|
| **Tier de key no detectable vía API (A2, refutado)** | Alto | Toggle manual `gemini_api_key_paga` declarado por el tutor + job global SIEMPRE resiliente a 429 (backoff + degradar concurrencia). Nada depende de adivinar el tier. |
| **Escala Moodle desconocida (A3)** | Alto | Detección por campo `grade` + mapeo configurable + 422 si no coincide. Verificar escala real del TUP antes de release. |
| **`fileurl` no disponible / formato distinto (A1)** | Alto | Verificación temprana con llamada real; el método de descarga aislado en `MoodleService` para ajustar sin tocar el resto. |
| **Mismatch nombre alumno (A4)** | Medio | `moodle_user_id` poblado en importación; fallback por fullname con error explícito si ambiguo. |
| **Background tasks se pierden al reiniciar el proceso** | Medio | Documentado; los estados de entrega quedan consistentes (re-disparable). Evolución: Celery/Redis. |
| **Link PDF público filtra datos** | Alto | Token mapea a una sola corrección; firma HMAC + expiración; sin listado. |
| **Credenciales/keys en logs** | Alto | Prohibido loguear password Moodle, token, `fileurl` con token, y API key. Revisión en code review. |
| **Permisos laxos heredados (A7)** | Medio | Validación de pertenencia en endpoints nuevos; recomendación de extender a existentes. |
| **Saturar N8N/Gemini en global** | Medio | Semaphore + backoff + degradación a concurrencia 1. |

---

## 13. Criterios de aceptación

1. Un tutor con credenciales Moodle puede importar las pendientes de una comisión/unidad, una materia o todas; las `Entrega` quedan en `SUBIDA` con `rubrica_id`, `comision_id` y `moodle_user_id` correctos.
2. La importación **no** sobrescribe entregas `CORREGIDA`, no duplica por `(rubrica_id, alumno_nombre)`, y reporta resumen con cargadas/omitidas/duplicadas/reentregas/errores.
3. Desde una entrega `CORREGIDA`, el tutor abre el modal, ve la nota a enviar y el comentario sugerido (plantilla según tipo), lo edita y envía; Moodle recibe nota + feedback con el link de devolución.
4. Para TP la nota se envía como Aprobado/Desaprobado (`>=60`); para no-TP se envía la nota numérica vigente (incluyendo ediciones del tutor). Si la escala del assignment no coincide, el sistema responde 422 sin enviar.
5. El link de devolución abre el PDF correcto **sin** sesión Active-IA, expira, y no expone otros alumnos.
6. No se puede enviar dos veces la misma corrección sin `forzar`; cada envío queda en `moodle_sync` con estado/fecha/usuario/error.
7. Al guardar una API key, el perfil muestra Paga/Gratuita/Inválida.
8. Con key clasificada Paga y entregas `SUBIDA`, "Corregir todo" encola todas (cross-rúbrica), procesa respetando cada rúbrica, muestra progreso y refleja resultados por rúbrica; un 429 no aborta todo el job.
9. Permisos: un tutor no asignado a la comisión recibe 403 al importar o subir.
10. Ninguna credencial/API key/token aparece en logs.

---

## 14. Desglose de tareas (orden recomendado)

### Fase 0 — Verificación (antes de codear)
- [x] T0.1 `mod_assign_get_submissions` del TUP → **CONFIRMADO**: `fileurl` + `?token=` funciona (A1).
- [x] T0.2 Tipo de escala por assignment → **CONFIRMADO**: TP=cualitativo (scale_id=5), exámenes=numérico, Integrador=numérico máx 10 (A3). Reglas en §7.
- [x] T0.2-bis **Textos + orden de scale_id=5** → **CONFIRMADO**: `índice 1='Aprobado'`, `índice 2='Desaprobado'` (¡orden invertido!). Cargado en `MOODLE_SCALE_MAP` (§7.4).
- [x] T0.3 Nombres de modelos Gemini (A2). **Resuelto vía doc oficial (mayo 2026):** los alias del prompt no son canónicos; defaults actualizados a `gemini-2.5-pro` / `gemini-2.5-flash-lite` (§8.1). **Script de confirmación con la key real:** `backend/scripts/verify_gemini_fase0.py`.
- [x] T0.4 Decisiones de §1 confirmadas: link PDF = token firmado; global = sólo key Paga; plantillas = JSON/config; importar = 3 niveles.

### Fase 1 — Datos y base ✅ (código escrito, migración pendiente de aplicar)
- [x] T1.1 `Entrega.moodle_user_id` (modelo + migración `010_moodle_bidireccional`).
- [x] T1.2 Modelo `MoodleSync` + enum `MoodleSyncEstado` + tabla `moodle_sync` en la migración. (Repository → Fase 2/3.)
- [x] T1.3 `Usuario.gemini_api_key_paga` (Boolean, server_default false) en modelo + migración.
- [~] T1.4 `COMENTARIO_TEMPLATES` → se difiere a Fase 3 (junto a su `ComentarioTemplateService`; sin consumidor ahora sería código muerto).
- [ ] **Aplicar** `alembic upgrade head` contra la DB (requiere confirmación del usuario; validado: head único, mapeo ORM OK).

### Fase 2 — Funcionalidad 1 (Importar)
- [x] T2.1 `MoodleService`: + `get_group_members_map` (userid→fullname), `get_submissions_with_files` (dataclasses `MoodleSubmission`/`MoodleFile`), `download_submission_file`. 5 tests TDD verdes + arreglados 3 tests preexistentes rotos (patch apuntaba a `app.core.security` en vez del símbolo importado en `moodle_service`). Suite: 9 passed.
- [x] T2.2 `EntregaService.crear_o_actualizar_desde_bytes` (bytes→entrega, idempotente, devuelve `ResultadoImportEntrega` con status creada/duplicada/ya_corregida/error, sin lanzar) + helper `_procesar_contenido`. Reusa consolidación/PDF/`_get_file_type`. NO toca `crear_entrega_individual/masiva` (prod). 5 tests TDD verdes. **Nota:** `test_entrega_service.py` está muerto (importa `CargaMasivaRequest` inexistente, API vieja) → deuda separada, no bloqueante.
- [x] T2.3 `MoodleImportService` (`app/services/moodle_import_service.py`): `importar(user_id, scope, ...)` resuelve pares Rúbrica×Comisión (patrón get_pendientes), `_importar_par` descarga (1 archivo directo / varios → ZIP) y delega a `crear_o_actualizar_desde_bytes`, clasifica `ResumenImportacion` (cargadas/duplicadas/omitidas_ya_corregidas/reentregas/sin_archivos/errores). Reentrega = `timemodified` Moodle > fecha corrección. 7 tests TDD verdes (suite Fase 2: 21 passed). `_resolver_pares` (queries DB) → validar en T2.6/manual.
- [x] T2.4 Router `POST /api/v1/moodle/importar` (`app/routers/moodle_import.py`) + schemas (`app/schemas/moodle_import.py`) + registrado en `main.py`. Errores: 424 (credenciales) / 502 (Moodle) / 422 (scope inválido). **Seguridad:** `_resolver_pares` filtra por `ComisionTutor.tutor_id` → un tutor sólo importa SUS comisiones (frontera a nivel datos). 2 tests integración (dependency_overrides + service mockeado, sin DB). Suite Fase 2: 23 passed.
  - **Hallazgo:** conftest usa SQLite → no soporta JSONB/ARRAY/enums PG; tests con `db_session` real no corren (incl. `test_entrega_service` muerto). Validación de integración real → contra base local (copia de prod).
- [x] T2.5 Frontend: types (`ImportarMoodleRequest/Response`) + `importarMoodle` service + `useImportarMoodle` hook (invalida pendientes+entregas) + `ImportarButton` (botón + Modal con resumen: cargadas/duplicadas/ya-corregidas/reentregas/sin-archivos/errores colapsables) integrado en `ComisionRow` (comision_unidad), `MateriaBlock` (materia, header reestructurado para no anidar botones) y `PendientesPage` (tutor). Botón "Ver en Moodle" intacto. **Pendiente validar con `tsc` (sin node_modules en sandbox) → el usuario corre `npm run build`.**
- [ ] T2.6 Tests backend + frontend.

### Fase 3 — Funcionalidad 2 (Subir a Moodle)
- [x] T3.1 `DevolucionLinkService` (token JWT firmado `tipo=devolucion`, `generar_token`/`validar_token`/`generar_path`, TTL 90d) + `TokenDevolucionInvalido`. Falta el endpoint público (en T3.4). 5 tests TDD verdes.
- [x] T3.2 `ComentarioTemplateService.render` (TP por banda desde `app/core/comentario_templates.py`; no-TP → `requiere_comentario_tutor=True` + cierre con link). 16 tests TDD verdes.
- [x] T3.3 `MoodleService.get_assignment_grade_config` + `save_grade` (mod_assign_save_grade) — refactor `_fetch_assignments`. `MoodleGradeService._mapear_nota` (escala invertida + escalado numérico, `GradeMapError`) + `MOODLE_SCALE_MAP`. `subir_correccion` (orquestación: carga relaciones, valida moodle_user_id/credenciales/IDs, idempotencia `moodle_sync` ENVIADO→409 salvo forzar, mapea, `save_grade`, audita ENVIADO/ERROR) + `MoodleSyncRepository`. Suite Fase 3: 53 passed.
- [x] T3.4 Endpoints: `GET /api/v1/correcciones/{id}/moodle/preview` + `POST /api/v1/correcciones/{id}/moodle` (router correcciones) + `GET /api/v1/public/devoluciones/{token}` (router público `public_docs.py`, sin JWT). Schemas `moodle_grade.py`. `MoodleGradeService.preview_correccion`. **Permisos (A7):** `verificar_acceso_comision` (async real en `permissions.py`: admin o ComisionTutor) usado en preview/subir. Registrado en `main.py`. 4 tests integración. Suite Fase 3: 57 passed.
- [x] T3.5 Frontend: tipos (`PreviewMoodle`, `SubirMoodleResponse`) + `moodle-grade.service.ts` (resuelve correccion_id vía `/correcciones/entregas/{id}` → preview/subir) + `SubirMoodleModal` (nota readonly, comentario editable precargado, link, checkbox forzar si `ya_enviada`, "Enviar" deshabilitado si no-TP sin comentario) + acción "Subir corrección a Moodle" en dropdown de entregas CORREGIDA + estado/render en `EntregasPage`. **Pendiente validar `tsc` (sin node_modules en sandbox).** Badge "sincronizado" en la lista → diferido (requiere exponer estado moodle_sync en EntregaListItem).
- [x] T3.6 Tests: backend 57 passed (unit + integración). Frontend → validar con `npm run build` + prueba real contra Moodle.

### Fase 4 — Funcionalidad 3 (Toggle key paga + corrección global)
- [x] T4.1 `PATCH /api/v1/perfil/key-paga` (toggle `gemini_api_key_paga`) + expuesto en `GET /perfil`. Validación de key (flash) ya existía.
- [x] T4.2 Frontend perfil: toggle "API key con facturación habilitada (paga)" en PerfilPage (visible si key válida) + `updateKeyPaga` service + `useUpdateKeyPaga` hook + campo `gemini_api_key_paga` en `UserProfile`.
- [x] T4.3 `EntregaRepository.get_subidas_ids_by_tutor` + `contar_estados_by_tutor` + `procesar_global_background` (Semaphore concurrency=5, sesión propia por tarea, backoff 429, no aborta el job).
- [x] T4.4 `POST /api/v1/correcciones/global` (valida key configurada→400 y paga→403; junta SUBIDA del tutor hasta `GLOBAL_BATCH_MAX=200`; encola background; 202) + `GET /api/v1/correcciones/global/progreso` (conteo por estado). 6 tests integración.
- [x] T4.5 Frontend dashboard: `CorregirTodoButton` (banner en DashboardTutor, visible si `gemini_api_key_paga` && subidas>0) → POST `/correcciones/global` + polling `/global/progreso` (refetchInterval 10s mientras procesa, muestra corregidas/en proceso/en cola) + `correccion-global.service.ts`. **Validar con `tsc`.**
- [x] T4.6 Tests: backend 6 integración (Fase 4). Frontend → `npm run build` + prueba real.

### Fase 5 — Cierre
- [x] T5.1 Revisión de logs: **sin secretos** (grep confirmó que ningún `logger.*` incluye token/password/api_key/fileurl; `save_grade`/`download_submission_file`/`get_token` no loguean el token). Permisos: `verificar_acceso_comision` en subir/preview; importación filtra por `ComisionTutor`.
- [x] T5.2 Criterios de aceptación §13 (ver tabla abajo).
- [x] T5.3 **No se agregaron env nuevas** (la detección de tier se descartó → sin `GEMINI_MODEL_*`). Lo configurable quedó como constantes (ver "Configuración" abajo).
```

---

## Configuración y operación (cierre)

**No hay variables de entorno nuevas.** Lo ajustable vive en constantes:

| Constante | Archivo | Qué hace |
|-----------|---------|----------|
| `MOODLE_SCALE_MAP` | `app/core/moodle_config.py` | Índice Aprobado/Desaprobado por `scale_id` (scale 5 = 1/2). **Si aparece otra escala, agregarla acá.** |
| `UMBRAL_APROBACION_TP` | `app/core/moodle_config.py` | 60 |
| `COMENTARIO_TEMPLATES_TP` / `CIERRE_DEVOLUCION_HTML` | `app/core/comentario_templates.py` | Plantillas de comentario |
| `DOWNLOAD_CONCURRENCY` | `app/services/moodle_import_service.py` | Descargas/consultas paralelas (8) |
| `DEFAULT_TTL_DIAS` | `app/services/devolucion_link_service.py` | Vigencia del link de devolución (90 d) |
| `GLOBAL_BATCH_MAX` | `app/routers/correcciones.py` | Tope de "Corregir todo" (200) |
| modelo validación Gemini | `app/routers/perfil.py` (`gemini-2.5-flash`) | Modelo para validar la API key |

**Notas operativas:**
- **`ENCRYPTION_KEY`**: para descifrar credenciales Moodle/Gemini en local con un dump de prod, debe ser la **misma de prod**.
- **Link de devolución absoluto**: usa `request.base_url`. Detrás de un reverse proxy puede necesitar un `PUBLIC_BASE_URL` configurable (ajuste futuro si el host no resuelve bien).
- **SSE de importación**: el endpoint envía `X-Accel-Buffering: no`; si hay nginx delante, verificar que no buffere `text/event-stream`.

## Criterios de aceptación — estado

| # | Criterio (§13) | Estado |
|---|----------------|--------|
| 1 | Importar comisión/materia/tutor → Entrega SUBIDA con `moodle_user_id` | ✅ código + tests + **probado real** |
| 2 | No sobrescribe corregidas, no duplica, reporta resumen | ✅ tests |
| 3 | Subir corrección: modal con nota + comentario editable + envío | ✅ código + tests |
| 4 | TP→Aprobado/Desaprobado; no-TP→numérica escalada; 422 si discordancia | ✅ tests (mapeo) — validar render real en Moodle |
| 5 | Link de devolución abre sin sesión, expira, no expone otros alumnos | ✅ tests (token) — validar real |
| 6 | Anti doble-envío (409) + auditoría `moodle_sync` | ✅ tests |
| 7 | Perfil muestra estado de la key + toggle paga | ✅ |
| 8 | "Corregir todo" con key paga, cross-rúbrica, progreso, resiliente 429 | ✅ código + tests — validar volumen real |
| 9 | Permisos: tutor no asignado → 403 | ✅ helper + uso |
| 10 | Sin secretos en logs | ✅ revisado |

**Pendiente de validación manual (requiere Moodle real, no verificable desde acá):** render del feedback en Moodle (#4), apertura del link por un alumno (#5), volumen real de "Corregir todo" (#8), y `npm run build` del frontend.

