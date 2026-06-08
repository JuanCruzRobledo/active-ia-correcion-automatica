"""
Tests de avance_mapper — lógica PURA (componentes DINÁMICOS por unidad, §9.bis F).

Cada componente declara su `fuente`:
  - CALIFICACION: por nota (estado_tp). Deuda si ≠ aprobado.
  - SEGUIMIENTO: por completion. Deuda si state 0.
La lógica depende de la FUENTE, no del tipo (TP/QUIZ/AUTOEVALUACION/CIERRE = etiqueta).
unidad alcanzada = la más alta con ≥1 componente realizado.
"""

import pytest

from app.models.enums import EstadoAvanceEnum
from app.services.avance_mapper import (
    calcular_actividades_faltantes,
    calcular_avance_alumno,
    calcular_deudas_y_alcance,
    clasificar_estado,
    detectar_cabeceras,
    estado_tp,
    section_num_de_cmid,
    unidad_de_section_num,
)


SECCIONES = [
    {"id": 2598, "section": 1, "name": "1- Estructuras Secuenciales", "modules": [
        {"id": 11154, "modname": "label", "completion": 0},
    ]},
    {"id": 2599, "section": 2, "name": "Actividades 🧩", "modules": [
        {"id": 11169, "modname": "assign", "completion": 2},
    ]},
    {"id": 2610, "section": 7, "name": "2- Estructuras Condicionales", "modules": []},
    {"id": 2649, "section": 58, "name": "10- Recursividad", "modules": []},
]


# ===================== helpers de secciones (ABM) =====================


def test_detecta_cabeceras_por_patron_numero_guion():
    assert [c["numero"] for c in detectar_cabeceras(SECCIONES)] == [1, 2, 10]


def test_detecta_formato_unidad_dos_puntos():
    secs = [
        {"id": 1, "section": 1, "name": "Unidad 1: Teoría de Sistemas", "modules": []},
        {"id": 3, "section": 3, "name": "Unidad 2 - Estructura", "modules": []},
    ]
    assert [c["numero"] for c in detectar_cabeceras(secs)] == [1, 2]


def test_section_num_de_cmid():
    assert section_num_de_cmid(SECCIONES)[11169] == 2


def test_unidad_de_section_num():
    cabeceras = [(1, 1), (2, 7), (10, 58)]
    assert unidad_de_section_num(2, cabeceras, tope_section_num=64) == 1
    assert unidad_de_section_num(0, cabeceras) is None


@pytest.mark.parametrize(
    "alcanzada,actual,esperado",
    [
        (None, 5, EstadoAvanceEnum.SIN_ACTIVIDAD),
        (5, 5, EstadoAvanceEnum.AL_DIA),
        (6, 5, EstadoAvanceEnum.AL_DIA),
        (4, 5, EstadoAvanceEnum.RIESGO_MEDIO),
        (3, 5, EstadoAvanceEnum.RIESGO_ALTO),
    ],
)
def test_clasificar_estado(alcanzada, actual, esperado):
    assert clasificar_estado(alcanzada, actual) == esperado


# ===================== estado_tp (calificación → estado) =====================


@pytest.mark.parametrize(
    "nota,esperado",
    [
        ("Aprobado", "aprobado"),
        ("APROBADO", "aprobado"),
        ("Desaprobado", "desaprobado"),  # contiene "aprob" pero gana "desaprob"
        ("7,00", "aprobado"),  # nota numérica → "tiene nota = realizado" (§9.bis F)
        ("10", "aprobado"),
        ("0,00", "aprobado"),  # incluso un 0 cuenta como realizado (hay nota)
        ("-", "sin_nota"),
        ("", "sin_nota"),
        (None, "sin_nota"),
    ],
)
def test_estado_tp(nota, esperado):
    assert estado_tp(nota) == esperado


# ===================== cálculo por componentes dinámicos =====================


def _cal(tipo, cmid):
    return {"tipo": tipo, "cmid": cmid, "fuente": "CALIFICACION"}


def _seg(tipo, cmid):
    return {"tipo": tipo, "cmid": cmid, "fuente": "SEGUIMIENTO"}


def _u(numero, *componentes):
    return {"numero": numero, "componentes": list(componentes)}


# U1: TP=11 (calif), autoeval=12 (seg), cierre=13 (seg). U2: ídem con 21/22/23.
CFG = [
    _u(1, _cal("TP", 11), _seg("AUTOEVALUACION", 12), _seg("CIERRE", 13)),
    _u(2, _cal("TP", 21), _seg("AUTOEVALUACION", 22), _seg("CIERRE", 23)),
]


def _deudas(statuses, notas=None, unidad_actual=2, cfg=CFG):
    _, d = calcular_deudas_y_alcance(statuses, notas or {}, cfg, unidad_actual=unidad_actual)
    return d


def _tipos(deudas, unidad):
    return sorted(d["tipo"] for d in deudas if d["unidad"] == unidad)


# ---- fuente CALIFICACION ----


def test_calificacion_sin_nota_es_deuda_no_entregado():
    deudas = _deudas([], notas={}, unidad_actual=1, cfg=[_u(1, _cal("TP", 11))])
    assert deudas == [{"unidad": 1, "tipo": "TP", "estado": "no entregado"}]


def test_calificacion_aprobado_no_es_deuda():
    deudas = _deudas([], notas={11: "Aprobado"}, unidad_actual=1, cfg=[_u(1, _cal("TP", 11))])
    assert deudas == []


def test_calificacion_desaprobado_es_deuda_y_cuenta_para_alcance():
    alcanzada, deudas = calcular_deudas_y_alcance(
        [], {11: "Desaprobado"}, [_u(1, _cal("TP", 11))], unidad_actual=1
    )
    assert alcanzada == 1  # entregó y se calificó → tocó la unidad
    assert deudas == [{"unidad": 1, "tipo": "TP", "estado": "desaprobado"}]


def test_quiz_por_calificacion_sin_nota_es_deuda():
    deudas = _deudas([], notas={}, unidad_actual=1, cfg=[_u(1, _cal("QUIZ", 30))])
    assert deudas == [{"unidad": 1, "tipo": "QUIZ", "estado": "no entregado"}]


# ---- fuente SEGUIMIENTO ----


def test_seguimiento_pendientes_son_deuda():
    deudas = _deudas(
        [{"cmid": 12, "state": 0}, {"cmid": 13, "state": 0}],
        unidad_actual=1, cfg=[_u(1, _seg("AUTOEVALUACION", 12), _seg("CIERRE", 13))],
    )
    assert _tipos(deudas, 1) == ["AUTOEVALUACION", "CIERRE"]


def test_seguimiento_hecho_no_es_deuda():
    deudas = _deudas([{"cmid": 12, "state": 1}], unidad_actual=1, cfg=[_u(1, _seg("AUTOEVALUACION", 12))])
    assert deudas == []


def test_quiz_por_seguimiento_hecho_no_es_deuda():
    deudas = _deudas([{"cmid": 30, "state": 2}], unidad_actual=1, cfg=[_u(1, _seg("QUIZ", 30))])
    assert deudas == []


def test_varios_componentes_del_mismo_tipo():
    # 2 quizzes por seguimiento: uno hecho, otro no → una sola deuda QUIZ.
    cfg = [_u(1, _seg("QUIZ", 30), _seg("QUIZ", 31))]
    deudas = _deudas([{"cmid": 30, "state": 1}], unidad_actual=1, cfg=cfg)
    assert deudas == [{"unidad": 1, "tipo": "QUIZ", "estado": "pendiente"}]


def test_unidad_sin_tp_ni_cierre_estilo_organizacion_empresarial():
    # Varios quizzes + 1 autoeval, sin TP ni cierre (caso Organización Empresarial).
    cfg = [_u(3, _seg("QUIZ", 40), _seg("QUIZ", 41), _seg("AUTOEVALUACION", 42))]
    statuses = [{"cmid": 40, "state": 1}, {"cmid": 41, "state": 0}, {"cmid": 42, "state": 1}]
    alcanzada, deudas = calcular_deudas_y_alcance(statuses, {}, cfg, unidad_actual=3)
    assert alcanzada == 3  # tocó al menos un componente
    assert deudas == [{"unidad": 3, "tipo": "QUIZ", "estado": "pendiente"}]  # solo el quiz 41


# ---- alcance / faltantes ----


def test_unidad_alcanzada_es_la_mas_alta_con_algun_componente():
    # U1 completa, U2 solo TP aprobado → alcanzada 2.
    alcanzada, _ = calcular_deudas_y_alcance(
        [{"cmid": 12, "state": 1}, {"cmid": 13, "state": 1}],
        {11: "Aprobado", 21: "Aprobado"},
        CFG,
        unidad_actual=2,
    )
    assert alcanzada == 2


def test_unidad_sin_componentes_se_ignora():
    alcanzada, deudas = calcular_deudas_y_alcance([], {}, [_u(1)], unidad_actual=1)
    assert alcanzada is None
    assert deudas == []


def test_calcular_actividades_faltantes_none_si_todo_ok():
    statuses = [
        {"cmid": 12, "state": 1}, {"cmid": 13, "state": 1},
        {"cmid": 22, "state": 1}, {"cmid": 23, "state": 1},
    ]
    notas = {11: "Aprobado", 21: "Aprobado"}
    assert calcular_actividades_faltantes(statuses, notas, CFG, unidad_actual=2) is None


def test_calcular_avance_alumno_integra_tp_desaprobado():
    statuses = [
        {"cmid": 12, "state": 1}, {"cmid": 13, "state": 1},  # U1 autoeval+cierre ok
        {"cmid": 22, "state": 1}, {"cmid": 23, "state": 1},  # U2 autoeval+cierre ok
    ]
    notas = {11: "Aprobado", 21: "Desaprobado"}  # U2 TP desaprobado
    r = calcular_avance_alumno(statuses, notas, CFG, unidad_actual=2)
    assert r["unidad_alcanzada"] == 2
    assert r["estado"] == EstadoAvanceEnum.AL_DIA
    assert r["actividad_actual_desaprobada"] is True
    deudas = r["actividades_faltantes"]["deudas"]
    assert any(d["unidad"] == 2 and d["tipo"] == "TP" and d["estado"] == "desaprobado" for d in deudas)
