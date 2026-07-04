"""
Tests de los helpers puros de CierreCursadaService (parseo de porcentaje,
interpretación del TP en escala, resolución de comisión por grupo Moodle).

No cubren el flujo completo de generar() (requiere Moodle real/mock pesado) —
ver test_cierre_cursada_calculo.py para el árbol de decisión, que es lo que
de verdad no se puede calcular mal.
"""

from types import SimpleNamespace

import pytest

from app.services.cierre_cursada_service import (
    CierreCursadaService,
    _parse_pct,
    _tp_resultado,
)


# ===================== _parse_pct =====================


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("70,00 %", 70.0),
        ("70,00", 70.0),
        ("100,00 %", 100.0),
        ("-", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_pct(texto, esperado):
    assert _parse_pct(texto) == esperado


# ===================== _tp_resultado =====================


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Aprobado", "Aprobado"),
        ("Desaprobado", "Desaprobado"),
        ("-", "N/E"),
        ("", "N/E"),
        (None, "N/E"),
    ],
)
def test_tp_resultado(texto, esperado):
    assert _tp_resultado(texto) == esperado


# ===================== _resolver_comision =====================


def _comision(id_, nombre, moodle_group_code, tutores=()):
    return SimpleNamespace(id=id_, nombre=nombre, moodle_group_code=moodle_group_code, tutores=tutores)


def _tutor(nombre):
    return SimpleNamespace(tutor=SimpleNamespace(nombre=nombre))


def test_resolver_comision_match_unico():
    comisiones = [
        _comision(1, "Comisión 1", "PROG1-COM1", tutores=[_tutor("Ana Pérez")]),
        _comision(2, "Comisión 2", "PROG1-COM2"),
    ]
    cid, nombre, tutor = CierreCursadaService._resolver_comision(["PROG1-COM1"], comisiones)
    assert (cid, nombre, tutor) == (1, "Comisión 1", "Ana Pérez")


def test_resolver_comision_case_insensitive():
    comisiones = [_comision(1, "Comisión 1", "PROG1-COM1")]
    cid, _, _ = CierreCursadaService._resolver_comision(["prog1-com1"], comisiones)
    assert cid == 1


def test_resolver_comision_sin_match():
    comisiones = [_comision(1, "Comisión 1", "PROG1-COM1")]
    cid, nombre, tutor = CierreCursadaService._resolver_comision(["Otro Grupo"], comisiones)
    assert (cid, nombre, tutor) == (None, "Sin comisión asignada", None)


def test_resolver_comision_multiples_matches_no_rompe():
    # Alumno en dos grupos que matchean dos comisiones distintas -> ambiguo, sin comisión.
    comisiones = [
        _comision(1, "Comisión 1", "PROG1-COM1"),
        _comision(2, "Comisión 2", "PROG1-COM2"),
    ]
    cid, nombre, tutor = CierreCursadaService._resolver_comision(
        ["PROG1-COM1", "PROG1-COM2"], comisiones
    )
    assert (cid, nombre, tutor) == (None, "Sin comisión asignada", None)


def test_resolver_comision_multiples_tutores_se_unen_con_barra():
    comisiones = [
        _comision(1, "Comisión 1", "PROG1-COM1", tutores=[_tutor("Ana Pérez"), _tutor("Juan Gómez")]),
    ]
    _, _, tutor = CierreCursadaService._resolver_comision(["PROG1-COM1"], comisiones)
    assert tutor == "Ana Pérez / Juan Gómez"


def test_resolver_comision_sin_moodle_group_code_no_matchea():
    comisiones = [_comision(1, "Comisión 1", None)]
    cid, nombre, _ = CierreCursadaService._resolver_comision(["Cualquier Grupo"], comisiones)
    assert (cid, nombre) == (None, "Sin comisión asignada")
