# Bugfix Requirements Document

## Introduction

La feature "cierre de cursada" presenta dos defectos reportados por el usuario que afectan
el resultado del reporte generado (clasificación por comisión y Nota Final por alumno):

- **Bug 1 — Las comisiones no se cargan.** Al generar el cierre de cursada, TODOS los alumnos
  quedan clasificados como "Sin comisión asignada", aun cuando pertenecen a un grupo de comisión
  válido de Moodle (ej. "M26 C1-09"). La resolución de comisión del cierre depende de que cada
  `Comision` tenga poblado y coincidente el campo manual `moodle_group_code`; cuando ese campo
  está vacío o no coincide con los nombres reales de grupo de Moodle, ningún alumno se asocia a
  su comisión real (`comision_id`, `comision_nombre`, `tutor_nombre`). El módulo de snapshot,
  en cambio, resuelve la comisión correctamente derivándola del nombre del grupo de Moodle.

- **Bug 2 — El "N/E" se propaga incorrectamente a la Nota Final.** Cuando un alumno no entrega
  alguno de los exámenes requeridos (algún parcial o el global), la Nota Final se calcula como
  "N/E". El comportamiento correcto es que los exámenes no entregados se sigan mostrando como
  "N/E" en su propia columna del reporte, pero cuenten como **0** en el cálculo ponderado de la
  Nota Final, que debe ser siempre un valor numérico 0–10.

Además, tras completar los fixes de Bug 1 y Bug 2, el usuario reportó dos ajustes adicionales de
corrección del reporte que refinan la salida del Excel de cierre:

- **Bug 3 — Los bloques de comisión no están ordenados.** En el Excel de cierre, los bloques por
  comisión se escriben en el orden en que los alumnos llegan desde la inscripción de Moodle
  (orden de inserción del diccionario en `_agrupar_por_comision`), por lo que los bloques aparecen
  en un orden arbitrario. El comportamiento correcto es que los bloques de comisión aparezcan
  ordenados ALFABÉTICAMENTE por nombre de comisión (ej. "M26 C1-01", "M26 C1-02", …), y que el
  bloque "Sin comisión asignada" quede SIEMPRE al final. El orden alfabético de los alumnos DENTRO
  de cada bloque (por Apellido, Nombre) ya existe y no cambia.

- **Bug 4 — La Nota Final se calcula para alumnos no promocionados.** Tras el fix de Bug 2, la
  Nota Final numérica (0–10) se computa para TODO alumno que tenga PARCIAL y GLOBAL configurados,
  sin importar su estado. En consecuencia, los alumnos REGULARIZA y RECURSA también obtienen una
  Nota Final numérica. El comportamiento correcto es que la Nota Final se complete SÓLO para los
  alumnos cuyo estado es PROMOCIONA; para REGULARIZA y RECURSA la Nota Final debe quedar vacía
  (celda del Excel en BLANCO, no "N/E") y `CierreCursadaAlumno.nota_final` debe persistirse como
  `None`.

## Bug Analysis

### Current Behavior (Defect)

Lo que ocurre hoy cuando se dispara cada bug.

**Bug 1 — Resolución de comisión**

1.1 WHEN se genera el cierre de cursada y un alumno pertenece a un grupo de comisión de Moodle con formato de comisión válido (ej. "M26 C1-09") THEN el sistema lo clasifica como "Sin comisión asignada" (`comision_id` nulo, `comision_nombre` = "Sin comisión asignada", `tutor_nombre` nulo) porque la resolución depende de que `Comision.moodle_group_code` esté poblado y coincida con el nombre del grupo.

1.2 WHEN ninguna comisión de la materia tiene `moodle_group_code` que coincida con los nombres reales de los grupos de Moodle THEN el sistema deja a TODOS los alumnos sin comisión asignada.

**Bug 2 — Nota Final con exámenes no entregados**

1.3 WHEN un alumno no entregó uno o más de los exámenes requeridos (algún PARCIAL o el GLOBAL, sin valor numérico) THEN el sistema calcula la Nota Final como "N/E".

1.4 WHEN un alumno tiene un examen en modo ESCALA que no está aprobado o no fue entregado THEN el sistema calcula la Nota Final como "N/E".

1.5 WHEN un alumno no entregó ningún examen THEN el sistema calcula la Nota Final como "N/E".

**Bug 3 — Orden de los bloques de comisión en el Excel**

1.6 WHEN se genera el Excel de cierre y existen varias comisiones THEN el sistema escribe los bloques de comisión en el orden de inserción de los alumnos desde la inscripción de Moodle (orden arbitrario/de llegada en `_agrupar_por_comision`), sin ordenarlos por nombre de comisión.

1.7 WHEN existe el bloque "Sin comisión asignada" THEN el sistema lo ubica en la posición en que aparece el primer alumno sin comisión (orden arbitrario), en lugar de dejarlo al final.

**Bug 4 — Nota Final para alumnos no promocionados**

1.8 WHEN un alumno con estado REGULARIZA o RECURSA tiene PARCIAL y GLOBAL configurados THEN el sistema calcula y persiste una Nota Final numérica (0–10) para ese alumno, aunque no haya promocionado.

1.9 WHEN un alumno no promocionado obtiene una Nota Final numérica THEN el Excel la muestra en la columna "Nota Final" (o "N/E" vía `_fmt_nota_final` si fuese `None`), en lugar de dejar la celda en blanco.

### Expected Behavior (Correct)

Lo que debería ocurrir en cada una de las condiciones anteriores.

**Bug 1 — Resolución de comisión**

2.1 WHEN se genera el cierre de cursada y un alumno pertenece a un grupo de comisión de Moodle con formato de comisión válido (ej. "M26 C1-09") THEN el sistema SHALL resolver y asociar la comisión real del alumno (`comision_id`, `comision_nombre` y `tutor_nombre`) sin depender de que `Comision.moodle_group_code` esté configurado manualmente.

2.2 WHEN los alumnos de la materia pertenecen a grupos de comisión válidos de Moodle THEN el sistema SHALL asignar cada alumno a su comisión correspondiente, en lugar de dejar a todos los alumnos sin comisión asignada.

**Bug 2 — Nota Final con exámenes no entregados**

2.3 WHEN un alumno no entregó uno o más exámenes (algún PARCIAL o el GLOBAL) THEN el sistema SHALL tratar cada examen no entregado como valor 0 en el cálculo ponderado de la Nota Final y devolver una Nota Final numérica (entero 0–10). Ejemplo: Parcial 1 = 93 (→ 9.3), Parcial 2 = N/E (→ 0), Global = N/E (→ 0) ⇒ Nota Final = round_half_up(((9.3 + 0) / 2) * 0.4 + 0 * 0.6) = round_half_up(1.86) = 2.

2.4 WHEN un alumno tiene un examen en modo ESCALA THEN el sistema SHALL normalizarlo a 10 si está "aprobado" y a 0 si está desaprobado o no entregado, para el cálculo de la Nota Final.

2.5 WHEN un alumno no entregó ningún examen (y la materia tiene exámenes PARCIAL/GLOBAL configurados) THEN el sistema SHALL calcular la Nota Final = 0.

2.6 WHEN la materia tiene exámenes PARCIAL y GLOBAL configurados THEN el sistema SHALL producir siempre una Nota Final numérica (entero 0–10) para cada alumno PROMOCIONA, nunca "N/E".

**Bug 3 — Orden de los bloques de comisión en el Excel**

2.7 WHEN se genera el Excel de cierre y existen varias comisiones THEN el sistema SHALL escribir los bloques de comisión ordenados ALFABÉTICAMENTE por nombre de comisión (ej. "M26 C1-01", "M26 C1-02", …).

2.8 WHEN existe el bloque "Sin comisión asignada" THEN el sistema SHALL ubicarlo SIEMPRE al final, después de todos los bloques de comisiones reales.

**Bug 4 — Nota Final para alumnos no promocionados**

2.9 WHEN un alumno tiene estado PROMOCIONA (y la materia tiene PARCIAL y GLOBAL configurados) THEN el sistema SHALL calcular y persistir su Nota Final numérica (entero 0–10) según la fórmula ponderada.

2.10 WHEN un alumno tiene estado REGULARIZA o RECURSA THEN el sistema SHALL dejar su Nota Final vacía (`CierreCursadaAlumno.nota_final` = `None`) y el Excel SHALL renderizar la celda "Nota Final" en BLANCO (celda vacía), nunca "N/E".

### Unchanged Behavior (Regression Prevention)

Comportamiento existente que debe preservarse.

3.1 WHEN un alumno NO pertenece a ningún grupo de comisión válido de Moodle THEN el sistema SHALL CONTINUE TO clasificarlo como "Sin comisión asignada" sin interrumpir la generación del cierre.

3.2 WHEN un alumno matchea de forma ambigua (cero o más de una comisión) THEN el sistema SHALL CONTINUE TO dejarlo sin comisión asignada sin romper la corrida del resto de los alumnos.

3.3 WHEN un examen no fue entregado THEN el sistema SHALL CONTINUE TO mostrar "N/E" en la columna de ese examen (Parcial n / Global TPI) del Excel; sólo cambia el cálculo de la Nota Final.

3.4 WHEN un alumno entregó todos sus exámenes con valores numéricos THEN el sistema SHALL CONTINUE TO calcular la Nota Final con la fórmula ponderada existente (promedio de parciales normalizados a 0–10 al 40 %, global normalizado a 0–10 al 60 %, redondeo `round_half_up`).

3.5 WHEN la materia no tiene exámenes PARCIAL/GLOBAL configurados THEN el sistema SHALL CONTINUE TO bloquear la generación del cierre con un error 400.

3.6 WHEN se clasifica el estado de cierre de un alumno (PROMOCIONA / REGULARIZA / RECURSA) THEN el sistema SHALL CONTINUE TO usar la lógica actual (un examen no entregado sigue contando como incumplimiento del mínimo/banda), independientemente del nuevo cálculo de la Nota Final.

**Bug 3 — Orden de los bloques de comisión en el Excel**

3.7 WHEN se escriben los alumnos DENTRO de un bloque de comisión THEN el sistema SHALL CONTINUE TO ordenarlos alfabéticamente por (Apellido, Nombre) como hoy (el orden intra-bloque ya existe en `_escribir_detalle` y no es un defecto).

3.8 WHEN se escribe el encabezado de un bloque de comisión THEN el sistema SHALL CONTINUE TO usar el formato "{comisión} — Tutor: {tutor}" sin cambios.

**Bug 4 — Nota Final para alumnos no promocionados**

3.9 WHEN un alumno tiene estado PROMOCIONA THEN el sistema SHALL CONTINUE TO calcular su Nota Final con la fórmula ponderada numérica existente (parciales normalizados a 0–10 al 40 %, global al 60 %, `round_half_up`, no entregados como 0).

3.10 WHEN un examen no fue entregado THEN el sistema SHALL CONTINUE TO mostrar "N/E" en la columna de ese examen (Parcial n / Global TPI) del Excel — el cambio de Bug 4 afecta únicamente a la columna "Nota Final", no a las columnas de exámenes.

3.11 WHEN se clasifica el estado de cierre de un alumno (PROMOCIONA / REGULARIZA / RECURSA) THEN el sistema SHALL CONTINUE TO usar la lógica actual de clasificación sin cambios; sólo cambia para qué estados se completa la Nota Final.

> **Nota de regresión (Bug 4 revierte una regla del fix de Bug 2):** El fix de Bug 2 estableció que
> TODO alumno con PARCIAL+GLOBAL obtiene una Nota Final numérica (incluidos REGULARIZA y RECURSA).
> Bug 4 acota esa regla a los alumnos PROMOCIONA únicamente. El test existente
> `test_regulariza_con_global_numerico_tiene_nota_final_numerica` codifica la regla anterior y DEBE
> actualizarse: un alumno REGULARIZA debe pasar a tener `nota_final = None` (celda en blanco en el
> Excel, no "N/E"). El cálculo numérico de la Nota Final para PROMOCIONA (3.9) y el renderizado
> "N/E" de las columnas de examen (3.10) no cambian.
