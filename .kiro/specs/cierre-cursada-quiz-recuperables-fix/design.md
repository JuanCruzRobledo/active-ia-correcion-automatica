# Cierre de Cursada — Quiz + Recuperables Bugfix Design

## Overview

Este diseño ataca seis defectos del **Cierre de Cursada** de Active-IA y de la
exploración/sincronización de grupos de Moodle. Todos afectan la carga de exámenes de
recuperatorio o la generación del reporte (clasificación + planilla Excel). Cada bug tiene
una causa raíz independiente, pero comparten el mismo pipeline (`ExamenMateria` →
`examen_mapper` → `cierre_cursada_calculo` → `cierre_cursada_service` → `excel_cierre_cursada`),
así que se resuelven de forma coordinada en una sola spec.

Resumen de la estrategia por bug:

- **Bug 1 (assign/quiz)** — `ExamenMateria` sólo guarda `moodle_cmid`, sin distinguir si la
  actividad de Moodle es Tarea (`assign`) o Cuestionario (`quiz`). Se agrega la columna
  `tipo_actividad` (enum nuevo `TipoActividadMoodleEnum` con valores `assign`/`quiz`), con
  migración que deja los registros existentes en `assign`, edición desde el ABM, resolución del
  link de Moodle según el tipo (`/mod/quiz/view.php` vs `/mod/assign/view.php`) y selección de la
  fuente de notas por tipo (el grade estructural `mod_assign_get_grades` sólo aplica a `assign`).

- **Bug 2 (Excel de 2 hojas)** — hoy el generador produce un único worksheet. Se refactoriza
  `excel_cierre_cursada` para emitir DOS hojas: "por Comisiones" (cuadros por comisión) y "Crudo"
  (lista plana alfabética con columnas Comision y Tutor), respetando el modelo
  `docs/modelos/Cierre_Programacin_3 FIX.xlsx`.

- **Bug 3 (exploración Moodle)** — los grupos de comisión llegan embebidos en el `groups[]` de
  `core_enrol_get_enrolled_users`, que en cursos con **grupos separados** omite los grupos que el
  usuario que consulta no puede ver. Eso hace que comisiones enteras no aparezcan (Prog 3:
  `M25 C3-01/02/15`) y que alumnos con comisión válida queden "Sin comisión" (Prog 1). El fix
  construye un mapa autoritativo `uid → grupos` con `core_group_get_course_groups` +
  `core_group_get_group_members` y lo usa como fuente primaria para resolver la comisión.

- **Bug 4 (fórmulas nativas)** — los conteos del resumen y la columna Recuperable se escriben
  como valores estáticos de Python. Se reemplazan por fórmulas nativas de Excel (`SI`/`CONTAR.SI`)
  con las referencias de columna exactas por hoja, de modo que editar el "Estado Alumno" recalcule
  el resumen y la marca de recuperable en vivo.

- **Bug 5 (ABANDONO)** — un alumno con todo en `N/E` hoy cae en RECURSA. Se agrega el estado
  ABANDONO (nuevo valor de `EstadoCierreEnum`) para el caso de no haber rendido ningún examen.

- **Bug 6 (Nota Final de REGULARIZA)** — hoy REGULARIZA queda con Nota Final en blanco. Se cambia
  para asignar SIEMPRE Nota Final = 5. Ver la sección "Decisión: Bug 6 vs modelo de referencia"
  para la discrepancia con `cierre-cursada-comision-nota-fix` y con el modelo (que muestra blanco).

Bugs 1 y 5 tocan modelo + migración (columna nueva / valor de enum nuevo). Bugs 2 y 4 se
concentran en `excel_cierre_cursada`. Bug 3 toca `moodle_service` + `cierre_cursada_service`
(resolución de comisión). Bug 6 es un cambio quirúrgico en `cierre_cursada_calculo`.

## Glossary

- **Bug_Condition (C)**: la condición de entrada que dispara cada defecto (formalizada por bug en
  "Bug Details").
- **Property (P)**: el comportamiento correcto esperado para las entradas que cumplen C.
- **Preservation**: el comportamiento existente que NO debe cambiar (mouse/otros inputs, estilos,
  clasificación PROMOCIONA, orden de comisiones, histórico append-only, etc.).
- **ExamenMateria**: modelo (`backend/app/models/examen_materia.py`) de un examen de la materia
  (PARCIAL/RECUPERATORIO/EXTENSION/EXTRAORDINARIA/GLOBAL). Fuente de verdad del cierre.
- **tipo_actividad**: campo NUEVO de `ExamenMateria` que marca la actividad de Moodle subyacente:
  `assign` (Tarea) o `quiz` (Cuestionario).
- **grade estructural**: `mod_assign_get_grades` de Moodle — sólo existe para actividades `assign`;
  distingue "entregado sin corregir" (grade=-1) de "ausente". No existe para `quiz`.
- **hoja "por Comisiones"**: worksheet 1 del Excel, agrupado en cuadros por comisión.
- **hoja "Crudo"**: worksheet 2 del Excel, lista plana alfabética con columnas Comision y Tutor.
- **Recuperable**: alumno RECURSA con un parcial `>= 40` y el otro `< 40`/no entregado.
- **ABANDONO**: alumno que no rindió ningún examen ni el global (todo `N/E`).
- **grupos separados (Moodle)**: `groupmode=1` de un curso; `core_enrol_get_enrolled_users` omite
  del `groups[]` de cada usuario los grupos que el consultante no puede ver sin la capability
  `moodle/site:accessallgroups`.

## Bug Details

### Bug 1 — Tipo de actividad ASSIGN vs QUIZ

El bug se manifiesta al dar de alta (o editar) un examen que en Moodle es un cuestionario
(`quiz`) y vincularlo como recuperatorio/extraordinaria de un parcial (caso "Extraordinaria 2" y
"Extraordinaria 3" de Programación 2 sobre el Parcial 2). Hoy `ExamenMateria` no tiene forma de
representar el tipo de actividad: sólo guarda `moodle_cmid` y se asume implícitamente que toda
actividad es Tarea (`assign`). El link/recurso de Moodle (`construir_url_entrega` en
`moodle_url_parser.py` arma SIEMPRE `/mod/assign/view.php?id=...`) y la elección de la fuente de
notas no distinguen `quiz` de `assign`.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = { accion, examen: {tipo, moodle_cmid, actividad_moodle_real} }
         accion IN {"alta", "edicion", "resolver_link", "resolver_notas"}
  OUTPUT: boolean

  RETURN input.examen.actividad_moodle_real == "quiz"
         AND NOT existeCampoTipoActividad(input.examen)   // hoy: siempre falta el campo
END FUNCTION
```

#### Examples

- Se da de alta "Extraordinaria 2" de Programación 2 (quiz cmid 17679) como rescate del Parcial 2:
  esperado = alta OK con `tipo_actividad = quiz`; actual = no hay forma de marcar el tipo, se
  asume `assign`.
- Se resuelve el link de un examen quiz: esperado = `https://.../mod/quiz/view.php?id=17679`;
  actual = `https://.../mod/assign/view.php?id=17679` (recurso equivocado).
- Se resuelven las notas de un examen quiz: esperado = usar la nota del calificador (texto), sin
  intentar el grade estructural de assign; actual = camino único que asume assign.
- (Edge) Examen assign existente antes del cambio: esperado = queda como `assign` por defecto y
  sigue funcionando igual.

### Bug 2 — El Excel de cierre sólo tiene una hoja

Se manifiesta al generar la planilla: `generar_excel_cierre` crea un único `ws = wb.active` con los
bloques por comisión. No existe la segunda hoja plana ("Crudo") del modelo de referencia, ni las
columnas Comision/Tutor por alumno en esa hoja.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = { run: CierreCursadaRun }   // corrida ya calculada
  OUTPUT: boolean

  wb := generar_excel_cierre(run)
  RETURN cantidadDeHojas(wb) != 2
         OR NOT existeHoja(wb, "{materia} Crudo")
         OR NOT hojaCrudoTieneColumnas(wb, ["Comision", "Tutor"])
END FUNCTION
```

#### Examples

- Cierre de Programación 3: esperado = 2 hojas ("Programación 3 por Comisiones" + "Programación 3
  Crudo"); actual = 1 hoja.
- Hoja "Crudo": esperado = lista plana ordenada alfabéticamente por alumno con columnas Comision y
  Tutor; actual = no existe.

### Bug 3 — La exploración de Moodle no trae/asocia bien las comisiones

Se manifiesta al explorar/sincronizar un curso: comisiones enteras no aparecen (Prog 3:
`M25 C3-01`, `M25 C3-02`, `M25 C3-15`) y alumnos con comisión válida se cuentan como "Sin comisión
asignada" (Prog 1). Tanto `GestionService.opciones_filtros/consultar` como
`CierreCursadaService._resolver_comision` dependen del `groups[]` embebido que devuelve
`core_enrol_get_enrolled_users`.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = { alumno_uid, course_id, grupos_reales_en_moodle }
  OUTPUT: boolean

  grupos_devueltos := enrolledUser(course_id, alumno_uid).groups   // groups[] embebido
  RETURN existeGrupoComision(grupos_reales_en_moodle)
         AND NOT existeGrupoComision(grupos_devueltos)   // el grupo real no vino en el groups[]
END FUNCTION
```

#### Examples

- Prog 3, comisión `M25 C3-01`: esperado = aparece en el explorador y sus alumnos se asocian;
  actual = no aparece (ningún `groups[]` la incluye).
- Prog 1, alumno del grupo `M25 C1-05`: esperado = queda asociado a su comisión; actual = "Sin
  comisión asignada".
- (Edge) Alumno realmente sin grupo de comisión: esperado = "Sin comisión asignada" (se preserva).

### Bug 4 — Conteos y columna "Recuperable" con valores estáticos

Se manifiesta al generar el Excel: `_escribir_resumen` escribe los conteos
(PROMOCIONADOS/REGULARES/RECURSANTES) como enteros fijos (`run.total_*`), y no hay columna ni
conteo de Recuperables. Si el usuario edita el "Estado Alumno" de una fila, nada se recalcula.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = { celda_resumen | celda_recuperable }
  OUTPUT: boolean

  RETURN esValorEstatico(input.celda_resumen)          // número Python, no fórmula
         OR NOT existeColumnaRecuperable(input)
         OR NOT esFormulaNativa(input.celda_recuperable)
END FUNCTION
```

#### Examples

- Celda "PROMOCIONADOS": esperado = `=CONTAR.SI(F:F;"PROMOCIONA")`; actual = `42` (entero fijo).
- Columna Recuperable (fila): esperado = fórmula `SI(...)` que marca "RECUPERABLE CON PARCIAL 1/2";
  actual = no existe.
- Editar el Estado de una fila a mano: esperado = el resumen y la marca de recuperable se
  recalculan; actual = quedan con el valor original.

### Bug 5 — Falta el estado ABANDONO

Se manifiesta al clasificar a un alumno que no rindió ningún examen ni el global (todo `N/E`):
`calcular_estado_cierre` lo clasifica como RECURSA porque no cumple promoción ni banda.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = { examenes: [{tipo, resultado_escala, valor_real, modo_aprobacion}] }
  OUTPUT: boolean

  todos_ne := PARA TODO e EN examenes:
                (e.modo == "ESCALA" Y e.resultado_escala NOT IN {"aprobado","desaprobado"})
                O (e.modo == "NUMERICO" Y e.valor_real IS NULL)
  RETURN todos_ne AND clasificacionActual(examenes) == "RECURSA"
END FUNCTION
```

#### Examples

- Alumno sin ninguna nota (Parcial 1, Parcial 2, Global todos `N/E`): esperado = ABANDONO; actual =
  RECURSA.
- (Edge) Alumno con Parcial 1 desaprobado y el resto `N/E`: esperado = RECURSA (rindió algo, no es
  abandono); se preserva.

### Bug 6 — Nota Final de REGULARIZA

Se manifiesta al persistir/mostrar un alumno REGULARIZA: `calcular_estado_cierre` devuelve
`nota_final = None` para todo estado distinto de PROMOCIONA, por lo que la columna "Nota Final"
queda en blanco.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = { veredicto: {estado, nota_final} }
  OUTPUT: boolean

  RETURN input.veredicto.estado == "REGULARIZA"
         AND input.veredicto.nota_final != 5
END FUNCTION
```

#### Examples

- Alumno REGULARIZA: esperado = Nota Final = 5 (persistida y en el Excel); actual = en blanco
  (`None`).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Los exámenes `assign` (Tarea) resuelven notas y link exactamente como hoy (el default del campo
  nuevo es `assign`, equivalente al comportamiento actual).
- La cadena de rescate (un PARCIAL/GLOBAL queda aprobado si aprobó el original o cualquier
  recu/ext/extraordinaria) mantiene su precedencia actual.
- La clasificación PROMOCIONA y su Nota Final ponderada (parciales 0–10 al 40 %, global al 60 %,
  `round_half_up`) no cambian.
- La clasificación REGULARIZA/RECURSA sólo cambia en los dos casos de esta spec (ABANDONO para todo
  `N/E`; Nota Final = 5 para REGULARIZA).
- El orden numérico natural de las comisiones y el orden alfabético de alumnos dentro de cada bloque
  (`comision-orden-numerico-fix`, `cierre-cursada-comision-nota-fix`) se mantienen, con "Sin
  comisión asignada" al final.
- El fallback "Sin comisión asignada" ante mapeo ausente/ambiguo sigue sin romper la corrida.
- Las columnas de examen (`Parcial n`, `Global TPI`) siguen mostrando `N/E` cuando no hay nota.
- El histórico append-only de corridas y el congelado de `examenes_snapshot` no cambian.
- Los estilos visuales de la casa (`excel_estilos.py`) se siguen usando en ambas hojas.
- El bloqueo con 400 cuando la materia no tiene exámenes PARCIAL/GLOBAL se preserva.
- Los exámenes en modo ESCALA se siguen evaluando por Aprobado/Desaprobado, no por nota numérica.

**Scope:**
Toda entrada que NO cumple la condición de bug correspondiente debe quedar inalterada:
- Bug 1: exámenes `assign` (mouse de "editar/eliminar", link, notas) intactos.
- Bug 3: alumnos que realmente no tienen grupo de comisión siguen en "Sin comisión asignada".
- Bug 5: alumnos que rindieron al menos un examen siguen clasificándose como hoy.
- Bug 6: alumnos PROMOCIONA (Nota Final ponderada) y RECURSA/ABANDONO (sin Nota Final numérica)
  no cambian por este bug.

## Hypothesized Root Cause

### Bug 1 — Falta un campo de tipo de actividad
`ExamenMateria` modela `moodle_cmid` pero no el tipo de actividad de Moodle. El resto del código
asume `assign`:
1. `moodle_url_parser.construir_url_entrega` arma SIEMPRE `/mod/assign/view.php`.
2. `cierre_cursada_service.generar` decide traer el grade estructural mirando el `modname` real de
   Moodle (`mod.get("modname") == "assign"`), lo que funciona, pero no hay una marca persistida en
   el examen para el link ni para el ABM/UI.
Sin un campo `tipo_actividad`, no se puede dar de alta un examen quiz de forma explícita ni resolver
su recurso correctamente.

### Bug 2 — Generador de una sola hoja
`generar_excel_cierre` usa `wb.active` y escribe un solo worksheet; no hay función que emita la
hoja plana ni las columnas Comision/Tutor.

### Bug 3 — Dependencia del `groups[]` embebido con grupos separados
`core_enrol_get_enrolled_users` devuelve, por usuario, sólo los grupos que el usuario que consulta
puede ver. En cursos con **grupos separados** (`groupmode=1`) y sin la capability
`moodle/site:accessallgroups`, Moodle omite del `groups[]` los grupos ajenos. Resultado:
- Comisiones cuyos alumnos no comparten grupo visible con el consultante no aparecen (Prog 3).
- Alumnos cuyo grupo de comisión no es visible quedan sin `groups[]` de comisión → "Sin comisión"
  (Prog 1).
Hipótesis secundaria (a descartar en la exploración): variaciones de formato del nombre de grupo
(espacios múltiples, NBSP, guion distinto) que hacen fallar el regex `_COMISION_RE`.

### Bug 4 — Conteos y recuperable calculados en Python
`_escribir_resumen` escribe `run.total_*` como enteros; no hay columna auxiliar de recuperable ni
fórmulas. Al no ser fórmulas, editar el Excel no recalcula nada.

### Bug 5 — Sin rama ABANDONO en el árbol de decisión
`calcular_estado_cierre` sólo distingue PROMOCIONA/REGULARIZA/RECURSA; el caso "todo ausente" cae
en el `else` (RECURSA).

### Bug 6 — Nota Final None para no-PROMOCIONA
`calcular_estado_cierre` hace `nota_final = calcular_nota_final(...) if estado == "PROMOCIONA" else
None`, dejando REGULARIZA en blanco.

## Correctness Properties

Property 1: Bug Condition — Alta/edición y resolución de examen `quiz`

_For any_ examen cuya actividad de Moodle es un cuestionario (`isBugCondition` de Bug 1 true), el
sistema fijado SHALL permitir persistir `tipo_actividad = quiz` en el alta/edición, resolver su link
como `/mod/quiz/view.php?id={cmid}` y elegir la fuente de notas por texto del calificador (sin grade
estructural de assign).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Bug Condition — Excel con dos hojas

_For any_ corrida de cierre (`isBugCondition` de Bug 2 true), el Excel generado SHALL tener
exactamente dos hojas: "{materia} por Comisiones" (cuadros por comisión, comisiones en orden natural
y alumnos alfabéticos dentro de cada cuadro) y "{materia} Crudo" (lista plana alfabética por alumno
con columnas Comision y Tutor).

**Validates: Requirements 2.5, 2.6, 2.7**

Property 3: Bug Condition — Comisiones resueltas por mapa autoritativo

_For any_ alumno que pertenece a un grupo de comisión válido en Moodle (`isBugCondition` de Bug 3
true), el sistema fijado SHALL asociarlo a su comisión (y traer la comisión al explorador) usando el
mapa autoritativo `core_group_get_course_groups` + `core_group_get_group_members`, en lugar de
depender del `groups[]` embebido.

**Validates: Requirements 2.8, 2.9, 2.10**

Property 4: Bug Condition — Conteos y Recuperable con fórmulas nativas

_For any_ hoja del Excel (`isBugCondition` de Bug 4 true), el sistema fijado SHALL escribir los
conteos del resumen (Promocionados/Regulares/Recursantes/Recuperables/Abandonos) y la columna
Recuperable por alumno como fórmulas nativas (`SI`/`CONTAR.SI`) con las referencias de columna
exactas por hoja, de modo que editar el "Estado Alumno" recalcule el resumen y la marca.

**Validates: Requirements 2.11, 2.12, 2.13, 2.14, 2.15**

Property 5: Bug Condition — Estado ABANDONO

_For any_ alumno cuyos exámenes principales están todos en `N/E` (`isBugCondition` de Bug 5 true),
el sistema fijado SHALL clasificarlo como ABANDONO (no RECURSA) y contarlo como ABANDONO, distinto
de RECURSA.

**Validates: Requirements 2.16, 2.17**

Property 6: Bug Condition — Nota Final = 5 para REGULARIZA

_For any_ alumno con estado REGULARIZA (`isBugCondition` de Bug 6 true), el sistema fijado SHALL
asignarle Nota Final = 5 (persistida y mostrada en el Excel).

**Validates: Requirements 2.18**

Property 7: Preservation — Exámenes assign y clasificación existente

_For any_ entrada que NO cumple ninguna condición de bug (examen `assign`, alumno que rindió algo,
alumno PROMOCIONA, input de mouse/otras teclas), el sistema fijado SHALL producir el mismo resultado
que el original: link `/mod/assign/view.php`, grade estructural de assign, clasificación
PROMOCIONA/RECURSA con su Nota Final actual, orden de comisiones/alumnos, `N/E` en columnas de
examen, histórico append-only y estilos de la casa.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12**

## Decisión: Bug 6 vs modelo de referencia

El modelo `Cierre_Programacin_3 FIX.xlsx` muestra a los alumnos REGULARIZA con la celda "Nota Final"
en blanco (refleja el estado ANTERIOR, spec `cierre-cursada-comision-nota-fix`, Bug 4). La
instrucción explícita del usuario (Bug 6) pide **Nota Final = 5** para REGULARIZA. Este diseño sigue
la instrucción del usuario (= 5) y deja documentada la discrepancia: si el negocio prefiriera
mantener el blanco del modelo, debe confirmarse antes de implementar. La implementación concentra la
regla en un único punto (`calcular_estado_cierre`) para que revertirla sea trivial (cambiar `5` por
`None`).

## Fix Implementation

### Bug 1 — Tipo de actividad ASSIGN vs QUIZ

**Enum nuevo** — `backend/app/models/enums.py`:
- Agregar `class TipoActividadMoodleEnum(str, Enum)` con `ASSIGN = "assign"` y `QUIZ = "quiz"`
  (valores en minúscula para comparar directo con `modname` de Moodle).

**Modelo** — `backend/app/models/examen_materia.py`:
- Agregar columna `tipo_actividad: Mapped[TipoActividadMoodleEnum]` con
  `SQLEnum(TipoActividadMoodleEnum, name="tipoactividadmoodleenum", create_type=True)`,
  `nullable=False`, `server_default="assign"`.

**Migración** — nueva revisión Alembic (`down_revision = 'e4f5a6b7c8d9'`, la head actual):
1. `CREATE TYPE tipoactividadmoodleenum AS ENUM ('assign','quiz')` (con `checkfirst`).
2. `ADD COLUMN tipo_actividad ... NOT NULL DEFAULT 'assign'` en `examenes_materia` → los registros
   existentes quedan en `assign` (cumple 2.2). Escrita a mano al estilo de
   `20260610_1600_..._examenes_materia.py`.
3. `downgrade`: `DROP COLUMN` + `DROP TYPE`.

**Schemas** — `backend/app/schemas/examen.py`:
- `ExamenMateriaCreate` y `ExamenMateriaUpdate`: agregar `tipo_actividad: TipoActividadMoodleEnum`
  con default `ASSIGN` (así los clientes viejos que no lo mandan quedan en assign).
- `ExamenMateriaResponse`: agregar `tipo_actividad`.

**Service** — `backend/app/services/examen_service.py`:
- `crear`/`actualizar`: setear `examen.tipo_actividad = data.tipo_actividad`.
- `_a_response`: incluir `tipo_actividad=examen.tipo_actividad`.

**Resolución de link** — `backend/app/services/moodle_url_parser.py`:
- Agregar helper puro `construir_url_actividad(host, cmid, tipo_actividad) -> str | None` que arma
  `/mod/quiz/view.php?id={cmid}` si `tipo_actividad == "quiz"` y `/mod/assign/view.php?id={cmid}` si
  `assign`. `construir_url_entrega` se deja intacto (lo usan las entregas de alumno, que siempre son
  assign) → preserva 3.1.

**Resolución de notas por tipo** — `backend/app/services/cierre_cursada_service.py`:
- Incluir `tipo_actividad` en el dict `examenes_config`.
- En el armado de `grades_por_cmid`, condicionar la llamada a `get_grades_full` a
  `ex["tipo_actividad"] == "assign"` (además del `modname`), para no intentar grade estructural en
  un `quiz`. El camino por texto de `examen_mapper` para `quiz` ya existe (usa el calificador).

**Frontend** — `frontend/src/features/materia-dashboard/`:
- `types/index.ts`: agregar `type TipoActividadMoodle = 'assign' | 'quiz'`, campo `tipo_actividad`
  en `ExamenMateria` y `ExamenInput`.
- `components/ExamenesEditor.tsx`: agregar un `Select` "Actividad de Moodle" (Tarea/Cuestionario),
  cargarlo en `cargarParaEditar`, incluirlo en el payload de `guardar` y mostrarlo como columna en
  la tabla. Default `assign`.

### Bug 2 — Excel de dos hojas

**Archivo** — `backend/app/services/excel_cierre_cursada.py`. `generar_excel_cierre` pasa a orquestar
dos hojas (respetando el límite de 500 LOC: extraer helpers):
1. Hoja 1 "por Comisiones": renombrar la lógica actual (`_escribir_resumen` +
   `_escribir_detalle` + `_agrupar_por_comision`) para escribir sobre `ws1 = wb.active`, con título
   `sheet_title(f"{materia_nombre} por Comisiones")`.
2. Hoja 2 "Crudo": nueva `ws2 = wb.create_sheet(sheet_title(f"{materia_nombre} Crudo"))`. Nueva
   función `_escribir_hoja_cruda(ws2, run, parciales, global_examen)`:
   - Encabezados: `Nombre y Apellido | Email | Comision | Tutor | Parcial n… | Global TPI | Estado
     Alumno | Nota Final | Recuperable`.
   - Filas: TODOS los alumnos ordenados alfabéticamente por `(apellido, nombre)` — sin cuadros por
     comisión —, con `comision_nombre` ("Sin comisión asignada" si aplica) y `tutor_nombre`.
   - Resumen arriba (banda + conteos) igual que la hoja 1, con las referencias de columna de la hoja
     "Crudo" (ver Bug 4).
- Se reutilizan los helpers de `excel_estilos.py` (`banda_titulo`, `celda_header`, `fila_datos`) →
  preserva 3.10.

### Bug 3 — Exploración/sincronización de grupos

**Exploración (diagnóstico) primero**: confirmar la hipótesis de grupos separados observando, en un
curso afectado, que `core_enrol_get_enrolled_users` devuelve `groups[]` incompleto mientras
`core_group_get_course_groups` sí lista `M25 C3-01/02/15`. Si se refuta, re-hipotetizar con la
variante de formato de nombre.

**MoodleService** — `backend/app/services/moodle_service.py`:
- Agregar `get_course_groups(token, host, course_id) -> list[dict]` (`core_group_get_course_groups`,
  cacheado por course_id) → `[{id, name}]` de TODOS los grupos.
- Agregar `get_group_members(token, host, group_id) -> list[int]` (`core_group_get_group_members`)
  → `[userid]` por grupo.
- Helper `construir_mapa_uid_grupos(groups, members_por_group) -> dict[int, list[dict]]`
  (`{uid: [{id, name}]}`) autoritativo, independiente del `groups[]` embebido.

**CierreCursadaService** — `_resolver_comision` y `generar`:
- Construir el mapa autoritativo `uid → grupos` una vez por corrida y pasar esos grupos (no
  `u.get("groups")`) a `_resolver_comision`. El bridge por `moodle_group_id` y el fallback por
  `parse_comision` no cambian → preserva 3.7.

**GestionService** — `opciones_filtros`/`consultar`/`exportar_pendientes_excel`:
- Usar el mismo mapa autoritativo para derivar regionales/comisiones y para resolver la comisión de
  cada alumno, en vez de `u.get("groups", [])`.

**Fallback**: si `core_group_get_group_members` no está habilitado en el WS del cliente, degradar al
`groups[]` embebido (comportamiento actual) y loguear la degradación — nunca romper la corrida.

### Bug 4 — Fórmulas nativas de Excel

**Archivo** — `backend/app/services/excel_cierre_cursada.py`. Al escribir cada hoja:
- Columna auxiliar Recuperable por fila (fórmula con la referencia de fila correspondiente):
  - Hoja "por Comisiones" (col H, estado F, parciales C/D):
    `=SI(F{n}<>"RECURSA";"";SI(Y(SI.ERROR(VALOR(C{n});0)>=40;SI.ERROR(VALOR(D{n});0)<40);"RECUPERABLE CON PARCIAL 2";SI(Y(SI.ERROR(VALOR(D{n});0)>=40;SI.ERROR(VALOR(C{n});0)<40);"RECUPERABLE CON PARCIAL 1";"")))`
  - Hoja "Crudo" (col J, estado H, parciales E/F): misma fórmula con las columnas E/F/H/J.
- Conteos del resumen como fórmulas:
  - Hoja "por Comisiones": `=CONTAR.SI(F:F;"PROMOCIONA")`, `="...REGULARIZA")`, `="...RECURSA")`,
    Recuperables `=CONTAR.SI(H:H;"RECUPERABLE*")`, Abandonos `=CONTAR.SI(F:F;"ABANDONO")`.
  - Hoja "Crudo": mismas fórmulas con Estado en `H:H`, Recuperables `=CONTAR.SI(J:J;"RECUPERABLE CON*")`.
- Escribir como fórmula = string que empieza con `=` en `ws.cell(...).value` (openpyxl las persiste
  como fórmula nativa). Las referencias exactas por hoja salen de bugfix.md (confirmadas contra el
  modelo). Nota: se usa la localización es-AR (`SI`, `CONTAR.SI`, `Y`, `VALOR`, `SI.ERROR`, `;` como
  separador) porque el archivo lo abre un Excel en español; documentar esta dependencia de locale.

### Bug 5 — Estado ABANDONO

**Enum** — `backend/app/models/enums.py`: agregar `ABANDONO = "ABANDONO"` a `EstadoCierreEnum`.

**Migración**: agregar el valor al tipo nativo Postgres
(`ALTER TYPE estadocierreenum ADD VALUE IF NOT EXISTS 'ABANDONO'`) en la misma revisión que Bug 1 (o
una dedicada). `ALTER TYPE ... ADD VALUE` no corre dentro de una transacción en algunas versiones de
PG → ejecutar con `op.execute` fuera del bloque transaccional o con autocommit (documentarlo).

**Cálculo** — `backend/app/services/cierre_cursada_calculo.py`, `calcular_estado_cierre`:
- Detectar `todos_ausentes`: para cada examen, "ausente" = modo ESCALA con `resultado_escala` que no
  es `aprobado` ni `desaprobado`, o modo NUMERICO con `valor_real is None`. Si TODOS los principales
  están ausentes → `estado = "ABANDONO"`.
- El chequeo de ABANDONO va ANTES del `else` de RECURSA (y no aplica si el alumno cumple
  promoción/banda) → preserva 3.5.

**Service** — `cierre_cursada_service.generar`:
- Extender `conteos` con `"ABANDONO": 0`.
- Agregar `total_abandono` al `CierreCursadaRun` (nueva columna en el modelo + migración) y a la
  actividad registrada. Alternativa mínima: derivar el total en el Excel por fórmula (Bug 4 ya
  cuenta ABANDONO con `CONTAR.SI`), pero se persiste el conteo por consistencia con los otros
  totales.

**Modelo/migración** — `CierreCursadaRun.total_abandono: Mapped[int]` (`default=0`,
`server_default="0"`); columna nueva en la misma revisión.

### Bug 6 — Nota Final = 5 para REGULARIZA

**Cálculo** — `backend/app/services/cierre_cursada_calculo.py`, `calcular_estado_cierre`:
- Cambiar la asignación de `nota_final`:
  - `PROMOCIONA` → `calcular_nota_final(examenes)` (sin cambios).
  - `REGULARIZA` → `5`.
  - `RECURSA`/`ABANDONO` → `None`.
- `calcular_nota_final` no se toca.

**Excel** — `_fmt_nota_final` ya imprime el entero cuando no es `None`, así que REGULARIZA mostrará
`5` sin cambios adicionales.

## Testing Strategy

### Validation Approach

Primero se surface el bug en el código SIN fijar (tests que fallan), confirmando la causa raíz;
luego se verifica que el fix corrige la condición de bug y preserva el resto. Bug 3 requiere una
fase de exploración explícita para confirmar/refutar la hipótesis de grupos separados antes de
codificar el fix.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples que demuestren cada bug ANTES del fix y confirmar/refutar la
hipótesis de causa raíz (crítico para Bug 3).

**Test Plan**: correr sobre el código sin fijar los siguientes casos y observar el fallo.

**Test Cases**:
1. **Quiz alta/link (Bug 1)**: intentar representar y resolver el link de un examen quiz → hoy no
   hay campo y el link sale `/mod/assign/...` (falla).
2. **Excel una hoja (Bug 2)**: `generar_excel_cierre` sobre una corrida → `len(wb.worksheets) == 1`
   (falla la expectativa de 2).
3. **Grupos separados (Bug 3)**: con un `core_enrol_get_enrolled_users` mockeado que omite el grupo
   de comisión (simulando separate groups), `_resolver_comision` devuelve "Sin comisión" aunque
   `core_group_get_course_groups` sí lista el grupo (falla). **Diagnóstico real**: inspeccionar la
   respuesta de ambos WS en un curso afectado para confirmar la hipótesis; si el `groups[]` viene
   completo, refutar y re-hipotetizar (formato de nombre).
4. **Conteos estáticos (Bug 4)**: leer la celda del resumen → es un `int`, no una fórmula `=CONTAR.SI`
   (falla).
5. **Abandono (Bug 5)**: alumno con todo `N/E` → `calcular_estado_cierre` devuelve `RECURSA` (falla
   la expectativa ABANDONO).
6. **Nota Final REGULARIZA (Bug 6)**: alumno REGULARIZA → `nota_final is None` (falla la expectativa
   `== 5`).

**Expected Counterexamples**: examen quiz sin tipo/link erróneo; Excel de 1 hoja; alumno con grupo
válido resuelto como "Sin comisión"; celdas de resumen numéricas; todo-`N/E` = RECURSA; REGULARIZA
sin nota.

### Fix Checking

**Goal**: para toda entrada que cumple la condición de bug, la función fijada produce el
comportamiento esperado.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)   // ver Correctness Properties 1..6
END FOR
```

### Preservation Checking

**Goal**: para toda entrada que NO cumple la condición de bug, la función fijada produce el mismo
resultado que la original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**Testing Approach**: property-based testing para preservación (genera muchos casos del dominio y
detecta edge cases). Especialmente útil en `cierre_cursada_calculo` (clasificación) y en la
resolución de comisión.

**Test Plan**: observar el comportamiento en el código sin fijar para exámenes assign, alumnos que
rindieron algo y alumnos PROMOCIONA, y escribir tests que verifiquen que se mantiene tras el fix.

**Test Cases**:
1. **Assign preservado (Bug 1)**: examen assign → link `/mod/assign/...`, grade estructural usado,
   notas iguales que hoy.
2. **Clasificación preservada (Bugs 5/6)**: PROMOCIONA (con Nota Final ponderada), RECURSA (rindió y
   no cumple) y REGULARIZA (sólo cambia Nota Final a 5) sin regresiones.
3. **Comisión real preservada (Bug 3)**: alumno realmente sin grupo → "Sin comisión asignada";
   orden de comisiones/alumnos sin cambios.
4. **Estilos y `N/E` (Bugs 2/4)**: ambas hojas usan estilos de la casa y las columnas de examen
   siguen mostrando `N/E`.

### Unit Tests

- `cierre_cursada_calculo`: ABANDONO para todo-`N/E`; RECURSA si rindió algo; REGULARIZA → Nota
  Final 5; PROMOCIONA con Nota Final ponderada intacta.
- `examen_service`/`schemas`: alta/edición con `tipo_actividad`; default `assign`.
- `moodle_url_parser`: `construir_url_actividad` para quiz y assign.
- `excel_cierre_cursada`: 2 hojas; encabezados de la hoja Crudo (Comision/Tutor); celdas de resumen
  y de Recuperable son fórmulas con las referencias correctas por hoja.
- `moodle_service`: parseo de `core_group_get_course_groups`/`core_group_get_group_members` y armado
  del mapa `uid → grupos`.

### Property-Based Tests

- Preservación de la clasificación: generar listas de exámenes aleatorias y verificar que sólo
  cambian los casos ABANDONO (todo-`N/E`) y la Nota Final de REGULARIZA respecto del original.
- Resolución de comisión: generar mapas de grupos aleatorios y verificar que un alumno con grupo de
  comisión válido siempre se asocia (con el mapa autoritativo) y que los ambiguos/vacíos caen en
  "Sin comisión".
- Fórmula Recuperable: generar combinaciones de notas de parciales y estado y verificar que la
  fórmula marca RECUPERABLE CON PARCIAL 1/2 sólo para RECURSA con un parcial `>=40` y el otro `<40`.

### Integration Tests

- Cierre end-to-end (Moodle mockeado): genera la corrida, persiste ABANDONO y `total_abandono`,
  Nota Final 5 para REGULARIZA, y produce el Excel de 2 hojas con fórmulas nativas.
- Flujo de exploración con grupos separados: los alumnos de `M25 C3-01/02/15` aparecen y se asocian
  a su comisión usando el mapa autoritativo.
- ABM de examen quiz: alta como extraordinaria de un parcial, edición assign→quiz, y link resuelto
  a `/mod/quiz/view.php` en el flujo del cierre.
