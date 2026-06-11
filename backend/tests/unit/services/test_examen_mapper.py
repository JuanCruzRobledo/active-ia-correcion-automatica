"""
Tests de examen_mapper — lógica PURA del seguimiento de exámenes.

Interpreta la nota de un examen (escala o numérica con umbral) y aplica el RESCATE:
un parcial queda aprobado si lo aprobó O si aprobó alguno de sus recuperatorios/
extensiones/extraordinarias (precedencia aprobado > desaprobado > ausente).
"""

import pytest

from app.services.examen_mapper import (
    calcular_resultados_examenes,
    interpretar_resultado,
    parsear_nota_numerica,
)


# ===================== parseo de nota numérica (es-AR) =====================


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("7,00", 7.0),   # coma decimal (Moodle es-AR)
        ("7.50", 7.5),   # punto decimal
        ("10", 10.0),
        ("  6,00 ", 6.0),  # con espacios
        ("0,00", 0.0),
        ("", None),
        ("-", None),
        (None, None),
        ("abc", None),
    ],
)
def test_parsear_nota_numerica(texto, esperado):
    assert parsear_nota_numerica(texto) == esperado


# ===================== interpretar_resultado =====================


@pytest.mark.parametrize(
    "nota,esperado",
    [
        ("Aprobado", "aprobado"),
        ("APROBADO", "aprobado"),
        ("Desaprobado", "desaprobado"),  # contiene "aprob" pero gana "desaprob"
        ("", "ausente"),
        ("-", "ausente"),
        (None, "ausente"),
    ],
)
def test_interpretar_escala(nota, esperado):
    assert interpretar_resultado(nota, "ESCALA", None) == esperado


@pytest.mark.parametrize(
    "nota,minima,esperado",
    [
        ("7,00", 6.0, "aprobado"),
        ("6,00", 6.0, "aprobado"),   # >= umbral
        ("5,99", 6.0, "desaprobado"),
        ("3,00", 4.0, "desaprobado"),
        ("", 6.0, "ausente"),        # sin nota = ausente, NO desaprobado
        ("-", 6.0, "ausente"),
        (None, 6.0, "ausente"),
    ],
)
def test_interpretar_numerico(nota, minima, esperado):
    assert interpretar_resultado(nota, "NUMERICO", minima) == esperado


# ===================== resultados con rescate =====================


def _ex(id, tipo, cmid, *, modo="ESCALA", nota_minima=None, recupera=None, orden=0):
    return {
        "id": id, "tipo": tipo, "moodle_cmid": cmid, "modo_aprobacion": modo,
        "nota_minima": nota_minima, "recupera_examen_id": recupera, "orden": orden,
    }


def _por_examen(resultados):
    return {r["examen_id"]: r for r in resultados}


def test_parcial_aprobado_sin_rescate():
    cfg = [_ex(1, "PARCIAL", 100)]
    res = _por_examen(calcular_resultados_examenes({100: "Aprobado"}, cfg))
    assert res[1]["resultado"] == "aprobado"
    assert res[1]["rescatado"] is False
    assert res[1]["numero"] == 1


def test_parcial_desaprobado_se_rescata_con_recuperatorio():
    cfg = [
        _ex(1, "PARCIAL", 100),
        _ex(2, "RECUPERATORIO", 200, recupera=1),
    ]
    res = _por_examen(
        calcular_resultados_examenes({100: "Desaprobado", 200: "Aprobado"}, cfg)
    )
    assert res[1]["resultado"] == "aprobado"
    assert res[1]["rescatado"] is True


def test_parcial_ausente_se_rescata_con_extraordinaria():
    cfg = [
        _ex(1, "PARCIAL", 100),
        _ex(2, "EXTRAORDINARIA", 200, recupera=1),
    ]
    res = _por_examen(calcular_resultados_examenes({200: "Aprobado"}, cfg))
    assert res[1]["resultado"] == "aprobado"
    assert res[1]["rescatado"] is True


def test_parcial_desaprobado_y_recu_desaprobado_queda_desaprobado():
    cfg = [_ex(1, "PARCIAL", 100), _ex(2, "RECUPERATORIO", 200, recupera=1)]
    res = _por_examen(
        calcular_resultados_examenes({100: "Desaprobado", 200: "Desaprobado"}, cfg)
    )
    assert res[1]["resultado"] == "desaprobado"
    assert res[1]["rescatado"] is False


def test_parcial_y_recu_ausentes_queda_ausente():
    cfg = [_ex(1, "PARCIAL", 100), _ex(2, "RECUPERATORIO", 200, recupera=1)]
    res = _por_examen(calcular_resultados_examenes({}, cfg))
    assert res[1]["resultado"] == "ausente"


def test_global_standalone():
    cfg = [_ex(1, "GLOBAL", 300, modo="NUMERICO", nota_minima=4.0)]
    res = _por_examen(calcular_resultados_examenes({300: "7,00"}, cfg))
    assert res[1]["resultado"] == "aprobado"
    assert res[1]["tipo"] == "GLOBAL"


def test_numero_se_deriva_por_tipo_segun_orden():
    cfg = [
        _ex(1, "PARCIAL", 100, orden=0),
        _ex(2, "PARCIAL", 101, orden=1),
        _ex(3, "GLOBAL", 300, orden=0),
    ]
    res = _por_examen(calcular_resultados_examenes({}, cfg))
    assert res[1]["numero"] == 1
    assert res[2]["numero"] == 2
    assert res[3]["numero"] == 1  # global numera aparte


def test_recuperatorios_no_aparecen_como_filas_principales():
    cfg = [_ex(1, "PARCIAL", 100), _ex(2, "RECUPERATORIO", 200, recupera=1)]
    resultados = calcular_resultados_examenes({100: "Aprobado"}, cfg)
    tipos = {r["tipo"] for r in resultados}
    assert tipos == {"PARCIAL"}  # solo principales (parciales/globales)
    assert len(resultados) == 1
