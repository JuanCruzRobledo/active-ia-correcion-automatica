# Pendientes "fantasma" en `/pendientes` (Pendientes Moodle)

Documenta la investigación de los "pendientes fantasma": entregas que aparecen como
pendientes de corrección en Active-IA pero que **no lo están** en Moodle. Incluye lo
ya resuelto y un caso abierto con su fix propuesto.

## Contexto técnico

`GET /api/v1/pendientes/moodle` → `MoodleService.get_pendientes()` calcula los pendientes
**en vivo contra Moodle** (no usa la tabla local `entregas`). Por cada (rúbrica × comisión)
llama `get_submissions_count()`, que cuenta como `espera` las submissions del grupo según
`mod_assign_get_submissions` + `mod_assign_get_grades`.

Los "miembros del grupo" salen de `_get_group_member_ids()` (vía `core_enrol_get_enrolled_users`
filtrado por `groupid`).

---

## ✅ Resuelto #1 — Re-entrega por timestamps (alumno ya calificado)

**Síntoma:** un alumno **ya corregido** (incluso Aprobado) aparecía pendiente; en el
calificador de Moodle no figuraba nada para corregir.

**Causa:** `get_submissions_count` marcaba `espera` cuando
`submission.timemodified > grade.timemodified` (heurística de "re-entrega"). Ese timestamp
se mueve cuando el alumno edita/reabre la entrega aunque Moodle la siga dando por
`gradingstatus="graded"`.

**Caso real:** COMI-12 / TP JavaScript, uid 955, Aprobado (escala índice `2.0`) el 23/04,
entrega tocada el 13/06 → aparecía pendiente.

**Fix (PR #8):** confiar en el `gradingstatus` de Moodle. Una entrega es `espera` solo si
`gradingstatus != "graded"` **o** no hay nota real (`es_calificacion_real`, descartando el
placeholder `grade=-1`). Se eliminó el override por timestamps. Usa `get_grades_full`
(nota + fecha) en lugar de `_fetch_grades_map`. Las re-entregas que sí requieren
recorrección se siguen detectando porque Moodle las marca `gradingstatus="notgraded"`.

---

## ✅ Resuelto #2 — Alumnos suspendidos contaban como pendientes

**Causa:** `_get_group_member_ids()` traía los miembros del grupo **sin** `onlyactive`, así
que un alumno con la matriculación **suspendida** (que NO aparece en el calificador de
Moodle) podía contar como pendiente.

**Fix:** `_get_group_member_ids()` ahora pide `onlyactive=1` a
`core_enrol_get_enrolled_users`. Test: `test_group_member_ids_pide_solo_activos`.

---

## ⚠️ ABIERTO — Entrega registrada pero alumno fuera del calificador

**Síntoma:** quedan 1-2 alumnos que aparecen como pendientes pero **no figuran en el
calificador del assignment** en Moodle (`mod/assign/view.php?action=grading`, ni con el
filtro "ver todos"), aunque sí figuran en **Participantes** del curso.

**Casos observados (COMI-12, course_id=44, group_id=4190):**

| Alumno | uid | TP(s) | Estado en Moodle |
|--------|-----|-------|------------------|
| NAZARENO OSCAR MALPASSI | 955 | Funcional (cmid 13311), Lombok (13286), JPA (13807) | activo en el grupo; entrega `submitted/notgraded`, `grade=-1`; **no listado en el calificador** |
| JUAN IGNACIO MALATESTA | 143 | Lombok (13286) | activo; entrega del 17/06 sin calificar |

**Descartado con diagnósticos read-only:**
- No es el fantasma #1 (acá `gradingstatus=notgraded`, no `graded`).
- No es suspensión (`onlyactive` los devuelve igual: 33 en el grupo, 0 suspendidos).
- No hay nota real tapada por el `-1` (un solo intento `a0`, `grade=-1`, sin nota previa).

**Causa raíz:** el conteo se basa en **membresía del grupo + existe entrega**, mientras que
el calificador de Moodle usa la **lista REAL de participantes del assignment**
(`mod_assign_get_participants`), que por algún motivo excluye a estos alumnos
(probable re-matriculación / cambio de grupo; el usuario reportó "antes me figuraba").
Es una inconsistencia del lado de Moodle: existe el registro de `submission` para un usuario
que el assignment ya no lista como participante.

### Fix propuesto (requiere acción en Moodle)

1. **Habilitar `mod_assign_get_participants`** en el external service del token de Moodle.
   Hoy está deshabilitada (devuelve *"No se puede encontrar registro de datos en la tabla
   external_functions"*).
2. En `get_submissions_count` (o en la resolución de miembros), **cruzar** los miembros del
   grupo contra la lista de `mod_assign_get_participants(assignid)` y contar solo los que
   están en **ambos**. Así el conteo matchea exactamente el calificador de Moodle y los
   "ghosts" (entrega registrada sin ser participante) dejan de contar.

Mientras tanto el desfase es chico (1-2 alumnos en pocos TPs) y el bug principal está
resuelto. Alternativa sin tocar Moodle: revisar/re-guardar el assignment o re-matricular al
alumno desde Moodle para que el calificador lo vuelva a listar.

---

## Diagnóstico (read-only)

La investigación se hizo con scripts read-only ejecutados en la Console del backend
(easypanel), que reproducen el cálculo y vuelcan el detalle por alumno
(`gradingstatus`, `sub_tm`, `grade_tm`, valor de nota, intentos, participantes).
No escriben nada en la DB ni en Moodle.
