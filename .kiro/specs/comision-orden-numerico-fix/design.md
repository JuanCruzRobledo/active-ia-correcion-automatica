# Orden Numérico Natural de Comisiones Bugfix Design

## Overview

Las comisiones se ordenan y agrupan como **cadena de texto** (orden lexicográfico) en lugar de por
el **valor numérico natural** de su sufijo. Como los nombres siguen el patrón `<prefijo>-<número>`
(`COMI-1`, `COMI-2`, … `COMI-27`), ordenar como texto intercala mal los números de distinta
longitud (`COMI-10` antes que `COMI-2`).

El defecto tiene una **única causa raíz** —comparar el nombre como `str`— replicada en cuatro
superficies:

1. **Excel de cierre de cursada** (`excel_cierre_cursada._agrupar_por_comision`): agrupa/ordena los
   bloques por `comision_nombre.casefold()` (sort Python puro).
2. **Listado / gestión de comisiones** (`comision_repository`: `get_all`, `get_by_materia`,
   `get_by_materia_con_tutores`, `get_by_tutor`): `order_by(... Comision.nombre.asc())` (SQL).
3. **Corrida de cierre — alumnos** (`cierre_cursada_repository.get_alumnos_de_run`):
   `order_by(CierreCursadaAlumno.comision_nombre.asc().nullslast(), …)` (SQL).
4. **Reporte de avance** (`avance_repository.get_alumnos_de_snapshot` y `get_alumnos_por_estado`):
   `order_by(AvanceAlumno.comision.asc().nullslast(), …)` (SQL).

**Estrategia del fix (DRY con un contrato de orden compartido).** Se introduce un único módulo de
utilidad `backend/app/utils/orden_natural.py` que define el contrato de orden natural en sus dos
formas necesarias, con la misma semántica:

- `natural_key(nombre) -> tuple` — clave de orden natural en **Python** (tokeniza el nombre en
  fragmentos de texto y número). La usa el sort Python del Excel (superficie 1).
- `orden_natural_sql(col) -> list[ColumnElement]` — lista de expresiones `ORDER BY` de **SQLAlchemy**
  que reproduce la misma semántica a nivel de base de datos (prefijo alfabético + sufijo numérico
  casteado a entero, `NULLS LAST`, desempate por nombre completo). La usan los repositorios
  (superficies 2, 3, 4).

> **Nota de diseño (por qué DOS formas y no una).** El Excel ordena en memoria una lista de objetos
> ya materializados, mientras que los repositorios deben ordenar **en la consulta** para que la
> **paginación del listado** (`get_all`, `OFFSET/LIMIT`) sea correcta: un sort en Python después de
> traer la página sólo reordenaría esa página, no el conjunto. No existe una función Python que se
> pueda inyectar en un `ORDER BY` de SQL; por eso el helper centraliza el **contrato semántico** en
> un solo módulo y lo expresa una vez para Python y una vez para SQL. Es DRY a nivel de contrato,
> no de línea de código. Ver "Fix Implementation → Decisión: Python vs SQL".

Todos los cambios son quirúrgicos: sólo cambia el **criterio de orden por nombre de comisión**. Los
criterios primarios (`anio desc` en el listado), los filtros, la paginación, los desempates
secundarios (`apellido, nombre`), el `NULLS LAST` de columnas nulables y el bloque
"Sin comisión asignada" al final se preservan.

> **Contexto:** La spec previa `cierre-cursada-comision-nota-fix` (Bug 3) fijó deliberadamente el
> orden de los bloques del Excel como **alfabético** (`nombre.casefold()`). Ese orden alfabético es
> justamente el que produce este defecto para sufijos numéricos de distinta longitud. Este fix
> reemplaza el criterio alfabético por el orden natural numérico, conservando el resto de garantías
> de aquel fix (bloque "Sin comisión asignada" al final y orden intra-bloque por `Apellido, Nombre`).

## Glossary

- **Bug_Condition (C)**: Condición que dispara el bug — un conjunto de nombres de comisión con
  sufijo numérico de distinta longitud (`COMI-2`, `COMI-10`, …) cuyo orden lexicográfico difiere del
  orden numérico natural.
- **Property (P)**: Comportamiento deseado — las comisiones se ordenan/agrupan por el valor numérico
  natural del sufijo del nombre (`COMI-1, COMI-2, …, COMI-10, …, COMI-27`).
- **Preservation**: Comportamiento existente que no debe cambiar — fallback alfabético para nombres
  sin sufijo numérico, `anio desc` como criterio primario del listado, bloque "Sin comisión
  asignada" al final, orden intra-bloque por `(Apellido, Nombre)`, `NULLS LAST` y filtros/paginación.
- **Orden natural / natural sort**: Orden que interpreta las secuencias de dígitos dentro de una
  cadena como enteros, de modo que `COMI-2` precede a `COMI-10`.
- **`natural_key(nombre)`**: Función pura (nueva) en `app.utils.orden_natural` que devuelve una clave
  de orden natural en Python: una tupla de pares `(0, texto)` / `(1, número)` obtenida al tokenizar
  el nombre; comparable elemento a elemento sin mezclar tipos.
- **`orden_natural_sql(col)`**: Función (nueva) en `app.utils.orden_natural` que, dada una columna de
  SQLAlchemy, devuelve la lista de expresiones `ORDER BY` que implementan el orden natural a nivel
  DB (prefijo alfabético case-insensitive, sufijo numérico casteado a `Integer` con `NULLS LAST`,
  desempate por el nombre completo).
- **`_agrupar_por_comision`**: Función de `excel_cierre_cursada.py` que agrupa los
  `CierreCursadaAlumno` por título de bloque (`"{comisión} — Tutor: {tutor}"`) y los ordena; hoy
  ordena por `comision_nombre.casefold()` (lexicográfico) — la causa raíz en la superficie 1.
- **Prefijo / sufijo numérico**: Para `COMI-27`, el prefijo es `COMI-` y el sufijo numérico es `27`.
  Un nombre puramente alfabético (`Teórica`) no tiene sufijo numérico → su sufijo es `NULL`/ausente.
- **`comision_nombre` / `comision`**: Campos denormalizados nulables de `CierreCursadaAlumno` y
  `AvanceAlumno` respectivamente; `NULL` (o "Sin comisión asignada") cuando el alumno no matcheó
  ninguna comisión → deben quedar al final (`NULLS LAST`).

## Bug Details

### Bug Condition

El bug se manifiesta cuando se listan o agrupan comisiones cuyos nombres terminan en un número y
esos números tienen distinta cantidad de dígitos. Al ordenar el nombre como texto, `"10" < "2"`
(comparación carácter a carácter: `'1' < '2'`), por lo que `COMI-10` queda antes de `COMI-2`. La
misma comparación textual está en el sort del Excel (`_agrupar_por_comision`) y en los `order_by`
de los tres repositorios afectados.

**Formal Specification:**

```
FUNCTION isBugCondition(nombres)
  INPUT: nombres = lista de nombres de comisión (strings no nulos)
  OUTPUT: boolean

  # El orden lexicográfico actual difiere del orden numérico natural esperado.
  orden_actual   := SORT(nombres, key = casefold)          # comparación textual (hoy)
  orden_esperado := SORT(nombres, key = natural_key)        # numérico natural (deseado)

  RETURN orden_actual != orden_esperado
END FUNCTION


FUNCTION natural_key(nombre)
  INPUT: nombre string
  OUTPUT: tupla comparable

  # Tokeniza en fragmentos alternados texto/dígitos; los dígitos se comparan como enteros.
  fragmentos := SPLIT(casefold(nombre) BY grupos de dígitos, conservando los separadores)
  RETURN [ (1, INT(f)) if f es dígitos else (0, f)  FOR f IN fragmentos ]
END FUNCTION
```

### Examples

- `["COMI-1","COMI-2","COMI-3","COMI-10","COMI-20","COMI-27"]`
  - Actual (texto): `COMI-1, COMI-10, COMI-2, COMI-20, COMI-27, COMI-3` (bug).
  - Esperado (natural): `COMI-1, COMI-2, COMI-3, COMI-10, COMI-20, COMI-27`.
- Excel de cierre con bloques `COMI-3`, `COMI-1`, `COMI-2`, `COMI-11` → Esperado: `COMI-1, COMI-2,
  COMI-3, COMI-11`; Actual (llegada/lexicográfico): `COMI-1, COMI-11, COMI-2, COMI-3`.
- Listado de comisiones (misma materia, `anio` 2025 y 2024): Esperado — primero todas las de 2025
  en orden natural, luego las de 2024 en orden natural. Actual — dentro de cada año, `COMI-10` antes
  de `COMI-2`.
- Alumnos de una corrida de cierre repartidos en `M26 C1-01`, `M26 C1-02`, `M26 C1-10`: Esperado —
  agrupados `…-01, …-02, …-10`; Actual — `…-01, …-10, …-02`.
- Edge (fallback alfabético, NO es bug): `["Teórica","Práctica","Laboratorio"]` sin sufijo numérico
  → orden alfabético `Laboratorio, Práctica, Teórica`, idéntico hoy y tras el fix.
- Edge (nulos): un alumno sin comisión (`comision_nombre = NULL` / "Sin comisión asignada") debe
  quedar al final, igual que hoy.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Los nombres SIN sufijo numérico (puramente alfabéticos) se siguen ordenando alfabéticamente como
  hoy (3.1).
- El desempate secundario existente (p. ej. `anio`, o `apellido, nombre` en reportes) se mantiene
  ante nombres/números idénticos (3.2).
- El listado general sigue usando `anio desc` como criterio PRIMARIO; el orden natural del nombre se
  aplica sólo como criterio secundario (3.3).
- El Excel sigue ubicando el bloque "Sin comisión asignada" SIEMPRE al final (3.4).
- Dentro de cada bloque/reporte, los alumnos siguen ordenados por `(Apellido, Nombre)` (3.5).
- Los valores nulos de comisión (`comision_nombre` / `comision` = `NULL`) siguen al final
  (`NULLS LAST`) sin interrumpir el listado ni la generación del reporte (3.6).
- Los filtros y la paginación del listado (materia, año, tutor, coordinador, página) se respetan sin
  cambios; sólo cambia el criterio de orden por nombre (3.7).

**Scope:**
Los inputs que NO disparan el bug quedan completamente inalterados:
- Conjuntos de comisiones cuyo orden lexicográfico ya coincide con el natural (p. ej. un solo
  dígito, o nombres puramente alfabéticos).
- El criterio `anio desc`, los filtros, la paginación y los conteos (`total`) del listado.
- El orden intra-bloque de alumnos, el formato del encabezado "{comisión} — Tutor: {tutor}" y los
  estilos del Excel.
- La ubicación al final de los valores nulos y del bloque "Sin comisión asignada".

**Note:** El comportamiento correcto esperado ante la condición de bug se define en las Correctness
Properties (Property 1). Esta sección enfoca lo que NO debe cambiar.

## Hypothesized Root Cause

Basado en el análisis del defecto, las causas son:

1. **Comparación textual del nombre (causa raíz principal)**: tanto el sort del Excel
   (`sorted(..., key=_clave_orden)` con `nombre.casefold()`) como los `order_by(Comision.nombre.asc())`
   / `comision_nombre.asc()` / `comision.asc()` de los repositorios comparan el nombre como `str`.
   Para sufijos numéricos de distinta longitud, `"10" < "2"` lexicográficamente.

2. **Ausencia de un criterio de orden compartido**: cada superficie implementa su propio `order_by`
   ad-hoc, por lo que el mismo defecto se repite cuatro veces y cualquier corrección puntual se
   desincroniza. No hay un único lugar que defina "cómo se ordenan las comisiones".

3. **Restricción de SQL para orden natural**: el orden natural no se obtiene con un `order_by` simple
   sobre la columna de texto; requiere extraer y castear el sufijo numérico dentro de la consulta.
   Hacerlo en Python tras el `fetch` rompería la paginación del listado (`get_all`), que necesita el
   `ORDER BY` aplicado ANTES del `OFFSET/LIMIT`.

## Correctness Properties

Property 1: Bug Condition - Orden numérico natural del nombre de comisión

_For any_ conjunto de nombres de comisión con sufijo numérico (`<prefijo>-<número>`), el sistema
SHALL ordenarlos/agruparlos por el valor ENTERO del sufijo dentro de cada prefijo (`COMI-1, COMI-2,
COMI-3, …, COMI-10, …, COMI-27`), y NO por su representación textual, en las cuatro superficies
(Excel de cierre, listado de comisiones, alumnos de la corrida de cierre y reporte de avance).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Fallback alfabético para nombres sin sufijo numérico

_For any_ conjunto de nombres de comisión donde no se dispara el bug (nombres puramente alfabéticos
o sin sufijo numérico), el resultado ordenado SHALL ser idéntico al orden alfabético
(case-insensitive) actual: `natural_key` y `orden_natural_sql` degradan a comparación de texto
cuando no hay sufijo numérico (sufijo `NULL`/ausente).

**Validates: Requirements 3.1**

Property 3: Preservation - Año descendente primario y filtros/paginación del listado

_For any_ consulta del listado de comisiones (`get_all`) con cualquier combinación de filtros
(materia, año, tutor, coordinador) y paginación (página, por_página), el resultado SHALL conservar
`anio desc` como criterio PRIMARIO, aplicar el orden natural del nombre sólo como secundario, y
devolver exactamente el mismo conjunto de filas y el mismo `total` que hoy para esos filtros —el
orden natural se calcula en la consulta, preservando la corrección de la paginación.

**Validates: Requirements 3.3, 3.7**

Property 4: Preservation - Desempate estable, intra-bloque y "Sin comisión asignada" al final

_For any_ conjunto de comisiones/alumnos, el fix SHALL preservar: el desempate secundario existente
ante nombres/números idénticos; el orden intra-bloque/reporte de alumnos por `(Apellido, Nombre)`; y
la ubicación del bloque "Sin comisión asignada" SIEMPRE al final del Excel, con el formato de
encabezado "{comisión} — Tutor: {tutor}" sin cambios.

**Validates: Requirements 3.2, 3.4, 3.5**

Property 5: Preservation - Valores nulos de comisión al final (NULLS LAST)

_For any_ conjunto de filas donde `comision_nombre` (cierre) o `comision` (avance) es `NULL`, el fix
SHALL ubicar esas filas al final del orden (`NULLS LAST`), sin lanzar excepción ni interrumpir la
generación del reporte, igual que hoy.

**Validates: Requirements 3.6**

## Fix Implementation

### Decisión: Python vs SQL (contrato de orden compartido)

| Superficie | Mecanismo | Motivo |
|------------|-----------|--------|
| Excel de cierre (`_agrupar_por_comision`) | **Python** `natural_key` | Ordena una lista ya materializada en memoria; no hay consulta. |
| Listado de comisiones (`get_all`) | **SQL** `orden_natural_sql` | Tiene `OFFSET/LIMIT`: el `ORDER BY` DEBE aplicarse en la consulta para que la paginación sea correcta. Un sort Python post-fetch sólo ordenaría la página. |
| Listado sin paginar (`get_by_materia`, `get_by_materia_con_tutores`, `get_by_tutor`) | **SQL** `orden_natural_sql` | Consistencia con `get_all` y para no cambiar el modo de carga. |
| Alumnos de la corrida (`get_alumnos_de_run`) | **SQL** `orden_natural_sql` | Ya ordena en la consulta; sólo cambia el criterio del nombre. |
| Reporte de avance (`get_alumnos_de_snapshot`, `get_alumnos_por_estado`) | **SQL** `orden_natural_sql` | Ídem. |

**Tradeoff (flagged):** `orden_natural_sql` usa expresiones regex de **PostgreSQL**
(`regexp_replace`, cast a `Integer`). El proyecto ya está atado a PostgreSQL (JSONB, asyncpg), así
que es aceptable; se documenta que esta función NO es portable a otros motores. La alternativa
(traer todo y ordenar en Python) se descarta porque rompe la paginación de `get_all` y obligaría a
cargar la tabla completa.

### Nuevo módulo compartido

**File (nuevo)**: `backend/app/utils/orden_natural.py`

Se coloca en `app/utils` (no en `services`) porque es una utilidad pura, sin reglas de negocio ni
acceso a datos, reutilizable por servicios y repositorios. Bien por debajo de 500 LOC.

Bosquejo:

```python
# app/utils/orden_natural.py
"""Orden natural (numeric-aware) para nombres de comisión ("COMI-2" antes de "COMI-10").

Un único contrato de orden expresado en dos formas equivalentes:
- natural_key(nombre): clave de orden para sort en Python (Excel de cierre).
- orden_natural_sql(col): expresiones ORDER BY de SQLAlchemy (repositorios; preserva paginación).

Semántica compartida: dígitos comparados como enteros; nombres sin sufijo numérico caen al
orden alfabético (case-insensitive); columnas nulables van al final (NULLS LAST) vía el caller.
"""
import re

from sqlalchemy import Integer, cast, func
from sqlalchemy.sql import ColumnElement

_DIGITOS = re.compile(r"(\d+)")


def natural_key(nombre: str | None) -> tuple:
    """Clave de orden natural. Tokeniza en fragmentos texto/dígitos; los dígitos → int.
    Cada elemento es (0, texto) o (1, numero) para comparar sin mezclar tipos."""
    if nombre is None:
        return ((2, ""),)  # sin nombre → al final entre las claves comparadas
    fragmentos = _DIGITOS.split(nombre.casefold())
    clave: list[tuple[int, object]] = []
    for i, f in enumerate(fragmentos):
        if i % 2 == 1:            # los índices impares son los grupos de dígitos
            clave.append((1, int(f)))
        elif f:
            clave.append((0, f))
    return tuple(clave) or ((0, ""),)


def orden_natural_sql(col: ColumnElement) -> list:
    """Expresiones ORDER BY que reproducen `natural_key` a nivel PostgreSQL:
    1) prefijo (nombre sin el sufijo numérico) en minúsculas → agrupa prefijos y alfabético;
    2) sufijo numérico final casteado a int, NULLS LAST → orden numérico + fallback alfabético;
    3) nombre completo → desempate estable.
    El caller antepone/pospone sus propios criterios (anio desc, apellido, nombre).
    """
    prefijo = func.lower(func.regexp_replace(col, r"\d+$", ""))
    sufijo = cast(
        func.nullif(func.regexp_replace(col, r"^.*?(\d+)$", r"\1"), col),
        Integer,
    )
    return [prefijo.asc(), sufijo.asc().nullslast(), col.asc()]
```

Notas sobre `orden_natural_sql`:
- `regexp_replace(col, '\d+$', '')` → prefijo (`COMI-` para `COMI-1`/`COMI-10`; `Teórica` para
  nombres sin dígitos finales) → agrupa por prefijo y da el fallback alfabético (3.1).
- `nullif(regexp_replace(col, '^.*?(\d+)$', '\1'), col)` → si hay dígitos finales, deja sólo el
  número; si NO hay, el `regexp_replace` no matchea y devuelve `col` intacto, y `nullif(col, col)` =
  `NULL` → castea a `NULL` → `NULLS LAST` deja los alfabéticos ordenados por su prefijo (3.1).
- `col.asc()` final → desempate estable (3.2).

### Superficie 1 — Excel de cierre de cursada

**File**: `backend/app/services/excel_cierre_cursada.py`

**Function**: `_agrupar_por_comision`

**Specific Changes**:
1. Importar `from app.utils.orden_natural import natural_key`.
2. Cambiar la clave de orden para las comisiones reales de `nombre.casefold()` a
   `natural_key(nombre)`, manteniendo la tupla `(0, …)` para reales y `(1, …)` para el bucket
   "Sin comisión asignada" (que sigue yendo al final).

```python
def _clave_orden(item):
    nombre = item[0]
    if nombre == _SIN_COMISION:
        return (1, ())                 # siempre al final (3.4)
    return (0, natural_key(nombre))    # orden numérico natural (2.2), alfabético si no hay sufijo (3.1)
```

Nada más cambia: el mapeo `{titulo: [alumnos]}`, el título "{comisión} — Tutor: {tutor}", el orden
intra-bloque por `(apellido, nombre)` en `_escribir_detalle` (3.5) y los estilos quedan intactos.

### Superficie 2 — Listado / gestión de comisiones

**File**: `backend/app/repositories/comision_repository.py`

**Functions**: `get_all`, `get_by_materia`, `get_by_materia_con_tutores`, `get_by_tutor`

**Specific Changes** (importar `from app.utils.orden_natural import orden_natural_sql`):
1. `get_all`: reemplazar
   `query.order_by(Comision.anio.desc(), Comision.nombre.asc())` por
   `query.order_by(Comision.anio.desc(), *orden_natural_sql(Comision.nombre))`.
   El `anio desc` sigue PRIMERO (3.3); el `order_by` se aplica antes del `offset/limit` existente, así
   que la paginación y el `count` no cambian (3.7).
2. `get_by_materia` y `get_by_tutor`: reemplazar `Comision.nombre.asc()` por
   `*orden_natural_sql(Comision.nombre)`, conservando `Comision.anio.desc()` como primero.
3. `get_by_materia_con_tutores`: reemplazar `.order_by(Comision.nombre.asc())` por
   `.order_by(*orden_natural_sql(Comision.nombre))` (no tiene criterio de año; sin cambios ahí).

### Superficie 3 — Corrida de cierre (alumnos)

**File**: `backend/app/repositories/cierre_cursada_repository.py`

**Function**: `get_alumnos_de_run`

**Specific Changes**:
1. Importar `orden_natural_sql`.
2. Reemplazar `CierreCursadaAlumno.comision_nombre.asc().nullslast()` por
   `*orden_natural_sql(CierreCursadaAlumno.comision_nombre)`, conservando `apellido.asc()` y
   `nombre.asc()` como desempates finales.

```python
.order_by(
    *orden_natural_sql(CierreCursadaAlumno.comision_nombre),   # natural + NULLS LAST (2.3, 3.6)
    CierreCursadaAlumno.apellido.asc(),                        # intra-grupo (3.5)
    CierreCursadaAlumno.nombre.asc(),
)
```

`orden_natural_sql` ya incluye `NULLS LAST` en el sufijo; para garantizar que `comision_nombre = NULL`
(o "Sin comisión asignada") caiga al final, el prefijo de un `NULL` también es `NULL` → `NULLS LAST`
en el primer criterio del helper. Se documenta en tests (Property 5).

### Superficie 4 — Reporte de avance

**File**: `backend/app/repositories/avance_repository.py`

**Functions**: `get_alumnos_de_snapshot`, `get_alumnos_por_estado`

**Specific Changes**:
1. Importar `orden_natural_sql`.
2. En ambas funciones, reemplazar `AvanceAlumno.comision.asc().nullslast()` por
   `*orden_natural_sql(AvanceAlumno.comision)`, conservando `apellido.asc()` y `nombre.asc()`.

> **Detalle NULLS LAST (importante):** el `.nullslast()` actual está sobre la columna de comisión.
> Con el helper, el orden natural antepone `prefijo` (que es `NULL` para comisión nula). Para
> mantener el comportamiento "nulos al final", `orden_natural_sql` aplica `.nullslast()` tanto al
> prefijo como al sufijo. Si se prefiere una garantía explícita, el caller puede anteponer
> `col.is_(None).asc()` (los `False`=0 antes que `True`=1). El diseño elige la primera opción
> (helper autónomo) por DRY; los tests de preservación (Property 5) lo verifican en ambas columnas.

## Testing Strategy

### Validation Approach

Enfoque en dos fases: primero exponer contraejemplos que demuestren el orden incorrecto sobre el
código sin arreglar, y luego verificar que el fix ordena naturalmente y preserva lo demás. El grueso
de la validación es sobre la función PURA `natural_key` (donde vive la lógica que puede calcularse
mal) más tests de integración a nivel repositorio para el orden SQL y la paginación.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples que demuestren el orden textual ANTES del fix; confirmar la causa
raíz (comparación como `str`). Si se refuta, re-hipotetizar.

**Test Plan**: Ejercitar el sort actual (Excel y `order_by`) con nombres de distinta longitud de
sufijo y observar el orden defectuoso.

**Test Cases**:
1. **Excel (superficie 1)**: alumnos en `COMI-1, COMI-2, COMI-10, COMI-20` → hoy
   `_agrupar_por_comision` devuelve las claves `COMI-1, COMI-10, COMI-2, COMI-20` (fallará hasta el
   fix); esperado `COMI-1, COMI-2, COMI-10, COMI-20`.
2. **Listado (superficie 2)**: comisiones del mismo año `COMI-2` y `COMI-10` → hoy `get_all` devuelve
   `COMI-10` antes de `COMI-2`; esperado `COMI-2` antes de `COMI-10`.
3. **Corrida de cierre (superficie 3)**: alumnos con `comision_nombre` `M26 C1-02` y `M26 C1-10` →
   hoy `…-10` antes de `…-02`; esperado `…-02` antes de `…-10`.
4. **Avance (superficie 4)**: `AvanceAlumno.comision` `COMI-3` y `COMI-21` → hoy `COMI-21` antes de
   `COMI-3`; esperado `COMI-3` antes de `COMI-21`.
5. **Edge — fallback alfabético (no bug)**: `Teórica, Práctica` → orden alfabético, igual hoy y tras
   el fix.

**Expected Counterexamples**:
- El sort/`order_by` ubica `COMI-10` antes de `COMI-2` en las cuatro superficies.
- Causa confirmada: comparación textual del nombre (sin extraer el sufijo numérico como entero).

### Fix Checking

**Goal**: Verificar que para todo input donde vale la condición de bug, el orden resultante es el
numérico natural.

**Pseudocode:**
```
FOR ALL nombres WHERE isBugCondition(nombres) DO
  ASSERT SORT(nombres, key=natural_key) == orden_numerico_natural(nombres)
  # A nivel repositorio (mismo contrato vía orden_natural_sql):
  ASSERT [c.nombre FOR c IN get_all(...).items] == orden_numerico_natural_dentro_de_cada(anio)
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todo input donde NO vale la condición de bug, el resultado es idéntico
al actual.

**Pseudocode:**
```
FOR ALL nombres WHERE NOT isBugCondition(nombres) DO
  ASSERT SORT(nombres, key=natural_key) == SORT(nombres, key=casefold)   # alfabético (3.1)
END FOR

# Listado: mismo conjunto de filas y mismo total para cualquier filtro/paginación (3.3, 3.7)
FOR ALL filtros, pagina DO
  ASSERT set(get_all_fixed(filtros, pagina).items) ⊆ set(comisiones que cumplen filtros)
  ASSERT get_all_fixed(filtros).total == get_all_original(filtros).total
  ASSERT primer criterio de orden == anio desc
END FOR

# Nulos y "Sin comisión asignada" al final; intra-bloque por (apellido, nombre) (3.4, 3.5, 3.6)
ASSERT bloque("Sin comisión asignada") es el último del Excel
ASSERT filas con comision NULL quedan al final del reporte
```

**Testing Approach**: Property-based testing para `natural_key` (orden y fallback) y tests de
integración con BD (o repositorio con datos sembrados) para el orden SQL y la corrección de la
paginación, que un test unitario puro no cubre.

**Test Plan**: Observar el comportamiento actual para inputs no-bug (nombres alfabéticos, un solo
dígito, filtros/paginación, nulos) y escribir tests que lo capturen.

**Test Cases**:
1. **Alfabético (3.1)**: nombres sin sufijo numérico → mismo orden que `casefold`.
2. **Año primario (3.3)**: comisiones de 2025 y 2024 → todas las de 2025 primero, luego 2024, cada
   grupo en orden natural.
3. **Paginación (3.7)**: `per_page=2` sobre `COMI-1..COMI-12` → las páginas concatenadas dan el orden
   natural completo (no páginas reordenadas), y `total` no cambia.
4. **Filtros (3.7)**: filtrar por materia/tutor/coordinador/año no altera el conjunto devuelto.
5. **Sin comisión al final (3.4)**: Excel con bloque "Sin comisión asignada" → último.
6. **Intra-bloque (3.5)**: dentro de un bloque, alumnos por `(apellido, nombre)`.
7. **Nulos (3.6)**: filas con `comision`/`comision_nombre` NULL → al final del reporte.

### Unit Tests

- `natural_key`: `COMI-2 < COMI-10 < COMI-27`; distintos prefijos (`A-1 < B-2`); nombres alfabéticos
  puros (orden = `casefold`); case-insensitive (`comi-2` = `COMI-2`); número embebido no final
  (`COMI-1A` → tratado como texto); nombre vacío / `None` (no rompe, cae al final).
- `orden_natural_sql`: devuelve 3 expresiones; el prefijo usa `lower`; el sufijo castea a `Integer`
  con `NULLS LAST`; el desempate final es la columna completa. (Verificable compilando la expresión o
  con integración.)
- `_agrupar_por_comision` (superficie 1): bloques `COMI-1, COMI-2, COMI-10` en orden natural;
  "Sin comisión asignada" último; una sola comisión (orden ya correcto); título con tutor intacto.

### Property-Based Tests

- **Orden natural (Property 1)**: generar listas de nombres `PREFIJO-<n>` con `n` aleatorios y
  prefijos aleatorios → `sorted(nombres, key=natural_key)` agrupa por prefijo y, dentro de cada
  prefijo, deja los `n` en orden entero creciente.
- **Fallback alfabético (Property 2)**: generar nombres SIN sufijo numérico →
  `sorted(nombres, key=natural_key) == sorted(nombres, key=str.casefold)`.
- **Estabilidad / desempate (Property 4)**: generar nombres con duplicados / mismos `(prefijo, n)` →
  el orden es determinista y estable (empata por el nombre completo).
- **Nulls last (Property 5)**: generar listas mezclando `None` y nombres → las claves de `None`
  quedan estrictamente al final.

### Integration Tests

- **Listado (superficie 2)**: sembrar comisiones `COMI-1..COMI-12` (dos años) y verificar que
  `get_all` las devuelve en `anio desc` + orden natural, con paginación (`per_page`) coherente y
  `total` correcto; repetir con filtros por materia/tutor/coordinador.
- **`get_by_materia` / `get_by_materia_con_tutores` / `get_by_tutor`**: devuelven orden natural.
- **Corrida de cierre (superficie 3)**: `get_alumnos_de_run` con alumnos en `M26 C1-01..C1-10` (y
  algunos sin comisión) → orden natural por comisión, nulos al final, luego `(apellido, nombre)`.
- **Avance (superficie 4)**: `get_alumnos_de_snapshot` y `get_alumnos_por_estado` con comisiones
  `COMI-2..COMI-11` (y nulos) → orden natural, nulos al final.
- **Excel de cierre (superficie 1)**: generar el `.xlsx` con varias comisiones de distinta longitud
  de sufijo → los bloques salen en orden natural y "Sin comisión asignada" al final.
