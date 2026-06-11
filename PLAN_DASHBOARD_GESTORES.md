# PLAN — Dashboard de Gestores (trazabilidad de avance de alumnos)

## 1. Objetivo

Reemplazar el dashboard actual del rol **GESTOR** (hoy muestra "Rol desconocido" / redirige a `/gestion`) por un **dashboard informativo** que muestre la **trazabilidad del avance de los alumnos** por materia:

1. Un **gráfico de torta** con la cantidad de alumnos en cada **estado de avance** (Al día / Riesgo medio / Riesgo alto / Sin actividad).
2. Tres **selectores encadenados**: **Cohorte** → **Cuatrimestre** → **Materia** (o "Todos").
3. **Título dinámico** del gráfico según la selección.
4. Al **clickear una porción** del gráfico → **modal de detalle** con los alumnos de ese estado: `Nombre · Apellido · Email · Actividad actual` (ej: *"Actividad de cierre, Unidad 7"*).
5. Los datos salen de un **snapshot diario** calculado por un **cron cada 24hs** desde Moodle (más un **botón manual** para pruebas, que se quita después).

> El estado de cada alumno se calcula comparando **la unidad más alta que el alumno completó en Moodle** contra **la unidad en la que está cursando la materia** (campo configurable).

---

## 2. Decisiones confirmadas (resueltas con el usuario, 2 rondas)

| # | Tema | Decisión |
|---|------|----------|
| 1 | **Qué es "la última actividad"** | La **actividad completada en Moodle de unidad más alta**. Ej: si Programación 1 tiene 10 unidades, se cursa la 5, y el alumno completó la actividad 3 de la unidad 5 → su unidad alcanzada es **5** → **Al día**. (No es la última cronológica: es el **punto más avanzado** alcanzado.) |
| 2 | **Mapeo actividad → unidad** | Las **Unidades se configuran a nivel Materia**: lista ordenada (Unidad 1..N), cada una con su `moodle_section_id`. La rúbrica/TP *opcionalmente* apunta a una unidad. Esto cubre actividades **sin rúbrica**, unidades **sin TP** y **recuperatorios** sin ambigüedad. |
| 3 | **Modelo Cohorte/Cuatrimestre** | **Ambas entidades**: `Cohorte` 1:N `Cuatrimestre` 1:N `Materia`. El admin da de alta cohortes y cuatrimestres. |
| 4 | **Origen de los datos del dashboard** | **Snapshot en DB** generado por el cron (no consulta Moodle en vivo). El dashboard lee la tabla = instantáneo y no satura Moodle. |
| 5 | **Scheduler** | **Cron en el backend** (APScheduler), 24hs. + **botón manual** (endpoint) para pruebas. |
| 6 | **Trazabilidad** | **Histórico con fecha**: cada corrida guarda un snapshot fechado → habilita ver la evolución en el tiempo. |
| 7 | **Alumnos sin ninguna actividad completada** | **Categoría propia "Sin actividad"** (4ª porción del gráfico), separada de "Riesgo alto". |
| 8 | **Categorización** | `delta = unidad_actual − unidad_alcanzada`: `0` = **Al día** (verde) · `1` = **Riesgo medio** (naranja) · `≥2` = **Riesgo alto** (rojo) · sin actividad = **Sin actividad** (gris). |
| 9 | **Gráficos** | **Recharts** (nueva dependencia del frontend). |
| 10 | **Quién setea `unidad_actual`** | El **admin** (junto con la config de la materia), no el gestor. |
| 11 | **Materia ↔ cohorte** | Cada `Materia` (= un curso Moodle) pertenece a **un solo** cuatrimestre/cohorte. "Programación 1" de M25 y de M26 son **materias distintas**. |
| 12 | **Cohortes a precargar (seed)** | `M25` (4 cuatrimestres), `A25` (2), `M26` (1), `A26` (1). Ver §5.1. |
| 13 | **Mapeo de cabeceras de unidad** | **Auto-detección + confirmación**: el ABM trae las secciones de Moodle, detecta las cabeceras por patrón `^\d+-\s` ("1- …", "2- …"), pre-completa el número de unidad, y el admin confirma/ajusta. |
| 14 | **Parciales / Trabajo Integrador** | **NO cuentan** para el avance: solo las unidades de contenido (1..N). Las secciones posteriores a la última unidad se excluyen del cálculo → el ABM acota el **cierre** de la última unidad (ver §6.1.8). |
| 15 | **Velocidad del cron** | **Serial** (1 call/alumno, de a una). Simple y sin riesgo de saturar Moodle. Si escala mal, se evalúa paralelismo moderado más adelante. |

---

## 3. Supuestos (defaults razonables — ajustables sin romper el diseño)

> Estos los decido con sentido común para no frenar el plan. Si alguno no te cierra, lo cambiamos al revisar.

- **Estado por (alumno, materia).** Un alumno cursa varias materias; su estado se calcula **por materia** (cada una tiene su unidad actual). Cuando el selector de materia es **"Todos"**, el gráfico **agrega los pares (alumno, materia)** del cuatrimestre — un alumno puede estar "Al día" en Prog 1 y "Riesgo alto" en Matemática, y cuenta una vez por cada materia.
- **"Actividad actual" mostrada en el modal** = el **nombre de la actividad completada de unidad más alta** + su unidad (ej: `"Actividad de cierre, Unidad 7"`). Si hay varias en la misma unidad máxima, se toma la de `timecompleted` más reciente.
- **Librería de gráficos: Recharts** ✅ **confirmado** (declarativa, liviana, `PieChart` con `onClick` por porción, juega bien con Tailwind/tokens).
- **Colores del gráfico** = tokens del design system: `success` (verde, Al día) · `warning` (naranja, Riesgo medio) · `destructive` (rojo, Riesgo alto) · `muted-foreground` (gris, Sin actividad). Funcionan en claro y oscuro.
- **Quién es "alumno"** = usuarios de Moodle con rol `student` (reusamos `get_enrolled_users_full`). Los alumnos **no son usuarios de Activia**: en el snapshot se identifican por `moodle_user_id` + nombre/apellido/email/comisión (no hay FK a `usuarios`).
- **Título dinámico** (confirmado con tus ejemplos):
  - Cohorte + Cuatrimestre + **Todos** → `"Cohorte M25 · Cuatrimestre 1"`
  - Cohorte + **Materia puntual** → `"M25 · Programación 1"` (no menciona el cuatrimestre)
- **Materias elegibles** para el cálculo = las que tienen `moodle_course_id` + `cuatrimestre_id` + `unidad_actual` + al menos una `Unidad` mapeada. Si falta config, la materia no aparece en el dashboard (y el cron la saltea con un warning).
- **Comisión** del alumno en el detalle = se deriva del grupo Moodle `M.. C..-..` (reusamos el parser de la feature Gestión).

---

## 4. Concepto central — cálculo del estado

```
Para cada alumno (student) de la materia:
  actividades_completadas = actividades de Moodle con completion = "completa"
                            (ver web services en §6)
  unidades_completadas    = { Unidad.numero | la actividad cae en una sección
                              mapeada a esa unidad }            (ver §5 mapeo)

  SI unidades_completadas está vacío:
      estado = SIN_ACTIVIDAD
  SINO:
      unidad_alcanzada = max(unidades_completadas)
      delta = materia.unidad_actual − unidad_alcanzada
      delta <= 0  → AL_DIA          (verde)     # alcanzó o superó la unidad actual
      delta == 1  → RIESGO_MEDIO    (naranja)   # una unidad atrás
      delta >= 2  → RIESGO_ALTO     (rojo)       # dos o más unidades atrás

  actividad_actual = la actividad completada de unidad_alcanzada con
                     timecompleted más reciente (nombre + "Unidad N")
```

> **Borde:** si una actividad completada cae en una sección **no mapeada** a ninguna `Unidad`, se ignora para el cálculo (y se loguea). Por eso el mapeo de unidades de la materia debe estar completo. El **spike T0** valida que esto se sostenga en los cursos UTN reales.

---

## 5. Modelo de datos (entidades nuevas + cambios)

### Nuevas entidades
- **`Cohorte`**: `id`, `codigo` (ej `M25`, `A26` — único), `nombre` (opcional), `activa`, timestamps. *CRUD admin.*
- **`Cuatrimestre`**: `id`, `cohorte_id` (FK), `numero` (1–4), `nombre` (opcional). `UNIQUE(cohorte_id, numero)`. *CRUD admin.*
- **`Unidad`**: `id`, `materia_id` (FK), `numero` (1..N), `moodle_section_id` (int = **sección CABECERA** de la unidad), `nombre` (opcional). `UNIQUE(materia_id, numero)`, `UNIQUE(materia_id, moodle_section_id)`. Ordenada por `numero`.
  > ⚠️ **Ajuste por spike T0 (ver §6.1):** una unidad NO es una sola sección — abarca un **rango de secciones consecutivas** (la cabecera `"N- Tema"` + sus satélites *Actividades / Práctica / Microteaching / Autoevaluación / …*). `moodle_section_id` apunta a la **sección cabecera**; el rango de cada unidad se **deriva en runtime** por orden de `section#` (una actividad pertenece a la unidad de la cabecera con mayor `section#` ≤ el `section#` de su sección).
- **`AvanceSnapshot`** (cabecera del snapshot): `id`, `materia_id` (FK), `generado_en` (datetime, index), `unidad_actual` (int — congela el valor del momento), `origen` (`CRON` | `MANUAL`), `total_alumnos`. Histórico (no se sobreescribe).
- **`AvanceAlumno`** (detalle, 1 fila por alumno del snapshot): `id`, `snapshot_id` (FK), `moodle_user_id`, `nombre`, `apellido`, `email`, `comision`, `unidad_alcanzada` (int nullable), `actividad_actual_nombre` (str nullable), `actividad_actual_unidad` (int nullable), `estado` (`EstadoAvanceEnum`).

### Cambios a entidades existentes
- **`Materia`**: `+ cuatrimestre_id` (FK, nullable durante migración), `+ unidad_actual` (int, nullable).
- **`Rubrica`**: `+ unidad_id` (FK a `Unidad`, nullable, opcional).

### Enum nuevo
- **`EstadoAvanceEnum`**: `AL_DIA`, `RIESGO_MEDIO`, `RIESGO_ALTO`, `SIN_ACTIVIDAD`. (Enum nativo PG → migración con `ALTER TYPE`/`create_type`, mismo patrón que `rol_enum`.)

### Relaciones para los selectores
`Cohorte (1:N) Cuatrimestre (1:N) Materia` → el árbol de selectores se arma desde acá. La **cohorte de la materia** queda explícita y desacoplada del parsing de comisiones.

### 5.1 Seed inicial (precarga de cohortes/cuatrimestres)
Se cargan en la migración/seed (idempotente — `IF NOT EXISTS` por `codigo`/`numero`):

| Cohorte | Cuatrimestres |
|---------|---------------|
| `M25` | 1, 2, 3, 4 |
| `A25` | 1, 2 |
| `M26` | 1 |
| `A26` | 1 |

Las **materias** se vinculan a su cuatrimestre desde el ABM (no se seedean: dependen de los cursos Moodle existentes).

---

## 6. Integración Moodle (web services NUEVOS — validar en T0)

Hoy `MoodleService` usa: `mod_assign_get_assignments/get_submissions/get_grades/save_grade` y `core_enrol_get_enrolled_users`. Faltan:

| Necesidad | Web service candidato | Devuelve |
|-----------|----------------------|----------|
| Secciones (unidades) + módulos del curso | `core_course_get_contents` | secciones (`id`, `name`, `section`) y módulos (`id`=cmid, `name`, `modname`, pertenencia a sección) |
| Actividades completadas por alumno | `core_completion_get_activities_completion_status` (por `courseid`+`userid`) | por cmid: `state` (0 incompleta / 1 completa / 2 complete_pass / 3 complete_fail) + `timecompleted` |

**Mapeo final (validado, ver §6.1):** para cada cmid completado → su `section#` (de `contents`) → la **unidad cuya cabecera** tiene el mayor `section#` ≤ ese valor → `Unidad.numero`. `unidad_alcanzada` = `max(Unidad.numero)` entre actividades con `state ∈ {1,2}`.

⚠️ **Performance (medido en T0):** es **1 llamada de completion por alumno** (~2s) — **`contents?userid=` NO existe en este Moodle** (no hay atajo embebido). Con 838 alumnos (Prog 1) → **~28 min/materia serial**. Por eso el cálculo vive en el **cron/snapshot** (no en vivo) y de madrugada. Llamadas **serializadas** (no paralelizar, rompe Moodle). Ver §11 para la estrategia si escala mal.

### 6.1 Hallazgos del spike T0 (✅ validado contra `course_id=38` — M26 Programación 1)

Script: `backend/scripts/spike_dashboard_gestores.py` (descartable, lee credenciales de env, no loguea secretos).

1. **`core_course_get_contents` funciona** (2.95s): devuelve **71 secciones** con `id` (estable), `section` (#, orden visual) y `modules[]` (cada uno con `id`=cmid, `modname`, `name`, `completion`).
2. **Una Unidad ≠ una sección.** Las 10 unidades son las secciones cabecera `"1- …"` … `"10- …"` (`section#` 1, 7, 13, 19, 25, 33, 40, 46, 52, 58). Cada unidad incluye sus secciones satélite siguientes (*Actividades, Práctica, Microteaching, Autoevaluación, Encuesta de cierre, Soluciones*) hasta la próxima cabecera. → modelo `Unidad` = **cabecera + rango derivado** (ver §5).
3. **Las "Actividad de cierre unidad N" existen** como `modname=assign` dentro de la sección **"Práctica"** de cada unidad (ej. `cmid=11169` "Actividad de cierre unidad 1" en `section#3`; `cmid=11312` "…unidad 7" en `section#42`). Confirma el ejemplo del requerimiento.
4. **`completion` por módulo**: muchos módulos tienen `completion=0` (labels, foros, recursos informativos → **no trackean, no cuentan**). Cuentan los `quiz`/`assign`/etc. con `completion≠0` efectivamente completados.
5. **`core_completion_get_activities_completion_status` funciona** (1.97s): trae `statuses[]` con `cmid`, `state` (1=completa, 2=completa-aprobada cuentan; 0=incompleta) y `timecompleted`. Suficiente para el cálculo.
6. **`core_course_get_contents` con `userid` NO se soporta** en este Moodle (`errorinvalidparam`). → **1 llamada de completion por alumno** (no hay forma de embeberlo).
7. **Performance real**: 838 alumnos (student) en Prog 1; ~**2s/alumno** → **~28 min/materia** serial. (El "0.29s" que imprimió el script fue el tiempo del *error* de B3, no una llamada real — corregir la métrica si se reusa el script.)
8. **Secciones que NO son unidades**: `section#0` (General), y al final *Trabajo Integrador* (`#64`), *Encuentros síncronos* (`#65`), *Evaluaciones/parciales* (`#66`), *Comisiones, Gestión Académica, Active-IA, Cuadro de honor* (`#67-70`). **Decisión (confirmada):** estas **NO cuentan** para el avance. Actividades **antes** de la 1ª cabecera → no cuentan. Actividades **después** del cierre de la última unidad de contenido → no cuentan (parciales, integrador quedan fuera).
   - **Implicación de modelado:** el bloque de la unidad `U` = secciones con `section#` ∈ `[cabecera_U, cabecera_{U+1})`. La **última** unidad necesita un **tope** (si no, absorbe todo lo posterior). → el ABM guarda, además de las cabeceras, el **`section#` de cierre** de la última unidad de contenido (auto-sugerido como la última sección satélite antes de "Trabajo Integrador"/"Evaluaciones"; ajustable). Una actividad cuyo `section#` supere ese tope → no cuenta.

---

## 7. Snapshot + Cron

- **`SnapshotService.generar(materia_id, origen)`**: trae alumnos (`get_enrolled_users_full`, rol student) → trae completion → mapea a unidades → categoriza → persiste `AvanceSnapshot` + N×`AvanceAlumno`. Llamadas a Moodle **serializadas**.
- **Cron**: APScheduler (`AsyncIOScheduler`, nueva dependencia) arrancado en el `lifespan` de `app/main.py`. Job diario (24hs) que corre `generar()` para **todas las materias elegibles** (con config completa), una por una.
- **Botón manual / endpoint**: `POST /gestion/dashboard/snapshot?materia_id=` dispara `generar(..., origen=MANUAL)` on-demand. (Temporal para pruebas — se quita junto con el botón del front cuando el cron esté validado.)
- **Idempotencia/histórico**: cada corrida inserta un snapshot nuevo (fechado). El dashboard lee **el más reciente** por materia; las tendencias leen la serie.

---

## 8. API (endpoints)

**Admin (config):**
- `Cohorte` CRUD · `Cuatrimestre` CRUD (bajo `require_admin`).
- `Materia`: editar `cuatrimestre_id` + `unidad_actual`; sub-recurso **Unidades** (CRUD por materia).
- `Rubrica`: setear `unidad_id` (opcional).

**Dashboard (GESTOR/ADMIN — `require_gestor_or_admin`):**
- `GET /gestion/dashboard/cohortes` → árbol `Cohorte → Cuatrimestre → Materias` (para los selectores).
- `GET /gestion/dashboard/avance?cohorte_id=&cuatrimestre_id=&materia_id=` → conteo por estado del **último snapshot** + título dinámico. (`materia_id` omitido = "Todos" del cuatrimestre.)
- `GET /gestion/dashboard/avance/detalle?...&estado=` → lista de alumnos en ese estado (alimenta el modal).
- `GET /gestion/dashboard/tendencia?...` → serie temporal de conteos por estado (histórico). *(fase 2 del front, opcional al inicio.)*
- `POST /gestion/dashboard/snapshot?materia_id=` → trigger manual (temporal).

---

## 9. Frontend

- **Charts**: instalar **Recharts** (⚠️ a confirmar). `PieChart` con `onClick` por `Cell` → abre modal.
- **Feature** `frontend/src/features/gestion-dashboard/` (o extender `gestion/`): selectores encadenados, gráfico, modal de detalle, (opcional) gráfico de tendencia.
- **Selectores**: Cohorte → habilita Cuatrimestre → habilita Materia (+"Todos"). Título dinámico según selección.
- **Modal de detalle**: tabla `Nombre · Apellido · Email · Actividad actual`. Reusa `Modal`, `Table`, `LoadingState`, `HelpButton` (todos ya con tokens del design system + dark mode).
- **Routing/rol**: el dashboard de GESTOR deja de redirigir a `/gestion` y muestra esta pantalla (corrige el "Rol desconocido" histórico).
- **Admin UI**: ABM de Cohortes/Cuatrimestres y, dentro de la Materia, configuración de Unidades (`numero` + `moodle_section_id`) y `unidad_actual`.

---

## 10. Tareas (TDD — RED→GREEN, repos/MoodleService mockeados)

| # | Tarea | Gobernanza |
|---|-------|-----------|
| **T0** | ✅ **HECHO** — Spike Moodle (`backend/scripts/spike_dashboard_gestores.py`) contra `course_id=38`. Validó contents + completion, descubrió el modelo cabecera+rango (§6.1) y midió performance (~2s/alumno). | — |
| **T1** | Modelo + migraciones: `Cohorte`, `Cuatrimestre`, `Unidad`, `Materia.cuatrimestre_id` + `unidad_actual`, `Rubrica.unidad_id`, `EstadoAvanceEnum`, `AvanceSnapshot`, `AvanceAlumno`. (Alembic **dentro de Docker**.) | MEDIUM |
| **T2** | CRUD admin `Cohorte` + `Cuatrimestre` (repo/service/router/schemas). | LOW |
| **T3** | CRUD `Unidad` por materia + `unidad_actual` + `Rubrica.unidad_id`. | LOW |
| **T4** | `MoodleService`: `get_course_contents()` + `get_activities_completion(userid)` (según T0). | MEDIUM |
| **T5** | `SnapshotService.generar()` — cálculo de estado + persistencia. Tests con Moodle mockeado. | MEDIUM |
| **T6** | Cron APScheduler (lifespan) + endpoint manual `POST /snapshot`. | MEDIUM |
| **T7** | Endpoints dashboard: `cohortes` (árbol), `avance` (pie + título), `detalle`, `tendencia`. | LOW |
| **T8** | Frontend admin: ABM Cohortes/Cuatrimestres + Unidades/`unidad_actual` en Materia. | LOW |
| **T9** | Frontend dashboard GESTOR: Recharts, selectores encadenados, título dinámico, modal de detalle. | MEDIUM |
| **T10** | Ayuda contextual (`help-system-content`) + `LoadingState` + reemplazo del dashboard GESTOR. | LOW |

---

## 11. Riesgos / preguntas abiertas

**Resueltas:** ✅ Recharts · ✅ precarga de cohortes (§5.1) · ✅ `unidad_actual` la setea el admin · ✅ materia = un solo cuatrimestre/cohorte.

**Resueltas (post-spike):** ✅ performance medida (serial ~28 min/materia, aceptable) · ✅ parciales/integrador NO cuentan · ✅ cabeceras por auto-detección + confirmación · ✅ cron serial.

**Queda abierta:**
1. **Frecuencia/horario del cron** — supuesto: **1×/día de madrugada** (ej. 03:00 `America/Argentina/Buenos_Aires`). Ajustable; lo confirmamos al llegar a T6.

---

## 12. Orden sugerido de ejecución

```
T0 (spike) ─→ T1 (modelo) ─┬─→ T2 (cohortes ABM) ──────────────┐
                            ├─→ T3 (unidades ABM) ──┐            │
                            └─→ T4 (Moodle WS) ─→ T5 (snapshot) ─→ T6 (cron) ─→ T7 (endpoints) ─→ T9 (dashboard) ─→ T10
                                                    T8 (admin front) ──────────────────────────────┘
```
T0 es **bloqueante** (valida supuestos de Moodle). T2/T3/T8 (ABM) pueden ir en paralelo con la rama de Moodle/snapshot.
