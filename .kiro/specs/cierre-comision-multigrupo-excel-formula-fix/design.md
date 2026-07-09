# Cierre — Comisión Multi-grupo + Fórmulas Excel Bugfix Design

## Overview

Este diseño ataca **dos defectos** del **Cierre de Cursada** de Active-IA reportados después de
publicar la spec `cierre-cursada-quiz-recuperables-fix`. Los dos comparten el mismo pipeline
(exploración de Moodle → resolución de comisión → generación del Excel), pero tienen causas raíz
independientes y se resuelven de forma coordinada en una sola spec.

Resumen de la estrategia por bug:

- **Bug 1 (comisión multi-grupo)** — Alumnos que pertenecen a UN grupo de comisión válido
  (`"A25 C2-01"`) MÁS varios grupos que no son de comisión (estado / instancia / regional) caen en
  "Sin comisión asignada". Caso reportado: **TAMARA ROCIO ALBARRACÍN** (comisión real `"A25 C2-01"`,
  grupos `["A25 C2-01", "Extraordinaria_sdo_parcial", "NO_RINDIERON_PARCIAL_1", "No-rindieron-P1",
  "R-Mendoza", "Ultima_INSTANCIA_Examen"]`). La resolución (`_resolver_comision`) aplica el puente
  por `moodle_group_id` a **todos** los grupos del alumno sin distinguir si son de comisión, así que
  un grupo que no es de comisión puede aportar un match espurio de una comisión distinta y disparar
  la regla de ambigüedad. El fix aísla los grupos con formato de comisión ANTES de los puentes y
  generaliza el regex (año = exactamente 2 dígitos). **La causa raíz exacta se CONFIRMA en la fase
  de diagnóstico (observación primero) con los grupos reales de TAMARA antes de codificar.**

- **Bug 2 (fórmulas Excel `#NAME?`)** — Las fórmulas nativas del Excel (columna "Recuperable" por
  fila y los conteos del resumen) se emiten con nombres de función es-AR (`SI`, `CONTAR.SI`, `Y`,
  `VALOR`, `SI.ERROR`) y `;` como separador. openpyxl las persiste VERBATIM en el OOXML, pero el
  formato de archivo `.xlsx` almacena las fórmulas con nombres en INGLÉS y COMA; por eso se muestran
  como `#NAME?` en cualquier locale de apertura. Causa raíz CONFIRMADA. El fix reescribe los dos
  helpers (`_formula_recuperable`, `_formulas_conteo_resumen`) para emitir nombres de función en
  inglés (`IF`, `COUNTIF`, `AND`, `VALUE`, `IFERROR`) con coma, conservando criterios comodín y
  referencias de columna.

Bug 1 toca `gestion_parser.py` (regex) y `cierre_cursada_service.py` (`_resolver_comision`). Bug 2
se concentra en `excel_cierre_cursada.py` (dos helpers puros) y arrastra la actualización de los
tests que asertan la sintaxis es-AR.

## Glossary

- **Bug_Condition (C)**: la condición de entrada que dispara cada defecto (formalizada por bug en
  "Bug Details"). `C1` = Bug 1 (resolución de comisión); `C2` = Bug 2 (fórmula emitida).
- **Property (P)**: el comportamiento correcto esperado para las entradas que cumplen C.
- **Preservation**: el comportamiento existente que NO debe cambiar (ambigüedad genuina, alumnos sin
  grupo de comisión, puente `moodle_group_id`, regionales, estructura del Excel, criterios comodín,
  archivo que abre con openpyxl).
- **`_resolver_comision`**: método estático de `CierreCursadaService`
  (`backend/app/services/cierre_cursada_service.py`) que, dada la lista de grupos de un alumno y las
  comisiones de la materia, devuelve `(comision_id, comision_nombre, tutor_nombre)`.
- **`parse_comision`**: función pura de `backend/app/services/gestion_parser.py` que devuelve el
  nombre de comisión si el grupo matchea el formato `{cohorte}{año} C{semestre}-{NN}`, o `None`.
- **`_COMISION_RE`**: regex de `gestion_parser.py` que reconoce el formato de comisión. Hoy
  `^[MA]\d+\s+C\d+-\d+$`; el fix lo generaliza a año de exactamente 2 dígitos.
- **grupo de comisión**: grupo de Moodle cuyo nombre matchea `{cohorte}{año} C{semestre}-{NN}`
  (cohorte `M`/`A`, año 2 dígitos, `C` + semestre, `-` + NN). Ej. `"A25 C2-01"`.
- **grupo que no es de comisión**: grupo de estado (`"NO_RINDIERON_PARCIAL_1"`), instancia
  (`"Ultima_INSTANCIA_Examen"`, `"Extraordinaria_sdo_parcial"`) o regional (`"R-Mendoza"`) — no debe
  interpretarse como comisión ni aportar match.
- **puente `moodle_group_id`**: bridge primario que matchea un grupo del alumno contra una comisión
  de la BD por el id de grupo de Moodle (`Comision.moodle_group_id`).
- **puente por nombre**: fallback que matchea el nombre de comisión parseado del grupo contra
  `Comision.nombre` (case-insensitive).
- **regla de ambigüedad**: `if len(encontradas) != 1: return None, "Sin comisión asignada", None`.
- **mapa autoritativo `uid → grupos`**: fuente de grupos por alumno construida en la spec previa
  (`cierre-cursada-quiz-recuperables-fix`, Bug 3) con `core_group_get_course_groups` +
  `core_group_get_group_members`; hoy alimenta a `_resolver_comision` la lista COMPLETA de grupos.
- **`_formula_recuperable` / `_formulas_conteo_resumen`**: helpers de
  `backend/app/services/excel_cierre_cursada.py` que arman los strings de fórmula (hoy es-AR).
- **`#NAME?`**: error que Excel/Google Sheets muestran cuando no reconocen el nombre de función de
  una fórmula almacenada.

## Bug Details

### Bug 1 — Condición de bug `C1(X)`

El bug se manifiesta cuando un alumno pertenece a EXACTAMENTE un grupo con formato de comisión válido
y además a varios grupos que no son de comisión, y `_resolver_comision` devuelve "Sin comisión
asignada" en lugar de su comisión real. La causa está en que el puente por `moodle_group_id` se
aplica a TODOS los grupos del alumno sin filtrar por formato: un grupo que no es de comisión puede
matchear una comisión de la BD por `moodle_group_id` (o el grupo real fallar ambos puentes) y romper
el conteo `len(encontradas) == 1`.

**Formal Specification:**
```
FUNCTION isBugCondition1(X)
  INPUT: X = (grupos: list<Grupo>, comisiones: list<Comision>)
  OUTPUT: boolean

  // Existe EXACTAMENTE UN grupo cuyo nombre matchea el formato de comisión
  grupos_comision ← [ g IN X.grupos WHERE matchesComisionFormat(g.name) ]
  RETURN (count(grupos_comision) = 1)
         AND (resolver_comision(X.grupos, X.comisiones) = "Sin comisión asignada")
END FUNCTION
```

Los grupos que no son de comisión (estado / instancia / regional) deben ignorarse y **nunca** deben
producir ambigüedad.

#### Examples

- **TAMARA ROCIO ALBARRACÍN** — grupos `["A25 C2-01", "Extraordinaria_sdo_parcial",
  "NO_RINDIERON_PARCIAL_1", "No-rindieron-P1", "R-Mendoza", "Ultima_INSTANCIA_Examen"]`, comisión
  real `"A25 C2-01"`: esperado = asignada a `"A25 C2-01"`; actual = "Sin comisión asignada".
- Alumno con `["M26 C1-01", "R-Córdoba"]`: esperado = `"M26 C1-01"`; actual (si `"R-Córdoba"` matchea
  otra comisión por `moodle_group_id`) = "Sin comisión asignada".
- Alumno con `["M25 C3-01"]` (un solo grupo de comisión, bien vinculado por `moodle_group_id`):
  esperado y actual = `"M25 C3-01"` (NO dispara el bug; se preserva).
- (Edge) Alumno con `["R-Mendoza", "NO_RINDIERON_PARCIAL_1"]` (sin grupo de comisión): esperado y
  actual = "Sin comisión asignada" (NO dispara el bug; se preserva — 3.2).

### Bug 2 — Condición de bug `C2(X)`

El bug se manifiesta al abrir el Excel de cierre: las fórmulas de la columna "Recuperable" y los
conteos del resumen se muestran como `#NAME?` porque se escribieron con nombres de función es-AR y
`;`, sintaxis inválida para el formato de archivo `.xlsx`.

**Formal Specification:**
```
FUNCTION isBugCondition2(X)
  INPUT: X = fórmula escrita en una celda del .xlsx
  OUTPUT: boolean

  RETURN usaNombresFuncionEsAR(X) OR usaPuntoYComaComoSeparador(X)
END FUNCTION
```

#### Examples

- Celda "PROMOCIONADOS": actual `=CONTAR.SI(F:F;"PROMOCIONA")` → `#NAME?`; esperado
  `=COUNTIF(F:F,"PROMOCIONA")` → calcula el conteo.
- Celda "Recuperable" (fila `n`): actual `=SI(F{n}<>"RECURSA";"";SI(Y(SI.ERROR(VALOR(...)` → `#NAME?`;
  esperado `=IF(F{n}<>"RECURSA","",IF(AND(IFERROR(VALUE(...)` → clasifica RECUPERABLE CON PARCIAL 1/2.
- (Edge) Un texto literal que no es fórmula (no empieza con `=`, p. ej. `"N/E"`): NO dispara el bug;
  se preserva sin cambios.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Un alumno que pertenece genuinamente a DOS comisiones reales distintas sigue en "Sin comisión
  asignada" (3.1).
- Un alumno sin ningún grupo con formato de comisión sigue en "Sin comisión asignada" (3.2).
- Un alumno con un único grupo de comisión bien vinculado por `moodle_group_id` se sigue resolviendo
  por ese puente primario, con el mismo orden y prioridad de puentes (`moodle_group_id` y luego
  nombre) (3.3).
- Un alumno con comisión resuelta sigue devolviendo `comision_id`, `comision_nombre` y nombre(s) de
  tutor como hoy (3.4).
- Un grupo regional (`"R-<nombre>"`) se sigue parseando como regional y no como comisión (3.5).
- La resolución de comisión nunca interrumpe la corrida por un alumno con mapeo ambiguo/roto (3.6).
- El Excel sigue produciendo las dos hojas ("por Comisiones" y "Crudo") con su estructura, estilos de
  la casa, celdas `N/E` y comportamiento de "Nota Final" definidos en la spec previa (3.7).
- Las fórmulas del Excel siguen usando los mismos criterios comodín (`"RECUPERABLE*"` en "por
  Comisiones", `"RECUPERABLE CON*"` en "Crudo") y las mismas referencias de columna por hoja (por
  Comisiones: Estado `F`, parciales `C`/`D`, aux Recuperable `H`; Crudo: Estado `H`, parciales
  `E`/`F`, Recuperable `J`); sólo cambian los nombres de función y el separador (3.8).
- El `.xlsx` generado sigue abriendo con openpyxl (para los tests) y computando los mismos valores de
  clasificación "Recuperable" y los mismos 5 conteos del resumen que las fórmulas es-AR pretendidas
  (3.9).

**Scope:**
Toda entrada que NO cumple `C1` ni `C2` queda inalterada:
- Bug 1: alumnos con ambigüedad genuina, alumnos sin grupo de comisión, alumnos con un único grupo de
  comisión bien vinculado, regionales.
- Bug 2: valores literales de celda (texto/números que no son fórmula) y la comparación de strings
  dentro de las propias fórmulas (`<>"RECURSA"`, criterios `COUNTIF`) — que son insensibles al
  locale y no cambian.

**Note:** El comportamiento correcto esperado ante cada condición de bug se define en las Correctness
Properties (Property 1 y Property 2). Esta sección enfoca lo que NO debe cambiar.

## Hypothesized Root Cause

### Bug 1 — Puente `moodle_group_id` aplicado a grupos que no son de comisión

Lectura del código actual de `_resolver_comision`:

```python
por_group_id = {c.moodle_group_id: c for c in comisiones if c.moodle_group_id}
por_nombre   = {c.nombre.strip().casefold(): c for c in comisiones if c.nombre}
encontradas  = {}
for g in grupos:                       # <-- itera TODOS los grupos del alumno
    gid = g.get("id")
    if gid is not None and gid in por_group_id:   # puente por moodle_group_id
        encontradas[por_group_id[gid].id] = por_group_id[gid]
        continue
    codigo = parse_comision(g.get("name") or "")  # puente por nombre (sólo formato comisión)
    if codigo:
        c = por_nombre.get(codigo.strip().casefold())
        if c:
            encontradas[c.id] = c
if len(encontradas) != 1:              # regla de ambigüedad
    return None, "Sin comisión asignada", None
```

El puente por `moodle_group_id` se evalúa sobre **cada** grupo del alumno, sin exigir que el grupo
tenga formato de comisión. El puente por nombre, en cambio, sólo puede matchear grupos con formato de
comisión (por `parse_comision`). Para TAMARA, el puente por nombre matchea únicamente `"A25 C2-01"`
(el único grupo con formato de comisión). Por lo tanto, la ambigüedad `len(encontradas) > 1` SÓLO
puede originarse en el puente por `moodle_group_id` disparando sobre un grupo que NO es de comisión.

Hipótesis, ordenadas por probabilidad tras leer el código:

1. **(a) Falso positivo por segundo match — MÁS PROBABLE.** Uno de los grupos que no son de comisión
   de TAMARA (`Extraordinaria_sdo_parcial`, `NO_RINDIERON_PARCIAL_1`, `No-rindieron-P1`, `R-Mendoza`,
   `Ultima_INSTANCIA_Examen`) tiene un `moodle_group_id` que coincide con el `Comision.moodle_group_id`
   de una comisión DISTINTA en la BD (mapeo de comisión mal vinculado en un import previo). Eso agrega
   una SEGUNDA comisión distinta a `encontradas` → `len(encontradas) == 2` → ambigüedad → "Sin
   comisión asignada", pese a que `"A25 C2-01"` sí matcheó por nombre.
2. **(c) Interacción con el mapa autoritativo `uid → grupos` — FACTOR HABILITANTE.** La spec previa
   (Bug 3) reemplazó el `groups[]` embebido (que en cursos con grupos separados venía INCOMPLETO) por
   el mapa autoritativo, que ahora entrega a `_resolver_comision` la lista COMPLETA de grupos del
   alumno. Eso explica por qué el defecto apareció DESPUÉS de esa spec y por qué afecta al patrón
   multi-grupo: antes, el grupo espurio podía no venir en el `groups[]`; ahora siempre viene y el
   puente por `moodle_group_id` lo evalúa.
3. **(b) Cero matches del grupo real — MENOS PROBABLE.** El grupo `"A25 C2-01"` falla los DOS puentes
   (su `moodle_group_id` no está seteado/no coincide Y `Comision.nombre` no es exactamente
   `"A25 C2-01"`). Menos probable porque, de ser así, TODOS los alumnos de esa comisión fallarían, no
   sólo los multi-grupo; el reporte indica que el patrón es específicamente multi-grupo.

**Diagnóstico (observación primero) — GATING antes de codificar:** ver "Testing Strategy →
Exploratory Bug Condition Checking". Se reproduce el caso de TAMARA con su lista real de 6 grupos
contra `_resolver_comision` y las comisiones reales de Programación 2, instrumentando el contenido de
`encontradas` (cuántas comisiones distintas y por qué puente matchea cada una) para CONFIRMAR (a)/(c)
o, si se refuta, re-hipotetizar hacia (b). Debe confirmarse ADEMÁS que el grupo real `"A25 C2-01"`
matchea el regex generalizado y que su `Comision` existe (por `moodle_group_id` o por nombre), para
garantizar que el fix (aislar el grupo de comisión) no pierda el match legítimo.

> **Supuesto a validar en el diagnóstico (tradeoff flagged).** El fix propuesto resuelve la comisión
> SÓLO a partir de los grupos con formato de comisión. Esto asume que el grupo de Moodle apuntado por
> `Comision.moodle_group_id` es él mismo de formato de comisión (lo normal: el grupo de la comisión
> se llama `"A25 C2-01"`). Si el diagnóstico revelara que una comisión está vinculada por
> `moodle_group_id` a un grupo SIN formato de comisión, ese es precisamente el vínculo mal cableado
> que causa el bug (a) y debe corregirse el dato o revisar la dirección del fix. El diagnóstico lo
> confirma antes de implementar.

### Bug 2 — Fórmulas emitidas con sintaxis es-AR

`_formula_recuperable` y `_formulas_conteo_resumen` construyen los strings de fórmula con nombres de
función en español (`SI`, `CONTAR.SI`, `Y`, `VALOR`, `SI.ERROR`) y `;` como separador. openpyxl
escribe ese string VERBATIM dentro del OOXML. El formato de archivo `.xlsx` (OOXML) almacena las
fórmulas SIEMPRE con nombres de función canónicos en inglés y COMA como separador; Excel / Google
Sheets recién traducen al locale de visualización al abrir. Por eso los nombres es-AR + `;` son
inválidos en el archivo almacenado y se renderizan como `#NAME?` en CUALQUIER locale. La nota de
locale del docstring del módulo (que hoy documenta la dependencia es-AR como intencional) es
justamente la premisa equivocada y debe reescribirse.

## Correctness Properties

Property 1: Bug Condition — Alumno multi-grupo asignado a su comisión real

_For any_ alumno donde la condición del Bug 1 se cumple (`isBugCondition1` true: existe exactamente
un grupo con formato de comisión y hoy se resuelve como "Sin comisión asignada"), el sistema fijado
SHALL identificar ese grupo con formato de comisión, resolver la comisión ÚNICAMENTE a partir de los
grupos con formato de comisión (ignorando los grupos de estado / instancia / regional, que nunca
aportan match ni ambigüedad) y asignar al alumno a esa comisión (`comision_nombre` = el nombre de la
única comisión de formato del alumno, distinto de "Sin comisión asignada"), usando el regex
generalizado `{cohorte}{año} C{semestre}-{NN}` con año de exactamente 2 dígitos.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Bug Condition — Fórmulas del Excel válidas en cualquier locale

_For any_ fórmula donde la condición del Bug 2 se cumple (`isBugCondition2` true: se emitía con
nombres es-AR y/o `;`), el sistema fijado SHALL emitirla con nombres de función en INGLÉS (`IF`,
`COUNTIF`, `AND`, `VALUE`, `IFERROR`) y COMA como separador, de modo que abra sin `#NAME?` en
cualquier locale y compute el MISMO resultado que la fórmula es-AR pretendida, conservando los mismos
criterios comodín (`"RECUPERABLE*"` / `"RECUPERABLE CON*"`) y las mismas referencias de columna por
hoja.

**Validates: Requirements 2.5, 2.6, 2.7, 2.8**

Property 3: Preservation — Comportamiento inalterado fuera de las condiciones de bug

_For any_ entrada que NO cumple `isBugCondition1` NI `isBugCondition2` (ambigüedad genuina entre dos
comisiones reales, alumno sin grupo de comisión, alumno con único grupo bien vinculado por
`moodle_group_id`, grupo regional, y valores/celdas del Excel que no son fórmula), el sistema fijado
SHALL producir exactamente el mismo resultado que el original: "Sin comisión asignada" para
0 o >1 comisiones DISTINTAS de formato, puente `moodle_group_id` primario con su orden actual,
`comision_id`/`comision_nombre`/tutor iguales, regionales parseadas como regional, corrida que no se
interrumpe, dos hojas del Excel con estilos y `N/E`, criterios comodín y referencias de columna sin
cambios, y archivo que abre con openpyxl con los mismos valores/conteos.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9**

## Fix Implementation

### Bug 1 — Aislar el grupo de comisión + generalizar el regex

**File**: `backend/app/services/gestion_parser.py`

**Cambio 1 — Regex generalizado (año = exactamente 2 dígitos)**:
- Reemplazar `_COMISION_RE = re.compile(r"^[MA]\d+\s+C\d+-\d+$")` por
  `_COMISION_RE = re.compile(r"^[MA]\d{2}\s+C\d+-\d+$")`.
- Sólo se acota el año a 2 dígitos (`\d{2}`); la cohorte (`[MA]`), el semestre (`C\d+`) y el número de
  comisión (`-\d+`) no cambian, para no hardcodear cohorte/año/semestre concretos. Así un grupo con
  año de distinta longitud (p. ej. `"A2025 C2-01"`) deja de interpretarse como comisión, y los grupos
  de estado/instancia/regional siguen sin matchear.
- `parse_comision`, `parse_regional` y `resolver_grupos_alumno` no cambian su firma; el efecto del
  regex más estricto se propaga solo.

**File**: `backend/app/services/cierre_cursada_service.py`

**Cambio 2 — Resolver la comisión sólo desde los grupos con formato de comisión**:
En `_resolver_comision`, filtrar los grupos del alumno a los de formato de comisión ANTES de aplicar
los puentes, de modo que los grupos que no son de comisión no puedan aportar un match espurio ni
disparar la ambigüedad:

```python
@staticmethod
def _resolver_comision(grupos, comisiones):
    por_group_id = {c.moodle_group_id: c for c in comisiones if c.moodle_group_id}
    por_nombre = {c.nombre.strip().casefold(): c for c in comisiones if c.nombre}
    # Sólo los grupos con formato de comisión resuelven una comisión: los grupos de
    # estado/instancia/regional se descartan ANTES de los puentes, así nunca aportan un
    # match espurio por moodle_group_id ni disparan la regla de ambigüedad (Bug 1).
    grupos_comision = [g for g in grupos if parse_comision(g.get("name") or "")]
    encontradas: dict[int, object] = {}
    for g in grupos_comision:
        gid = g.get("id")
        if gid is not None and gid in por_group_id:      # puente primario: moodle_group_id
            c = por_group_id[gid]
            encontradas[c.id] = c
            continue
        codigo = parse_comision(g.get("name") or "")     # fallback: nombre
        if codigo:
            c = por_nombre.get(codigo.strip().casefold())
            if c:
                encontradas[c.id] = c
    if len(encontradas) != 1:                             # 0 o >1 comisiones DISTINTAS
        return None, "Sin comisión asignada", None
    comision = next(iter(encontradas.values()))
    tutor_nombre = " / ".join(ct.tutor.nombre for ct in comision.tutores) or None
    return comision.id, comision.nombre, tutor_nombre
```

Notas de preservación:
- El puente por `moodle_group_id` sigue siendo primario y conserva su precedencia (se evalúa antes
  del `continue`) para el grupo de comisión real (3.3). Como el grupo apuntado por
  `Comision.moodle_group_id` es de formato de comisión (supuesto validado en el diagnóstico),
  sobrevive al filtro y el match legítimo no se pierde.
- Un alumno con DOS grupos de comisión distintos que mapean a dos comisiones distintas sigue dando
  `len(encontradas) == 2` → "Sin comisión asignada" (ambigüedad genuina, 3.1).
- Un alumno sin grupo de comisión da `grupos_comision == []` → `len(encontradas) == 0` → "Sin comisión
  asignada" (3.2).
- Los regionales `"R-*"` no matchean `parse_comision`, se descartan del filtro y siguen sin
  interpretarse como comisión (3.5).
- La firma y el contrato de retorno no cambian → `comision_id`/`comision_nombre`/tutor iguales (3.4);
  nunca se lanza excepción → la corrida no se interrumpe (3.6).

> El `generar` de `CierreCursadaService` (que ya arma el mapa autoritativo `uid → grupos` y se lo pasa
> a `_resolver_comision`) NO cambia: sigue pasando la lista completa de grupos; el filtrado por
> formato de comisión vive dentro de `_resolver_comision`.

### Bug 2 — Emitir fórmulas en inglés con coma

**File**: `backend/app/services/excel_cierre_cursada.py`

**Cambio 3 — `_formula_recuperable`** (reescribir el string a inglés + coma, mismas referencias de
columna por argumento):

```python
def _formula_recuperable(estado_col: str, p1_col: str, p2_col: str, fila: int) -> str:
    return (
        f'=IF({estado_col}{fila}<>"RECURSA","",'
        f"IF(AND(IFERROR(VALUE({p1_col}{fila}),0)>=40,IFERROR(VALUE({p2_col}{fila}),0)<40),"
        f'"RECUPERABLE CON PARCIAL 2",'
        f"IF(AND(IFERROR(VALUE({p2_col}{fila}),0)>=40,IFERROR(VALUE({p1_col}{fila}),0)<40),"
        f'"RECUPERABLE CON PARCIAL 1","")))'
    )
```

- Traducción 1:1 de la fórmula es-AR: `SI→IF`, `Y→AND`, `SI.ERROR→IFERROR`, `VALOR→VALUE`, `;→,`.
- Los strings de comparación/resultado (`<>"RECURSA"`, `"RECUPERABLE CON PARCIAL 1/2"`, `""`) NO
  cambian (son insensibles al locale). Las letras de columna (`estado_col`/`p1_col`/`p2_col`) siguen
  recibiéndose como parámetros → mismas referencias por hoja (por Comisiones F/C/D; Crudo H/E/F) (3.8).
- Resultado esperado por fila `n` (hoja "por Comisiones"):
  `=IF(F{n}<>"RECURSA","",IF(AND(IFERROR(VALUE(C{n}),0)>=40,IFERROR(VALUE(D{n}),0)<40),"RECUPERABLE CON PARCIAL 2",IF(AND(IFERROR(VALUE(D{n}),0)>=40,IFERROR(VALUE(C{n}),0)<40),"RECUPERABLE CON PARCIAL 1","")))`

**Cambio 4 — `_formulas_conteo_resumen`** (reescribir `CONTAR.SI→COUNTIF`, `;→,`):

```python
def _formulas_conteo_resumen(estado_letra, recuperable_letra, recuperable_criterio):
    def _por_estado(patron: str) -> str:
        return f'=COUNTIF({estado_letra}:{estado_letra},"{patron}")'

    return [
        ("PROMOCIONADOS", _por_estado("PROMOCIONA")),
        ("REGULARES", _por_estado("REGULARIZA")),
        ("RECURSANTES", _por_estado("RECURSA")),
        ("RECUPERABLES",
         f'=COUNTIF({recuperable_letra}:{recuperable_letra},"{recuperable_criterio}")'),
        ("ABANDONOS", _por_estado("ABANDONO")),
    ]
```

- Conteos resultantes (por Comisiones): `=COUNTIF(F:F,"PROMOCIONA")`, `=COUNTIF(F:F,"REGULARIZA")`,
  `=COUNTIF(F:F,"RECURSA")`, `=COUNTIF(H:H,"RECUPERABLE*")`, `=COUNTIF(F:F,"ABANDONO")`.
- Hoja "Crudo": Estado en `H`, Recuperable en `J`, criterio `"RECUPERABLE CON*"` →
  `=COUNTIF(J:J,"RECUPERABLE CON*")`. El criterio comodín y las referencias por hoja no cambian (3.8).

**Cambio 5 — Docstring/nota de locale del módulo**: reescribir la nota que hoy declara la dependencia
es-AR como intencional. La nueva nota debe documentar que las fórmulas se emiten con nombres de
función en inglés y coma (sintaxis canónica del formato `.xlsx`), que Excel/Google Sheets muestran
traducidas al locale de apertura, y que por eso abren sin `#NAME?` en cualquier locale. Actualizar
también los comentarios inline de `_escribir_resumen` / `_escribir_resumen_crudo` /
`_escribir_hoja_cruda` que citan la sintaxis es-AR.

> `_recuperable_para_fila`, `_escribir_resumen`, `_escribir_detalle`, `_escribir_hoja_cruda` y
> `generar_excel_cierre` no cambian su lógica: siguen invocando los mismos helpers con las mismas
> letras de columna; sólo cambia el string que esos helpers producen. La estructura de dos hojas,
> estilos, `N/E` y "Nota Final" quedan intactos (3.7, 3.9).

### Tests existentes a actualizar (Bug 2)

`backend/tests/unit/services/test_excel_cierre_cursada.py` aserta HOY los strings es-AR y debe
actualizarse a la sintaxis inglesa (estas aserciones dejan de reflejar el comportamiento correcto tras
el fix):

- `test_resumen_de_conteos_como_formulas_nativas_a2_b6`: cambiar `'=CONTAR.SI(F:F;"PROMOCIONA")'` →
  `'=COUNTIF(F:F,"PROMOCIONA")'`, `'=CONTAR.SI(F:F;"REGULARIZA")'` → `'=COUNTIF(F:F,"REGULARIZA")'`,
  `'=CONTAR.SI(F:F;"RECURSA")'` → `'=COUNTIF(F:F,"RECURSA")'`, `'=CONTAR.SI(H:H;"RECUPERABLE*")'` →
  `'=COUNTIF(H:H,"RECUPERABLE*")'`, `'=CONTAR.SI(F:F;"ABANDONO")'` → `'=COUNTIF(F:F,"ABANDONO")'`.
- `test_bug_conteo_promocionados_es_formula_no_entero`: `'=CONTAR.SI(F:F;"PROMOCIONA")'` →
  `'=COUNTIF(F:F,"PROMOCIONA")'`.
- `test_bug_columna_recuperable_es_formula_por_fila`: `celda.startswith(f'=SI(F{n}<>"RECURSA";"";SI(Y(')`
  → `celda.startswith(f'=IF(F{n}<>"RECURSA","",IF(AND(')`; `f"SI.ERROR(VALOR(C{n});0)>=40"` →
  `f"IFERROR(VALUE(C{n}),0)>=40"`; `f"SI.ERROR(VALOR(D{n});0)<40"` → `f"IFERROR(VALUE(D{n}),0)<40"`
  (los asserts de `"RECUPERABLE CON PARCIAL 1/2"` no cambian).
- `test_bug_conteo_recuperables_y_abandonos_son_formulas`: `'=CONTAR.SI(H:H;"RECUPERABLE*")'` →
  `'=COUNTIF(H:H,"RECUPERABLE*")'`, `'=CONTAR.SI(F:F;"ABANDONO")'` → `'=COUNTIF(F:F,"ABANDONO")'`.

## Testing Strategy

### Validation Approach

Enfoque en dos fases: primero surface los contraejemplos que demuestran cada bug sobre el código SIN
arreglar (para Bug 1, además, un paso de diagnóstico que CONFIRMA la causa raíz con los datos reales
de TAMARA antes de codificar), y luego se verifica que el fix corrige la condición de bug y preserva
el resto. Property-based testing para la preservación de la resolución de comisión y la lógica de la
fórmula "Recuperable".

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples que demuestren cada bug ANTES del fix y CONFIRMAR la causa raíz del
Bug 1 (crítico: gating antes de codificar). Si se refuta, re-hipotetizar.

**Test Plan**: correr sobre el código sin arreglar los casos siguientes y observar el fallo /
instrumentar el estado interno.

**Test Cases**:
1. **Diagnóstico TAMARA (Bug 1) — GATING**: construir la lista real de 6 grupos de TAMARA
   (`["A25 C2-01", "Extraordinaria_sdo_parcial", "NO_RINDIERON_PARCIAL_1", "No-rindieron-P1",
   "R-Mendoza", "Ultima_INSTANCIA_Examen"]`, cada uno con su `id` de Moodle) y el conjunto de
   `Comision` reales de Programación 2, e invocar `_resolver_comision`. Instrumentar / inspeccionar el
   contenido de `encontradas`:
   - Si `len(encontradas) >= 2` y una de las comisiones matcheó por `moodle_group_id` desde un grupo
     que NO es `"A25 C2-01"` → **confirma (a)** (segundo match espurio), habilitado por (c).
   - Si `len(encontradas) == 0` → **confirma (b)** (el grupo real falla ambos puentes): re-hipotetizar
     y ajustar el fix (revisar `moodle_group_id`/nombre de la comisión en la BD).
   Esperado del caso sin arreglar: `_resolver_comision(...) == (None, "Sin comisión asignada", None)`
   (falla la expectativa de `"A25 C2-01"`).
2. **Multi-grupo con segundo match espurio (Bug 1)**: alumno con `["M26 C1-01", <grupo no-comisión
   con moodle_group_id de otra comisión>]` → hoy "Sin comisión asignada" (falla); esperado
   `"M26 C1-01"`.
3. **Regex año 2 dígitos (Bug 1)**: `parse_comision("A2025 C2-01")` → hoy devuelve `"A2025 C2-01"`
   (el `\d+` acepta 4 dígitos); esperado tras el fix `None` (año debe ser 2 dígitos).
   `parse_comision("A25 C2-01")` sigue devolviendo `"A25 C2-01"`.
4. **Recuperable `#NAME?` (Bug 2)**: leer la celda "Recuperable" de una fila RECURSA → hoy empieza con
   `=SI(...` con `;` (falla la expectativa de `=IF(...` con `,`).
5. **Conteos `#NAME?` (Bug 2)**: leer la celda "PROMOCIONADOS" → hoy `=CONTAR.SI(F:F;"PROMOCIONA")`
   (falla la expectativa `=COUNTIF(F:F,"PROMOCIONA")`).

**Expected Counterexamples**:
- Bug 1: TAMARA (y todo alumno multi-grupo con un grupo no-comisión mal vinculado) resuelto como "Sin
  comisión asignada"; `encontradas` con ≥2 comisiones donde la 2ª vino de un grupo que no es de
  comisión; el regex acepta años de longitud distinta de 2.
- Bug 2: toda celda de fórmula emitida con nombres es-AR + `;` (se mostraría `#NAME?`).

### Fix Checking

**Goal**: Verificar que para todo input donde vale la condición de bug, la función fijada produce el
comportamiento esperado.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition1(X) DO
  (_, comision_nombre, _) := _resolver_comision'(X.grupos, X.comisiones)
  ASSERT comision_nombre == nombreDeLaUnicaComisionFormato(X.grupos)
  ASSERT comision_nombre != "Sin comisión asignada"
END FOR

FOR ALL X WHERE isBugCondition2(X) DO
  X' := formulaEmitidaPor(F')                       // inglés + coma
  ASSERT usaNombresFuncionIngles(X') AND usaComaComoSeparador(X')
  ASSERT valorCalculado(X') == valorEsperado(intencionEsAR(X))   // sin #NAME?
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todo input donde NO vale ninguna condición de bug, la función fijada
produce el mismo resultado que la original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition1(X) AND NOT isBugCondition2(X) DO
  ASSERT F(X) == F'(X)
END FOR
```

**Testing Approach**: property-based testing para preservación (genera muchos casos del dominio y
detecta edge cases). Especialmente útil en `_resolver_comision` (combinaciones de grupos de comisión /
no-comisión / vínculos por `moodle_group_id`) y en la lógica de la fórmula "Recuperable".

**Test Plan**: observar el comportamiento del código sin arreglar para las entradas que NO disparan
los bugs (ambigüedad genuina, sin grupo de comisión, único grupo bien vinculado, regionales, celdas
que no son fórmula) y escribir tests que verifiquen que se mantiene tras el fix.

**Test Cases**:
1. **Ambigüedad genuina (3.1)**: alumno con dos grupos de comisión distintos (`"A25 C2-01"` +
   `"A25 C2-02"`) que mapean a dos comisiones → "Sin comisión asignada" (igual que hoy).
2. **Sin grupo de comisión (3.2)**: alumno sólo con grupos de estado/instancia/regional → "Sin
   comisión asignada".
3. **Único grupo bien vinculado (3.3)**: alumno con `["A25 C2-01"]` cuyo `moodle_group_id` matchea la
   comisión → resuelto por el puente primario, con `comision_id`/nombre/tutor iguales (3.4).
4. **Regional preservada (3.5)**: `parse_regional("R-Mendoza") == "Mendoza"` y `parse_comision` de un
   `"R-*"` sigue `None`.
5. **Estructura Excel (3.7, 3.9)**: el `.xlsx` sigue con dos hojas, estilos de la casa, `N/E` en
   columnas de examen y "Nota Final" en blanco para no-PROMOCIONA; abre con openpyxl.
6. **Referencias/criterios de fórmula (3.8)**: las fórmulas inglesas conservan Estado F / parciales
   C-D / Recuperable H (por Comisiones) y Estado H / parciales E-F / Recuperable J (Crudo), con
   criterios `"RECUPERABLE*"` / `"RECUPERABLE CON*"`.

### Unit Tests

- `gestion_parser.parse_comision`: acepta `"A25 C2-01"`, `"M26 C1-01"`, `"M25 C3-01"`; rechaza
  `"A2025 C2-01"` (año 4 dígitos), `"A5 C2-01"` (año 1 dígito), `"R-Mendoza"`, `"NO_RINDIERON_PARCIAL_1"`,
  `"Extraordinaria_sdo_parcial"`, `""`/`None`.
- `cierre_cursada_service._resolver_comision`: caso TAMARA (6 grupos → `"A25 C2-01"`); segundo match
  espurio por grupo no-comisión eliminado; ambigüedad genuina → "Sin comisión asignada"; sin grupo de
  comisión → "Sin comisión asignada"; único grupo por `moodle_group_id` → comisión + tutor.
- `excel_cierre_cursada._formula_recuperable`: string exacto en inglés con coma para (F,C,D) y
  (H,E,F); presencia de `IF`/`AND`/`IFERROR`/`VALUE`, ausencia de `SI`/`Y`/`;`.
- `excel_cierre_cursada._formulas_conteo_resumen`: cinco tuplas con `COUNTIF(...,...)` y las
  referencias/criterios correctos por hoja.

### Property-Based Tests

- **Resolución de comisión (Property 1 + Preservación)**: generar listas de grupos mezclando 0/1/≥2
  grupos con formato de comisión (con `moodle_group_id` seteado o no) y N grupos que no son de
  comisión (algunos con `moodle_group_id` que colisiona con otra comisión). Verificar: con
  exactamente 1 grupo de comisión → siempre resuelve esa comisión (los no-comisión nunca alteran el
  resultado); con 0 o ≥2 grupos de comisión distintos → "Sin comisión asignada".
- **Regex generalizado (Property 1)**: generar nombres `{M|A}{año}{sep}C{sem}-{NN}` con año de
  longitud variable → `parse_comision` devuelve el nombre sólo cuando el año tiene exactamente 2
  dígitos.
- **Fórmula Recuperable (Property 2)**: generar combinaciones de notas de parciales y estado y
  verificar que la fórmula inglesa (evaluada con la misma semántica) marca "RECUPERABLE CON PARCIAL
  1/2" exactamente en los mismos casos que la es-AR pretendida (RECURSA con un parcial `>=40` y el
  otro `<40`/N/E-tratado-como-0), y que sólo cambian nombres de función y separador.

### Integration Tests

- **Cierre end-to-end (Moodle mockeado)**: una corrida con TAMARA (grupos reales) + alumnos de otras
  comisiones → TAMARA queda en `"A25 C2-01"`, los demás en su comisión, y el Excel de dos hojas se
  genera con fórmulas en inglés que abren sin `#NAME?`.
- **Excel abre/valida (Bug 2)**: generar el `.xlsx`, reabrir con openpyxl y verificar que todas las
  celdas de fórmula empiezan con `=` y usan nombres en inglés + coma; ninguna con `SI`/`CONTAR.SI`/`;`.
- **Multi-grupo variado (Bug 1)**: alumnos con distintas combinaciones de grupos no-comisión (incluido
  uno con `moodle_group_id` colisionante) → todos resueltos a su única comisión de formato.
