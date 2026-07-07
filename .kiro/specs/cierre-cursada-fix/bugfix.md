# Documento de Requisitos del Bugfix

## Introducción

La pantalla de **Cierre de Cursada** clasifica a los alumnos de una materia en tres
categorías (Promocionado / Regular / Recursante) y genera una planilla Excel con el
resultado. Tras la última actualización, la pantalla dejó de funcionar bien y los
reportes generados salen mal: los alumnos quedan clasificados de forma incorrecta y
el Excel no tiene el formato esperado.

La causa raíz es que el cierre de cursada usa un sistema paralelo y aislado, con
umbrales fijos hardcodeados y un mapeo manual de ítems del calificador, en vez de
consumir la configuración de exámenes definida en el **dashboard de cada materia**
(`ExamenMateria`), que debería ser la única fuente de verdad. Como consecuencia:

- Clasifica con umbrales fijos (por ejemplo 60% para promocionar, 40% para
  regularizar) en vez de la `nota_minima` configurada por examen.
- No distingue el examen **global** como un requisito propio (obligatorio para
  promocionar, opcional para regularizar).
- No aplica la banda relativa de "regular" (mínimo − 20 en escala 100 / mínimo − 2 en
  escala 10).
- El Excel generado no coincide con el modelo corregido `docs/modelos/modelo planilla de
  cierre CORREGIDO.xlsx`: el generador actual produce columnas extra (TPs, Autoeval,
  Habilitado) y un gráfico de dona que el modelo corregido no tiene. Los TPs no
  intervienen en la clasificación ni en el reporte; la única fuente de verdad es
  `ExamenMateria` (PARCIAL/GLOBAL).
- El generador actual incluye una columna `Nota Final`, pero la calcula de forma
  incorrecta (sólo para los alumnos promotores y con un enfoque hardcodeado que no sigue
  la fórmula de negocio). Se requiere calcular la **Nota Final** de cada alumno con la
  fórmula ponderada oficial y mostrarla en una columna propia ubicada inmediatamente
  **después** de `Estado Alumno`.

Este bugfix busca que el cierre de cursada vuelva a clasificar correctamente, calcule la
**Nota Final** de cada alumno con la fórmula ponderada oficial y genere la planilla en el
formato correcto, tomando la configuración de la materia como fuente de verdad.

**Fórmula de Nota Final (provista por el usuario):**
- Con 2 parciales + 1 global:
  `NF = [(Parcial 1 + Parcial 2) / 2] * 0.4 + Nota Global * 0.6`
- Caso general (N parciales + 1 global):
  `NF = [(Parcial 1 + Parcial 2 + … + Parcial N) / N] * 0.4 + Nota Global * 0.6`,
  es decir `NF = (promedio de los N parciales) * 0.4 + (nota del examen GLOBAL) * 0.6`.

## Bug Analysis

### Current Behavior (Defect)

El cierre de cursada clasifica mal a los alumnos y produce una planilla con formato
incorrecto por no consumir la configuración de exámenes de la materia.

1.1 WHEN se genera el cierre de cursada de una materia THEN el sistema clasifica a los alumnos usando umbrales fijos hardcodeados (autoeval 90%, parcial promoción 60%, parcial regulariza 40%, TPI 60%) en vez de la `nota_minima` configurada por examen en el dashboard de la materia

1.2 WHEN una materia tiene un examen configurado como GLOBAL THEN el sistema no lo trata como un requisito propio (no lo exige para promocionar ni lo considera opcional para regularizar)

1.3 WHEN se evalúa si un alumno queda Regular THEN el sistema no aplica una banda relativa al mínimo del examen (mínimo − 20 en escala 100 / mínimo − 2 en escala 10), sino un umbral fijo de regularización

1.4 WHEN el alumno no alcanza ninguna de las condiciones de promoción ni de regularización basadas en umbrales fijos THEN el sistema lo clasifica sin considerar los mínimos reales configurados por examen

1.5 WHEN se genera la planilla Excel del cierre THEN el sistema produce un archivo cuyo formato (hojas y columnas) no coincide con el modelo corregido `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx`: el generador actual agrega columnas que el modelo corregido no tiene (`TPs Aprobados`, `Autoeval OK`, `TPI`, `Habilitado para Final`) y un gráfico de dona en el resumen

1.6 WHEN se quiere generar el cierre THEN el sistema exige un mapeo manual de ítems del calificador de Moodle (`CierreCursadaItem`) en vez de tomar la configuración de exámenes de la materia como fuente de verdad

1.7 WHEN se genera el cierre THEN el sistema no muestra una columna `Nota Final` correcta para todos los alumnos: el generador actual sólo computa una `Nota Final` para los alumnos promotores y con un enfoque hardcodeado/distinto que no aplica la fórmula ponderada oficial (promedio de parciales al 40% + nota del global al 60%)

### Expected Behavior (Correct)

El cierre de cursada debe clasificar en base a la configuración de exámenes de la
materia y generar la planilla con el formato del modelo.

2.1 WHEN se genera el cierre de cursada de una materia THEN el sistema SHALL clasificar a cada alumno usando la `nota_minima` configurada por examen en el dashboard de la materia (`ExamenMateria`) como fuente de verdad

2.2 WHEN una materia tiene un examen configurado como GLOBAL THEN el sistema SHALL exigir alcanzar su mínimo para clasificar al alumno como **Promocionado**, y SHALL tratarlo como opcional para clasificar al alumno como **Regular**

2.3 WHEN un alumno alcanza el mínimo de aprobación de TODOS los exámenes configurados (incluido el global) THEN el sistema SHALL clasificarlo como **Alumno Promocionado**

2.4 WHEN un alumno no promociona pero alcanza al menos (nota_minima − 20 para exámenes en escala 100, mínimo tipo 60) o (nota_minima − 2 para exámenes en escala 10, mínimo tipo 6) en TODOS los exámenes EXCEPTO el global THEN el sistema SHALL clasificarlo como **Alumno Regular**

2.5 WHEN un alumno no cumple los requisitos de promoción ni de regularización THEN el sistema SHALL clasificarlo como **Alumno Recursante**

2.6 WHEN se genera la planilla Excel del cierre THEN el sistema SHALL producir un archivo con el mismo formato (hojas y columnas) que el modelo corregido `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx`, aplicando los estilos visuales de la casa (`excel_estilos.py` / `excel_service.py`)

2.7 WHEN se genera el cierre THEN el sistema SHALL tomar la configuración de exámenes de la materia (`ExamenMateria`) como fuente de verdad, sin requerir un mapeo manual separado de ítems del calificador (`CierreCursadaItem`)

2.8 WHEN se genera la planilla Excel del cierre THEN el sistema SHALL producir una tabla con exactamente estas columnas: `Nombre y Apellido | Email | Parcial n… | Global TPI | Estado Alumno | Nota Final` (una columna `Parcial n` por cada examen configurado como PARCIAL, una única columna `Global TPI` para el examen GLOBAL, y la columna `Nota Final` ubicada inmediatamente después de `Estado Alumno`), y SHALL NO incluir columnas de TPs (`TPs Aprobados`, `Autoeval OK`, `TPI`, `Habilitado para Final`) ni un gráfico de dona

2.9 WHEN se puebla la columna `Global TPI` de un alumno THEN el sistema SHALL mostrar la nota/resultado del examen configurado como GLOBAL (valor numérico cuando el alumno lo rindió/aprobó, `N/E` en caso contrario), y NO una nota final compuesta ni un promedio

2.10 WHEN se clasifica a un alumno y se genera su planilla THEN el sistema SHALL derivar el veredicto y el reporte EXCLUSIVAMENTE de `ExamenMateria` (PARCIAL/GLOBAL), sin que los TPs intervengan en la clasificación ni en el reporte

2.11 WHEN se genera el cierre de cursada de una materia THEN el sistema SHALL calcular la **Nota Final** de cada alumno como un promedio ponderado: el promedio de las notas de los N exámenes configurados como PARCIAL ponderado al 40%, más la nota del examen configurado como GLOBAL ponderada al 60%, es decir `NF = (promedio de los N parciales) * 0.4 + (nota del examen GLOBAL) * 0.6`

2.12 WHEN se genera la planilla Excel del cierre THEN el sistema SHALL incluir una columna `Nota Final` ubicada inmediatamente **después** de la columna `Estado Alumno`, mostrando la Nota Final calculada de cada alumno

2.13 WHEN a un alumno le falta algún insumo requerido para la Nota Final (no rindió el examen GLOBAL, o algún examen PARCIAL no tiene nota numérica) THEN el sistema SHALL representar la Nota Final como `N/E` (no aplica) en vez de un número incorrecto; la Nota Final SHALL calcularse únicamente cuando todos los parciales y el global tengan una nota numérica

> **Nota (a confirmar en diseño):** Se asume por defecto que la Nota Final se computa sólo
> cuando todos los parciales y el global tienen nota numérica; en caso contrario se muestra
> `N/E`. Si el negocio requiriera otro tratamiento (p. ej. computar con los insumos
> disponibles o usar la nota del recuperatorio), debe confirmarse antes de implementar.

> **Flag para diseño (no se resuelve en requisitos):** los exámenes PARCIAL y el examen
> GLOBAL pueden estar en escalas distintas (parciales en escala 100, p. ej. 60/80/100;
> global en escala 10, p. ej. 9.0). El diseño DEBE normalizar todos los valores a una
> escala común antes de aplicar la fórmula ponderada, de lo contrario la Nota Final saldrá
> mal. La escala de cada examen se detecta desde su `nota_minima` (ver diseño).

### Unchanged Behavior (Regression Prevention)

El fix no debe alterar el comportamiento correcto que ya existe.

3.1 WHEN un examen PARCIAL o GLOBAL tiene recuperatorio/extensión/extraordinaria vinculados THEN el sistema SHALL CONTINUAR resolviendo el examen como aprobado si aprobó el original o cualquiera de sus instancias de rescate

3.2 WHEN un examen está configurado en modo ESCALA (Aprobado/Desaprobado) THEN el sistema SHALL CONTINUAR evaluándolo por el resultado de la escala y no por una nota numérica

3.3 WHEN se genera el cierre THEN el sistema SHALL CONTINUAR agrupando a los alumnos por comisión y tutor en el reporte

3.4 WHEN se genera una corrida de cierre THEN el sistema SHALL CONTINUAR guardándola como histórico append-only sin sobrescribir corridas anteriores

3.5 WHEN se genera cualquier reporte Excel de la plataforma THEN el sistema SHALL CONTINUAR usando los estilos visuales de la casa (paleta, bordes, banda de título, gráficos de dona) ya definidos en `excel_estilos.py`

3.6 WHEN se resuelve la comisión de un alumno por su grupo de Moodle y el mapeo es ambiguo o inexistente THEN el sistema SHALL CONTINUAR asignándolo a "Sin comisión asignada" sin romper la corrida
