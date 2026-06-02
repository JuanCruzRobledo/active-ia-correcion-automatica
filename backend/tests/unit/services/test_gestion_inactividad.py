"""Tests de las bandas de inactividad (app/services/gestion_inactividad.py).

T3 del PLAN_GESTION.md. Modelo CORREGIDO por el usuario: bandas CERRADAS, NO
acumulativas. "1 mes" trae SOLO 30-59 días (no los de 2 meses ni los que nunca
entraron). "2 meses" es el único catch-all (60+). "Nunca" es categoría aparte.
"""

import pytest

from app.services.gestion_inactividad import (
    NUNCA,
    RANGO,
    coincide_inactividad,
    dias_inactividad,
)

NOW = 1_700_000_000  # epoch fijo para los tests (se pasa explícito, no se usa el reloj)


def _lca(dias: int) -> int:
    """lastcourseaccess que corresponde a `dias` de inactividad respecto de NOW."""
    return NOW - dias * 86_400


# --- dias_inactividad ---------------------------------------------------------

@pytest.mark.parametrize(
    "lastcourseaccess,esperado",
    [
        (0, None),              # nunca entró
        (None, None),           # sin dato
        (NOW, 0),               # entró recién
        (_lca(1), 1),
        (_lca(45), 45),
    ],
)
def test_dias_inactividad(lastcourseaccess, esperado):
    assert dias_inactividad(lastcourseaccess, NOW) == esperado


# --- bandas (bordes) ----------------------------------------------------------

@pytest.mark.parametrize(
    "tipo,dias,esperado",
    [
        ("1_dia", 0, False), ("1_dia", 1, True), ("1_dia", 2, False),
        ("2_dias", 1, False), ("2_dias", 2, True), ("2_dias", 6, True), ("2_dias", 7, False),
        ("1_semana", 6, False), ("1_semana", 7, True), ("1_semana", 13, True), ("1_semana", 14, False),
        ("2_semanas", 13, False), ("2_semanas", 14, True), ("2_semanas", 20, True), ("2_semanas", 21, False),
        ("3_semanas", 20, False), ("3_semanas", 21, True), ("3_semanas", 29, True), ("3_semanas", 30, False),
        ("1_mes", 29, False), ("1_mes", 30, True), ("1_mes", 59, True), ("1_mes", 60, False),
        ("2_meses", 59, False), ("2_meses", 60, True), ("2_meses", 365, True),  # catch-all
    ],
)
def test_bandas_cerradas(tipo, dias, esperado):
    assert coincide_inactividad(_lca(dias), NOW, tipo) is esperado


# --- "Nunca" es categoría aparte (núcleo del pedido del usuario) --------------

def test_nunca_matchea_solo_a_los_que_nunca_entraron():
    assert coincide_inactividad(0, NOW, NUNCA) is True
    assert coincide_inactividad(_lca(500), NOW, NUNCA) is False  # entró hace 500 días: NO es "nunca"


@pytest.mark.parametrize("tipo", ["1_dia", "1_mes", "2_meses"])
def test_nunca_no_cae_en_ninguna_banda_de_dias(tipo):
    # lastcourseaccess == 0 (nunca entró) NO debe matchear ninguna banda de días,
    # ni siquiera el catch-all de "2 meses".
    assert coincide_inactividad(0, NOW, tipo) is False


def test_rango_custom_es_inclusivo():
    # "de 45 a 60 días" → incluye 45 y 60, excluye 44 y 61.
    assert coincide_inactividad(_lca(44), NOW, RANGO, desde=45, hasta=60) is False
    assert coincide_inactividad(_lca(45), NOW, RANGO, desde=45, hasta=60) is True
    assert coincide_inactividad(_lca(60), NOW, RANGO, desde=45, hasta=60) is True
    assert coincide_inactividad(_lca(61), NOW, RANGO, desde=45, hasta=60) is False


def test_rango_no_incluye_a_los_que_nunca_entraron():
    assert coincide_inactividad(0, NOW, RANGO, desde=0, hasta=99999) is False
