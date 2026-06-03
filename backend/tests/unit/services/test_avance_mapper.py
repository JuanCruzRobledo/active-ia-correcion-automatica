"""
Tests de avance_mapper — lógica PURA de mapeo unidad↔sección (Dashboard de Gestores, T4/T5).

TDD RED→GREEN: estas funciones son el núcleo del cálculo de avance, sin I/O.
Datos basados en la estructura real del curso 38 (spike T0, §6.1 del plan).
"""

import pytest

from app.models.enums import EstadoAvanceEnum
from app.services.avance_mapper import (
    calcular_avance_alumno,
    clasificar_estado,
    detectar_cabeceras,
    section_num_de_cmid,
    unidad_alcanzada,
    unidad_de_section_num,
)


# Subconjunto realista de secciones (como las devuelve core_course_get_contents)
SECCIONES = [
    {"id": 2597, "section": 0, "name": "PROGRAMACION I - General", "modules": [
        {"id": 11142, "modname": "forum", "completion": 0},
    ]},
    {"id": 2598, "section": 1, "name": "1- Estructuras Secuenciales", "modules": [
        {"id": 11154, "modname": "label", "completion": 0},
    ]},
    {"id": 2599, "section": 2, "name": "Actividades 🧩", "modules": [
        {"id": 11158, "modname": "label", "completion": 1},
    ]},
    {"id": 2600, "section": 3, "name": "Práctica 💻", "modules": [
        {"id": 11169, "modname": "assign", "completion": 0},  # "Actividad de cierre unidad 1"
    ]},
    {"id": 2610, "section": 7, "name": "2- Estructuras Condicionales", "modules": []},
    {"id": 2649, "section": 58, "name": "10- Recursividad", "modules": [
        {"id": 11344, "modname": "label", "completion": 0},
    ]},
    {"id": 2650, "section": 59, "name": "Actividades 🚀", "modules": [
        {"id": 11349, "modname": "quiz", "completion": 2},
    ]},
    {"id": 2657, "section": 64, "name": "Trabajo Integrador Obligatorio", "modules": [
        {"id": 11386, "modname": "page", "completion": 2},
    ]},
]


# ===================== detectar_cabeceras =====================


def test_detecta_cabeceras_por_patron_numero_guion():
    cabeceras = detectar_cabeceras(SECCIONES)
    # Solo "1-", "2-", "10-" son cabeceras
    numeros = [c["numero"] for c in cabeceras]
    assert numeros == [1, 2, 10]  # ordenado por numero


def test_cabeceras_traen_section_id_y_nombre():
    cabeceras = detectar_cabeceras(SECCIONES)
    u1 = next(c for c in cabeceras if c["numero"] == 1)
    assert u1["moodle_section_id"] == 2598
    assert u1["section"] == 1
    assert "Estructuras Secuenciales" in u1["nombre"]


def test_ignora_general_actividades_y_no_cabeceras():
    cabeceras = detectar_cabeceras(SECCIONES)
    nombres = [c["nombre"] for c in cabeceras]
    assert not any("General" in n for n in nombres)
    assert not any(n.startswith("Actividades") for n in nombres)
    assert not any("Integrador" in n for n in nombres)


def test_multidigito_diez():
    cabeceras = detectar_cabeceras(SECCIONES)
    u10 = next(c for c in cabeceras if c["numero"] == 10)
    assert u10["moodle_section_id"] == 2649


def test_detecta_formato_unidad_dos_puntos():
    # Organización Empresarial usa "Unidad N: Tema" en vez de "N- Tema".
    secs = [
        {"id": 1, "section": 1, "name": "Unidad 1: Teoría de Sistemas", "modules": []},
        {"id": 2, "section": 2, "name": "Material de apoyo", "modules": []},
        {"id": 3, "section": 3, "name": "Unidad 2 - Estructura organizacional", "modules": []},
    ]
    cabeceras = detectar_cabeceras(secs)
    assert [c["numero"] for c in cabeceras] == [1, 2]
    assert all("Material" not in c["nombre"] for c in cabeceras)


# ===================== section_num_de_cmid =====================


def test_section_num_de_cmid_mapea_modulo_a_su_seccion():
    mapa = section_num_de_cmid(SECCIONES)
    assert mapa[11169] == 3   # "Actividad de cierre unidad 1" → Práctica (section# 3)
    assert mapa[11349] == 59  # quiz en Actividades de U10 → section# 59
    assert mapa[11386] == 64  # Trabajo Integrador → section# 64


# ===================== unidad_de_section_num =====================

# cabeceras (numero, section#) ordenadas: U1@1, U2@7, U10@58
CABECERAS = [(1, 1), (2, 7), (10, 58)]


def test_unidad_de_section_num_cae_en_cabecera_anterior():
    # section# 3 (Práctica U1) → Unidad 1
    assert unidad_de_section_num(3, CABECERAS, tope_section_num=64) == 1
    # section# 59 (Actividades de U10) → Unidad 10
    assert unidad_de_section_num(59, CABECERAS, tope_section_num=64) == 10


def test_seccion_antes_de_primera_cabecera_no_cuenta():
    # section# 0 (General) → no hay unidad
    assert unidad_de_section_num(0, CABECERAS, tope_section_num=64) is None


def test_seccion_en_o_despues_del_tope_no_cuenta():
    # section# 64 (Trabajo Integrador) y posteriores → no cuentan (parciales/integrador)
    assert unidad_de_section_num(64, CABECERAS, tope_section_num=64) is None
    assert unidad_de_section_num(66, CABECERAS, tope_section_num=64) is None


def test_sin_tope_la_ultima_unidad_absorbe_el_resto():
    # tope=None → section# 64 cae en la última unidad (U10)
    assert unidad_de_section_num(64, CABECERAS, tope_section_num=None) == 10


# ===================== unidad_alcanzada =====================

# cmid → section#: 11=U1(sec3), 22=U2(sec8 — Actividades de U2), 33=integrador(sec64)
SECTION_NUM_POR_CMID = {11: 3, 22: 8, 33: 64}
CABECERAS_2 = [(1, 1), (2, 7)]


def test_unidad_alcanzada_toma_la_maxima_completada():
    statuses = [
        {"cmid": 11, "state": 2, "timecompleted": 100},  # U1 completa-aprobada
        {"cmid": 22, "state": 1, "timecompleted": 200},  # U2 completa
    ]
    assert (
        unidad_alcanzada(statuses, SECTION_NUM_POR_CMID, CABECERAS_2, tope_section_num=64)
        == 2
    )


def test_unidad_alcanzada_ignora_incompletas():
    statuses = [
        {"cmid": 11, "state": 2, "timecompleted": 100},
        {"cmid": 22, "state": 0, "timecompleted": 0},  # incompleta → no cuenta
    ]
    assert (
        unidad_alcanzada(statuses, SECTION_NUM_POR_CMID, CABECERAS_2, tope_section_num=64)
        == 1
    )


def test_unidad_alcanzada_ignora_actividades_sobre_el_tope():
    statuses = [
        {"cmid": 11, "state": 1, "timecompleted": 100},
        {"cmid": 33, "state": 1, "timecompleted": 500},  # integrador (>= tope) → no cuenta
    ]
    assert (
        unidad_alcanzada(statuses, SECTION_NUM_POR_CMID, CABECERAS_2, tope_section_num=64)
        == 1
    )


def test_unidad_alcanzada_sin_completadas_devuelve_none():
    statuses = [{"cmid": 11, "state": 0, "timecompleted": 0}]
    assert (
        unidad_alcanzada(statuses, SECTION_NUM_POR_CMID, CABECERAS_2, tope_section_num=64)
        is None
    )


def test_unidad_alcanzada_cuenta_completa_reprobada():
    # state 3 = completa-reprobada → el alumno SÍ realizó la actividad, cuenta para el avance
    statuses = [{"cmid": 22, "state": 3, "timecompleted": 200}]  # U2, reprobada
    assert (
        unidad_alcanzada(statuses, SECTION_NUM_POR_CMID, CABECERAS_2, tope_section_num=64)
        == 2
    )


# ===================== clasificar_estado =====================


@pytest.mark.parametrize(
    "alcanzada,actual,esperado",
    [
        (None, 5, EstadoAvanceEnum.SIN_ACTIVIDAD),
        (5, 5, EstadoAvanceEnum.AL_DIA),      # delta 0
        (6, 5, EstadoAvanceEnum.AL_DIA),      # superó (delta negativo)
        (4, 5, EstadoAvanceEnum.RIESGO_MEDIO),  # delta 1
        (3, 5, EstadoAvanceEnum.RIESGO_ALTO),   # delta 2
        (1, 5, EstadoAvanceEnum.RIESGO_ALTO),   # delta 4
    ],
)
def test_clasificar_estado(alcanzada, actual, esperado):
    assert clasificar_estado(alcanzada, actual) == esperado


# ===================== calcular_avance_alumno (integración pura) =====================

SECCIONES_CALC = [
    {"id": 100, "section": 1, "name": "1- Uno", "modules": [
        {"id": 11, "modname": "assign", "name": "Actividad de cierre unidad 1", "completion": 2},
    ]},
    {"id": 200, "section": 7, "name": "2- Dos", "modules": [
        {"id": 22, "modname": "quiz", "name": "Cuestionario U2", "completion": 2},
        {"id": 23, "modname": "assign", "name": "Actividad de cierre unidad 2", "completion": 2},
    ]},
]
# Cabeceras de las UNIDADES configuradas: (numero, moodle_section_id de la cabecera)
CABECERAS_CALC = [(1, 100), (2, 200)]


def test_calcular_avance_alumno_al_dia_con_actividad_actual():
    statuses = [
        {"cmid": 11, "state": 2, "timecompleted": 100},
        {"cmid": 22, "state": 1, "timecompleted": 300},
        {"cmid": 23, "state": 1, "timecompleted": 400},  # más reciente en U2
    ]
    r = calcular_avance_alumno(
        statuses, SECCIONES_CALC, CABECERAS_CALC, unidad_actual=2, tope_section_id=None
    )
    assert r["unidad_alcanzada"] == 2
    assert r["estado"] == EstadoAvanceEnum.AL_DIA
    assert r["actividad_actual_unidad"] == 2
    # la actividad de mayor timecompleted en la unidad alcanzada
    assert r["actividad_actual_nombre"] == "Actividad de cierre unidad 2"
    assert r["actividad_actual_desaprobada"] is False  # state 1 → aprobada


def test_calcular_avance_alumno_sin_actividad():
    statuses = [{"cmid": 11, "state": 0, "timecompleted": 0}]
    r = calcular_avance_alumno(
        statuses, SECCIONES_CALC, CABECERAS_CALC, unidad_actual=2, tope_section_id=None
    )
    assert r["unidad_alcanzada"] is None
    assert r["estado"] == EstadoAvanceEnum.SIN_ACTIVIDAD
    assert r["actividad_actual_nombre"] is None
    assert r["actividad_actual_desaprobada"] is False


def test_calcular_avance_alumno_marca_actividad_desaprobada():
    # Llegó a U2 pero su actividad más reciente quedó reprobada (state 3)
    statuses = [
        {"cmid": 11, "state": 2, "timecompleted": 100},  # U1 aprobada
        {"cmid": 23, "state": 3, "timecompleted": 400},  # U2 reprobada (más reciente)
    ]
    r = calcular_avance_alumno(
        statuses, SECCIONES_CALC, CABECERAS_CALC, unidad_actual=2, tope_section_id=None
    )
    assert r["unidad_alcanzada"] == 2  # cuenta aunque reprobó
    assert r["actividad_actual_nombre"] == "Actividad de cierre unidad 2"
    assert r["actividad_actual_desaprobada"] is True
