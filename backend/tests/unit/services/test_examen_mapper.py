"""
Tests de examen_mapper — lógica PURA del seguimiento de exámenes.

Interpreta la nota de un examen (escala o numérica con umbral) y aplica el RESCATE:
un parcial queda aprobado si lo aprobó O si aprobó alguno de sus recuperatorios/
extensiones/extraordinarias (precedencia aprobado > desaprobado > ausente).
"""

import pytest

from app.services.examen_mapper import (
    calcular_resultados_examenes,
    clasificar_grade_estructural,
    examen_corte,
    interpretar_resultado,
    parsear_nota_numerica,
)


def test_examen_corte_mas_alto():
    # Recibe el formato del modelo: {id, tipo, orden}; el número/etiqueta se derivan.
    assert examen_corte([]) is None
    assert examen_corte(None) is None
    p12 = [
        {"id": 1, "tipo": "PARCIAL", "orden": 0},
        {"id": 2, "tipo": "PARCIAL", "orden": 1},
    ]
    assert examen_corte(p12) == "Parcial 2"  # parcial de mayor número
    assert examen_corte(p12 + [{"id": 3, "tipo": "GLOBAL", "orden": 2}]) == "Global 1"
    # Recuperatorios/extensiones no son corte.
    assert examen_corte([{"id": 9, "tipo": "RECUPERATORIO", "orden": 0}]) is None


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


def test_global_desaprobado_se_rescata_con_recuperatorio():
    # El rescate también aplica a los GLOBALES: un recuperatorio que apunta a un
    # global desaprobado lo deja aprobado y marca rescatado=True.
    cfg = [
        _ex(1, "GLOBAL", 300),
        _ex(2, "RECUPERATORIO", 400, recupera=1),
    ]
    res = _por_examen(
        calcular_resultados_examenes({300: "Desaprobado", 400: "Aprobado"}, cfg)
    )
    assert res[1]["resultado"] == "aprobado"
    assert res[1]["rescatado"] is True
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


# ===================== señal estructural (grade=-1: entregado/sin corregir) =====================


def test_clasificar_grade_estructural():
    # Sin registro = no entregó. grade=-1 con entrega = sin corregir. grade>=0 = calificado.
    assert clasificar_grade_estructural(None) == "ausente"
    assert clasificar_grade_estructural({"grade": "-1.00000", "timemodified": 1700}) == "sin_corregir"
    assert clasificar_grade_estructural({"grade": "-1.00000", "timemodified": 0}) == "ausente"
    assert clasificar_grade_estructural({"grade": None, "timemodified": 1700}) == "sin_corregir"
    assert clasificar_grade_estructural({"grade": "85.00", "timemodified": 1700}) == "calificado"
    assert clasificar_grade_estructural({"grade": "0.00", "timemodified": 1700}) == "calificado"


def test_estructural_entregado_sin_corregir():
    # El caso del global: 407 entregaron, grade=-1. El texto muestra "-" (ausente);
    # la señal estructural los detecta como 'sin_corregir'.
    cfg = [_ex(7, "GLOBAL", 300, modo="NUMERICO", nota_minima=6.0)]
    res = _por_examen(
        calcular_resultados_examenes(
            {300: "-"}, cfg, estructural_uid={300: {"grade": "-1.00000", "timemodified": 1700}}
        )
    )
    assert res[7]["resultado"] == "sin_corregir"


def test_estructural_calificado_interpreta_el_texto():
    # grade>=0 ⇒ hay nota real → se interpreta el texto (NUMERICO con umbral).
    cfg = [_ex(1, "PARCIAL", 100, modo="NUMERICO", nota_minima=60.0),
           _ex(2, "PARCIAL", 101, modo="NUMERICO", nota_minima=60.0, orden=1)]
    res = _por_examen(
        calcular_resultados_examenes(
            {100: "100.00", 101: "50.00"}, cfg,
            estructural_uid={
                100: {"grade": "100.00", "timemodified": 1700},
                101: {"grade": "50.00", "timemodified": 1700},
            },
        )
    )
    assert res[1]["resultado"] == "aprobado"      # 100 >= 60
    assert res[2]["resultado"] == "desaprobado"   # 50 < 60


def test_estructural_sin_registro_es_ausente():
    # cmid con fuente estructural pero sin entrega (entry None) → ausente (aunque el texto
    # trajera algo: la señal estructural manda para distinguir entregó / no entregó).
    cfg = [_ex(1, "PARCIAL", 100)]
    res = _por_examen(
        calcular_resultados_examenes({100: "Aprobado"}, cfg, estructural_uid={100: None})
    )
    assert res[1]["resultado"] == "ausente"


def test_sin_fuente_estructural_usa_texto():
    # Examen quiz (cmid NO está en estructural) → comportamiento histórico (texto).
    cfg = [_ex(1, "PARCIAL", 100)]
    res = _por_examen(
        calcular_resultados_examenes({100: "Aprobado"}, cfg, estructural_uid={})
    )
    assert res[1]["resultado"] == "aprobado"


def test_rescate_recuperatorio_sin_corregir_estructural():
    # Parcial reprobado (calificado) + recuperatorio entregado-sin-corregir → 'sin_corregir'
    # (todavía puede aprobar; sin_corregir pisa a desaprobado en la precedencia).
    cfg = [_ex(1, "PARCIAL", 100, modo="NUMERICO", nota_minima=60.0),
           _ex(2, "RECUPERATORIO", 200, recupera=1)]
    res = _por_examen(
        calcular_resultados_examenes(
            {100: "50.00"}, cfg,
            estructural_uid={
                100: {"grade": "50.00", "timemodified": 1700},
                200: {"grade": "-1.00000", "timemodified": 1700},
            },
        )
    )
    assert res[1]["resultado"] == "sin_corregir"
    assert res[1]["rescatado"] is False
