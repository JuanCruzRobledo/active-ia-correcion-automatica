# Bugfix Requirements Document

## Introduction

Este bugfix agrupa seis defectos reportados por el usuario sobre el **Cierre de Cursada**
de la plataforma Active-IA (corrección automática TUD) y su exploración/sincronización con
Moodle. Todos afectan la generación del reporte de cierre (clasificación de alumnos + planilla
Excel) y la carga de exámenes de recuperatorio.

Los seis problemas son:

- **Bug 1 — Tipo de actividad ASSIGN vs QUIZ.** Los exámenes que en Moodle son cuestionarios
  (`quiz`) no se pueden dar de alta correctamente como recuperatorios/extraordinarias de un
  parcial. Concretamente, "Extraordinaria 2" y "Extraordinaria 3" de Programación 2 son quizes
  y dan error al darlas de alta como rescate del Parcial 2. Hoy `ExamenMateria` guarda sólo el
  `moodle_cmid`, sin distinguir si la actividad es una Tarea (`assign`) o un Cuestionario
  (`quiz`), y el link/recurso de Moodle cambia según el tipo:
  - assign: `https://tup.sied.utn.edu.ar/mod/assign/view.php?id=17648`
  - quiz 1: `https://tup.sied.utn.edu.ar/mod/quiz/view.php?id=17679`
  - quiz 2: `https://tup.sied.utn.edu.ar/mod/quiz/view.php?id=20467`
  Se necesita un campo para marcar el tipo de actividad (`assign` o `quiz`). Los registros ya
  existentes deben quedar como `assign` por defecto (migración) y debe poderse editar a `quiz`.

- **Bug 2 — El Excel debe tener dos hojas.** Hoy la planilla de cierre se genera con una sola
  hoja (bloques por comisión). El modelo de referencia
  `docs/modelos/Cierre_Programacin_3 FIX.xlsx` tiene DOS hojas:
  - Hoja 1 "Programación 3 por Comisiones": agrupada en cuadros por comisión, ordenada por
    comisión y luego alfabéticamente por alumno dentro de cada comisión.
  - Hoja 2 "Programación 3 Crudo": lista plana ordenada alfabéticamente por alumno, con dos
    columnas nuevas "Comision" y "Tutor" del alumno.

- **Bug 3 — La exploración de Moodle no trae/asocia bien las comisiones.** En Programación 3 no
  aparecen las comisiones `M25 C3-01`, `M25 C3-02` y `M25 C3-15`. En Programación 1 se cuentan
  alumnos como "sin comisión" cuando en realidad sí tienen comisión asignada en Moodle. Es un
  defecto de la exploración/sincronización de grupos de Moodle cuya causa raíz debe investigarse.

- **Bug 4 — Las columnas de conteo y "Recuperable" deben calcularse con fórmulas nativas de
  Excel.** Hoy los conteos del resumen y la columna de recuperables se escriben como valores
  estáticos calculados en Python. El comportamiento correcto es que se escriban como fórmulas
  nativas de Excel (`SI`/`IF`, `CONTAR.SI`/`COUNTIF`), de modo que si un usuario edita
  manualmente el "Estado Alumno" de una fila, el conteo del resumen y la marca de recuperable se
  recalculen automáticamente. Un alumno recuperable es aquel que tiene al menos un parcial con
  nota `>= 40` y el otro parcial no entregado o desaprobado con nota `< 40`.

- **Bug 5 — Falta el estado ABANDONO.** Hoy un alumno que no rindió ningún examen ni el global
  (todo en `N/E`) se clasifica como RECURSA. El comportamiento correcto es clasificarlo como
  ABANDONO (nuevo estado): sin ningún examen ni global rendido.

- **Bug 6 — Los alumnos REGULARIZA deben tener Nota Final = 5.** Hoy los alumnos con estado
  REGULARIZA quedan con la Nota Final vacía (según la spec previa `cierre-cursada-comision-nota-fix`,
  Bug 4). El nuevo comportamiento pedido es que los alumnos REGULARIZA tengan SIEMPRE Nota Final = 5.

**Especificación de fórmulas nativas del Excel (provistas por el usuario y confirmadas contra el
modelo `Cierre_Programacin_3 FIX.xlsx`).** Las referencias de columna difieren entre las dos
hojas porque la hoja cruda agrega las columnas "Comision" y "Tutor":

- Hoja 1 "por Comisiones" (columnas: A Nombre y Apellido, B Email, C Parcial 1, D Parcial 2,
  E Global TPI, F Estado Alumno, G Nota Final, H Recuperable auxiliar):
  - Recuperable (por fila, columna auxiliar H):
    `=SI(F8<>"RECURSA";"";SI(Y(SI.ERROR(VALOR(C8);0)>=40;SI.ERROR(VALOR(D8);0)<40);"RECUPERABLE CON PARCIAL 2";SI(Y(SI.ERROR(VALOR(D8);0)>=40;SI.ERROR(VALOR(C8);0)<40);"RECUPERABLE CON PARCIAL 1";"")))`
  - Promocionados: `=CONTAR.SI(F:F;"PROMOCIONA")`
  - Regulares: `=CONTAR.SI(F:F;"REGULARIZA")`
  - Recursantes: `=CONTAR.SI(F:F;"RECURSA")`
  - Recuperables: `=CONTAR.SI(H:H;"RECUPERABLE*")`
  - Abandonos: `=CONTAR.SI(F:F;"ABANDONO")`
- Hoja 2 "Crudo" (columnas: A Nombre y Apellido, B Email, C Comision, D Tutor, E Parcial 1,
  F Parcial 2, G Global TPI, H Estado Alumno, I Nota Final, J Recuperable):
  - Recuperable (por fila, columna J):
    `=SI(H8<>"RECURSA";"";SI(Y(SI.ERROR(VALOR(E8);0)>=40;SI.ERROR(VALOR(F8);0)<40);"RECUPERABLE CON PARCIAL 2";SI(Y(SI.ERROR(VALOR(F8);0)>=40;SI.ERROR(VALOR(E8);0)<40);"RECUPERABLE CON PARCIAL 1";"")))`
  - Promocionados: `=CONTAR.SI(H:H;"PROMOCIONA")`
  - Regulares: `=CONTAR.SI(H:H;"REGULARIZA")`
  - Recursantes: `=CONTAR.SI(H:H;"RECURSA")`
  - Recuperables: `=CONTAR.SI(J:J;"RECUPERABLE CON*")`
  - Abandonos: `=CONTAR.SI(H:H;"ABANDONO")`

> **Contexto de specs previas (para no duplicar):** Este fix se apoya en y ajusta el trabajo de
> `cierre-cursada-fix` (clasificación dirigida por `ExamenMateria` + Nota Final ponderada),
> `cierre-cursada-comision-nota-fix` (resolución de comisión por `moodle_group_id` + fallback por
> nombre, y Nota Final numérica sólo para PROMOCIONA con REGULARIZA/RECURSA en blanco) y
> `comision-orden-numerico-fix` (orden numérico natural de comisiones). Dos puntos entran en
> conflicto deliberado con lo anterior y se resuelven aquí: (a) Bug 6 cambia la regla de Nota Final
> de REGULARIZA (antes en blanco, ahora = 5), y (b) los conteos del resumen dejan de ser valores
> estáticos de Python para pasar a fórmulas nativas de Excel (Bug 4).

> **Discrepancia a confirmar en diseño (Bug 6 vs modelo):** El modelo de referencia
> `Cierre_Programacin_3 FIX.xlsx` muestra a los alumnos REGULARIZA con la celda "Nota Final" en
> blanco, lo que refleja el estado ANTERIOR (spec `cierre-cursada-comision-nota-fix`). La
> instrucción textual del usuario (Bug 6) pide Nota Final = 5 para REGULARIZA. Estas requisitos
> siguen la instrucción explícita del usuario (= 5); si el negocio prefiriera mantener el blanco
> del modelo, debe confirmarse antes de implementar.

## Bug Analysis

### Current Behavior (Defect)

Lo que ocurre hoy cuando se dispara cada bug.

**Bug 1 — Tipo de actividad ASSIGN vs QUIZ**

1.1 WHEN se da de alta un examen (parcial/recuperatorio/extensión/extraordinaria/global) THEN el sistema sólo permite registrar el `moodle_cmid` sin indicar si la actividad de Moodle es una Tarea (`assign`) o un Cuestionario (`quiz`).

1.2 WHEN un examen corresponde a un cuestionario de Moodle (`quiz`) y se lo intenta dar de alta como recuperatorio/extraordinaria de un parcial (caso "Extraordinaria 2" y "Extraordinaria 3" de Programación 2 sobre el Parcial 2) THEN el sistema falla/da error porque asume que toda actividad de examen es de tipo Tarea (`assign`) y arma el link/recurso de Moodle como `/mod/assign/view.php`.

1.3 WHEN el cierre resuelve las notas de un examen que en realidad es un `quiz` THEN el sistema lo trata bajo el mismo camino que un `assign` (no distingue la fuente por tipo), sin un campo de tipo que lo identifique.

**Bug 2 — El Excel de cierre sólo tiene una hoja**

1.4 WHEN se genera la planilla Excel del cierre THEN el sistema produce un único worksheet con los bloques por comisión, sin la segunda hoja "cruda" (lista plana) del modelo `docs/modelos/Cierre_Programacin_3 FIX.xlsx`.

1.5 WHEN se genera la planilla Excel del cierre THEN el sistema NO incluye una hoja plana ordenada alfabéticamente por alumno con las columnas "Comision" y "Tutor" del alumno.

**Bug 3 — La exploración de Moodle no trae/asocia bien las comisiones**

1.6 WHEN se explora/sincroniza Programación 3 con Moodle THEN el sistema no trae las comisiones `M25 C3-01`, `M25 C3-02` y `M25 C3-15` (no aparecen en el resultado).

1.7 WHEN se explora/sincroniza Programación 1 con Moodle THEN el sistema cuenta alumnos como "Sin comisión asignada" aunque esos alumnos sí pertenecen a un grupo de comisión válido en Moodle.

**Bug 4 — Conteos y columna "Recuperable" con valores estáticos**

1.8 WHEN se genera la planilla Excel del cierre THEN el sistema escribe los conteos del resumen (Promocionados/Regulares/Recursantes) como valores numéricos estáticos calculados en Python, no como fórmulas nativas de Excel.

1.9 WHEN un usuario edita manualmente el "Estado Alumno" de una fila en el Excel generado THEN los conteos del resumen NO se recalculan (quedan con el valor original), porque son números fijos y no fórmulas.

1.10 WHEN se genera la planilla Excel del cierre THEN el sistema no incluye una marca/columna "Recuperable" por alumno ni un conteo de recuperables, y no existe la lógica de recuperable (al menos un parcial `>= 40` y el otro no entregado o `< 40`) expresada como fórmula recalculable.

**Bug 5 — Falta el estado ABANDONO**

1.11 WHEN un alumno no rindió ningún examen ni el global (todas sus notas de parciales y global son `N/E`) THEN el sistema lo clasifica como RECURSA, sin distinguir el caso de abandono total.

1.12 WHEN se cuentan los alumnos del cierre THEN el sistema no dispone del estado ABANDONO, por lo que los alumnos que nunca rindieron nada quedan mezclados dentro de RECURSA.

**Bug 6 — Nota Final de REGULARIZA**

1.13 WHEN un alumno tiene estado REGULARIZA THEN el sistema deja su Nota Final vacía (celda en blanco en el Excel, `nota_final = None` persistido), en lugar de asignarle Nota Final = 5.

### Expected Behavior (Correct)

Lo que debería ocurrir en cada una de las condiciones anteriores.

**Bug 1 — Tipo de actividad ASSIGN vs QUIZ**

2.1 WHEN se da de alta o se edita un examen THEN el sistema SHALL permitir marcar el tipo de actividad de Moodle como `assign` (Tarea) o `quiz` (Cuestionario).

2.2 WHEN existen registros de examen anteriores a este cambio THEN el sistema SHALL migrarlos con tipo de actividad `assign` por defecto, y SHALL permitir editarlos posteriormente a `quiz`.

2.3 WHEN un examen es de tipo `quiz` y se lo da de alta como recuperatorio/extraordinaria de un parcial (caso "Extraordinaria 2"/"Extraordinaria 3" de Programación 2 sobre el Parcial 2) THEN el sistema SHALL permitir el alta sin error, resolviendo el link/recurso de Moodle según el tipo (`/mod/quiz/view.php` para `quiz`, `/mod/assign/view.php` para `assign`).

2.4 WHEN el cierre resuelve las notas de un examen THEN el sistema SHALL usar el tipo de actividad marcado (`assign`/`quiz`) para elegir el camino correcto de obtención de notas desde Moodle.

**Bug 2 — El Excel de cierre debe tener dos hojas**

2.5 WHEN se genera la planilla Excel del cierre THEN el sistema SHALL producir un archivo con DOS hojas, con el mismo formato que el modelo `docs/modelos/Cierre_Programacin_3 FIX.xlsx`.

2.6 WHEN se genera la hoja 1 ("{Materia} por Comisiones") THEN el sistema SHALL agrupar a los alumnos en cuadros por comisión, ordenando las comisiones y, dentro de cada comisión, a los alumnos alfabéticamente.

2.7 WHEN se genera la hoja 2 ("{Materia} Crudo") THEN el sistema SHALL producir una lista plana ordenada alfabéticamente por alumno (sin cuadros por comisión), agregando las columnas "Comision" y "Tutor" del alumno.

**Bug 3 — La exploración de Moodle debe traer/asociar bien las comisiones**

2.8 WHEN se explora/sincroniza Programación 3 con Moodle THEN el sistema SHALL traer las comisiones `M25 C3-01`, `M25 C3-02` y `M25 C3-15` (y toda comisión con formato de grupo válido) sin omitirlas.

2.9 WHEN se explora/sincroniza Programación 1 con Moodle y un alumno pertenece a un grupo de comisión válido THEN el sistema SHALL asociarlo a su comisión real en lugar de contarlo como "Sin comisión asignada".

2.10 WHEN se investiga la causa del defecto de exploración/sincronización THEN el sistema SHALL corregir la causa raíz identificada (a determinar en diseño) que hace que ciertas comisiones no se traigan o que alumnos con comisión válida queden sin comisión.

**Bug 4 — Conteos y columna "Recuperable" con fórmulas nativas de Excel**

2.11 WHEN se genera la planilla Excel del cierre THEN el sistema SHALL escribir los conteos del resumen (Promocionados, Regulares, Recursantes, Recuperables, Abandonos) como fórmulas nativas de Excel (`CONTAR.SI`/`COUNTIF`) sobre las columnas correspondientes, no como valores numéricos estáticos.

2.12 WHEN un usuario edita manualmente el "Estado Alumno" de una fila en el Excel generado THEN el sistema SHALL permitir que los conteos del resumen y la marca de recuperable se recalculen automáticamente por las fórmulas nativas (sin volver a generar el archivo).

2.13 WHEN se genera cada hoja del Excel THEN el sistema SHALL incluir una columna/fórmula "Recuperable" por alumno que marque "RECUPERABLE CON PARCIAL 1" o "RECUPERABLE CON PARCIAL 2" según la definición: sólo para alumnos RECURSA, cuando un parcial es `>= 40` y el otro es `< 40` o no entregado (`N/E`, tratado como 0 vía `SI.ERROR(VALOR(...);0)`).

2.14 WHEN se escriben las fórmulas THEN el sistema SHALL usar las referencias de columna correctas por hoja: en la hoja "por Comisiones" la columna de Estado es `F`, los parciales `C`/`D`, y la columna auxiliar de recuperable `H`; en la hoja "Crudo" el Estado es `H`, los parciales `E`/`F`, y la columna de recuperable `J` (por las columnas "Comision"/"Tutor" agregadas), tal como en el modelo.

2.15 WHEN se cuenta el total de recuperables THEN el sistema SHALL usar `CONTAR.SI` sobre la columna de recuperable con el patrón `"RECUPERABLE*"` (hoja "por Comisiones") / `"RECUPERABLE CON*"` (hoja "Crudo"), según el modelo.

**Bug 5 — Estado ABANDONO**

2.16 WHEN un alumno no rindió ningún examen (todos los parciales y el global en `N/E`, sin ninguna nota ni global rendido) THEN el sistema SHALL clasificarlo con el nuevo estado ABANDONO, en vez de RECURSA.

2.17 WHEN se generan los conteos y la clasificación THEN el sistema SHALL contemplar ABANDONO como un estado distinto de RECURSA (los alumnos ABANDONO no se cuentan como RECURSA).

**Bug 6 — Nota Final de REGULARIZA**

2.18 WHEN un alumno tiene estado REGULARIZA THEN el sistema SHALL asignarle SIEMPRE Nota Final = 5 (persistida y mostrada en la columna "Nota Final" del Excel), en lugar de dejarla en blanco.

### Unchanged Behavior (Regression Prevention)

Comportamiento existente que debe preservarse.

3.1 WHEN un examen es de tipo Tarea (`assign`) THEN el sistema SHALL CONTINUE TO resolver sus notas y su link como hoy (el nuevo campo de tipo por defecto es `assign`, y el comportamiento actual equivale a `assign`).

3.2 WHEN un examen PARCIAL/GLOBAL tiene recuperatorio/extensión/extraordinaria vinculados THEN el sistema SHALL CONTINUE TO resolverlo como aprobado si aprobó el original o cualquiera de sus instancias de rescate, con la precedencia actual.

3.3 WHEN se clasifica a un alumno que sí rindió y aprobó los exámenes requeridos THEN el sistema SHALL CONTINUE TO clasificarlo como PROMOCIONA con su Nota Final ponderada numérica actual (parciales normalizados a 0–10 al 40 %, global al 60 %, `round_half_up`).

3.4 WHEN un alumno no promociona pero cumple la banda relativa en todos los exámenes excepto el global THEN el sistema SHALL CONTINUE TO clasificarlo como REGULARIZA (sólo cambia su Nota Final, que pasa a ser 5 por Bug 6).

3.5 WHEN un alumno no cumple promoción ni regularización pero sí rindió al menos un examen THEN el sistema SHALL CONTINUE TO clasificarlo como RECURSA (sólo el caso de todo `N/E` cambia a ABANDONO por Bug 5).

3.6 WHEN se genera la hoja 1 (por comisiones) THEN el sistema SHALL CONTINUE TO ordenar las comisiones por orden numérico natural del nombre y a los alumnos dentro de cada bloque alfabéticamente por (Apellido, Nombre), con "Sin comisión asignada" al final (garantías de `comision-orden-numerico-fix` y `cierre-cursada-comision-nota-fix`).

3.7 WHEN un alumno no pertenece a ningún grupo de comisión válido de Moodle o el mapeo es ambiguo THEN el sistema SHALL CONTINUE TO clasificarlo como "Sin comisión asignada" sin interrumpir la corrida.

3.8 WHEN un examen no fue rendido THEN el sistema SHALL CONTINUE TO mostrar `N/E` en la columna de ese examen (Parcial n / Global TPI) del Excel.

3.9 WHEN se genera una corrida de cierre THEN el sistema SHALL CONTINUE TO guardarla como histórico append-only sin sobrescribir corridas anteriores, congelando la config de exámenes usada.

3.10 WHEN se genera cualquier reporte Excel de la plataforma THEN el sistema SHALL CONTINUE TO usar los estilos visuales de la casa (paleta, bordes, banda de título) ya definidos en `excel_estilos.py`.

3.11 WHEN la materia no tiene exámenes PARCIAL/GLOBAL configurados THEN el sistema SHALL CONTINUE TO bloquear la generación del cierre con un error 400.

3.12 WHEN un examen PARCIAL/GLOBAL está en modo ESCALA (Aprobado/Desaprobado) THEN el sistema SHALL CONTINUE TO evaluarlo por el resultado de la escala y no por una nota numérica.
