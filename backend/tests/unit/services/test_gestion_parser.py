"""Tests de los parsers de grupo de Moodle (app/services/gestion_parser.py).

T2 del PLAN_GESTION.md. Los nombres reales (validados en el spike T0 contra
https://tup.sied.utn.edu.ar) son:
  - Comisión: "M26 C1-09"  (formato M{año} C{sem}-{NN})
  - Regional: "R-Mendoza", "R-Concepción del Uruguay", "R-La Plata"  (prefijo R-)
  - A ignorar: "Grupo_104", "NO_RINDIO_PRIMER_PARCIAL", "Cohorte Marzo 2026", "Z-FINAL-..."
"""

import pytest

from app.services.gestion_parser import (
    SIN_COMISION,
    SIN_REGIONAL,
    parse_comision,
    parse_regional,
    resolver_grupos_alumno,
)


# --- parse_comision -----------------------------------------------------------

@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("M26 C1-09", "M26 C1-09"),     # caso real típico (M = cohorte marzo)
        ("M25 C3-09", "M25 C3-09"),     # otro año/semestre
        ("M26 C1-27", "M26 C1-27"),     # comisión de dos dígitos altos
        ("A25 C2-01", "A25 C2-01"),     # A = cohorte agosto (Programación 2)
        ("A26 C1-05", "A26 C1-05"),     # agosto, otro año/comisión
        ("Grupo_104", None),            # grupo de trabajo → no es comisión
        ("R-Mendoza", None),            # regional → no es comisión
        ("Cohorte Marzo 2026", None),   # cohorte → no es comisión
        ("NO_RINDIO_PRIMER_PARCIAL", None),
        ("", None),
        ("M26C1-09", None),             # sin espacio: no matchea el formato real
    ],
)
def test_parse_comision(nombre, esperado):
    assert parse_comision(nombre) == esperado


# --- parse_regional -----------------------------------------------------------

@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("R-Mendoza", "Mendoza"),
        ("R-Concepción del Uruguay", "Concepción del Uruguay"),  # con espacios y tilde
        ("R-La Plata", "La Plata"),
        ("Requiere final OE", None),    # empieza con R pero NO con "R-"
        ("Grupo_2", None),
        ("M26 C1-09", None),
        ("R-", None),                   # prefijo sin nombre → no es regional válida
    ],
)
def test_parse_regional(nombre, esperado):
    assert parse_regional(nombre) == esperado


# --- resolver_grupos_alumno ---------------------------------------------------

def test_resolver_toma_regional_y_comision():
    grupos = ["M26 C1-09", "R-Mendoza", "Grupo_104"]
    assert resolver_grupos_alumno(grupos) == ("Mendoza", "M26 C1-09")


def test_resolver_sin_comision():
    grupos = ["R-Rosario", "Cohorte Marzo 2026"]
    assert resolver_grupos_alumno(grupos) == ("Rosario", SIN_COMISION)


def test_resolver_sin_regional():
    grupos = ["M26 C1-05", "Grupo_2"]
    assert resolver_grupos_alumno(grupos) == (SIN_REGIONAL, "M26 C1-05")


def test_resolver_solo_grupos_a_ignorar():
    grupos = ["Grupo_2", "NO_RINDIO_PRIMER_PARCIAL", "Z-FINAL-AYSO-01-08-25"]
    assert resolver_grupos_alumno(grupos) == (SIN_REGIONAL, SIN_COMISION)


def test_resolver_sin_grupos():
    assert resolver_grupos_alumno([]) == (SIN_REGIONAL, SIN_COMISION)


def test_resolver_toma_la_primera_de_cada_tipo():
    grupos = ["R-Mendoza", "R-Rosario", "M26 C1-01", "M26 C1-02"]
    assert resolver_grupos_alumno(grupos) == ("Mendoza", "M26 C1-01")
