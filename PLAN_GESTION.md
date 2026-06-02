# PLAN — Pantalla "Gestión" (rol GESTOR) + export Excel por Regional

## 1. Objetivo

Nueva pantalla **Gestión** para un usuario con rol **GESTOR**, donde pueda:

1. Elegir un curso de Moodle (una de nuestras Materias con `moodle_course_id`).
2. Aplicar los filtros que Moodle permite (rol, estatus, grupos, inactividad).
3. Ver el resultado en pantalla (preview).
4. **Descargar un Excel** con el formato pedido:
   `Nombre · Apellido · Email · Regional · Comisión · Tiempo de inactividad`
   más el **total de alumnos** que matchean los filtros.
   - Una **hoja por Regional**.
   - Dentro de cada Regional, ordenado por **Comisión**.

Ejemplo de filtro: *Rol = Alumno · Inactivos por más de 1 mes · Estatus = Activo*.

---

## 2. Decisiones confirmadas (preguntas resueltas con el usuario)

| # | Tema | Decisión |
|---|------|----------|
| 1 | **Rol "Gestor"** | **Crear rol `GESTOR` nuevo** en el enum (no reusar ADMIN). |
| 2 | **Regional + Comisión** | Son **grupos SEPARADOS** del alumno (✅ confirmado en T0 contra Moodle real). **Comisión** = grupo `{cohorte}{año} C{sem}-{NN}` donde cohorte = `M` (marzo) o `A` (agosto), ej `M26 C1-09` / `A25 C2-01`. **Regional** = grupo `R-{nombre}` (ej `R-Mendoza`). El alumno está en AMBOS a la vez. |
| 3 | **Alcance** | **Un curso (Materia) que elige el Gestor**. Los filtros (regional, comisión, roles) son los de ESE curso. |
| 4 | **Inactividad** | **Último acceso al curso** (`lastcourseaccess`) — coincide con el filtro de Participantes de Moodle. |
| 5 | **Columna Comisión** | Se muestra **completa** (`M26 C1-09`), no solo el número. |
| 6 | **Grupos a ignorar** | Los grupos `Grupo_NN` y de estado (`NO_RINDIO_PRIMER_PARCIAL`, `No-rindio-P1`, `Entrego_*`, `Z-FINAL-*`, etc.) **se omiten**: no son ni filtro ni columna. Solo importan `R-*` y `M.. C..-..`. |

---

## 3. Supuestos (defaults razonables — ajustables sin romper el diseño)

> Estos los decido yo con sentido común para no frenar el plan. Si alguno no te cierra, lo cambiamos.

- **Columna "Comisión"** del Excel = el grupo de comisión **completo** (`M26 C1-09`).
- **Regional** = el nombre tras el prefijo `R-` (`R-Mendoza` → `Mendoza`) o se deja con prefijo si querés (a definir en UI; el orden de hojas es alfabético igual).
- **"Tiempo de inactividad"** = días desde `lastcourseaccess` (ej: `47 días`). Si `lastcourseaccess = 0` → `"Nunca"`.
- **"Total de alumnos con estos filtros"** = NO es una columna por fila (no tendría sentido repetirla). Va como:
  - una celda/fila **resumen al pie de cada hoja** (total de esa regional), y
  - una **hoja "Resumen"** con el total global + desglose por regional/comisión.
- **Roles Moodle** (shortnames, ✅ confirmados en T0): `student` = Estudiante, `editingteacher` = Profesor, `teacher` = Profesor sin permiso de edición.
- **Estatus** = estado de la *matriculación*: `activo` = enrolment activo, `inactivo` = suspendido. ⚠️ No hay flag `suspended` por usuario → se resuelve por **doble llamada** (ver §5.2).
- Si el alumno **no tiene grupo `R-`** → Regional = `"Sin regional"`. Si **no tiene grupo `M.. C..-..`** → Comisión = `"—"`. No se pierde la fila.
- Los grupos `Grupo_NN` y de estado se **ignoran** por completo.

---

## 4. Filtros (lo que Moodle permite)

| Filtro | Valores UI | Cómo se resuelve |
|--------|-----------|------------------|
| **Rol** | Estudiante · Profesor · Profesor sin permiso de edición · (Todos) | `user.roles[].shortname`: `student` / `editingteacher` / `teacher` |
| **Estatus** | Activo · Inactivo · (Todos) | enrolment activo/suspendido → **doble llamada** `onlyactive=1` vs `onlyactive=0` (ver §5.2) |
| **Regional** | (regionales del curso) multi-select + "Todas" | grupos del alumno con prefijo `R-`, derivados de `user.groups[]` |
| **Comisión** | (comisiones del curso) multi-select + "Todas" | grupos del alumno con formato `M.. C..-..`, derivados de `user.groups[]` |
| **Inactividad** | 1 día · 2 días · 1 semana · 2 semanas · 3 semanas · 1 mes · 2 meses · **Rango (de N a M días)** · **Nunca** | **banda cerrada** de días vs `now - lastcourseaccess` (NO acumulativo) |

**Modelo: BANDAS CERRADAS (no acumulativo).** Cada opción es un rango `[low, high)` en días, definido por el umbral de la opción siguiente. Los días intermedios se absorben en la banda de abajo (sin huecos, sin solapamientos).

`días_inactivo = floor((now - lastcourseaccess) / 86_400)` — solo para alumnos que SÍ entraron (`lastcourseaccess > 0`).

```
Opción        Banda (días)     Incluye si...
1 día         [1, 2)           1 ≤ días < 2
2 días        [2, 7)           2 ≤ días < 7      (absorbe 3-6)
1 semana      [7, 14)          7 ≤ días < 14
2 semanas     [14, 21)         14 ≤ días < 21
3 semanas     [21, 30)         21 ≤ días < 30    (absorbe 28-29)
1 mes         [30, 60)         30 ≤ días < 60    ("más de 1 mes hasta 2")
2 meses       [60, ∞)          días ≥ 60         (CATCH-ALL, pero lastcourseaccess > 0)
Rango custom  [N, M]           N ≤ días ≤ M      (N y M los carga el Gestor)
Nunca         —                lastcourseaccess == 0  (categoría aparte)
```

**Reglas clave:**
- Seleccionar `1 mes` trae SOLO 30-59 días: **no** trae los de 2 meses, **ni** los que nunca entraron.
- `2 meses` es el único catch-all: 60 días o más, **excluyendo** a los que nunca entraron.
- `Nunca` (`lastcourseaccess == 0`) **jamás** se mezcla con las bandas de días.
- Borde inferior inclusivo, superior exclusivo (`[low, high)`) — uniforme en todas las bandas.

---

## 5. Arquitectura — Backend (Clean Architecture)

### 5.1 Rol nuevo `GESTOR`  ⚠️ dominio sensible (permisos)
- `app/models/enums.py`: agregar `GESTOR = "GESTOR"` a `RolEnum`.
- **Migración Alembic**: el enum de rol vive en columna PG → migración que agrega el valor al type enum (`ALTER TYPE ... ADD VALUE 'GESTOR'`).
- `app/core/permissions.py`: `require_gestor(user)` + (opcional) `require_gestor_or_admin`.

### 5.2 MoodleService — métodos nuevos  (✅ validado en T0)
- ~~`get_course_groups` / `core_group_get_course_groups`~~ **DESCARTADO**: el WS devuelve `nopermissions` ("Gestionar grupos") para el rol del Gestor. Los grupos (regional y comisión) se **derivan del `groups[]` de los usuarios matriculados**.
- `get_enrolled_users_full(token, host, course_id, *, only_active: bool) -> list[dict]`
  WS `core_enrol_get_enrolled_users`. **Confirmado** que devuelve por usuario: `id, firstname, lastname, fullname, email, roles[] (con shortname), groups[] (con name), lastcourseaccess, lastaccess`.
  - **Estatus activo/suspendido**: NO hay flag `suspended` por usuario. Se resuelve por **doble llamada**:
    `activos = enrolled(onlyactive=1)`, `todos = enrolled(onlyactive=0)`, `suspendidos = todos − activos` (por `id`).
  - Para cursos grandes: `options` `limitnumber`/`limitfrom` permiten paginar si hace falta (visto que un curso puede tener cientos y la consulta full puede tardar >30s).

### 5.3 Parsers de grupo (utils puros — TDD)  (✅ formato real validado en T0)
Dos parsers independientes sobre los nombres de `user.groups[]`:
- `parse_comision(nombre) -> str | None`: matchea `^M\d+\s+C\d+-\d+$` (ej `M26 C1-09`) → devuelve el nombre completo o `None`.
- `parse_regional(nombre) -> str | None`: matchea `^R-(.+)$` (ej `R-Mendoza`) → devuelve `Mendoza` (o el nombre con prefijo, a definir) o `None`.
- `resolver_grupos_alumno(groups) -> (regional, comision)`: recorre los grupos del alumno, toma el primero que matchea cada patrón. Ignora `Grupo_NN`, `NO_RINDIO_*`, `No-rindio-*`, `Entrego_*`, `Z-*`, etc. Fallbacks: Regional `"Sin regional"`, Comisión `"—"`.

### 5.4 GestionService (`app/services/gestion_service.py`)
- `listar_cursos(usuario) -> list[CursoItem]` — Materias activas con `moodle_course_id` (desde nuestra DB).
- `opciones_filtros(usuario, materia_id) -> FiltrosDisponibles` — regionales + comisiones del curso (derivadas del `groups[]` de los matriculados, NO de `core_group_get_course_groups`) + catálogos de rol/estatus/inactividad.
- `consultar(usuario, materia_id, filtros) -> ResultadoGestion` — trae enrolled users (con doble llamada para estatus), resuelve regional/comisión por alumno, calcula inactividad, aplica filtros, ordena (regional → comisión), devuelve filas + total.
- `exportar_excel(usuario, materia_id, filtros) -> bytes` — reusa `consultar` + arma el xlsx.

### 5.5 Excel (extender `app/services/excel_service.py`)
- `exportar_gestion(resultado) -> bytes`:
  - una `Worksheet` por **Regional** (orden alfabético), filas ordenadas por Comisión.
  - columnas: Nombre · Apellido · Email · Regional · Comisión · Tiempo de inactividad.
  - fila resumen al pie con total de la regional.
  - hoja **"Resumen"** con total global + desglose.
  - Reusa estilos de headers ya existentes (`ExcelService`).

### 5.6 Router (`app/routers/gestion.py`, prefix `/api/v1/gestion`)
| Método | Ruta | Devuelve |
|--------|------|----------|
| GET | `/gestion/cursos` | lista de cursos elegibles |
| GET | `/gestion/cursos/{materia_id}/filtros` | grupos del curso + catálogos |
| POST | `/gestion/cursos/{materia_id}/consulta` | preview (filas + total) |
| POST | `/gestion/cursos/{materia_id}/excel` | `StreamingResponse` xlsx |

- Todos protegidos con `require_gestor` (¿+ ADMIN? a confirmar).
- `424` si el Gestor no tiene credenciales Moodle configuradas (mismo patrón que `get_pendientes`).
- `main.py`: registrar `gestion_router`.

### 5.7 Schemas (`app/schemas/gestion.py`)
- `FiltrosGestionRequest` (rol, estatus, grupos[], inactividad_tipo, inactividad_valor).
- `AlumnoGestionResponse`, `ConsultaGestionResponse` (items + total + por_regional).
- `CursoGestionResponse`, `FiltrosDisponiblesResponse`.

---

## 6. Arquitectura — Frontend (feature-based)

`frontend/src/features/gestion/`:
- `types/index.ts` — interfaces espejo de los schemas.
- `services/gestion.service.ts` — getCursos, getFiltros, consultar, **descargarExcel** (blob → download).
- `hooks/` — `useCursosGestion`, `useFiltrosGestion`, `useConsultaGestion` (React Query).
- `components/`
  - `FiltrosGestionForm.tsx` — selector de curso, rol, estatus, grupos (multi), inactividad (select + input X cuando aplica), botón **Descargar Excel**.
  - `ResultadosGestionTable.tsx` — preview agrupado por regional, con total.
- `pages/GestionPage.tsx`.

Integración:
- `app/router.tsx`: ruta `/gestion` (lazy).
- `shared/components/layout/Sidebar.tsx`: item "Gestión" (icon p.ej. `BarChart3`/`Download`), `roles: ['GESTOR','ADMIN']`.
- Front: agregar `GESTOR` al type de roles y a los guards de ruta.

---

## 7. Tareas (orden de implementación, TDD donde aplica)

> Gobernanza: **T1 (rol/permisos) es dominio CRÍTICO** → describo y **espero tu OK explícito** antes de escribir. El resto es MEDIUM (implemento con checkpoints).

- **T0 — Spike Moodle ✅ HECHO** (`backend/scripts/spike_moodle_gestion.py`, descartable): confirmado contra `https://tup.sied.utn.edu.ar` que `core_enrol_get_enrolled_users` trae `lastcourseaccess`/`roles`/`groups`/`email`; que `core_group_get_course_groups` da `nopermissions` (→ derivar grupos de los users); que el estatus suspendido va por doble llamada; y el **formato real** de grupos (Comisión `M26 C1-09`, Regional `R-Mendoza`, + grupos a ignorar).
- **T1 — Rol GESTOR ✅ HECHO:** `GESTOR` en `RolEnum` (enums.py); `require_gestor` + `require_gestor_or_admin` (permissions.py); migración `012_add_gestor_rol` (`ALTER TYPE rol_enum ADD VALUE 'GESTOR'` vía `autocommit_block`, downgrade que recrea el tipo). 8 tests nuevos (TDD) en verde. ⚠️ Falta aplicar la migración en la base: `alembic upgrade head`.
- **T2 — Parsers de grupo ✅ HECHO:** `app/services/gestion_parser.py` con `parse_comision` (`^[MA]\d+\s+C\d+-\d+$` → cohorte M=marzo/A=agosto), `parse_regional` (`^R-(.+)$` → sin prefijo), `resolver_grupos_alumno` (primer match de cada tipo, fallbacks `SIN_REGIONAL`/`SIN_COMISION`). 24 tests (TDD, parametrizados contra nombres reales de prod) en verde.
- **T3 — Bandas de inactividad ✅ HECHO:** `app/services/gestion_inactividad.py` con `dias_inactividad(lastcourseaccess, now)`, `coincide_inactividad(...)`, `BANDAS` (presets `[low, high)`, `2_meses` catch-all), `NUNCA`/`RANGO`, `TIPOS_VALIDOS`. 37 tests (TDD) en verde: bordes 29/30/59/60, nunca-no-cae-en-bandas, catch-all, rango inclusivo.
- **T4 — MoodleService ✅ HECHO:** `get_enrolled_users_full(course_id, only_active)` (core_enrol_get_enrolled_users, timeout 60s, cache por (course,only_active), errores invalidtoken→Auth) + `get_enrolled_users_with_status` (doble llamada onlyactive 1/0 → marca `suspendido`). 6 tests (TDD, httpx mockeado). *(sin `get_course_groups` — descartado en T0)*
- **T5 — GestionService ✅ HECHO (falta `exportar_excel` → T6):** `listar_cursos` (MateriaRepository.get_con_moodle nuevo), `opciones_filtros` (deriva regionales/comisiones de participantes + catálogos ROLES/ESTATUS/INACTIVIDAD), `consultar` (filtros rol/estatus/regional/comisión/inactividad + orden regional→comisión→apellido + humanización + total). DTOs: CursoGestion, FiltrosDisponibles, FiltrosGestion, AlumnoGestion, ResultadoGestion. 10 tests (TDD, repo+MoodleService mockeados). 424 sin credenciales, 404 curso sin Moodle.
- **T6 — Excel ✅ HECHO:** `ExcelService.exportar_gestion(resultado, materia_nombre)` (hoja por regional, orden por comisión, columnas Nombre·Apellido·Email·Regional·Comisión·Tiempo de inactividad, total por hoja, hoja "Resumen" con totales por regional + global, `_sheet_title` sanea nombres ≤31). `GestionService.exportar_excel` (reusa `consultar` + delega). 7 tests (TDD, recargando el xlsx con openpyxl).
- **T7 — Schemas + Router ✅ HECHO:** `app/schemas/gestion.py` (FiltrosGestionRequest con validación rol/estatus/inactividad+rango, CursoGestionResponse, FiltrosDisponiblesResponse, ConsultaGestionResponse, AlumnoGestionResponse). `app/routers/gestion.py`: GET /gestion/cursos, GET /cursos/{id}/filtros, POST /cursos/{id}/consulta, POST /cursos/{id}/excel (StreamingResponse xlsx), todos con `require_gestor_or_admin`. Registrado en main.py (prefix /api/v1). 7 tests de integración (router mockeado): 4 endpoints + 422 inactividad inválida + 403 tutor + 200 admin.
- **T8 — Frontend ✅ HECHO:** `features/gestion/` (types, gestion.service con descarga blob xlsx, hooks useCursosGestion/useFiltrosGestion/useConsultaGestion, FiltrosGestionForm con multi-select regional/comisión + rango inactividad, ResultadosGestionTable agrupada por regional, GestionPage). Sidebar +ítem "Gestión" (BarChart3, roles GESTOR/ADMIN). Router +ruta /gestion. RolEnum del front +GESTOR + UsuarioForm (z.enum + opción) + UsuariosPage (Record<RolEnum> completados). `tsc -b` y `eslint` limpios.
- **T9 — Verificación ✅:** backend `pytest` 210 passed (4 errores pre-existentes ajenos); frontend `tsc -b` + `eslint` limpios. Migración 012 validada sobre copia real de prod. Falta: prueba manual end-to-end y commit.

---

## 8. Criterios de aceptación

1. Un usuario **GESTOR** ve el ítem "Gestión" en el sidebar; un TUTOR no.
2. El Gestor elige un curso y ve las **regionales** y **comisiones** reales de ese curso como filtros (derivadas de los participantes; sin `Grupo_NN` ni grupos de estado).
3. Filtro *Rol=Alumno · Inactividad "1 mes" · Activo* devuelve **solo** alumnos con matriculación activa cuya última entrada al curso fue hace **30 a 59 días** — NO incluye a los de 2 meses ni a los que nunca entraron (banda cerrada, no acumulativa).
4. `2 meses` trae 60 días o más (catch-all) excluyendo a los que nunca entraron. La opción **"Nunca"** lista — aparte — alumnos que jamás entraron al curso. El rango custom "de N a M días" trae exactamente esa banda.
5. El **Excel** tiene **una hoja por Regional**, cada hoja ordenada por **Comisión**, con las columnas pedidas y el **total** de alumnos.
6. La **Regional y la Comisión** salen correctas de los grupos del alumno: grupo `R-Mendoza` → Regional `Mendoza`; grupo `M26 C1-09` → Comisión `M26 C1-09`. Un alumno sin grupo `R-` cae en "Sin regional".
7. Si el Gestor no configuró credenciales Moodle → mensaje claro (424), no error feo.
8. Backend con tests en verde; frontend sin errores de tipo/lint.

---

## 9. Riesgos / cosas a vigilar  (actualizado tras T0)

- ✅ **Estatus activo/suspendido** — RESUELTO: no hay flag por usuario → doble llamada `onlyactive=1/0` (§5.2).
- ✅ **Permisos del token** — RESUELTO: `core_enrol_get_enrolled_users` OK; `core_group_get_course_groups` NO (sin permiso) → grupos derivados de participantes.
- ✅ **Formato de grupo** — RESUELTO: Comisión `M.. C..-..`, Regional `R-*` (grupos separados); resto se ignora.
- ⚠️ **Performance:** cursos grandes (cientos de alumnos) hacen que `core_enrol_get_enrolled_users` tarde **>30s** (visto en T0 con curso "TV"). Mitigaciones: timeout amplio (≥60s), posible paginación (`limitfrom`/`limitnumber`) y/o caché por curso. La doble llamada (estatus) duplica el costo → cachear la respuesta cruda y derivar activos/suspendidos en memoria.
- ⚠️ **Consistencia de nombres de grupo:** los parsers dependen del formato. Mitigado con fallbacks ("Sin regional"/"—") y tests; si aparece un curso con otra convención, no rompe (solo cae en los fallbacks).

---

## 10. Lo que reusamos (no reinventamos nada)

- `openpyxl` + `ExcelService` (export ya existe, solo agregamos un método multi-hoja).
- Patrón de llamada a Moodle WS y caché de `MoodleService`.
- Credenciales Moodle por-usuario + manejo 424.
- Estructura feature-based del front (idéntica a `por-entregar`/`entregas`).
