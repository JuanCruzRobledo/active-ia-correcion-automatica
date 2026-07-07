"""
Tests unitarios del módulo compartido `app.utils.orden_natural` (bugfix
comision-orden-numerico-fix, tarea 3.1).

Cubre `natural_key` (clave de orden en Python) y `orden_natural_sql` (expresiones
`ORDER BY` de SQLAlchemy), según design.md → "Nuevo módulo compartido" y el listado de
Unit Tests de la sección "Testing Strategy".

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.6**
"""

from hypothesis import given, strategies as st
from sqlalchemy import Column, String, Integer as SAInteger, cast
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.expression import UnaryExpression

from app.utils.orden_natural import natural_key, orden_natural_sql


# ============================================================================
# natural_key
# ============================================================================


def test_natural_key_orden_numerico_dentro_del_mismo_prefijo():
    """COMI-2 < COMI-10 < COMI-27 -- el sufijo numérico se compara como entero, no
    como texto. **Validates: Requirements 2.1, 2.2, 2.3, 2.4**"""
    nombres = ["COMI-27", "COMI-2", "COMI-10"]
    assert sorted(nombres, key=natural_key) == ["COMI-2", "COMI-10", "COMI-27"]


def test_natural_key_distintos_prefijos_agrupan_por_prefijo_primero():
    """A-1 < B-2 -- el prefijo alfabético tiene prioridad sobre el sufijo numérico
    (se agrupa por prefijo antes de comparar el número)."""
    nombres = ["B-2", "A-1"]
    assert sorted(nombres, key=natural_key) == ["A-1", "B-2"]


def test_natural_key_nombres_alfabeticos_puros_orden_igual_a_casefold():
    """Nombres sin sufijo numérico -- el orden resultante es idéntico a
    `sorted(nombres, key=str.casefold)` (fallback alfabético, Preservation 3.1).
    **Validates: Requirements 3.1**"""
    nombres = ["Teórica", "Práctica", "Laboratorio"]
    assert sorted(nombres, key=natural_key) == sorted(nombres, key=str.casefold)


def test_natural_key_case_insensitive():
    """comi-2 y COMI-2 deben producir la MISMA clave (case-insensitive)."""
    assert natural_key("comi-2") == natural_key("COMI-2")


def test_natural_key_numero_embebido_no_final_no_rompe_el_orden():
    """Un número embebido que no es el sufijo final (`COMI-1A`) sigue tokenizándose
    en fragmentos texto/dígitos (mismo contrato que el resto del nombre) y no rompe la
    comparación: el fragmento de texto final ('a') se compara como texto normal tras
    el fragmento numérico."""
    clave = natural_key("COMI-1A")
    # Los índices pares son texto (0, ...), los impares son dígitos (1, ...).
    assert clave == ((0, "comi-"), (1, 1), (0, "a"))
    # No lanza excepción y sigue siendo comparable con otras claves.
    assert natural_key("COMI-1A") < natural_key("COMI-2")


def test_natural_key_none_ordena_al_final():
    """`None` cae estrictamente al final de cualquier nombre real.
    **Validates: Requirements 3.6**"""
    nombres_y_none: list[str | None] = ["COMI-2", None, "COMI-1"]
    ordenado = sorted(nombres_y_none, key=natural_key)
    assert ordenado == ["COMI-1", "COMI-2", None]


def test_natural_key_nombre_vacio_no_rompe():
    """Nombre vacío no lanza excepción y produce una clave comparable, distinta de la
    clave de `None` (no cae al final por ser vacío, sólo por ser `None`)."""
    assert natural_key("") == ((0, ""),)
    assert natural_key("") < natural_key(None)


@given(
    prefijo=st.sampled_from(["COMI", "A", "M26 C1"]),
    numeros=st.lists(st.integers(min_value=0, max_value=9999), min_size=2, max_size=8, unique=True),
)
def test_prop_natural_key_orden_entero_para_cualquier_lista_de_numeros(prefijo, numeros):
    """Para cualquier lista de números (mismo prefijo), `sorted(key=natural_key)`
    produce el mismo orden que ordenar los enteros directamente.
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**"""
    nombres = [f"{prefijo}-{n}" for n in numeros]
    ordenado = sorted(nombres, key=natural_key)
    numeros_ordenados = sorted(numeros)
    assert ordenado == [f"{prefijo}-{n}" for n in numeros_ordenados]


@given(
    nombres=st.lists(
        st.sampled_from(["Teórica", "Práctica", "Laboratorio", "Alfa", "Beta", "gamma", "ZETA"]),
        unique=True,
        min_size=1,
        max_size=6,
    )
)
def test_prop_natural_key_fallback_alfabetico_para_cualquier_lista_sin_sufijo(nombres):
    """Para cualquier lista de nombres sin sufijo numérico, `natural_key` degrada al
    orden alfabético actual (`casefold`). **Validates: Requirements 3.1**"""
    assert sorted(nombres, key=natural_key) == sorted(nombres, key=str.casefold)


# ============================================================================
# orden_natural_sql
# ============================================================================


_col = Column("nombre", String)


def test_orden_natural_sql_devuelve_tres_expresiones():
    """`orden_natural_sql` devuelve una lista de exactamente 3 expresiones ORDER BY."""
    expresiones = orden_natural_sql(_col)
    assert isinstance(expresiones, list)
    assert len(expresiones) == 3
    for expr in expresiones:
        assert isinstance(expr, (ColumnElement, UnaryExpression))


def test_orden_natural_sql_prefijo_usa_lower_y_es_ascendente():
    """El primer criterio (prefijo) usa `lower()` (case-insensitive) y es ascendente."""
    prefijo_expr = orden_natural_sql(_col)[0]
    compilado = str(prefijo_expr.compile(compile_kwargs={"literal_binds": True}))
    assert "lower" in compilado.lower()
    assert "regexp_replace" in compilado.lower()
    assert compilado.strip().upper().endswith("ASC") or " ASC" in compilado.upper()


def test_orden_natural_sql_sufijo_castea_a_integer_con_nulls_last():
    """El segundo criterio (sufijo) castea a `Integer` y aplica `NULLS LAST`."""
    sufijo_expr = orden_natural_sql(_col)[1]
    compilado = str(sufijo_expr.compile(compile_kwargs={"literal_binds": True}))
    assert "nullif" in compilado.lower()
    assert "nulls last" in compilado.lower()


def test_orden_natural_sql_desempate_final_es_la_columna_completa():
    """El tercer criterio es la columna completa ascendente (desempate estable,
    Preservation 3.2). **Validates: Requirements 3.2**"""
    desempate_expr = orden_natural_sql(_col)[2]
    compilado = str(desempate_expr.compile(compile_kwargs={"literal_binds": True}))
    assert compilado.strip() == "nombre ASC" or compilado.strip().lower().startswith("nombre")


def test_orden_natural_sql_acepta_columna_casteada_o_expresion():
    """`orden_natural_sql` acepta cualquier `ColumnElement` (no sólo una `Column`
    directa), por ejemplo el resultado de un `cast`, sin lanzar excepción."""
    expr = cast(_col, String)
    expresiones = orden_natural_sql(expr)
    assert len(expresiones) == 3
