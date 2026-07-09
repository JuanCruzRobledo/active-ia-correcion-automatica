# Bugfix Requirements Document

## Introduction

La feature **Cierre de Cursada** (clasificación PROMOCIONA / REGULARIZA / RECURSA dirigida
por `ExamenMateria`, exportada a Excel) acumula un conjunto de defectos reportados por el
usuario relacionados con la exportación a Excel y la integración con Moodle. Este bugfix
agrupa seis defectos independientes bajo una misma corrida de trabajo, porque todos tocan
la misma superficie (cierre de cursada + integración Moodle) y varios comparten los mismos
archivos (`excel_cierre_cursada.py`, `cierre_cursada_service.py`, `cierre_cursada_calculo.py`,
`examen_service.py`/`examen_materia.py`, `moodle_url_parser.py` y el resolver de comisiones).

Contexto: los nombres de materia usados como ejemplo (**Programación 3**, **Programación 1**,
**Programación 2**) son ilustrativos; el comportamiento corregido debe aplicar a la materia
real de cada corrida.

Defectos incluidos:

- **Bug A — Tipo de vínculo Moodle (assign vs quiz).** `ExamenMateria` no distingue si la
  actividad de Moodle del examen es una **tarea (`assign`)** o un **cuestionario (`quiz`)**.
  Como consecuencia, dar de alta ciertos exámenes que son quizzes (ej. "Extraordinaria 2" y
  "Extraordinaria 3" de Programación 2, vinculadas como recuperatorios del Parcial 2) arroja
  error, y el enlace a Moodle se arma siempre como `/mod/assign/view.php?id=<cmid>`, quedando
  roto para los que en realidad son `/mod/quiz/view.php?id=<cmid>`.

- **Bug B — Formato de exportación Excel en dos hojas.** El Excel de cierre se genera con una
  sola hoja. El usuario necesita dos hojas: una **"{Materia} por Comisiones"** (agrupada en
  recuadros/tablas por comisión) y otra **"{Materia} Crudo"** (listado plano alfabético) con
  dos columnas nuevas por alumno: **Comisión** y **Tutor**.

- **Bug C — Exploración/sync de Moodle.** Para Programación 3 la sincronización no trae las
  comisiones **M25 C3-01**, **M25 C3-02** y **M25 C3-15**. Para Programación 1, alumnos que
  sí tienen comisión válida se cuentan como "sin comisión". Requiere una investigación de la
  integración con Moodle (el diseño determinará la causa raíz).

- **Bug D — Columna "Recuperables" + conteos por fórmula de Excel.** Falta una columna que
  identifique a los recursantes **recuperables**, y los conteos del resumen se escriben hoy
  como números fijos, de modo que editar manualmente el estado de un alumno en el Excel no
  recalcula los totales. Los conteos deben calcularse con fórmulas `CONTAR.SI` para que
  recalculen solos.

- **Bug E — Estado "ABANDONO".** Un alumno que no entregó ningún examen ni el global (todo
  "N/E") hoy queda como RECURSA. Debe clasificarse como **ABANDONO**.

- **Bug F — Nota Final de los regulares.** Los alumnos con estado REGULARIZA deben tener
  **siempre Nota Final = 5**. Hoy la Nota Final de los regulares queda vacía (ver spec previa
  `cierre-cursada-comision-nota-fix`, Bug 4).

Relación con specs previas (para evitar duplicación y mantener consistencia):
- `cierre-cursada-fix`: reescribió el cierre dirigido por `ExamenMateria` y el formato del Excel.
- `cierre-cursada-comision-nota-fix`: fijó la resolución de comisión por grupo de Moodle, el
  cálculo de Nota Final (no entregado = 0) y dejó la Nota Final de REGULARIZA/RECURSA en blanco.
- `comision-orden-numerico-fix`: fijó el orden **numérico natural** del nombre de comisión.

Este bugfix **cambia deliberadamente** dos reglas de esas specs: la Nota Final de REGULARIZA
pasa de "en blanco" a **5** (Bug F), y se agrega el estado **ABANDONO** que antes caía en
RECURSA (Bug E). El resto de las garantías previas se preservan (ver Regresión).

## Bug Analysis

### Current Behavior (Defect)

Lo que ocurre hoy cuando se dispara cada bug.

**Bug A — Tipo de vínculo Moodle (assign vs quiz)**

1.1 WHEN un examen (`ExamenMateria`) apunta a una actividad de Moodle que es un cuestionario (`quiz`) THEN el sistema no ofrece ninguna forma de marcar el tipo de actividad, porque `ExamenMateria` sólo persiste `moodle_cmid` y asume siempre que la actividad es una tarea (`assign`).

1.2 WHEN se da de alta un recuperatorio/extensión/extraordinaria (ej. "Extraordinaria 2" y "Extraordinaria 3" de Programación 2, vinculadas al Parcial 2) cuya actividad de Moodle es un `quiz` THEN el sistema arroja un error y no permite registrarlo.

1.3 WHEN el sistema construye el enlace a la actividad de Moodle de un examen THEN usa siempre la ruta `/mod/assign/view.php?id=<cmid>`, produciendo un enlace incorrecto para los exámenes que en realidad son quizzes (deberían resolver a `/mod/quiz/view.php?id=<cmid>`).

**Bug B — Formato de exportación Excel en dos hojas**

1.4 WHEN se exporta el Excel del cierre de cursada THEN el sistema genera un archivo con una **única hoja**, sin separar una hoja "por Comisiones" y una hoja "Crudo".

1.5 WHEN se genera el Excel THEN no existe una hoja **"{Materia} Crudo"** con el listado plano de alumnos ordenado alfabéticamente ni las columnas **Comisión** y **Tutor** por alumno.

1.6 WHEN se nombra la hoja del Excel THEN el sistema usa un título genérico de cierre en lugar de **"{Materia} por Comisiones"** para la hoja agrupada.

**Bug C — Exploración/sync de Moodle**

1.7 WHEN se sincroniza/explora Programación 3 desde Moodle THEN el sistema no trae las comisiones **M25 C3-01**, **M25 C3-02** y **M25 C3-15** (no quedan disponibles para el cierre ni para la gestión, aunque existen como grupos en Moodle).

1.8 WHEN se procesa Programación 1 THEN el sistema cuenta como **"sin comisión"** a alumnos que sí pertenecen a una comisión válida de Moodle.

**Bug D — Columna "Recuperables" + conteos por fórmula de Excel**

1.9 WHEN se genera el Excel THEN el resumen de conteos (Promocionados / Regulares / Recursantes) se escribe como **números fijos (literales)** tomados de la corrida (`run.total_promociona`, etc.), por lo que editar manualmente el estado de un alumno en la planilla **no recalcula** los totales.

1.10 WHEN se genera el Excel THEN **no existe una columna "Recuperable"** que identifique a los recursantes recuperables.

1.11 WHEN se genera el resumen del Excel THEN **no hay conteos de "Recuperables" ni de "Abandonos"** (sólo Promocionados / Regulares / Recursantes).

**Bug E — Estado "ABANDONO"**

1.12 WHEN un alumno no entregó ningún examen ni el global (todos los resultados son "N/E") THEN el sistema lo clasifica como **RECURSA**, porque el estado **ABANDONO** no existe en el veredicto de cierre.

**Bug F — Nota Final de los regulares**

1.13 WHEN un alumno queda con estado **REGULARIZA** THEN el sistema deja su Nota Final vacía (`nota_final = None`, celda en blanco en el Excel), en lugar de asignarle **5**.

### Expected Behavior (Correct)

Lo que debería ocurrir en cada una de las condiciones anteriores.

**Bug A — Tipo de vínculo Moodle (assign vs quiz)**

2.1 WHEN se da de alta o edita un examen THEN el sistema SHALL permitir marcar el **tipo de actividad de Moodle** del examen como **`assign`** (tarea) o **`quiz`** (cuestionario), persistiéndolo en `ExamenMateria`.

2.2 WHEN se da de alta un recuperatorio/extensión/extraordinaria vinculado a un examen cuya actividad de Moodle es un `quiz` (ej. "Extraordinaria 2"/"Extraordinaria 3" de Programación 2) THEN el sistema SHALL registrarlo sin arrojar error.

2.3 WHEN existen exámenes ya dados de alta antes de este fix THEN el sistema SHALL asumirlos por defecto como **`assign`**, y SHALL permitir **editarlos a `quiz`**.

2.4 WHEN el sistema construye el enlace a la actividad de Moodle de un examen THEN SHALL usar `/mod/quiz/view.php?id=<cmid>` cuando el tipo es `quiz` y `/mod/assign/view.php?id=<cmid>` cuando el tipo es `assign`.

**Bug B — Formato de exportación Excel en dos hojas**

2.5 WHEN se exporta el Excel del cierre de cursada THEN el sistema SHALL generar un archivo con **dos hojas**.

2.6 WHEN se genera la hoja agrupada THEN el sistema SHALL nombrarla **"{Materia} por Comisiones"** (ej. "Programación 3 por Comisiones"), con los alumnos agrupados en recuadros/tablas por comisión, ordenados **por comisión** y, dentro de cada comisión, **alfabéticamente** (por Apellido, Nombre).

2.7 WHEN se genera la hoja plana THEN el sistema SHALL nombrarla **"{Materia} Crudo"** (ej. "Programación 3 Crudo"), con todos los alumnos ordenados **alfabéticamente**, e incluir dos columnas por alumno: **Comisión** y **Tutor**.

**Bug C — Exploración/sync de Moodle**

2.8 WHEN se sincroniza/explora Programación 3 desde Moodle THEN el sistema SHALL traer las comisiones **M25 C3-01**, **M25 C3-02** y **M25 C3-15** y dejarlas disponibles para el cierre y la gestión.

2.9 WHEN se procesa Programación 1 y un alumno pertenece a una comisión válida de Moodle THEN el sistema SHALL asignarlo a **su comisión real**, en lugar de contarlo como "sin comisión".

**Bug D — Columna "Recuperables" + conteos por fórmula de Excel**

2.10 WHEN se genera el resumen del Excel THEN el sistema SHALL escribir los conteos como **fórmulas `CONTAR.SI`** (no números fijos) sobre la columna de estado, de modo que recalculen automáticamente si un estado se edita a mano. Las fórmulas (nomenclatura de Excel en español; la letra exacta de columna se ajusta al layout de cada hoja en diseño) son:
  - Promocionados: `=CONTAR.SI(F:F;"PROMOCIONA")` (hoja por Comisiones) / `=CONTAR.SI(H:H;"PROMOCIONA")` (hoja Crudo)
  - Regulares: `=CONTAR.SI(F:F;"REGULARIZA")` / `=CONTAR.SI(H:H;"REGULARIZA")`
  - Recursantes: `=CONTAR.SI(F:F;"RECURSA")` / `=CONTAR.SI(H:H;"RECURSA")`
  - Abandonos: `=CONTAR.SI(F:F;"ABANDONO")` / `=CONTAR.SI(H:H;"ABANDONO")`
  - Recuperables: `=CONTAR.SI(H:H;"RECUPERABLE*")` (hoja por Comisiones) / `=CONTAR.SI(J:J;"RECUPERABLE*")` (hoja Crudo)

2.11 WHEN se genera el Excel THEN el sistema SHALL incluir una columna **"Recuperable"** calculada por **fórmula de Excel** que marque como recuperable a un alumno **RECURSA** que tenga al menos un parcial con nota `>= 40` y el otro parcial **no entregado** o **desaprobado (`< 40`)**. La fórmula de referencia (columnas de estado `F`, Parcial 1 `C`, Parcial 2 `D`, columna resultado `H`; se ajustan al layout en diseño) es:
```
=SI(F8<>"RECURSA";"";SI(Y(SI.ERROR(VALOR(C8);0)>=40;SI.ERROR(VALOR(D8);0)<40);"RECUPERABLE CON PARCIAL 2";SI(Y(SI.ERROR(VALOR(D8);0)>=40;SI.ERROR(VALOR(C8);0)<40);"RECUPERABLE CON PARCIAL 1";"")))
```

2.12 WHEN se cuenta el total de recuperables THEN el sistema SHALL usar `=CONTAR.SI(H:H;"RECUPERABLE CON*")` (equivalente a `RECUPERABLE*`), referenciando la columna "Recuperable".

**Bug E — Estado "ABANDONO"**

2.13 WHEN un alumno no entregó ningún examen ni el global (todos sus resultados son "N/E") THEN el sistema SHALL clasificarlo como **ABANDONO**.

**Bug F — Nota Final de los regulares**

2.14 WHEN un alumno queda con estado **REGULARIZA** THEN el sistema SHALL asignarle **siempre Nota Final = 5** (persistida y mostrada en el Excel), independientemente de sus notas.

### Unchanged Behavior (Regression Prevention)

Comportamiento existente que debe preservarse.

3.1 WHEN un examen apunta a una actividad de Moodle de tipo tarea (`assign`) THEN el sistema SHALL CONTINUE TO resolverlo como hoy (enlace `/mod/assign/view.php?id=<cmid>` y grade estructural por instancia `assign` en el cierre).

3.2 WHEN se clasifica a un alumno THEN el sistema SHALL CONTINUE TO derivar el veredicto de `ExamenMateria` (mínimo `nota_minima`, banda relativa, modo ESCALA/NUMERICO y cadena de rescate recuperatorio/extensión/extraordinaria) como en las specs previas; sólo cambian las reglas de ABANDONO (E) y de Nota Final de REGULARIZA (F).

3.3 WHEN un alumno cumple el mínimo de TODOS los exámenes (incluido el GLOBAL) THEN el sistema SHALL CONTINUE TO clasificarlo como **PROMOCIONA** y calcular su Nota Final ponderada como hoy (promedio de parciales al 40 % + global al 60 %, escala normalizada, `round_half_up`, no entregado = 0).

3.4 WHEN se agrupan/ordenan las comisiones (en cualquier hoja o reporte) THEN el sistema SHALL CONTINUE TO usar el **orden numérico natural** del nombre de comisión (spec `comision-orden-numerico-fix`), ubicando el bloque **"Sin comisión asignada" siempre al final**.

3.5 WHEN se escriben los alumnos dentro de un bloque de comisión THEN el sistema SHALL CONTINUE TO ordenarlos alfabéticamente por (Apellido, Nombre).

3.6 WHEN un examen no fue entregado THEN el sistema SHALL CONTINUE TO mostrar **"N/E"** en la columna de ese examen (Parcial n / Global TPI); los cambios de este fix afectan la Nota Final, el estado ABANDONO y las columnas/conteos nuevos, no el renderizado "N/E" de las columnas de examen.

3.7 WHEN se genera cualquier Excel de la plataforma THEN el sistema SHALL CONTINUE TO usar los estilos visuales de la casa (`excel_estilos.py`).

3.8 WHEN se genera una corrida de cierre THEN el sistema SHALL CONTINUE TO guardarla como histórico append-only, congelando `examenes_snapshot`, sin sobrescribir corridas previas.

3.9 WHEN un alumno no pertenece a ninguna comisión válida de Moodle o su match es ambiguo (0 o >1 comisiones) THEN el sistema SHALL CONTINUE TO clasificarlo como "Sin comisión asignada" sin romper la corrida del resto de los alumnos.

3.10 WHEN un alumno tiene estado **RECURSA** o **ABANDONO** THEN el sistema SHALL CONTINUE TO dejar su Nota Final vacía (celda en blanco, no "N/E"); sólo REGULARIZA (=5, por Bug F) y PROMOCIONA (ponderada) llevan Nota Final.

> **Nota de regresión (Bug F revierte una regla de `cierre-cursada-comision-nota-fix`, Bug 4):**
> aquel fix estableció `nota_final = None` (blanco) para REGULARIZA. Este bugfix lo cambia a
> `nota_final = 5` fijo. El o los tests que codifican "REGULARIZA con Nota Final en blanco"
> deben actualizarse a "REGULARIZA con Nota Final = 5".

> **Nota de regresión (Bug E amplía el conjunto de estados):** el veredicto de cierre pasa de
> 3 estados (PROMOCIONA/REGULARIZA/RECURSA) a 4 (agrega ABANDONO). Los alumnos con todo "N/E"
> que hoy caen en RECURSA pasan a ABANDONO; los tests y conteos que asumen sólo 3 estados deben
> actualizarse.
