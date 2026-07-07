# Cierre de Cursada — Diseño del Bugfix

## Overview

El cierre de cursada dejó de clasificar bien porque corre sobre un sistema paralelo y
aislado: un **mapeo manual de ítems del calificador** (`CierreCursadaItem`) con
**umbrales fijos hardcodeados** (autoeval 90 %, parcial promoción 60 %, parcial
regulariza 40 %, TPI 60 %) en `REGLAS_CIERRE_DEFAULT`. Ese sistema ignora por completo
la configuración de exámenes de la materia (`ExamenMateria`), que es la fuente de verdad
del dashboard de gestores: define por examen su `tipo` (PARCIAL/GLOBAL), su
`modo_aprobacion` (ESCALA/NUMERICO), su `nota_minima` y sus cadenas de rescate
(`recupera_examen_id`).

La estrategia del fix es **eliminar el sistema paralelo** y hacer que el cierre consuma
`ExamenMateria` + las notas ya descargadas de Moodle, aplicando una función PURA de
clasificación análoga a `examen_mapper` / `cierre_cursada_calculo.calcular_estado` pero
dirigida por la config de cada examen:

- **Promocionado**: alcanza el mínimo (`nota_minima`, con rescate) en TODOS los exámenes,
  incluido el GLOBAL.
- **Regular**: alcanza al menos `(nota_minima − banda)` en todos los exámenes EXCEPTO el
  GLOBAL (que es opcional para regularizar). La banda es **20** para exámenes en escala
  100 y **2** para exámenes en escala 10.
- **Recursante**: no cumple ninguna de las anteriores.

Además se rehace el generador de Excel (`excel_cierre_cursada.py`) para reproducir
fielmente el modelo **corregido** `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx`
(decodificado abajo con precisión) reutilizando los helpers de estilo de la casa
(`excel_estilos.py`), **más una columna adicional `Nota Final`** (ver abajo) que el usuario
pidió explícitamente agregar como última columna, inmediatamente después de `Estado Alumno`.

**Nota Final (nuevo requisito).** Cada alumno lleva una **Nota Final** calculada con la
fórmula ponderada oficial: el promedio de los N exámenes PARCIAL al 40 % más la nota del
examen GLOBAL al 60 % — `NF = (promedio de los N parciales) * 0.4 + (nota del GLOBAL) * 0.6`
(el caso "2 parciales + 1 global" es simplemente N=2:
`NF = [(P1 + P2)/2] * 0.4 + Global * 0.6`). El punto crítico es que los parciales y el
global pueden estar en **escalas distintas** (parciales en escala 100, global en escala 10),
así que la fórmula NO se aplica sobre los `valor_real` crudos: primero se **normalizan todos
los exámenes a una escala común** (0–10) reutilizando `detectar_escala(nota_minima)`. La NF
resultante es un entero 0–10 (redondeo `round_half_up`), y es `N/E` cuando falta algún
insumo requerido (ver requisito 2.13). Se calcula en una función PURA nueva
(`calcular_nota_final`) y se persiste en la columna `nota_final` ya existente de
`CierreCursadaAlumno` (reutilizada, `Integer` 0–10, nullable = `N/E`).

> **Nota sobre el modelo (corrección del usuario):** el modelo válido es
> `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx`. El archivo anterior
> (`modelo planilla de cierre.xlsx`) estaba **desactualizado**: su hoja "Programacion 3"
> incluía columnas `TP n` que **no corresponden**. La planilla corregida **NO tiene
> columnas de TPs** en ninguna hoja. La clasificación ya estaba dirigida exclusivamente
> por `ExamenMateria` (PARCIAL/GLOBAL) y los TPs **no juegan ningún rol** ni en la
> clasificación ni en el Excel (`ExamenMateria` ni siquiera modela TPs: sus tipos son
> PARCIAL/RECUPERATORIO/EXTENSION/EXTRAORDINARIA/GLOBAL).

Este documento resuelve los tres ítems abiertos que quedaron diferidos desde requisitos:
el **layout exacto del Excel modelo** (Ítem Abierto 1, contra el archivo CORREGIDO), la
**detección de escala 100 vs 10** (Ítem Abierto 2) y el **destino de `CierreCursadaItem`**
(Ítem Abierto 3).

---

## Glossary

- **Bug_Condition (C)**: el cierre clasifica y/o dibuja el Excel sin consumir
  `ExamenMateria` — usa umbrales fijos, mapeo manual de ítems y un layout que no coincide
  con el modelo.
- **Property (P)**: para toda materia con exámenes configurados, el veredicto de cada
  alumno se deriva EXCLUSIVAMENTE de `ExamenMateria` (tipo, modo, `nota_minima`, rescate)
  y el Excel reproduce el modelo con los estilos de la casa.
- **Preservation**: comportamiento correcto ya existente que el fix NO debe cambiar
  (cadenas de rescate, exámenes ESCALA, agrupación por comisión/tutor, histórico
  append-only, estilos de la casa, fallback "Sin comisión asignada").
- **ExamenMateria**: modelo (`app/models/examen_materia.py`) que define un examen de una
  materia. Campos clave: `tipo`, `moodle_cmid`, `modo_aprobacion`, `nota_minima`,
  `recupera_examen_id`, `orden`. **Fuente de verdad del cierre.**
- **Examen principal**: examen de `tipo` PARCIAL o GLOBAL — es una fila/columna del
  reporte. Los RECUPERATORIO/EXTENSION/EXTRAORDINARIA no son principales: se pliegan
  dentro del principal que rescatan.
- **Cadena de rescate**: un PARCIAL/GLOBAL queda aprobado si lo aprobó él o alguna de sus
  instancias de rescate (`examen_mapper.calcular_resultados_examenes`).
- **banda (regular)**: relajación relativa al mínimo para clasificar como Regular. `20`
  en escala 100, `2` en escala 10.
- **escala del examen**: 100 (mínimos tipo 60) o 10 (mínimos tipo 6). Se detecta desde la
  magnitud de `nota_minima` (ver Ítem Abierto 2).
- **Nota Final (NF)**: promedio ponderado del alumno — `(promedio de los N parciales) * 0.4
  + (nota del GLOBAL) * 0.6`, calculado sobre valores **normalizados a escala común (0–10)**.
  Entero 0–10 (`round_half_up`) o `N/E` si falta algún insumo requerido.
- **normalización de escala**: llevar el `valor_real` de cada examen a una escala común
  (0–10) antes de aplicar la fórmula de NF: los valores en escala 100 se dividen por 10, los
  de escala 10 quedan igual. Reutiliza `detectar_escala(nota_minima)`.
- **`calcular_nota_final`**: nueva función PURA (en `cierre_cursada_calculo.py`) que computa
  la NF a partir de los mismos insumos por examen que `calcular_estado_cierre`.
- **`calcular_estado_cierre`**: nueva función PURA que reemplaza a
  `cierre_cursada_calculo.calcular_estado`, dirigida por config de examen.
- **`CierreCursadaItem`**: modelo del mapeo manual de ítems del calificador — se
  **elimina** por este fix (ver Ítem Abierto 3).

---

## Bug Details

### Bug Condition

El bug se manifiesta cada vez que se genera un cierre de cursada de una materia: la
función de cierre (`CierreCursadaService.generar` + `cierre_cursada_calculo.calcular_estado`)
clasifica con umbrales fijos y un mapeo manual de ítems en vez de consumir
`ExamenMateria`, y el generador de Excel produce columnas/hojas que no coinciden con el
modelo.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input = { materia, examenes_config: list[ExamenMateria], notas_moodle }
  OUTPUT: boolean

  # Hay al menos un examen configurado en el dashboard (fuente de verdad disponible)…
  tiene_config := LENGTH(input.examenes_config) > 0

  # …pero el veredicto/planilla NO se derivan de esa config:
  clasifica_con_umbral_fijo := usa REGLAS_CIERRE_DEFAULT / umbral_tp_pct
                               EN LUGAR DE examen.nota_minima
  ignora_global            := NOT trata el examen GLOBAL como requisito de promoción
                               y opcional para regular
  ignora_banda_relativa    := NOT aplica (nota_minima − banda) para Regular
  exige_mapeo_manual       := requiere CierreCursadaItem confirmado para calcular
  excel_no_coincide        := layout(Excel) != layout(modelo planilla de cierre.xlsx)
  nota_final_incorrecta    := NO calcula la Nota Final ponderada oficial para TODOS los
                              alumnos con escala normalizada (sólo la computa para
                              promotores y/o sobre valores de escalas mixtas sin normalizar)

  RETURN tiene_config AND (
           clasifica_con_umbral_fijo OR ignora_global OR ignora_banda_relativa
           OR exige_mapeo_manual OR excel_no_coincide OR nota_final_incorrecta
         )
END FUNCTION
```

### Examples

- **Umbral fijo vs mínimo real** — Un parcial con `nota_minima = 50` (escala 100). Un
  alumno saca 55. Esperado: aprueba el mínimo del examen. Actual: se compara contra el
  fijo `parcial_promocion_min_pct = 60` → NO promociona por un umbral que la materia
  nunca configuró.
- **Global ignorado** — Materia con un examen GLOBAL (`nota_minima = 6`, escala 10). Un
  alumno aprueba ambos parciales pero no rinde el global. Esperado: **Regular** (global
  opcional para regular) y NO **Promocionado** (global obligatorio para promocionar).
  Actual: el global no existe como concepto en el cálculo → clasifica sin exigirlo.
- **Banda relativa ausente** — Parcial `nota_minima = 60` (escala 100). Un alumno saca
  45. Esperado: 45 ≥ (60 − 20 = 40) → cumple la banda de Regular. Actual: se compara
  contra el fijo `parcial_regulariza_min_pct = 40` (coincide por casualidad acá, pero
  rompe si el mínimo fuera 70 → banda 50).
- **Escala 10** — Parcial `nota_minima = 6` (escala 10). Un alumno saca 4. Esperado: 4 ≥
  (6 − 2 = 4) → cumple banda de Regular. Actual: el sistema fijo asume porcentajes 0–100
  → interpreta 4 como 4 % y lo reprueba.
- **Excel** — El archivo generado hoy tiene columnas
  `TPs Aprobados / Autoeval OK / Parcial 1 / Parcial 2 / TPI / Nota Final / Estado Alumno /
  Habilitado para Final` más una dona, mientras el modelo corregido tiene exactamente 6
  columnas (`Nombre y Apellido | Email | Parcial 1 | Parcial 2 | Global TPI | Estado
  Alumno`), sin columnas de TPs y sin gráfico. El fix reproduce esas 6 columnas y agrega
  `Nota Final` como 7ª (última) columna por pedido del usuario.
- **Nota Final mal calculada** — Un alumno REGULARIZA con parciales `70/80` (escala 100) y
  global `8.0` (escala 10). Esperado: NF = `((7.0+8.0)/2)*0.4 + 8.0*0.6 = 3.0 + 4.8 = 7.8 →
  8` (con escala normalizada a 0–10). Actual: el generador deja `Nota Final = N/E` para
  no-promotores, y para promotores la calcula sobre valores en escalas mixtas sin normalizar
  → número sin sentido.

---

## Expected Behavior

### Preservation Requirements

**Comportamientos que NO deben cambiar (regresión):**
- **Cadenas de rescate** (bugfix 3.1): un PARCIAL/GLOBAL sigue aprobado si aprobó él o
  cualquiera de sus recuperatorios/extensiones/extraordinarias.
- **Exámenes ESCALA** (bugfix 3.2): se siguen evaluando por su resultado de escala
  (`Aprobado`/`Desaprobado`), no por nota numérica.
- **Agrupación por comisión y tutor** (bugfix 3.3): el reporte sigue agrupando alumnos
  por comisión + tutor.
- **Histórico append-only** (bugfix 3.4): cada corrida sigue guardándose sin sobrescribir
  las anteriores (`CierreCursadaRun`).
- **Estilos de la casa** (bugfix 3.5): el Excel sigue usando la paleta, bordes, banda de
  título y helpers de `excel_estilos.py`.
- **Fallback de comisión** (bugfix 3.6): un alumno con grupo de Moodle ambiguo/inexistente
  sigue cayendo en "Sin comisión asignada" sin romper la corrida
  (`CierreCursadaService._resolver_comision` se conserva 1:1).

**Alcance:**
Todo input que NO involucre la clasificación ni el layout del Excel debe quedar intacto:
la descarga masiva de Moodle (WS + sesión + export dual, número constante de requests),
la resolución de comisión/tutor, la persistencia append-only y el resto de reportes Excel
de la plataforma (`excel_service.py`, avance de tutores) que comparten `excel_estilos.py`.

**Nota:** El comportamiento correcto esperado (qué debe dar la clasificación) está en
"Correctness Properties" (Property 1). Esta sección enumera qué NO debe cambiar.

---

## Hypothesized Root Cause

La causa raíz es **un sistema de cierre paralelo que nunca se integró con `ExamenMateria`**.
Desglosado:

1. **Umbrales fijos hardcodeados**: `REGLAS_CIERRE_DEFAULT` en
   `cierre_cursada_service.py` (autoeval 90, parcial promoción 60, parcial regulariza 40,
   TPI 60) y `umbral_tp_pct` por request. `cierre_cursada_calculo.calcular_estado` compara
   contra esos fijos, no contra `examen.nota_minima`.

2. **Mapeo manual de ítems como fuente de verdad**: `CierreCursadaItem` +
   `CategoriaItemCierreEnum` (TP/AUTOEVAL/PARCIAL_1/PARCIAL_2/TPI/IGNORAR) obligan al
   coordinador a categorizar cada ítem del calificador a mano, en vez de leer el
   `moodle_cmid` que **ya** está en cada `ExamenMateria`.

3. **El examen GLOBAL no es un concepto del cálculo**: `calcular_estado` sólo conoce
   `parcial1_pcts`/`parcial2_pcts`/`tpi_pcts`; no hay noción de "global obligatorio para
   promoción, opcional para regular".

4. **Sin banda relativa ni noción de escala**: la relajación de Regular es un fijo
   (`parcial_regulariza_min_pct`) y todo se asume porcentaje 0–100; no existe
   `(nota_minima − banda)` ni detección de escala 10 vs 100.

5. **Generador de Excel con columnas ad-hoc**: `excel_cierre_cursada.py` dibuja columnas
   fijas propias del modelo viejo, no las columnas dinámicas por examen del modelo real.

6. **Nota Final hardcodeada y sin normalizar escala**: `calcular_estado` sólo computa la NF
   para PROMOCIONA (`((p1+p2)/2)*0.4 + tpi*0.6`, luego `/10`) — los alumnos REGULARIZA/
   RECURSA quedan en `N/E` aunque tengan todas las notas, y el cálculo opera sobre
   porcentajes de ítems del sistema viejo, no sobre `valor_real` normalizado a una escala
   común, por lo que con parciales en escala 100 y global en escala 10 la NF sale mal.

**Confirmación/refutación:** los tests exploratorios (Testing Strategy) deben mostrar,
sobre el código SIN arreglar, que (a) alumnos se clasifican con umbrales que la materia no
configuró y (b) el Excel no reproduce el modelo. Si no se reproduce el fallo, se
re-hipotetiza.

---

## Correctness Properties

Property 1: Bug Condition — Clasificación dirigida por ExamenMateria

_For any_ materia con exámenes configurados y un alumno con sus notas de Moodle (donde
`isBugCondition` es verdadera), la función corregida `calcular_estado_cierre` SHALL
clasificar al alumno derivando el veredicto EXCLUSIVAMENTE de `ExamenMateria`:
**Promocionado** si alcanza `nota_minima` (con rescate) en TODOS los exámenes incluido el
GLOBAL; **Regular** si (no promociona y) alcanza `(nota_minima − banda)` en todos los
exámenes EXCEPTO el GLOBAL, con `banda = 20` en escala 100 y `banda = 2` en escala 10;
**Recursante** en cualquier otro caso.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation — Comportamiento no relacionado sin cambios

_For any_ input donde `isBugCondition` es falsa (cadenas de rescate, exámenes en modo
ESCALA, resolución de comisión/tutor, persistencia append-only, estilos de Excel de la
casa, fallback "Sin comisión asignada"), el código corregido SHALL producir exactamente
el mismo resultado que el original, preservando la lógica de rescate, la evaluación por
escala, la agrupación, el histórico y el lenguaje visual compartido.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

Property 3: Excel reproduce el modelo corregido + columna Nota Final

_For any_ corrida persistida, el `.xlsx` generado SHALL tener, por materia, la estructura
del modelo `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx`: título
"TOTAL MATERIA {NOMBRE}" (merge `A1:B1`), resumen de 3 filas
PROMOCIONADOS/REGULARES/RECURSANTES con su conteo, y por comisión una barra
"COMISION N - TUTOR {NOMBRE}" (merge desde la columna `C` hasta la última columna) seguida
de una tabla con **exactamente** las columnas
`Nombre y Apellido | Email | Parcial 1 | Parcial 2 | Global TPI | Estado Alumno | Nota Final`
(los `Parcial n` derivados de los exámenes PARCIAL configurados, `Global TPI` del examen
GLOBAL, y `Nota Final` como **última** columna inmediatamente después de `Estado Alumno`),
**sin columnas de TPs** y **sin gráfico de dona**, usando los helpers de `excel_estilos.py`.
La columna `Nota Final` es una **adición deliberada** más allá del modelo decodificado (que
tiene 6 columnas terminando en `Estado Alumno`): el usuario la pidió explícitamente como
7ª columna. Con 2 parciales + 1 global la última columna es `G` (la barra de bloque mergea
`C..G`).

**Validates: Requirements 2.6, 2.8, 2.12, 3.5**

Property 4: Nota Final ponderada con escala normalizada

_For any_ alumno donde TODOS los exámenes PARCIAL y el GLOBAL tienen nota numérica, la
función corregida `calcular_nota_final` SHALL devolver
`NF = (promedio de los N parciales normalizados a 0–10) * 0.4 + (global normalizado a 0–10)
* 0.6`, redondeada con `round_half_up` a entero 0–10; y SHALL devolver `None` (`N/E` en el
reporte) cuando falte cualquier insumo requerido (algún parcial o el global sin nota
numérica, o en modo ESCALA sin valor numérico). La normalización lleva cada `valor_real` a
la escala común (escala 100 → dividir por 10; escala 10 → sin cambio) usando
`detectar_escala(nota_minima)`, de modo que mezclar escalas nunca produce una NF errónea.

**Validates: Requirements 2.11, 2.13**

---

## Layout exacto del modelo CORREGIDO (Ítem Abierto 1 — RESUELTO)

Decodificado con `openpyxl` sobre `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx`
(`data_only=False`). El archivo trae 2 hojas de ejemplo (`Programacion 1` y
`Programacion 3`) y **ambas tienen exactamente la misma estructura de 6 columnas, SIN
columnas de TPs**. **Una hoja por materia** (nombre de hoja = nombre de la materia,
saneado con `excel_estilos.sheet_title`). Nuestra corrida es por materia → el workbook
tiene UNA hoja.

> **Corrección respecto del decode anterior:** el modelo viejo mostraba en "Programacion 3"
> columnas `TP 1 … TP 10` (rango `A1:P10`). Eso era **incorrecto/desactualizado**. En el
> modelo CORREGIDO, "Programacion 3" tiene rango `A1:F10` — las mismas 6 columnas que
> "Programacion 1". **No existen columnas de TPs.**

**Estructura por hoja (filas 1-based), verificada contra el archivo CORREGIDO:**

| Fila | Contenido | Detalle exacto del archivo |
|------|-----------|----------------------------|
| R1 | `TOTAL MATERIA {NOMBRE}` | merge `A1:B1`, en mayúsculas (ej. `TOTAL MATERIA PROGRAMACION 1`) |
| R2 | `PROMOCIONADOS` \| `{n}` | A2=etiqueta, B2=conteo (ej. `3`) |
| R3 | `REGULARES` \| `{n}` | A3=etiqueta, B3=conteo |
| R4 | `RECURSANTES` \| `{n}` | A4=etiqueta, B4=conteo |
| R5 | (vacía) | separador |
| R6 | Barra de bloque: `COMISION N - TUTOR {NOMBRE}` | merge **`C6:G6`** (empieza en col **C**, NO en A; llega hasta la última columna = `Nota Final`) |
| R7 | Encabezados de columna | las 6 columnas del modelo + `Nota Final` (ver abajo) |
| R8+ | Filas de alumnos | una por alumno, ordenadas por apellido/nombre |
| (vacía) | separador entre bloques | |
| … | siguiente bloque comisión (barra `C{f}:G{f}` + headers + datos) | ej. `C12:G12`, `C18:G18` |

**Encabezados (fila de header de cada bloque) — las 6 columnas del modelo CORREGIDO MÁS la
columna adicional `Nota Final` (7ª, agregada por pedido del usuario):**

```
A: Nombre y Apellido | B: Email | C: Parcial 1 | D: Parcial 2 | E: Global TPI | F: Estado Alumno | G: Nota Final
```

> **Nota (adición deliberada):** el modelo decodificado tiene **6 columnas** que terminan en
> `Estado Alumno` (`A..F`). La columna **`Nota Final`** NO está en el modelo; se agrega como
> **última** columna (7ª) por pedido explícito del usuario, inmediatamente después de
> `Estado Alumno`. Con N parciales la última columna corre en consecuencia (2 parciales →
> `G`); la barra de bloque mergea desde `C` hasta esa última columna.

Las columnas de exámenes se **derivan de la config de la materia**: una columna `Parcial n`
por cada examen `tipo == PARCIAL` (numerado por `orden`) y una columna `Global TPI` para el
examen `tipo == GLOBAL`. En los dos ejemplos del modelo hay 2 parciales + 1 global → las
columnas centrales `Parcial 1 | Parcial 2 | Global TPI` (más `Nombre y Apellido` y `Email`
al inicio, `Estado Alumno` y luego `Nota Final` al final). Si una materia tuviera otro
número de parciales, la cantidad de columnas `Parcial n` acompaña; el resto de la estructura
es idéntica y `Nota Final` sigue siendo siempre la última columna.

**Valores observados en las celdas (verificados):**

- Columnas `Parcial n`: valor **numérico** (`60.0`, `80.0`, `70.0`, `100.0`, `50.0`,
  `40.0`, `20.0`) o `N/E` si el alumno no rindió. Son valores en **escala 100** (el `real`
  del ítem, que en escala 100 coincide con el porcentaje).
- Columna `Global TPI`: **numérico** (`9.0` en los ejemplos) sólo para los alumnos que
  PROMOCIONAN; `N/E` para REGULARIZA y RECURSA. → Es el **resultado/nota del examen
  GLOBAL** (ver Ítem Abierto — Global TPI resuelto abajo).
- Columna `Estado Alumno`: `PROMOCIONA` / `REGULARIZA` / `RECURSA` (coincide con
  `EstadoCierreEnum.value`).
- Columna `Nota Final` (adición, NO presente en el modelo decodificado): **entero 0–10** o
  `N/E`. Es la NF ponderada calculada por `calcular_nota_final` sobre valores normalizados a
  0–10 (ver sección "Nota Final"). `N/E` cuando falta algún parcial o el global con nota
  numérica.
- Nota sobre la barra de bloque: en el modelo "Programacion 1" el texto es
  `COMISION 1 - TUTOR MATIAS SANTIAGO TORRES` y en "Programacion 3" es
  `COMISION 7 - JUAN SARMIENTO` (sin la palabra "TUTOR"). Se conserva el patrón actual
  `"{comision} — Tutor: {tutor}"` del generador salvo indicación contraria; lo esencial y
  verificado es que la barra **arranca en la columna C** y mergea `C..F`.

**Semántica de `Global TPI` (confirmación resuelta):** `Global TPI` es la **nota/resultado
del examen configurado como `tipo == GLOBAL`** (no una nota final compuesta ni un promedio).
Es numérico cuando el alumno rindió/aprobó el global (por eso `9.0` aparece en los
promocionados, que necesitan el global para promocionar) y `N/E` cuando no lo rindió/aprobó.
Esto es consistente con la regla de clasificación: el GLOBAL es obligatorio para PROMOCIONA
y opcional para REGULARIZA, de ahí que sólo los promocionados muestren valor numérico en los
ejemplos. Se puebla desde `global_valor` (el mejor `valor_real` del examen GLOBAL con rescate
aplicado). Si más adelante el archivo real mostrara otra semántica, se re-documenta; con el
CORREGIDO decodificado, la lectura es "nota del examen global".

**Diferencias con el generador actual (`excel_cierre_cursada.py`) a corregir:**
el actual usa columnas fijas `TPs Aprobados / Autoeval OK / Parcial 1 / Parcial 2 / TPI /
Nota Final / Estado Alumno / Habilitado para Final` y agrega una **dona** en el resumen.
El modelo corregido **no tiene columnas de TPs**, **no tiene gráfico de dona** (`CHARTS: 0`
en ambas hojas) y usa el resumen simple de 3 conteos (`PROMOCIONADOS/REGULARES/RECURSANTES`
en A2:B4). → Se reescriben las columnas a las 6 del modelo (derivando `Parcial n`/`Global
TPI` de la config) **más la columna `Nota Final` al final**, se eliminan las columnas
TP/Autoeval/TPI/Habilitado, y se elimina la dona del cierre (los estilos de
banda/bloque/header/zebra se conservan). La columna `Nota Final` **se conserva pero se
recalcula bien**: hoy el generador la computa sólo para promotores y con un enfoque
hardcodeado; con el fix se calcula para TODOS los alumnos con la fórmula ponderada oficial y
escala normalizada (`calcular_nota_final`), o `N/E` si falta un insumo. La barra de bloque
debe mergear desde la columna **C** (no desde A), a diferencia del helper `barra_bloque`
estándar que arranca en la columna 1 → se parametriza la columna inicial o se mergea `C..G`
de forma explícita (hasta la última columna, `Nota Final`) reutilizando los estilos
(`FILL_BLOQUE`, `FONT_BLOQUE`).

---

## Detección de escala y algoritmo de clasificación (Ítem Abierto 2 — RESUELTO)

### Detección de escala (función pura)

Se detecta la escala desde la **magnitud de `nota_minima`** (config-driven, sin llamadas
extra a Moodle → mantiene la función PURA y testeable). Es el enfoque más robusto porque
`nota_minima` la carga el coordinador en la MISMA escala en la que califica, y el export
dual ya entrega tanto `real` (nota en la escala propia del ítem) como `percentage`.

```
FUNCTION detectar_escala(nota_minima)
  INPUT: nota_minima of type float | None
  OUTPUT: 100 | 10 | None

  IF nota_minima IS None THEN
    RETURN None            # examen en modo ESCALA (Aprobado/Desaprobado): sin escala numérica
  END IF
  RETURN 100 IF nota_minima >= 10 ELSE 10
END FUNCTION

FUNCTION banda_regular(nota_minima)
  escala := detectar_escala(nota_minima)
  IF escala IS None THEN RETURN None          # ESCALA: no hay banda numérica
  RETURN 20 IF escala == 100 ELSE 2
END FUNCTION
```

**Casos borde documentados:**
- `nota_minima == 6` → escala 10 → banda 2. `nota_minima == 60` → escala 100 → banda 20.
- **Frontera en 10**: `nota_minima >= 10` se clasifica como escala 100. Un mínimo de 10 es
  ambiguo (10/10 exigido en escala 10 vs. mínimo bajo en escala 100). Los valores reales
  esperados son 6 (escala 10) y 60 (escala 100), lejos de la frontera. Se documenta el
  corte en 10 y se recomienda validar en el dashboard que `nota_minima` sea coherente con
  la escala del ítem de Moodle.
- **Mínimos distintos de 60/6** (p. ej. 50 o 7): funcionan igual — la banda es siempre 20
  (escala 100) o 2 (escala 10), no depende del valor exacto del mínimo, sólo de su escala.
- **Modo ESCALA** (`nota_minima IS None`): sin banda; el examen se evalúa por su resultado
  de escala (Aprobado/Desaprobado) tanto para promoción como para regular.

**Coherencia de escalas en la comparación:** `examen_mapper` ya compara el valor `real`
del ítem contra `nota_minima` (misma escala del ítem). Por eso la clasificación reutiliza
`real` como valor obtenido y compara contra `nota_minima` y contra `(nota_minima − banda)`
en esa misma escala. En escala 100, `real == percentage`, lo que coincide con los valores
del modelo.

### Algoritmo de clasificación (función pura)

Reemplaza a `cierre_cursada_calculo.calcular_estado`. Recibe la lista de resultados de los
**exámenes principales** del alumno (ya con rescate aplicado por
`examen_mapper.calcular_resultados_examenes`, extendido para además exponer el mejor valor
numérico `real` entre la instancia base y sus rescates).

```
# Entrada por examen principal (PARCIAL | GLOBAL):
#   { examen_id, tipo, modo_aprobacion, nota_minima,
#     valor_real,          # mejor 'real' numérico entre base + rescates (None si ausente / ESCALA)
#     resultado_escala }   # 'aprobado' | 'desaprobado' | 'ausente' (rescate aplicado)

FUNCTION cumple_minimo(examen)
  IF examen.modo_aprobacion == 'ESCALA' THEN
    RETURN examen.resultado_escala == 'aprobado'
  END IF
  RETURN examen.valor_real IS NOT None AND examen.valor_real >= examen.nota_minima
END FUNCTION

FUNCTION cumple_banda(examen)
  # Para Regular en exámenes NO globales.
  IF examen.modo_aprobacion == 'ESCALA' THEN
    RETURN examen.resultado_escala == 'aprobado'   # ESCALA no tiene banda: exige aprobado
  END IF
  banda := banda_regular(examen.nota_minima)
  RETURN examen.valor_real IS NOT None AND examen.valor_real >= (examen.nota_minima - banda)
END FUNCTION

FUNCTION calcular_estado_cierre(examenes)
  INPUT: examenes = lista de exámenes principales del alumno (PARCIAL/GLOBAL)
  OUTPUT: { estado, examenes_resultado, global_valor }

  IF LENGTH(examenes) == 0 THEN
    # Guard: sin exámenes principales no se puede clasificar (lo maneja el service → HTTP 400)
    RAISE SinExamenesConfigurados
  END IF

  no_globales := [e FOR e IN examenes IF e.tipo != 'GLOBAL']
  globales    := [e FOR e IN examenes IF e.tipo == 'GLOBAL']

  promociona := ALL(cumple_minimo(e) FOR e IN examenes)          # incluye GLOBAL

  regulariza := (NOT promociona)
                AND ALL(cumple_banda(e) FOR e IN no_globales)     # GLOBAL opcional

  IF promociona THEN estado := 'PROMOCIONA'
  ELSE IF regulariza THEN estado := 'REGULARIZA'
  ELSE estado := 'RECURSA'

  RETURN { estado, ... }
END FUNCTION
```

**Notas de diseño del algoritmo:**
- **Rescate preservado** (bugfix 3.1): `valor_real` y `resultado_escala` ya vienen con la
  cadena de rescate resuelta por `examen_mapper` (aprobado > sin_corregir > desaprobado >
  ausente para la escala; máximo `real` para el numérico).
- **GLOBAL** (bugfix 2.2): obligatorio para PROMOCIONA (entra en `promociona`), excluido de
  REGULARIZA (`no_globales`).
- **ESCALA** (bugfix 3.2): sin banda; `cumple_minimo == cumple_banda == (resultado ==
  'aprobado')`.
- Sin GLOBAL configurado: `globales == []` → promoción exige mínimo en todos los parciales;
  regular exige banda en todos los parciales.

### Nota Final — cálculo ponderado con escala normalizada (nuevo)

La **Nota Final** es un promedio ponderado por alumno:
`NF = (promedio de los N exámenes PARCIAL) * 0.4 + (nota del examen GLOBAL) * 0.6`. El caso
"2 parciales + 1 global" es simplemente N=2: `NF = [(P1 + P2)/2] * 0.4 + Global * 0.6`.

**Problema de escalas mixtas (crítico).** Los parciales suelen estar en **escala 100**
(p. ej. 60/80/100) y el global en **escala 10** (p. ej. 9.0). Aplicar la fórmula sobre los
`valor_real` crudos mezclando escalas da un resultado sin sentido (p. ej. `(80+60)/2*0.4 +
9*0.6 = 28 + 5.4 = 33.4`, que no es una nota interpretable). Por eso, **antes** de aplicar
los pesos se **normaliza cada examen a una escala común**. Se elige **0–10** como escala de
salida porque:
- coincide con la columna `CierreCursadaAlumno.nota_final` ya existente (`Integer`, 0–10),
- coincide con el comportamiento legacy (`round_half_up(nf / 10)` en la función vieja),
- es la escala natural de la nota de cátedra.

```
FUNCTION normalizar_a_10(valor_real, nota_minima)
  INPUT: valor_real: float | None ; nota_minima: float | None
  OUTPUT: float | None      # valor en escala 0–10, o None si no hay valor numérico

  IF valor_real IS None THEN RETURN None
  escala := detectar_escala(nota_minima)          # 100 | 10 | None
  IF escala == 100 THEN RETURN valor_real / 10     # 80 → 8.0, 100 → 10.0
  RETURN valor_real                                # escala 10 (o None/ESCALA) → sin cambio
END FUNCTION

FUNCTION calcular_nota_final(examenes)
  INPUT: examenes = lista de exámenes principales del alumno (PARCIAL/GLOBAL),
         mismos insumos que calcular_estado_cierre
         (tipo, modo_aprobacion, nota_minima, valor_real)
  OUTPUT: int (0–10) | None      # None = 'N/E'

  parciales := [e FOR e IN examenes IF e.tipo == 'PARCIAL']
  globales  := [e FOR e IN examenes IF e.tipo == 'GLOBAL']

  # Requisito 2.13: NF sólo si TODOS los parciales y el global tienen nota numérica.
  IF LENGTH(parciales) == 0 OR LENGTH(globales) != 1 THEN RETURN None

  parciales_norm := [normalizar_a_10(e.valor_real, e.nota_minima) FOR e IN parciales]
  global_norm    := normalizar_a_10(globales[0].valor_real, globales[0].nota_minima)

  # Si algún insumo requerido falta (ausente, o ESCALA sin valor numérico) → N/E.
  IF ANY(v IS None FOR v IN parciales_norm) OR global_norm IS None THEN RETURN None

  promedio_parciales := SUM(parciales_norm) / LENGTH(parciales_norm)
  nf := promedio_parciales * 0.4 + global_norm * 0.6
  RETURN round_half_up(nf)          # entero 0–10
END FUNCTION
```

**Notas de diseño de la NF:**
- **Insumo faltante → `N/E`** (bugfix 2.13): si el alumno no rindió el global, o algún
  parcial no tiene nota numérica (ausente o examen en modo **ESCALA** sin valor numérico),
  la NF es `None` → `N/E`. No se computa una NF parcial.
- **Reutiliza `valor_real`**: la función toma exactamente los mismos insumos por examen que
  `calcular_estado_cierre` (`valor_real` ya con rescate aplicado por `examen_mapper`, el
  mejor valor numérico entre base y rescates), de modo que la NF respeta las cadenas de
  rescate igual que la clasificación.
- **Salida entero 0–10** con `round_half_up` (se reutiliza el helper existente), consistente
  con la columna `nota_final` y con el legacy.
- **Integración**: `calcular_estado_cierre` devuelve también `nota_final` (llamando a
  `calcular_nota_final` con la misma lista de exámenes) o se llama en paralelo desde el
  service; el service persiste el valor en `CierreCursadaAlumno.nota_final` (nullable =
  `N/E`).

> **Flag para confirmar (escala de salida):** se asume **entero 0–10** (redondeado) para la
> Nota Final, por consistencia con la columna existente y el legacy. Si el negocio prefiere
> otra representación (p. ej. **un decimal**, o mantener **escala 0–100**), debe confirmarse
> antes de implementar: cambiaría el tipo de la columna (`Integer` → `Numeric`) y el formato
> de celda. El resto del diseño (normalización + fórmula) no cambia.

---

## Destino de `CierreCursadaItem` (Ítem Abierto 3 — RESUELTO)

**Decisión: eliminar `CierreCursadaItem` y todo el mapeo manual.** `ExamenMateria` ya
guarda `moodle_cmid` por examen, así que el vínculo ítem-de-Moodle → examen ya existe en la
config del dashboard. El mapeo manual es redundante y es la causa raíz #2.

**Cambios de modelo de datos:**

1. **`CierreCursadaItem`**: se elimina el modelo y la tabla `cierre_cursada_items`
   (migración `drop_table`). Se elimina `CategoriaItemCierreEnum` de los usos del cierre
   (queda el enum si algún otro módulo lo referencia — verificar en la tarea de
   implementación; hoy sólo lo usa el cierre).

2. **`CierreCursadaRun`**: se conserva (histórico append-only, bugfix 3.4). Se
   **deprecan** los campos del modelo viejo:
   - `umbral_tp_pct` y `reglas_snapshot` dejan de tener sentido (ya no hay umbrales
     fijos). Migración: hacerlos **nullable** y dejar de escribirlos (no se borran para no
     romper la lectura de corridas históricas). Alternativamente, `reglas_snapshot` puede
     reutilizarse para congelar un **snapshot de la config de exámenes** usada en la
     corrida (recomendado, mejora la reproducibilidad histórica). Se recomienda la opción
     "snapshot de config": renombrar conceptualmente a `examenes_snapshot` (nueva columna
     JSONB nullable) y dejar `umbral_tp_pct`/`reglas_snapshot` nullable como legacy.

3. **`CierreCursadaAlumno`**: el shape fijo (`tp_ok`, `autoeval_ok`, `p1_max`, `p2_max`,
   `tpi_max`, `parcial1_instancias`, `parcial2_instancias`, `tpi_instancias`,
   `habilitado_final`) ya no representa el resultado por-examen dinámico. Cambios:
   - **Agregar** `resultados_examenes` (JSONB nullable): lista por examen principal
     `[{examen_id, etiqueta, tipo, modo, valor_real, resultado_escala, cumple_minimo,
     cumple_banda, rescatado}]` — auditoría dirigida por config.
   - **Agregar** `global_valor` (Float nullable): valor de la columna `Global TPI` (nota
     del examen GLOBAL con rescate; `None` → `N/E`).
   - **NO se agrega** ninguna columna de TPs: el modelo corregido no tiene columnas TP y
     `ExamenMateria` no modela TPs, así que no hay `tps_display` ni detección de ítems TP.
   - **Conservar** `estado`, `nombre`, `apellido`, `email`, `comision_id`,
     `comision_nombre`, `tutor_nombre`.
   - **Reutilizar** `nota_final` (`Integer` nullable, 0–10) para la **Nota Final** ponderada
     nueva (`calcular_nota_final`). Cambia su semántica: antes se llenaba sólo para
     PROMOCIONA con un cálculo hardcodeado; ahora se llena para TODOS los alumnos con la
     fórmula oficial y escala normalizada, y queda `None` (`N/E`) sólo cuando falta un insumo
     requerido (no por estado). No requiere cambio de tipo (sigue `Integer` 0–10), salvo que
     se confirme otra escala de salida (ver flag en la sección Nota Final).
   - **Deprecar** (nullable, legacy, dejar de escribir): `tp_ok`, `autoeval_ok`, `p1_max`,
     `p2_max`, `tpi_max`, `parcial{1,2}_instancias`, `tpi_instancias`, `habilitado_final`.

**Implicancias de migración** (Alembic, `backend/alembic/versions/`):
- `drop_table('cierre_cursada_items')` (+ drop del tipo `categoriaitemcierreenum` si no lo
  usa nadie más).
- `alter_column` a nullable en `cierre_cursada_runs.umbral_tp_pct` y `.reglas_snapshot`;
  `add_column` `examenes_snapshot` JSONB nullable.
- `alter_column` a nullable en las columnas legacy de `cierre_cursada_alumnos`;
  `add_column` `resultados_examenes` (JSONB nullable) y `global_valor` (Float nullable).
  (No se agrega ninguna columna de TPs.)
- Las corridas viejas quedan legibles pero su Excel regenerado usará el layout nuevo (no
  reproducirá 1:1 la data vieja porque el shape cambió). Se documenta como aceptable
  (append-only: las corridas viejas siguen existiendo como registro; la regeneración de
  Excel de corridas pre-fix es best-effort). **Flag**: confirmar si se requiere
  compatibilidad de regeneración para corridas históricas.

**Cambios de contrato de API (router):**
- Se **eliminan** `GET /cierre-cursada/materias/{materia_id}/items` y
  `POST /cierre-cursada/materias/{materia_id}/items` (mapeo manual).
- `POST /cierre-cursada/materias/{materia_id}/generar`: `GenerarCierreRequest` pierde
  `umbral_tp_pct` y `reglas` (obsoletos). Queda `cuatrimestre_id`. Si se confirma que las
  columnas TP influyen, se podría reincorporar un parámetro — por ahora NO.
- `GET /runs/{run_id}/excel` y `GET /materias/{materia_id}/historial`: sin cambios de
  contrato.
- **Impacto frontend (HAY regresión — corregir)**: existe una pantalla **"Cierre de
  cursada"** en la ruta `/cierre-cursada`, implementada en
  `frontend/src/features/cierre-cursada/`, que hoy consume **exactamente** los
  endpoints/campos que este fix elimina (los `/items` de mapeo manual y el `umbral_tp_pct`
  del `generar`). Por lo tanto **este fix SÍ produce regresiones de frontend** que deben
  resolverse en la misma entrega. El detalle concreto de las ediciones está en la sección
  **"Impacto frontend — cambios concretos"** más abajo.

### Impacto frontend — cambios concretos

La feature `frontend/src/features/cierre-cursada/` está acoplada 1:1 al sistema viejo
(mapeo manual de ítems + umbral de TPs). Al eliminar `CierreCursadaItem`, los endpoints
`/items` y el `umbral_tp_pct`/`reglas` del contrato, el frontend deja de compilar/funcionar
si no se actualiza. Ediciones requeridas (manteniendo **TypeScript strict** y la estructura
de feature-folder, AGENTS.md):

1. **`components/ItemsMappingEditor.tsx` — ELIMINAR el componente completo.** Toda la UI de
   mapeo manual (categorías TP/AUTOEVAL/PARCIAL_1/PARCIAL_2/TPI/IGNORAR, conteos por
   categoría, confirmación de ítems) queda obsoleta porque el mapeo ya no existe: la fuente
   de verdad es `ExamenMateria`. Se borra el archivo.

2. **`pages/CierreCursadaPage.tsx` — quitar el paso de mapeo y el umbral.**
   - Eliminar el render de `<ItemsMappingEditor />` y su import, la sección "Mapeo de ítems
     del calificador" y sus estados de carga/error (`itemsQuery.isLoading`,
     `itemsQuery.error`, `itemsQuery.data`) → se elimina el uso de `useCierreItems`.
   - Eliminar el input **"% mínimo de TPs aprobados"**, el estado `umbralTp`/`setUmbralTp` y
     la validación `umbralValido`.
   - `handleGenerar` ahora envía **sólo** `{ cuatrimestre_id }`:
     `generar.mutateAsync({ cuatrimestre_id: cuatrimestreId })` y luego
     `descargarExcel(run.id)`.
   - **Conservar** los selectores de **materia + cuatrimestre** (el backend `generar` sigue
     requiriendo `cuatrimestre_id`) y la tabla de **historial** (`useHistorialCierre`).
   - Actualizar el docstring de la pantalla para reflejar el nuevo flujo (ya no hay
     revisión de mapeo).

3. **`services/cierre-cursada.service.ts`** — eliminar `getItems()` y `confirmarMapping()`
   (llaman a los endpoints `/items` borrados) y sus imports de tipos
   (`CierreItemConfirmado`, `CierreItemSugerido`). Ajustar `generar()` para recibir el
   `GenerarCierreInput` nuevo (sin `umbral_tp_pct`/`reglas`). **Conservar** `generar`,
   `descargarExcel` y `getHistorial`.

4. **`hooks/useCierreCursada.ts`** — eliminar `useCierreItems` y `useConfirmarMapping`, la
   query key `items` de `cierreCursadaKeys`, y el import de `CierreItemConfirmado`.
   **Conservar** `useGenerarCierre` y `useHistorialCierre` (este último sigue usando la key
   `historial`).

5. **`components/HistorialRunsTable.tsx`** — eliminar la columna **"Umbral TP"** (`<th>` y
   la celda `{r.umbral_tp_pct}%`), ya que `umbral_tp_pct` desaparece de `CierreRun`. El
   resto de la tabla (Generado / Promociona / Regulariza / Recursa / Total + descarga de
   Excel) se conserva.

6. **`types/index.ts`** — alinear los tipos al contrato nuevo:
   - Eliminar `CategoriaItemCierre`, `CierreItemSugerido`, `CierreItemConfirmado` y
     `ReglasCierreOverride` (todo el vocabulario del mapeo manual).
   - `GenerarCierreInput` pasa a ser `{ cuatrimestre_id: number }` (sin `umbral_tp_pct` ni
     `reglas`).
   - `CierreRun`: eliminar `umbral_tp_pct`. **Conservar** `EstadoCierre`
     (`PROMOCIONA | REGULARIZA | RECURSA`) y el resto de campos de `CierreRun`.

**Sobre la vista de resultados por alumno / Nota Final:** hoy la pantalla NO renderiza una
tabla de resultados por alumno — sólo permite elegir materia + cuatrimestre, (antes)
revisar el mapeo, ver el historial y **descargar el Excel**. La vista de resultados real es
el propio `.xlsx` (que ya incluye las columnas nuevas del modelo corregido + `Nota Final`,
ver Property 3/4). Por eso el frontend no necesita agregar columnas de resultados: alcanza
con quitar el mapeo/umbral y mantener el flujo de generación + descarga. Si en el futuro se
agregara una vista in-app de resultados, debería reflejar las columnas nuevas
(`Parcial n | Global TPI | Estado Alumno | Nota Final`).

**Flujo resultante de la pantalla** (tras quitar el paso de mapeo): elegir **materia +
cuatrimestre** → clic en **"Generar cierre y descargar Excel"** → descarga del `.xlsx`. La
UI de mapeo/umbral y sus estados de carga/error se eliminan; el historial de corridas se
mantiene debajo.

---

## Fix Implementation

### Componentes a cambiar

**1. `backend/app/services/cierre_cursada_calculo.py`** (clasificación + NF, PURA)
- Reemplazar `calcular_estado` por `calcular_estado_cierre` (algoritmo de arriba).
- Agregar `detectar_escala(nota_minima)` y `banda_regular(nota_minima)`.
- Agregar `normalizar_a_10(valor_real, nota_minima)` y `calcular_nota_final(examenes)`
  (sección "Nota Final"). `calcular_estado_cierre` devuelve además `nota_final` llamando a
  `calcular_nota_final` con la misma lista de exámenes (o el service la llama en paralelo con
  los mismos insumos).
- Eliminar `sugerir_categoria`, las regex de mapeo, `tp_ok`, `autoeval_ok`, las constantes
  `CATEGORIA_*` y `_UNIDADES_OPCIONALES_DEFAULT` (pertenecen al sistema viejo).
- Conservar `round_half_up` (lo reutiliza `calcular_nota_final`); conservar `max_o_none` si
  aplica.
- Mantener el módulo SIN I/O.

**2. `backend/app/services/examen_mapper.py`** (rescate + valor numérico)
- Extender `calcular_resultados_examenes` para que cada resultado principal incluya
  también el **mejor `valor_real`** numérico entre la instancia base y sus rescates
  (además de `resultado` de escala), necesario para `cumple_minimo`/`cumple_banda`.
- No romper firmas existentes usadas por el dashboard de gestores (agregar campo, no
  quitar). Preservar precedencia de rescate y `interpretar_resultado` (bugfix 3.1, 3.2).

**3. `backend/app/services/cierre_cursada_service.py`** (orquestación)
- `generar(materia_id, cuatrimestre_id, usuario)`: quitar `umbral_tp_pct`/`reglas_override`
  y toda la lógica de `CierreCursadaItem`/`por_categoria`/guards de mapeo.
- Cargar `ExamenMateria` de la materia vía `ExamenRepository.get_by_materia`.
- Guard nuevo: si la materia no tiene exámenes PARCIAL/GLOBAL → `HTTPException(400,
  "La materia no tiene exámenes configurados en el dashboard")`.
- Reusar la descarga masiva actual (WS + sesión + `parsear_export_calificador_dual`) y,
  para exámenes cuya fuente es `assign`, opcionalmente el grade estructural
  (`clasificar_grade_estructural`) — igual que el snapshot.
- Armar la config por examen (`{id, tipo, moodle_cmid, modo_aprobacion, nota_minima,
  recupera_examen_id, orden}`) y llamar a `examen_mapper.calcular_resultados_examenes`
  para resolver rescates + valores, luego `calcular_estado_cierre` por alumno.
- **No hay detección de columnas TP**: el modelo corregido no tiene columnas de TPs y
  `ExamenMateria` no los modela; sólo se procesan los exámenes PARCIAL/GLOBAL configurados.
- Conservar `_resolver_comision` 1:1 (bugfix 3.3, 3.6) y la persistencia append-only
  (bugfix 3.4). Poblar los nuevos campos de `CierreCursadaAlumno`, incluida la **Nota Final**
  en la columna reutilizada `nota_final` (resultado de `calcular_nota_final`, o `None` =
  `N/E`).
- Eliminar los métodos `obtener_items_calificador` / `confirmar_mapping`.
- Registrar actividad `CIERRE_CURSADA_GENERADO` igual que hoy.
- Vigilar el límite de **500 LOC**: si el service crece, extraer el armado de config de
  examen a un helper.

**4. `backend/app/services/excel_cierre_cursada.py`** (Excel = modelo corregido + Nota Final)
- Reescribir para el layout del modelo CORREGIDO (arriba): título `TOTAL MATERIA {NOMBRE}`
  (merge `A1:B1`), resumen de 3 filas `PROMOCIONADOS/REGULARES/RECURSANTES` con conteo (SIN
  dona), y por comisión barra `COMISION N - TUTOR {NOMBRE}` (merge desde la columna **C**
  hasta la última) + tabla con las 6 columnas del modelo **más `Nota Final` al final**:
  `Nombre y Apellido | Email | Parcial n… | Global TPI | Estado Alumno | Nota Final`. **Sin
  columnas de TPs.**
- Eliminar del generador las columnas `TPs Aprobados / Autoeval OK / TPI / Habilitado para
  Final` y la dona. **Conservar** la columna `Nota Final` pero moverla al **final** (después
  de `Estado Alumno`) y poblarla desde `a.nota_final` para TODOS los alumnos (no sólo
  promotores).
- Reusar `banda_titulo`, `celda_header`, `fila_datos`, `sheet_title`, `sanitize_filename`,
  paleta/bordes de `excel_estilos.py` (bugfix 3.5). Para la barra de bloque, reutilizar
  `FILL_BLOQUE`/`FONT_BLOQUE` mergeando desde la columna **C** hasta la última columna
  (`Nota Final`; con 2 parciales → `C..G`) — el modelo arranca la barra en C, no en A →
  parametrizar `barra_bloque` con columna inicial o mergear `C..{última}` explícito.
- Los encabezados de examen se derivan de la config de la corrida: una columna `Parcial n`
  por cada PARCIAL (numerado por `orden`) y `Global TPI` para el GLOBAL (etiquetas vía
  `examen_mapper.etiqueta_examen` / derivadas del `tipo`+`orden`). `Estado Alumno` y luego
  `Nota Final` cierran la tabla.
- Formato de celdas: `Parcial n` = numérico o `N/E`; `Global TPI` = `global_valor` numérico
  o `N/E`; `Estado Alumno` = `PROMOCIONA/REGULARIZA/RECURSA`; `Nota Final` = entero 0–10
  (`a.nota_final`) o `N/E` cuando es `None` (reutilizar el helper `_fmt_nota_final` actual).
- Actualizar los anchos de columna: mantener 26 para `Nombre y Apellido`/`Email`, ~16 para
  las columnas centrales y `Nota Final`; el ancho itera sobre el nuevo total de columnas
  (`len(HEADERS)` = 6 fijas + parciales dinámicos + `Nota Final`).
- Resaltar en rojo las filas `RECURSA` (se conserva el criterio visual actual; ojo: el
  índice de la columna `Estado Alumno` ya no es el último — `Nota Final` es la última).

**5. `backend/app/models/cierre_cursada.py`** + **`app/schemas/cierre_cursada.py`**
- Eliminar `CierreCursadaItem`; ajustar columnas de `CierreCursadaRun`/`CierreCursadaAlumno`
  (ver Ítem Abierto 3). Actualizar schemas: quitar `CierreItem*`, `CierreMapping*`,
  `umbral_tp_pct`/`reglas` de `GenerarCierreRequest`.

**6. `backend/app/repositories/cierre_cursada_repository.py`**
- Eliminar `get_mapping` / `upsert_mapping`. Conservar `crear_run` / `get_run` /
  `listar_runs` / `get_alumnos_de_run` (acceso a BD desde el service sólo vía repo —
  AGENTS.md).

**7. `backend/app/routers/cierre_cursada.py`**
- Eliminar endpoints de `/items`; ajustar `generar` a la nueva firma (sin umbral). Sin
  lógica de negocio en el router (AGENTS.md). Conservar códigos HTTP: 404 (no encontrado),
  400 (validación), 424 (sin credenciales Moodle), 502 (error Moodle/gateway).

**8. Migración Alembic** — ver "Implicancias de migración".

**9. Frontend `frontend/src/features/cierre-cursada/`** (alinear la pantalla al contrato
nuevo — ver "Impacto frontend — cambios concretos" en el Ítem Abierto 3)
- Eliminar `components/ItemsMappingEditor.tsx` (UI de mapeo manual, obsoleta).
- `pages/CierreCursadaPage.tsx`: quitar el paso de mapeo (`useCierreItems` +
  `<ItemsMappingEditor />`) y el input "% mínimo de TPs" (`umbralTp`/`umbralValido`);
  `handleGenerar` envía sólo `{ cuatrimestre_id }`. Conservar selectores materia+cuatrimestre
  e historial.
- `services/cierre-cursada.service.ts`: eliminar `getItems`/`confirmarMapping`; `generar`
  con `GenerarCierreInput` nuevo. Conservar `descargarExcel`/`getHistorial`.
- `hooks/useCierreCursada.ts`: eliminar `useCierreItems`/`useConfirmarMapping` y la key
  `items`. Conservar `useGenerarCierre`/`useHistorialCierre`.
- `components/HistorialRunsTable.tsx`: eliminar la columna "Umbral TP".
- `types/index.ts`: eliminar `CategoriaItemCierre`/`CierreItemSugerido`/
  `CierreItemConfirmado`/`ReglasCierreOverride`; `GenerarCierreInput = { cuatrimestre_id:
  number }`; quitar `umbral_tp_pct` de `CierreRun` (conservar `EstadoCierre`).
- Mantener TypeScript strict y la estructura feature-folder (AGENTS.md).

### Convenciones de error (AGENTS.md)
- Validación de entrada / sin exámenes configurados → `HTTPException(400)`.
- Materia / corrida no encontrada → `HTTPException(404)`.
- Sin credenciales de Moodle → `HTTPException(424)` (patrón actual `_SIN_CREDENCIALES`).
- Error de Moodle (auth/conexión/export inválido) → `HTTPException(424/502)` (patrón
  `MoodleAuthError`/`MoodleConnectionError` actual).

---

## Data Flow

```
ExamenRepository.get_by_materia(materia)          MoodleService (WS + sesión, requests constantes)
        │  config por examen                              │  enrolled + course_contents + export dual
        │  {tipo, cmid, modo, nota_minima, recupera}      │  parsear_export_calificador_dual → {uid:{cmid:{real,percentage}}}
        └──────────────┬───────────────────────────────── ┘  (+ grade estructural para assign)
                       ▼
        examen_mapper.calcular_resultados_examenes(notas_uid, config, estructural)
                       │  resuelve cadenas de rescate + mejor valor_real por principal
                       ▼
        cierre_cursada_calculo.calcular_estado_cierre(examenes_alumno)   ← FUNCIÓN PURA
        (+ calcular_nota_final: normaliza escalas a 0–10 y pondera 40/60)
                       │  {estado, resultados_examenes, global_valor, nota_final}
                       ▼
        CierreCursadaService.generar → CierreCursadaAlumno (+ comisión/tutor) → CierreCursadaRun (append-only)
                       │
                       ▼
        excel_cierre_cursada.generar_excel_cierre(materia, run)  → .xlsx (modelo CORREGIDO + columna Nota Final al final, sin TPs/dona, estilos de la casa)
```

La configuración de examen y las notas de Moodle **convergen** en `examen_mapper`
(rescate + valor) y de ahí a la clasificadora PURA; el Excel sólo dibuja lo ya calculado y
persistido (no recalcula).

---

## Testing Strategy

### Validation Approach

Dos fases: primero exhibir contraejemplos que demuestren el bug sobre el código SIN
arreglar; luego verificar que el fix clasifica bien y preserva el comportamiento no
relacionado. Se prioriza **property-based testing** para la clasificadora PURA
(`calcular_estado_cierre` + `detectar_escala`/`banda_regular`), que es determinística y sin
I/O.

### Exploratory Bug Condition Checking

**Goal**: exhibir contraejemplos ANTES del fix; confirmar o refutar la causa raíz.

**Test Plan**: construir materias con `ExamenMateria` reales y notas conocidas, correr el
cierre actual y observar que clasifica con umbrales fijos / ignora el global / no aplica
banda, y que el Excel no coincide con el modelo.

**Test Cases** (fallan en el código sin arreglar):
1. Parcial `nota_minima=50` (escala 100), alumno con 55 → el actual NO lo aprueba (usa
   fijo 60).
2. Materia con GLOBAL, alumno aprueba parciales y no rinde global → el actual no distingue
   global (debería ser Regular, no Promocionado).
3. Parcial `nota_minima=70` (escala 100), alumno con 55 → banda esperada 50 (55 ≥ 50 →
   Regular); el actual usa fijo 40.
4. Parcial `nota_minima=6` (escala 10), alumno con 4 → banda 2 (4 ≥ 4 → Regular); el
   actual trata 4 como 4 % → Recursa.
5. Excel: comparar hojas/columnas generadas contra el modelo CORREGIDO → no coinciden (el
   actual trae columnas TPs Aprobados/Autoeval OK/TPI/Nota Final/Habilitado + dona, que el
   modelo corregido no tiene).
6. Nota Final: alumno REGULARIZA con parciales y global numéricos → el generador actual deja
   `nota_final = None` (`N/E`) porque sólo la computa para PROMOCIONA; esperado: NF numérica
   por la fórmula ponderada. Y alumno con parciales en escala 100 + global en escala 10 → la
   función vieja (`round_half_up(nf/10)` sobre crudos mezclados) da un valor incorrecto vs.
   la NF con escala normalizada.

**Expected Counterexamples**: veredictos distintos a los esperados por config, un `.xlsx`
con headers/estructura distintos al modelo, y una Nota Final ausente para no-promotores o
mal computada por escalas mixtas. Causas: umbrales fijos, global ausente del cálculo, sin
banda/escala, layout ad-hoc, NF hardcodeada sólo para promotores y sin normalizar escala.

### Fix Checking

**Goal**: para todo input donde vale la bug condition, la función corregida da el
comportamiento esperado.

**Pseudocode:**
```
FOR ALL alumno WHERE isBugCondition(materia_con_examenes, alumno) DO
  resultado := calcular_estado_cierre(examenes_de(alumno))
  ASSERT resultado.estado == veredicto_esperado_por_config(alumno)
END FOR
```

### Preservation Checking

**Goal**: para todo input donde NO vale la bug condition, el resultado es igual al
original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT rescate_original(input)      == rescate_fixed(input)      # examen_mapper
  ASSERT escala_original(input)       == escala_fixed(input)       # interpretar_resultado
  ASSERT comision_original(input)     == comision_fixed(input)     # _resolver_comision
  ASSERT estilos_excel(input)         == estilos_de_la_casa(input) # excel_estilos
END FOR
```

**Testing Approach**: property-based para la clasificadora y para `examen_mapper`
(preservación de rescate/escala). PBT genera muchos casos y cubre bordes que un test manual
no ve.

**Test Cases de preservación**:
1. Cadena de rescate: parcial desaprobado + recuperatorio aprobado → sigue "aprobado"
   (igual que hoy).
2. Examen ESCALA: Aprobado/Desaprobado se sigue evaluando por escala.
3. Resolución de comisión ambigua → "Sin comisión asignada" sin romper la corrida.
4. Estilos: el `.xlsx` sigue usando banda/bloque/header/zebra de `excel_estilos.py`.

### Unit Tests
- `detectar_escala` / `banda_regular`: 6→10/2, 60→100/20, frontera 10, None (ESCALA).
- `calcular_estado_cierre`: Promociona (todos incl. global), Regular (banda, global
  opcional), Recursa; sin global; guard sin exámenes.
- `calcular_nota_final` (Nota Final):
  - **2 parciales + 1 global** en escala común: `P1=8, P2=6, Global=9` (escala 10) →
    `((8+6)/2)*0.4 + 9*0.6 = 2.8 + 5.4 = 8.2 → 8`.
  - **N>2 parciales**: 3 parciales `(8,6,10)` promedio 8 → `8*0.4 + Global*0.6`.
  - **N/E cuando falta el global**: global sin nota numérica → `None`.
  - **N/E cuando falta un parcial**: algún PARCIAL ausente o en modo ESCALA sin valor
    numérico → `None`.
  - **Normalización de escala mixta**: parciales en escala 100 (`P1=80, P2=60`,
    `nota_minima=60`) + global en escala 10 (`Global=9.0`, `nota_minima=6`) → normaliza
    parciales a `8.0, 6.0`, promedio `7.0` → `7.0*0.4 + 9.0*0.6 = 2.8 + 5.4 = 8.2 → 8`
    (verifica que NO se computa sobre crudos, que daría `28+5.4`).
  - **Bordes de redondeo** (`round_half_up`): NF cruda `6.5 → 7`, `6.49 → 6`.
- `excel_cierre_cursada`: las 6 columnas del modelo corregido **más `Nota Final`** en el
  orden exacto
  (`Nombre y Apellido | Email | Parcial 1 | Parcial 2 | Global TPI | Estado Alumno | Nota Final`),
  derivando `Parcial n` de los PARCIAL configurados y `Global TPI` del GLOBAL, con
  `Nota Final` como última columna; resumen de 3 conteos en `A2:B4`; barra de bloque
  mergeando desde la columna C hasta la última (`C..G` con 2 parciales); **sin columnas de
  TPs** y **sin dona**; celda `Nota Final` = entero o `N/E`.

### Property-Based Tests (para la clasificadora PURA)
Generadores: nº de parciales, presencia de global, `modo_aprobacion`, `nota_minima` ∈
{6, 60, y otros}, valores obtenidos, cadenas de rescate. Propiedades:
1. **Monotonía**: si un alumno cumple el mínimo en todos los exámenes (incl. global) →
   siempre PROMOCIONA.
2. **Regular ⊇ banda**: si cumple banda en todos los no-globales y NO promociona →
   REGULARIZA (global irrelevante).
3. **Recursa por defecto**: si algún no-global no cumple banda → RECURSA.
4. **Exactamente en el mínimo**: `valor == nota_minima` → cumple mínimo (`>=`, no `>`).
5. **Exactamente en la banda**: `valor == nota_minima − banda` → cumple banda (bordes
   4 = 6−2 y 40 = 60−20).
6. **Escala 10 vs 100 no se cruzan**: un valor válido en una escala no cambia el veredicto
   por interpretarse en la otra (la escala se fija por `nota_minima`).
7. **Rescate**: aprobar cualquier instancia de rescate ⇒ el principal cuenta como
   cumple_minimo.
8. **Global**: quitar el global nunca cambia el veredicto Regular; agregar un global no
   cumplido nunca permite Promociona.

**Propiedades de la Nota Final** (`calcular_nota_final`):
9. **Rango**: cuando la NF no es `N/E`, siempre cae en `[0, 10]` (con inputs normalizados en
   `[0,10]`, la combinación convexa `0.4·avg + 0.6·g` ∈ `[0,10]`; el redondeo la mantiene en
   el entero 0–10).
10. **`N/E` sii falta insumo**: la NF es `N/E` si y sólo si falta algún parcial o el global
    con nota numérica (o hay 0 parciales / ≠1 global). Si todos los insumos requeridos
    existen, la NF es numérica.
11. **Monotonía**: subir el `valor_real` (normalizado) de cualquier examen requerido nunca
    baja la NF (antes de redondear); es no decreciente en cada insumo.
12. **La escala no se filtra (normalización correcta)**: expresar un mismo examen en escala
    100 (`valor` = v·10, `nota_minima` = 60) o en escala 10 (`valor` = v, `nota_minima` = 6)
    produce la MISMA NF — el valor normalizado no depende de la escala de entrada.

### Integration Tests
- Flujo completo `generar` con un curso mock de Moodle (export dual + config de exámenes) →
  conteos y agrupación por comisión correctos; corrida persistida (append-only).
- `GET /runs/{run_id}/excel` → `.xlsx` con el layout del modelo corregido (6 columnas + la
  columna `Nota Final` como última, sin TPs, sin dona), con la Nota Final poblada para todos
  los alumnos que tengan los insumos y `N/E` para el resto.
- Materia sin exámenes → `HTTPException(400)`. Usuario sin credenciales → `424`.
