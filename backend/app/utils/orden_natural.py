"""Orden natural (numeric-aware) para nombres de comisión ("COMI-2" antes de "COMI-10").

Un único contrato de orden expresado en dos formas equivalentes:
- natural_key(nombre): clave de orden para sort en Python (Excel de cierre).
- orden_natural_sql(col): expresiones ORDER BY de SQLAlchemy (repositorios; preserva
  la paginación, ya que el ORDER BY se aplica en la consulta, antes del OFFSET/LIMIT).

Semántica compartida (ver .kiro/specs/comision-orden-numerico-fix/design.md):
- Los dígitos se comparan como enteros (no como texto), de modo que "COMI-2" precede a
  "COMI-10".
- Los nombres sin sufijo numérico caen al orden alfabético (case-insensitive) actual —
  no hay regresión para ese caso (Preservation, Property 2).
- Un número embebido que NO está al final del nombre (p. ej. "COMI-1A") se trata como
  texto, no como sufijo numérico: sólo el sufijo NUMÉRICO FINAL del nombre se extrae
  para comparación entera.
- Valores nulos (columna SQL) o `None` (Python) quedan al final (NULLS LAST).

Esta es una utilidad PURA: sin reglas de negocio ni acceso a datos, reutilizable por
servicios (Excel) y repositorios (SQL).
"""
import re

from sqlalchemy import Integer, cast, func
from sqlalchemy.sql import ColumnElement

# Tokeniza en fragmentos alternados texto/dígitos, conservando los separadores
# (grupos capturados por re.split quedan incluidos en la lista resultante).
_DIGITOS = re.compile(r"(\d+)")


def natural_key(nombre: str | None) -> tuple:
    """Clave de orden natural para usar como `key=` de `sorted`/`list.sort` en Python.

    Tokeniza `casefold(nombre)` en fragmentos de texto y de dígitos. Cada fragmento se
    convierte en un par `(0, texto)` (fragmento de texto) o `(1, numero)` (fragmento de
    dígitos, comparado como entero) para que la comparación entre tuplas nunca mezcle
    tipos (`str` vs `int`) en la misma posición.

    - `None` ordena estrictamente al final de cualquier nombre real: se usa `(2, "")`
      como único elemento de la tupla, y ningún nombre real produce un elemento con
      prioridad `2` en la primera posición (los fragmentos de texto usan `0`, los de
      dígitos usan `1`), así que `natural_key(None)` es siempre mayor que la clave de
      cualquier nombre no nulo.
    - Un nombre vacío (`""`) produce la tupla `((0, ""),)` — no es `None`, así que no
      cae al final; sencillamente ordena junto a otros nombres vacíos/vacíos-de-texto.
    """
    if nombre is None:
        return ((2, ""),)

    fragmentos = _DIGITOS.split(nombre.casefold())
    clave: list[tuple[int, object]] = []
    for i, fragmento in enumerate(fragmentos):
        if i % 2 == 1:
            # Los índices impares son los grupos capturados por _DIGITOS (dígitos).
            clave.append((1, int(fragmento)))
        elif fragmento:
            # Los índices pares son texto; se descartan los fragmentos vacíos que
            # aparecen cuando el nombre empieza o termina con un grupo de dígitos.
            clave.append((0, fragmento))

    return tuple(clave) or ((0, ""),)


def orden_natural_sql(col: ColumnElement) -> list:
    """Expresiones `ORDER BY` de SQLAlchemy que reproducen `natural_key` a nivel
    PostgreSQL, para usar en `query.order_by(*orden_natural_sql(columna), ...)`.

    Devuelve, en orden de prioridad, LOS TRES términos con `NULLS LAST` explícito
    (no implícito/dependiente del motor de base de datos — ver nota más abajo):
    1. Prefijo (nombre sin el sufijo numérico final) en minúsculas, ascendente,
       `NULLS LAST` — agrupa por prefijo y da el fallback alfabético para nombres sin
       sufijo numérico (Preservation 3.1).
    2. Sufijo numérico final casteado a `Integer`, ascendente, `NULLS LAST` — orden
       numérico dentro de cada prefijo; si el nombre no termina en dígitos, este valor
       es `NULL` y el `NULLS LAST` lo deja después de los que sí tienen sufijo, dentro
       del mismo prefijo.
    3. La columna completa, ascendente, `NULLS LAST` — desempate estable final
       (Preservation 3.2).

    Nota (por qué `NULLS LAST` explícito en LOS TRES términos, no sólo el sufijo):
    cuando `col` es `NULL` (comisión no asignada), los TRES términos evalúan a `NULL`
    (`regexp_replace(NULL, ...)` es `NULL`, así que tanto el prefijo como el sufijo lo
    son, y `col` mismo es `NULL`). El orden ASC por defecto de PostgreSQL ubica los
    `NULL` al final, así que omitir `.nullslast()` en el prefijo y en el desempate
    final "funciona" hoy por ese default — pero es un comportamiento IMPLÍCITO del
    motor, no garantizado por el código. Aplicar `.nullslast()` explícitamente a los
    tres términos hace que la garantía de Property 5 (NULLS LAST) sea parte del
    contrato de la función, independiente del motor de base de datos.

    Notas de implementación (ver design.md → "Nuevo módulo compartido"):
    - `regexp_replace(col, '\\d+$', '')` extrae el prefijo: para "COMI-1"/"COMI-10" es
      "COMI-"; para un nombre sin dígitos finales (p. ej. "Teórica") es el nombre
      completo sin cambios.
    - `nullif(regexp_replace(col, '^.*?(\\d+)$', '\\1'), col)`: si el nombre termina en
      dígitos, `regexp_replace` devuelve sólo esos dígitos (que son distintos de
      `col`, así que `nullif` no anula); si NO termina en dígitos, el patrón no
      matchea y `regexp_replace` devuelve `col` sin cambios, por lo que
      `nullif(col, col)` es `NULL` — de ahí el cast a `Integer` con `NULLS LAST`.
    - Un número embebido no-final (p. ej. "COMI-1A") no matchea `\\d+$`, así que se
      trata como texto puro (prefijo = nombre completo, sufijo = NULL).

    Esta función usa expresiones de regex de PostgreSQL (`regexp_replace`) y NO es
    portable a otros motores de base de datos (el proyecto ya está atado a
    PostgreSQL).
    """
    prefijo = func.lower(func.regexp_replace(col, r"\d+$", ""))
    sufijo = cast(
        func.nullif(func.regexp_replace(col, r"^.*?(\d+)$", r"\1"), col),
        Integer,
    )
    return [prefijo.asc().nullslast(), sufijo.asc().nullslast(), col.asc().nullslast()]
