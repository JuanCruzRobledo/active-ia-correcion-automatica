# Bugfix Requirements Document

## Introduction

Este bugfix agrupa **dos defectos** reportados por el usuario después de que se publicara la
spec `cierre-cursada-quiz-recuperables-fix`. Ambos afectan la salida del **Cierre de Cursada**
de Active-IA (corrección automática TUD): la resolución de la comisión de un alumno durante la
exploración de Moodle, y las fórmulas nativas del Excel de cierre.

Los dos problemas son:

- **Bug 1 — Alumnos multi-grupo caen en "Sin comisión asignada".** En Programación 2 (cohorte
  agosto 2025, 2º cuatrimestre) varios alumnos que SÍ tienen una comisión válida aparecen
  clasificados como "Sin comisión asignada" en el cierre. Caso concreto reportado: la alumna
  **TAMARA ROCIO ALBARRACÍN** aparece como "Sin comisión" a pesar de pertenecer a la comisión
  real **"A25 C2-01"**. Sus grupos de Moodle son:
  `"A25 C2-01"`, `"Extraordinaria_sdo_parcial"`, `"NO_RINDIERON_PARCIAL_1"`, `"No-rindieron-P1"`,
  `"R-Mendoza"`, `"Ultima_INSTANCIA_Examen"`. El patrón común de los casos que fallan es el mismo:
  alumnos que pertenecen a VARIOS grupos que no son de comisión (grupos de estado / instancia /
  regional) además de su grupo de comisión.

- **Bug 2 — Las fórmulas del Excel muestran `#NAME?`.** El Excel de cierre (hojas "por Comisiones"
  y "Crudo") muestra `#NAME?` en todas las celdas de fórmula: la columna "Recuperable" por fila y
  los conteos del resumen (`CONTAR.SI`). El usuario tiene que corregirlas manualmente o no puede
  usar la planilla tal cual sale.

### Formato del código de comisión (a generalizar, NO hardcodear)

El regex que reconoce un grupo de comisión debe generalizarse (sin valores fijos de año, cohorte
ni semestre) según el formato real:

```
{cohorte}{año} C{semestre}-{NN}
```

- **cohorte:** `M` (marzo) o `A` (agosto).
- **año:** exactamente 2 dígitos (`25`, `26`, `27`, ...).
- **`C`** literal seguido del número de semestre (`1`, `2`, `3`, ...).
- **`-`** y el número de comisión (`01`, `02`, ...).

Ejemplos válidos: `"A25 C2-01"` (Programación 2, agosto 2025, semestre 2, comisión 1),
`"M26 C1-01"` (Programación 1, marzo 2026, semestre 1, comisión 1),
`"M25 C3-01"` (Programación 3, marzo 2025, semestre 3, comisión 1).

### Enfoque de exploración / reproducción (observación primero)

Este spec sigue un enfoque **de observación primero**: la causa raíz NO se asume, se confirma
contra el comportamiento real antes de escribir código.

- **Bug 1 (causa raíz por confirmar en diseño con los datos de grupo reales).** La condición del
  bug se dispara en la resolución de comisión del cierre. Las hipótesis a confirmar o refutar en
  la fase de diseño, reproduciendo con los grupos reales de TAMARA (`"A25 C2-01"` +
  `Extraordinaria_sdo_parcial` + `NO_RINDIERON_PARCIAL_1` + `No-rindieron-P1` + `R-Mendoza` +
  `Ultima_INSTANCIA_Examen`), son:
  - **(a) Falso positivo por segundo match:** uno de los OTROS grupos del alumno (estado /
    instancia / regional) matchea una comisión de la BD por `moodle_group_id`, produciendo un
    SEGUNDO match distinto y disparando la regla de ambigüedad (`len(encontradas) != 1`), que
    resuelve a "Sin comisión asignada".
  - **(b) Cero matches del grupo real:** el grupo de comisión real `"A25 C2-01"` falla los DOS
    puentes: su `moodle_group_id` no está seteado o no coincide, Y el `Comision.nombre` en la BD
    no es exactamente `"A25 C2-01"` (desajuste de nombre) → 0 matches.
  - **(c) Interacción con el mapa autoritativo `uid → grupos`** (Bug 3 del spec previo) sobre la
    regla de ambigüedad.
  - Debe confirmarse ADEMÁS que el regex reconoce correctamente el formato de comisión y sólo ese
    formato (año = exactamente 2 dígitos), para que grupos de estado/instancia/regional nunca se
    interpreten como comisión.
- **Bug 2 (causa raíz confirmada).** Las fórmulas se escriben con nombres de función es-AR
  (`SI`, `CONTAR.SI`, `Y`, `VALOR`, `SI.ERROR`) y `;` como separador de argumentos. openpyxl
  escribe el string de fórmula VERBATIM dentro del OOXML, pero el formato de archivo `.xlsx`
  almacena las fórmulas con nombres de función en INGLÉS y COMA como separador; Excel / Google
  Sheets las traducen al locale de visualización recién al abrir. Por eso los nombres es-AR + `;`
  son inválidos en el archivo almacenado y se muestran como `#NAME?` en CUALQUIER locale.

### Formalización de las condiciones de bug

**Bug 1 — Condición de bug `C1(X)`.** `X` es un alumno con su lista de grupos de Moodle y el
conjunto de comisiones de la materia:

```pascal
FUNCTION isBugCondition1(X)
  INPUT: X = (grupos: list<Grupo>, comisiones: list<Comision>)
  OUTPUT: boolean

  // Existe EXACTAMENTE UN grupo cuyo nombre matchea el formato de comisión
  // {cohorte}{año} C{semestre}-{NN}, y ese grupo corresponde a UNA comisión real...
  grupos_comision ← [ g IN X.grupos WHERE matchesComisionFormat(g.name) ]
  RETURN (count(grupos_comision) = 1)
         AND (resolver_comision(X.grupos, X.comisiones) = "Sin comisión asignada")
END FUNCTION
```

```pascal
// Property: Fix Checking — el alumno multi-grupo se asigna a su comisión real
FOR ALL X WHERE isBugCondition1(X) DO
  (comision_id, comision_nombre, _) ← resolver_comision'(X.grupos, X.comisiones)
  ASSERT comision_nombre = nombreDeLaUnicaComisionFormato(X.grupos)
  ASSERT comision_nombre <> "Sin comisión asignada"
END FOR
```

Los grupos que no son de comisión (estado / instancia / regional) deben ignorarse y **nunca**
deben producir ambigüedad.

**Bug 2 — Condición de bug `C2(X)`.** `X` es una celda de fórmula emitida en el `.xlsx`:

```pascal
FUNCTION isBugCondition2(X)
  INPUT: X = fórmula escrita en una celda del .xlsx
  OUTPUT: boolean

  // La fórmula usa nombres de función es-AR y/o ';' como separador de argumentos
  RETURN usaNombresFuncionEsAR(X) OR usaPuntoYComaComoSeparador(X)
END FUNCTION
```

```pascal
// Property: Fix Checking — la fórmula abre y calcula en cualquier locale
FOR ALL X WHERE isBugCondition2(X) DO
  X' ← fórmula emitida por F'   // nombres en inglés + coma
  ASSERT usaNombresFuncionIngles(X') AND usaComaComoSeparador(X')
  ASSERT valorCalculado(X') = valorEsperado(intencionEsAR(X))
  ASSERT abreSinError(X', locale = cualquiera)   // sin #NAME?
END FOR
```

**Objetivo de preservación (ambos bugs):**

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition1(X) AND NOT isBugCondition2(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

Donde `F` es el código antes del fix y `F'` el código después.

### Dirección del fix (a detallar en diseño)

- **Bug 1:** generalizar el regex de comisión (año = exactamente 2 dígitos, sin hardcodear
  cohorte/año/semestre) y corregir la resolución de comisión para que priorice/aísle el grupo con
  formato de comisión y para que los grupos que no son de comisión no generen matches espurios ni
  ambigüedad. La causa raíz exacta (hipótesis a / b / c) se confirma en diseño con los datos
  reales antes de codificar.
- **Bug 2:** emitir las fórmulas con nombres de función en INGLÉS y COMA como separador
  (`IF`, `COUNTIF`, `AND`, `VALUE`, `IFERROR`), conservando los mismos criterios comodín
  (`"RECUPERABLE*"`, `"RECUPERABLE CON*"`) y las mismas referencias de columna por hoja.
  Ejemplo de la fórmula "Recuperable":
  `=IF(F{n}<>"RECURSA","",IF(AND(IFERROR(VALUE(C{n}),0)>=40,IFERROR(VALUE(D{n}),0)<40),"RECUPERABLE CON PARCIAL 2",IF(AND(IFERROR(VALUE(D{n}),0)>=40,IFERROR(VALUE(C{n}),0)<40),"RECUPERABLE CON PARCIAL 1","")))`
  y los conteos `=COUNTIF(F:F,"PROMOCIONA")`, `=COUNTIF(H:H,"RECUPERABLE*")`, etc.

## Bug Analysis

### Current Behavior (Defect)

Lo que ocurre hoy cuando se dispara cada bug.

**Bug 1 — Alumnos multi-grupo resueltos como "Sin comisión asignada"**

1.1 WHEN un alumno pertenece a exactamente un grupo con formato de comisión válido (`"A25 C2-01"`) y además a varios grupos que no son de comisión (estado / instancia / regional, p. ej. `"Extraordinaria_sdo_parcial"`, `"NO_RINDIERON_PARCIAL_1"`, `"No-rindieron-P1"`, `"R-Mendoza"`, `"Ultima_INSTANCIA_Examen"`) THEN el sistema lo clasifica como "Sin comisión asignada" en lugar de asignarlo a su comisión real.

1.2 WHEN alguno de los grupos que no son de comisión del alumno coincide accidentalmente con una comisión de la BD por `moodle_group_id`, o el grupo de comisión real no matchea por `moodle_group_id` ni por nombre THEN el sistema obtiene un número de comisiones encontradas distinto de 1 (0 o más de 1) y aplica la regla de ambigüedad devolviendo "Sin comisión asignada".

1.3 WHEN el regex de reconocimiento de comisión evalúa un año con distinta cantidad de dígitos THEN el sistema no acota el año a exactamente 2 dígitos, dejando el patrón más laxo de lo que exige el formato real `{cohorte}{año} C{semestre}-{NN}`.

**Bug 2 — Las fórmulas del Excel muestran `#NAME?`**

1.4 WHEN se genera el Excel de cierre y se abre en Excel o Google Sheets THEN el sistema muestra `#NAME?` en la columna "Recuperable" de cada fila, porque la fórmula se escribió con nombres de función es-AR (`SI`, `Y`, `VALOR`, `SI.ERROR`) y `;` como separador.

1.5 WHEN se genera el Excel de cierre y se abre en Excel o Google Sheets THEN el sistema muestra `#NAME?` en las celdas de conteo del resumen (Promocionados / Regulares / Recursantes / Recuperables / Abandonos), porque se escribieron con `CONTAR.SI` y `;` en vez de `COUNTIF` y coma.

1.6 WHEN el archivo `.xlsx` se guarda con openpyxl THEN el string de fórmula se persiste VERBATIM en el OOXML con la sintaxis es-AR, que es inválida para el formato de archivo (que requiere nombres en inglés y coma), por lo que la fórmula queda rota en TODO locale de apertura.

### Expected Behavior (Correct)

Lo que debería ocurrir en cada una de las condiciones anteriores.

**Bug 1 — Alumnos multi-grupo asignados a su comisión real**

2.1 WHEN un alumno pertenece a exactamente un grupo con formato de comisión válido y además a varios grupos que no son de comisión THEN el sistema SHALL identificar el grupo con formato de comisión y asignar al alumno a esa comisión.

2.2 WHEN el alumno tiene grupos que no son de comisión (estado / instancia / regional) THEN el sistema SHALL ignorarlos y SHALL evitar que generen matches espurios o ambigüedad en la resolución de comisión.

2.3 WHEN se reconoce un nombre de grupo de comisión THEN el sistema SHALL usar un regex generalizado del formato `{cohorte}{año} C{semestre}-{NN}` (cohorte `M`/`A`, año de exactamente 2 dígitos, `C` + número de semestre, `-` + número de comisión) sin hardcodear valores concretos de cohorte, año ni semestre.

2.4 WHEN se investiga la causa raíz del defecto THEN el sistema SHALL confirmarla contra los datos de grupo reales del caso reportado (TAMARA ROCIO ALBARRACÍN / `"A25 C2-01"`) antes de aplicar el fix, y SHALL corregir la causa identificada (hipótesis a: segundo match espurio; b: cero matches del grupo real; c: interacción con el mapa autoritativo `uid → grupos`).

**Bug 2 — Fórmulas del Excel válidas en cualquier locale**

2.5 WHEN se genera el Excel de cierre THEN el sistema SHALL emitir las fórmulas con nombres de función en INGLÉS (`IF`, `COUNTIF`, `AND`, `VALUE`, `IFERROR`) y COMA como separador de argumentos.

2.6 WHEN se abre el Excel generado en Excel o Google Sheets THEN el sistema SHALL mostrar las fórmulas calculadas correctamente, sin `#NAME?` y sin requerir ningún ajuste regional o de locale por parte del usuario.

2.7 WHEN se emite la fórmula "Recuperable" por fila THEN el sistema SHALL producir `=IF(F{n}<>"RECURSA","",IF(AND(IFERROR(VALUE(C{n}),0)>=40,IFERROR(VALUE(D{n}),0)<40),"RECUPERABLE CON PARCIAL 2",IF(AND(IFERROR(VALUE(D{n}),0)>=40,IFERROR(VALUE(C{n}),0)<40),"RECUPERABLE CON PARCIAL 1","")))` (referencias de columna según la hoja) que compute el MISMO resultado que la fórmula es-AR pretendida.

2.8 WHEN se emiten los conteos del resumen THEN el sistema SHALL producir `COUNTIF` en inglés (p. ej. `=COUNTIF(F:F,"PROMOCIONA")`, `=COUNTIF(H:H,"RECUPERABLE*")`) que computen los MISMOS 5 conteos que las fórmulas es-AR pretendidas.

### Unchanged Behavior (Regression Prevention)

Comportamiento existente que debe preservarse.

3.1 WHEN un alumno pertenece genuinamente a DOS comisiones reales distintas (ambigüedad real) THEN el sistema SHALL CONTINUE TO clasificarlo como "Sin comisión asignada".

3.2 WHEN un alumno no pertenece a ningún grupo con formato de comisión válido THEN el sistema SHALL CONTINUE TO clasificarlo como "Sin comisión asignada".

3.3 WHEN un alumno pertenece a un único grupo de comisión correctamente vinculado por `moodle_group_id` THEN el sistema SHALL CONTINUE TO resolverlo por ese puente primario, con el mismo orden y prioridad de puentes (`moodle_group_id` y luego nombre) que hoy.

3.4 WHEN un alumno con comisión resuelta tiene tutores asignados THEN el sistema SHALL CONTINUE TO devolver el `comision_id`, `comision_nombre` y el nombre de tutor(es) como hoy.

3.5 WHEN un grupo es regional (`"R-<nombre>"`) THEN el sistema SHALL CONTINUE TO parsearlo como regional y no como comisión (no debe interpretarse como grupo de comisión).

3.6 WHEN se resuelve la comisión de cualquier alumno THEN el sistema SHALL CONTINUE TO no interrumpir la corrida del cierre por un alumno con mapeo ambiguo o roto.

3.7 WHEN se genera el Excel de cierre THEN el sistema SHALL CONTINUE TO producir las dos hojas ("por Comisiones" y "Crudo") con su estructura, estilos de la casa, celdas `N/E` y comportamiento de "Nota Final" definidos en la spec previa `cierre-cursada-quiz-recuperables-fix`.

3.8 WHEN se emiten las fórmulas del Excel THEN el sistema SHALL CONTINUE TO usar los mismos criterios comodín (`"RECUPERABLE*"` en "por Comisiones", `"RECUPERABLE CON*"` en "Crudo") y las mismas referencias de columna por hoja (por Comisiones: Estado `F`, parciales `C`/`D`, auxiliar Recuperable `H`; Crudo: Estado `H`, parciales `E`/`F`, Recuperable `J`); sólo cambian los nombres de función y el separador.

3.9 WHEN se guarda el `.xlsx` generado THEN el sistema SHALL CONTINUE TO producir un archivo que abre con openpyxl (para los tests), computando los mismos valores de clasificación "Recuperable" y los mismos 5 conteos del resumen que las fórmulas es-AR pretendidas.
