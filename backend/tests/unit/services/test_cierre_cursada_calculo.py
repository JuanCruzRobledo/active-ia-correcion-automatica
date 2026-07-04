"""
Tests de cierre_cursada_calculo — lógica PURA del cierre de cursada
(PROMOCIONA / REGULARIZA / RECURSA), portada 1:1 desde el script de
referencia validado de la skill `informe-cierre-cursada`.

Reglas (ver references/reglas-cierre.md de la skill):
  - autoeval_ok: TODAS las unidades no-opcionales >= 90% (no promedio).
  - tp_ok: % de TPs "Aprobado" >= umbral_tp_pct (N/E cuenta como NO aprobado).
  - p1_max/p2_max/tpi_max: nota más alta entre TODAS las instancias rendidas.
  - Nota Final (solo si promociona) en escala 0-10, redondeo round_half_up.
"""

import pytest

from app.services.cierre_cursada_calculo import (
    autoeval_ok as f_autoeval_ok,
    calcular_estado,
    max_o_none,
    round_half_up,
    sugerir_categoria,
    tp_ok as f_tp_ok,
)

REGLAS = {
    "autoeval_min_pct": 90,
    "parcial_promocion_min_pct": 60,
    "parcial_regulariza_min_pct": 40,
    "tpi_min_pct": 60,
}


# ===================== round_half_up =====================


@pytest.mark.parametrize(
    "valor,esperado",
    [
        (0.5, 1),
        (1.4999, 1),
        (1.5, 2),
        (6.5, 7),
        (6.4999, 6),
    ],
)
def test_round_half_up(valor, esperado):
    assert round_half_up(valor) == esperado


# ===================== tp_ok =====================


def test_tp_ok_sin_tps_es_vacuamente_verdadero():
    assert f_tp_ok([], umbral_tp_pct=100) is True


def test_tp_ok_ne_no_cuenta_como_aprobado():
    # 1 de 4 aprobado (25%) — los N/E no suman al numerador ni se descuentan del denominador.
    assert f_tp_ok(["Aprobado", "N/E", "N/E", "N/E"], umbral_tp_pct=50) is False


def test_tp_ok_borde_exacto_inclusive():
    # 2 de 2 aprobados = 100%, umbral 100 → inclusive.
    assert f_tp_ok(["Aprobado", "Aprobado"], umbral_tp_pct=100) is True
    # 1 de 2 = 50%, umbral 50 → inclusive.
    assert f_tp_ok(["Aprobado", "Desaprobado"], umbral_tp_pct=50) is True
    # 1 de 2 = 50%, umbral 51 → falla por debajo.
    assert f_tp_ok(["Aprobado", "Desaprobado"], umbral_tp_pct=51) is False


# ===================== autoeval_ok =====================


def test_autoeval_ok_lista_vacia_es_falso():
    # Sin ninguna unidad no-opcional evaluable, no se puede afirmar autoeval_ok.
    assert f_autoeval_ok([], minimo=90) is False


def test_autoeval_ok_un_none_rompe_la_condicion():
    assert f_autoeval_ok([96.3, None, 100.0], minimo=90) is False


def test_autoeval_ok_borde_exacto_inclusive():
    assert f_autoeval_ok([90.0, 90.0], minimo=90) is True
    assert f_autoeval_ok([89.999, 100.0], minimo=90) is False


# ===================== max_o_none =====================


def test_max_o_none_lista_vacia():
    assert max_o_none([]) is None


def test_max_o_none_todo_none():
    assert max_o_none([None, None]) is None


def test_max_o_none_mezcla():
    assert max_o_none([None, 60.0, None, 80.0]) == 80.0


def test_max_o_none_solo_recuperatorio_rendido():
    # Instancia original ausente (None), solo se rindió el recuperatorio.
    assert max_o_none([None, 45.0]) == 45.0


# ===================== calcular_estado — matriz de bordes =====================


def _alumno(tps=None, autoeval=None, p1=None, p2=None, tpi=None):
    return {
        "tps": tps if tps is not None else ["Aprobado"] * 4,
        "autoeval_pcts": autoeval if autoeval is not None else [96.3, 100.0],
        "parcial1_pcts": p1 if p1 is not None else [60.0],
        "parcial2_pcts": p2 if p2 is not None else [60.0],
        "tpi_pcts": tpi if tpi is not None else [60.0],
    }


def test_promociona_exacto_en_60_60_60():
    resultado = calcular_estado(_alumno(p1=[60.0], p2=[60.0], tpi=[60.0]), REGLAS, 100)
    assert resultado["estado"] == "PROMOCIONA"
    assert resultado["habilitado_final"] == "No aplica (promocionó)"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"autoeval": [89.9, 100.0]},  # autoeval falla por un unidad
        {"tps": ["Desaprobado"] * 4},  # tp_ok falla
        {"p1": [59.9]},
        {"p2": [59.9]},
        {"tpi": [59.9]},
    ],
)
def test_promociona_falla_por_un_punto_cae_a_chequeo_regulariza(kwargs):
    resultado = calcular_estado(_alumno(**kwargs), REGLAS, 100)
    assert resultado["estado"] != "PROMOCIONA"


def test_regulariza_exacto_en_40_40():
    resultado = calcular_estado(_alumno(p1=[40.0], p2=[40.0], tpi=[0.0]), REGLAS, 100)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["nota_final"] is None


def test_regulariza_con_tpi_none_no_habilita_final():
    resultado = calcular_estado(_alumno(p1=[40.0], p2=[40.0], tpi=[None]), REGLAS, 100)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["habilitado_final"] == "No (falta aprobar TPI)"


def test_regulariza_con_tpi_exacto_60_habilita_final():
    resultado = calcular_estado(_alumno(p1=[40.0], p2=[40.0], tpi=[60.0]), REGLAS, 100)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["habilitado_final"] == "Sí"


def test_regulariza_con_tpi_59_999_no_habilita_final():
    resultado = calcular_estado(_alumno(p1=[40.0], p2=[40.0], tpi=[59.999]), REGLAS, 100)
    assert resultado["habilitado_final"] == "No (falta aprobar TPI)"


def test_recursa_por_debajo_de_regulariza():
    resultado = calcular_estado(_alumno(p1=[39.9], p2=[40.0]), REGLAS, 100)
    assert resultado["estado"] == "RECURSA"
    assert resultado["nota_final"] is None
    assert resultado["habilitado_final"] == "No"


def test_recursa_sin_rendir_nada():
    resultado = calcular_estado(
        _alumno(tps=["N/E"] * 4, autoeval=[None], p1=[None], p2=[None], tpi=[None]),
        REGLAS,
        100,
    )
    assert resultado["estado"] == "RECURSA"


def test_nota_final_solo_se_calcula_si_promociona():
    regulariza = calcular_estado(_alumno(p1=[50.0], p2=[50.0], tpi=[100.0]), REGLAS, 100)
    assert regulariza["nota_final"] is None
    recursa = calcular_estado(_alumno(p1=[10.0], p2=[10.0], tpi=[100.0]), REGLAS, 100)
    assert recursa["nota_final"] is None


def test_nota_final_redondeo_half_up():
    # ((70+70)/2)*0.4 + 65*0.6 = 28 + 39 = 67 -> /10 = 6.7 -> round_half_up = 7
    resultado = calcular_estado(_alumno(p1=[70.0], p2=[70.0], tpi=[65.0]), REGLAS, 100)
    assert resultado["estado"] == "PROMOCIONA"
    assert resultado["nota_final"] == 7


def test_nota_final_caso_borde_punto_5():
    # ((60+60)/2)*0.4 + 60*0.6 = 24 + 36 = 60 -> /10 = 6.0 exacto -> round_half_up = 6
    resultado = calcular_estado(_alumno(p1=[60.0], p2=[60.0], tpi=[60.0]), REGLAS, 100)
    assert resultado["nota_final"] == 6


def test_p1_max_toma_la_instancia_de_recuperatorio():
    # Original ausente (None), solo se rindió el recuperatorio con 65.
    resultado = calcular_estado(_alumno(p1=[None, 65.0], p2=[60.0], tpi=[60.0]), REGLAS, 100)
    assert resultado["p1_max"] == 65.0
    assert resultado["estado"] == "PROMOCIONA"


# ===================== sugerir_categoria =====================


@pytest.mark.parametrize(
    "nombre,categoria,unidad,opcional",
    [
        ("Actividad de cierre unidad 3", "TP", 3, False),
        ("Actividad de cierre Unidad 9", "TP", 9, True),
        ("Actividad de cierre Unidad 10", "TP", 10, True),
        ("Cuestionario de Autoevaluación - Unidad 4", "AUTOEVAL", 4, False),
        ("Autoevaluación Unidad 9", "AUTOEVAL", 9, True),
        ("Primer Parcial", "PARCIAL_1", None, False),
        ("Primera Examen Parcial", "PARCIAL_1", None, False),
        ("Recuperatorio Primer Parcial", "PARCIAL_1", None, False),
        ("Extraordinaria Primer Parcial", "PARCIAL_1", None, False),
        ("Extensión Primer Parcial", "PARCIAL_1", None, False),
        ("Segundo Parcial", "PARCIAL_2", None, False),
        ("Recuperatorio Segundo Examen Parcial", "PARCIAL_2", None, False),
        ("Entrega del Trabajo Integrador", "TPI", None, False),
        ("Recuperatorio Entrega del Trabajo Integrador", "TPI", None, False),
        ("Cuestionario de Actividad 1", "IGNORAR", None, False),
        ("Cuestionario de Actividad 2", "IGNORAR", None, False),
        ("Antes de comenzar con el estudio de la materia...", "IGNORAR", None, False),
        ("Algo sin clasificar todavía", "IGNORAR", None, False),
    ],
)
def test_sugerir_categoria(nombre, categoria, unidad, opcional):
    resultado = sugerir_categoria(nombre)
    assert resultado["categoria"] == categoria
    assert resultado["unidad"] == unidad
    assert resultado["opcional"] is opcional


def test_sugerir_categoria_case_insensitive():
    assert sugerir_categoria("ACTIVIDAD DE CIERRE UNIDAD 5")["categoria"] == "TP"
    assert sugerir_categoria("primer parcial")["categoria"] == "PARCIAL_1"
