"""
Tests de cierre_cursada_calculo — lógica PURA del cierre de cursada
(PROMOCIONA / REGULARIZA / RECURSA) dirigida por la configuración de
exámenes de la materia (`ExamenMateria`).

Reglas (ver diseño, "Algoritmo de clasificación"):
  - cumple_minimo: ESCALA -> resultado_escala == 'aprobado'; NUMERICO ->
    valor_real >= nota_minima (inclusive).
  - cumple_banda: ESCALA -> igual que cumple_minimo (sin banda numérica);
    NUMERICO -> valor_real >= (nota_minima - banda).
  - calcular_estado_cierre: PROMOCIONA si cumple_minimo en TODOS (incl.
    GLOBAL); REGULARIZA si no promociona y cumple_banda en todos los NO
    globales; RECURSA en cualquier otro caso.
"""

import pytest

from app.services.cierre_cursada_calculo import (
    banda_regular,
    calcular_estado_cierre,
    calcular_nota_final,
    cumple_banda,
    cumple_minimo,
    detectar_escala,
    max_o_none,
    normalizar_a_10,
    round_half_up,
    SinExamenesConfigurados,
)


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


# ===================== detectar_escala / banda_regular =====================


@pytest.mark.parametrize(
    "nota_minima,escala_esperada,banda_esperada",
    [
        (6, 10, 2),
        (60, 100, 20),
        (50, 100, 20),
        (7, 10, 2),
    ],
)
def test_detectar_escala_y_banda_regular(nota_minima, escala_esperada, banda_esperada):
    assert detectar_escala(nota_minima) == escala_esperada
    assert banda_regular(nota_minima) == banda_esperada


def test_detectar_escala_frontera_en_10():
    # nota_minima >= 10 se clasifica como escala 100 (frontera documentada).
    assert detectar_escala(10) == 100
    assert banda_regular(10) == 20


def test_detectar_escala_none_es_modo_escala():
    assert detectar_escala(None) is None
    assert banda_regular(None) is None


# ===================== normalizar_a_10 =====================


def test_normalizar_a_10_escala_100_divide_por_10():
    assert normalizar_a_10(80, 60) == 8.0


def test_normalizar_a_10_escala_10_sin_cambio():
    assert normalizar_a_10(9.0, 6) == 9.0


def test_normalizar_a_10_valor_none_es_none():
    assert normalizar_a_10(None, 60) is None
    assert normalizar_a_10(None, None) is None


# ===================== cumple_minimo / cumple_banda =====================


def _examen(tipo="PARCIAL", modo="NUMERICO", nota_minima=60.0, valor_real=None, resultado_escala=None, examen_id=1):
    return {
        "examen_id": examen_id,
        "tipo": tipo,
        "modo_aprobacion": modo,
        "nota_minima": nota_minima,
        "valor_real": valor_real,
        "resultado_escala": resultado_escala,
    }


def test_cumple_minimo_numerico_borde_exacto_inclusive():
    assert cumple_minimo(_examen(nota_minima=60.0, valor_real=60.0)) is True


def test_cumple_minimo_numerico_por_debajo_falla():
    assert cumple_minimo(_examen(nota_minima=60.0, valor_real=59.999)) is False


def test_cumple_minimo_numerico_sin_valor_falla():
    assert cumple_minimo(_examen(nota_minima=60.0, valor_real=None)) is False


def test_cumple_minimo_escala_usa_resultado_escala():
    assert cumple_minimo(_examen(modo="ESCALA", nota_minima=None, resultado_escala="aprobado")) is True
    assert cumple_minimo(_examen(modo="ESCALA", nota_minima=None, resultado_escala="desaprobado")) is False
    assert cumple_minimo(_examen(modo="ESCALA", nota_minima=None, resultado_escala="ausente")) is False


def test_cumple_banda_numerico_borde_exacto_escala_100():
    # nota_minima=60, banda=20 -> 40 cumple banda.
    assert cumple_banda(_examen(nota_minima=60.0, valor_real=40.0)) is True
    assert cumple_banda(_examen(nota_minima=60.0, valor_real=39.999)) is False


def test_cumple_banda_numerico_borde_exacto_escala_10():
    # nota_minima=6, banda=2 -> 4 cumple banda.
    assert cumple_banda(_examen(nota_minima=6.0, valor_real=4.0)) is True
    assert cumple_banda(_examen(nota_minima=6.0, valor_real=3.999)) is False


def test_cumple_banda_escala_es_igual_a_cumple_minimo():
    examen_aprobado = _examen(modo="ESCALA", nota_minima=None, resultado_escala="aprobado")
    examen_desaprobado = _examen(modo="ESCALA", nota_minima=None, resultado_escala="desaprobado")
    assert cumple_banda(examen_aprobado) == cumple_minimo(examen_aprobado) is True
    assert cumple_banda(examen_desaprobado) == cumple_minimo(examen_desaprobado) is False


# ===================== calcular_estado_cierre =====================


def test_promociona_todos_incluido_global():
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=80.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=6.0, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "PROMOCIONA"
    assert resultado["global_valor"] == 6.0
    # parciales normalizados: 60->6.0, 80->8.0 (promedio 7.0); global 6.0 (escala 10, sin cambio)
    # NF = 7.0*0.4 + 6.0*0.6 = 2.8 + 3.6 = 6.4 -> round_half_up = 6
    assert resultado["nota_final"] == 6
    assert len(resultado["resultados_examenes"]) == 3


def test_no_promociona_si_falla_global():
    # Ambos parciales aprueban el mínimo pero el global no lo rinde -> no PROMOCIONA.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=None, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"


def test_regulariza_banda_global_opcional():
    # Parciales cumplen banda (no mínimo), global ausente -> REGULARIZA (global opcional).
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=40.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=70.0, valor_real=55.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=None, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["global_valor"] is None


def test_recursa_no_cumple_banda_en_algun_parcial():
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=39.9, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=2),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "RECURSA"


def test_sin_global_configurado_promocion_regular_exigen_solo_parciales():
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=2),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "PROMOCIONA"
    assert resultado["global_valor"] is None


def test_guard_sin_examenes_lanza_excepcion():
    with pytest.raises(SinExamenesConfigurados):
        calcular_estado_cierre([])


def test_borde_valor_igual_a_nota_minima_cumple_minimo_inclusive():
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=6.0, examen_id=2),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "PROMOCIONA"


def test_borde_valor_igual_a_nota_minima_menos_banda_cumple_banda_inclusive():
    # nota_minima=60, banda=20 -> 40 cumple banda exacto -> REGULARIZA.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=40.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=4.0, examen_id=2),  # 6-2=4
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"


def test_examen_escala_sin_valor_numerico_promociona_por_resultado_escala():
    examenes = [
        _examen(tipo="PARCIAL", modo="ESCALA", nota_minima=None, resultado_escala="aprobado", examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=6.0, examen_id=2),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "PROMOCIONA"


def test_resultados_examenes_incluye_cumple_minimo_y_cumple_banda():
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=45.0, examen_id=1),
    ]
    resultado = calcular_estado_cierre(examenes)
    (detalle,) = resultado["resultados_examenes"]
    assert detalle["cumple_minimo"] is False
    assert detalle["cumple_banda"] is True


def test_regulariza_tiene_nota_final_5():
    # Bug 6 (tarea 9.3, spec cierre-cursada-quiz-recuperables-fix): un alumno
    # que REGULARIZA (no promociona) debe tener `nota_final == 5` (valor fijo),
    # aunque tenga parciales y global numéricos que producirían una Nota Final
    # ponderada distinta. Esta regla sobrescribe deliberadamente la anterior
    # (`cierre-cursada-comision-nota-fix`, que dejaba REGULARIZA en blanco).
    # La Nota Final ponderada sigue siendo exclusiva de PROMOCIONA; RECURSA y
    # ABANDONO quedan en blanco (None).
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=45.0, examen_id=1),  # banda 40, no minimo
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["nota_final"] == 5


# ===================== calcular_nota_final =====================


def test_nota_final_dos_parciales_un_global_escala_10():
    # P1=8, P2=6, Global=9 (todo escala 10, nota_minima=6 -> escala 10).
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=8.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=6.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=3),
    ]
    # ((8+6)/2)*0.4 + 9*0.6 = 2.8 + 5.4 = 8.2 -> 8
    assert calcular_nota_final(examenes) == 8


def test_nota_final_n_mayor_a_dos_parciales():
    # 3 parciales (8, 6, 10) promedio 8 -> 8*0.4 + Global*0.6.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=8.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=6.0, examen_id=2),
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=10.0, examen_id=3),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=4),
    ]
    # 8*0.4 + 9*0.6 = 3.2 + 5.4 = 8.6 -> 9
    assert calcular_nota_final(examenes) == 9


def test_nota_final_global_faltante_cuenta_como_cero():
    # Tras el fix (tarea 3.2): el GLOBAL no entregado ya no corta con `None` ("N/E"),
    # cuenta como 0 en la ponderación. Único parcial: 8.0 (escala 10, sin cambio).
    # NF = 8.0*0.4 + 0.0*0.6 = 3.2 -> round_half_up = 3.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=8.0, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=None, examen_id=2),
    ]
    assert calcular_nota_final(examenes) == 3


def test_nota_final_parcial_faltante_cuenta_como_cero():
    # Tras el fix (tarea 3.2): un parcial no entregado cuenta como 0 en el promedio
    # de parciales, en vez de invalidar el cálculo. Promedio parciales = (0.0+8.0)/2
    # = 4.0; Global = 9.0 (escala 10). NF = 4.0*0.4 + 9.0*0.6 = 1.6 + 5.4 = 7.0 -> 7.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=None, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=8.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=3),
    ]
    assert calcular_nota_final(examenes) == 7


def test_nota_final_none_si_no_hay_parciales():
    examenes = [
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=1),
    ]
    assert calcular_nota_final(examenes) is None


def test_nota_final_none_si_no_hay_exactamente_un_global():
    # 0 globales.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=8.0, examen_id=1),
    ]
    assert calcular_nota_final(examenes) is None
    # 2 globales.
    examenes_2 = [
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=8.0, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=8.0, examen_id=3),
    ]
    assert calcular_nota_final(examenes_2) is None


def test_nota_final_parcial_escala_aprobado_vale_diez():
    # Tras el fix (tarea 3.2): un parcial en modo ESCALA aprobado vale 10.0 en la
    # ponderación (no None). NF = 10.0*0.4 + 9.0*0.6 = 4.0 + 5.4 = 9.4 -> 9.
    examenes = [
        _examen(tipo="PARCIAL", modo="ESCALA", nota_minima=None, resultado_escala="aprobado", examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=2),
    ]
    assert calcular_nota_final(examenes) == 9


def test_nota_final_normaliza_escala_mixta_no_mezcla_crudos():
    # Parciales en escala 100 (nota_minima=60): P1=80, P2=60 -> normalizados 8.0, 6.0.
    # Global en escala 10 (nota_minima=6): Global=9.0 -> sin cambio.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=80.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=3),
    ]
    # promedio normalizado (8.0+6.0)/2 = 7.0 -> 7.0*0.4 + 9.0*0.6 = 2.8 + 5.4 = 8.2 -> 8
    # (NO 28 + 5.4 = 33.4, que resultaría de promediar los crudos 80/60 sin normalizar)
    assert calcular_nota_final(examenes) == 8


@pytest.mark.parametrize(
    "valor_real,esperado",
    [
        (65.0, 7),  # normalizado 6.5 -> promedio 6.5 (global igual) -> nf 6.5 -> round_half_up 7
        (64.9, 6),  # normalizado 6.49 -> nf 6.49 -> round_half_up 6
    ],
)
def test_nota_final_bordes_de_redondeo(valor_real, esperado):
    # Un solo parcial y un global con el mismo valor normalizado -> NF == ese valor.
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=valor_real, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=60.0, valor_real=valor_real, examen_id=2),
    ]
    assert calcular_nota_final(examenes) == esperado


# ===================== Preservación (tarea 2, ANTES del fix) =====================
#
# Property 2: Preservation (design.md, cierre-cursada-comision-nota-fix) — Req 3.3, 3.5,
# 3.6. Metodología observation-first: se corre el código SIN arreglar con inputs que NO
# disparan el Bug 2 y se captura el comportamiento observado.
#
# - Guard estructural / sin global (edge, 3.5-scope): ya cubierto arriba, sin duplicar,
#   por `test_nota_final_none_si_no_hay_parciales` (0 parciales) y
#   `test_nota_final_none_si_no_hay_exactamente_un_global` (0 o 2 globales) — ambos
#   observan que `calcular_nota_final` sigue devolviendo `None` (fuera del alcance de la
#   garantía numérica de la tarea 3.2, que exige exactamente 1 PARCIAL+1 GLOBAL).
# - Estado sin cambios (3.6): ya cubierto arriba, sin duplicar, por
#   `test_no_promociona_si_falla_global` y `test_regulariza_banda_global_opcional`, que
#   ejercitan `calcular_estado_cierre` con un GLOBAL no entregado (`valor_real=None`) y
#   observan el mismo estado (REGULARIZA) que se espera preservar tras el fix de la
#   Nota Final (que sólo toca `calcular_nota_final`, no `calcular_estado_cierre`).


def test_preservacion_columna_ne_examen_no_entregado_queda_en_none():
    """Columna N/E (3.3): un examen no entregado (`valor_real=None`) debe seguir
    apareciendo como `None` en `resultados_examenes` (columna del examen en el Excel:
    "N/E") y en `global_valor` cuando es el GLOBAL el que falta — INDEPENDIENTEMENTE
    de que el fix de la tarea 3.2 haga que la Nota Final deje de ser `None`. Este test
    sólo verifica las columnas por-examen, no la Nota Final (que es justamente lo que
    el Bug 2 cambia; no se dispara ninguna aserción sobre `nota_final` acá)."""
    # GLOBAL no entregado.
    examenes_global_faltante = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=60.0, valor_real=None, examen_id=2),
    ]
    resultado = calcular_estado_cierre(examenes_global_faltante)
    assert resultado["global_valor"] is None
    valores_por_examen = {e["examen_id"]: e["valor_real"] for e in resultado["resultados_examenes"]}
    assert valores_por_examen == {1: 60.0, 2: None}

    # PARCIAL no entregado (el global sí se entregó).
    examenes_parcial_faltante = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=None, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=80.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=60.0, valor_real=60.0, examen_id=3),
    ]
    resultado_2 = calcular_estado_cierre(examenes_parcial_faltante)
    assert resultado_2["global_valor"] == 60.0
    valores_por_examen_2 = {e["examen_id"]: e["valor_real"] for e in resultado_2["resultados_examenes"]}
    assert valores_por_examen_2 == {1: None, 2: 80.0, 3: 60.0}


# ===================== Bug 2 exploration (tarea 1, ANTES del fix) =====================
#
# Property 2: Bug Condition - Nota Final numérica tratando no entregados como 0
# (design.md). CRITICAL: estos tests codifican el comportamiento ESPERADO tras el fix
# (isBugCondition_nota_final en design.md) -> DEBEN FALLAR sobre calcular_nota_final
# SIN arreglar, que hoy corta con `return None` ante cualquier faltante en vez de
# tratarlo como 0. La falla confirma que el Bug 2 existe.
# **Validates: Requirements 1.3, 1.4, 1.5**


def test_bug_nota_final_parcial_y_global_faltantes_cuentan_como_cero():
    """Bug 2: P1=93 (nota_minima 60 -> normalizado 9.3), P2=None (no entregado -> 0),
    Global=None (no entregado -> 0). Esperado (tras el fix):
    round_half_up(((9.3 + 0) / 2) * 0.4 + 0 * 0.6) = round_half_up(1.86) = 2.
    HOY: calcular_nota_final corta con `return None` en cuanto detecta un parcial o el
    global sin nota numérica -> devuelve None (\"N/E\") en vez de 2."""
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=93.0, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=None, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=60.0, valor_real=None, examen_id=3),
    ]
    assert calcular_nota_final(examenes) == 2


def test_bug_nota_final_parcial_escala_aprobado_vale_diez():
    """Bug 2: parcial en modo ESCALA aprobado (sin valor numérico) debe valer 10 en el
    cálculo de la Nota Final, combinado con Global=9.0.
    Esperado (tras el fix): round_half_up(10*0.4 + 9*0.6) = round_half_up(9.4) = 9.
    HOY: normalizar_a_10 devuelve None para el examen ESCALA (no tiene valor_real) ->
    calcular_nota_final corta y devuelve None (\"N/E\") en vez de 9."""
    examenes = [
        _examen(tipo="PARCIAL", modo="ESCALA", nota_minima=None, resultado_escala="aprobado", examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=2),
    ]
    assert calcular_nota_final(examenes) == 9


def test_bug_nota_final_ningun_examen_entregado_es_cero():
    """Bug 2: alumno que no entregó ningún examen (materia con >=1 PARCIAL y 1 GLOBAL
    configurados, todos sin nota numérica). Esperado (tras el fix): Nota Final = 0.
    HOY: calcular_nota_final devuelve None (\"N/E\") en vez de 0."""
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=None, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=60.0, valor_real=None, examen_id=2),
    ]
    assert calcular_nota_final(examenes) == 0


# ===================== Bug 4 exploration (tarea 6, ANTES del fix) =====================
#
# Property 6: Bug Condition - Nota Final sólo para PROMOCIONA (design.md,
# isBugCondition_nota_no_promociona). CRITICAL: estos tests codifican el comportamiento
# ESPERADO tras el fix -> DEBEN FALLAR sobre `calcular_estado_cierre` SIN arreglar, que
# hoy devuelve `"nota_final": calcular_nota_final(examenes)` para CUALQUIER estado, sin
# gatear por `estado == "PROMOCIONA"`. La falla confirma que el Bug 4 existe. NO se debe
# modificar `calcular_estado_cierre` (ni ningún otro código fuente) para hacer pasar
# estos tests.
# **Validates: Requirements 1.8, 1.9**


def test_regulariza_con_numericos_tiene_nota_final_5():
    """Bug 6 (tarea 9.3): alumno REGULARIZA (parciales que cumplen la banda pero no el
    mínimo, más un global numérico) -> `nota_final == 5` (valor fijo), NO la Nota Final
    ponderada. Antes de Bug 6 este mismo escenario esperaba `nota_final is None`
    (regla de `cierre-cursada-comision-nota-fix`, Bug 4); Bug 6 la sobrescribe con
    la instrucción explícita del usuario (REGULARIZA -> 5). El gate por estado
    sigue vigente: sólo PROMOCIONA usa la Nota Final ponderada."""
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=45.0, examen_id=1),  # banda 40, no minimo
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["nota_final"] == 5


def test_abandono_con_examenes_no_entregados_tiene_nota_final_none():
    """Nota Final en BLANCO para un alumno que no entregó ningún examen (celda
    "Nota Final" vacía en el Excel).

    Origen: este test provenía de `cierre-cursada-comision-nota-fix` (Bug 4) y
    verificaba que un alumno con TODOS los exámenes `N/E` quedaba con
    `nota_final is None`, asumiendo `estado == "RECURSA"`. Con el fix de Bug 5
    (spec `cierre-cursada-quiz-recuperables-fix`, tarea 9.2), un alumno con todos
    los principales ausentes ahora se clasifica correctamente como `ABANDONO`,
    no `RECURSA`. La intención original (Nota Final en blanco) se preserva: tanto
    RECURSA como ABANDONO dejan `nota_final = None` (tarea 9.3, sólo PROMOCIONA
    tiene Nota Final ponderada y REGULARIZA = 5)."""
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=None, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=60.0, valor_real=None, examen_id=2),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "ABANDONO"
    assert resultado["nota_final"] is None


# ===================== Bug 5 exploration (tarea 5, ANTES del fix) =====================
#
# Property 5: Bug Condition - Estado ABANDONO
# (cierre-cursada-quiz-recuperables-fix/design.md, isBugCondition de Bug 5).
# CRITICAL: estos tests codifican el comportamiento ESPERADO tras el fix -> DEBEN FALLAR
# sobre `calcular_estado_cierre` SIN arreglar, que hoy clasifica al alumno con TODOS los
# exámenes principales en `N/E` como "RECURSA" (cae en el `else`), sin distinguir el caso
# de abandono total. La falla confirma que el Bug 5 existe. NO se debe modificar
# `calcular_estado_cierre` (ni ningún otro código fuente) para hacer pasar estos tests.
#
# Scoped PBT: al ser un bug determinista, la propiedad se acota al caso concreto
# "todos los principales ausentes".
# Bug Condition: todos_ne AND clasificacionActual(examenes) == "RECURSA".
# **Validates: Requirements 1.11, 1.12**


def test_bug_todos_ne_numerico_deberia_ser_abandono():
    """Bug 5: alumno con Parcial 1, Parcial 2 y Global todos `N/E` en modo NUMERICO
    (`valor_real=None`) -> esperado (tras el fix) `estado == "ABANDONO"`.
    HOY: `calcular_estado_cierre` no tiene rama ABANDONO; ninguno cumple mínimo ni banda,
    así que cae en el `else` y devuelve `"RECURSA"` en vez de `"ABANDONO"`."""
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=None, examen_id=1),
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=None, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=None, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "ABANDONO"


def test_bug_todos_ne_escala_sin_resultado_deberia_ser_abandono():
    """Bug 5: alumno con exámenes principales en modo ESCALA sin resultado (ni
    `aprobado` ni `desaprobado`) -> esperado (tras el fix) `estado == "ABANDONO"`.
    HOY: `calcular_estado_cierre` devuelve `"RECURSA"` (no hay rama ABANDONO)."""
    examenes = [
        _examen(tipo="PARCIAL", modo="ESCALA", nota_minima=None, resultado_escala=None, examen_id=1),
        _examen(tipo="PARCIAL", modo="ESCALA", nota_minima=None, resultado_escala="ausente", examen_id=2),
        _examen(tipo="GLOBAL", modo="ESCALA", nota_minima=None, resultado_escala=None, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "ABANDONO"


# ===================== Bug 6 exploration (tarea 6, ANTES del fix) =====================
#
# Property 6: Bug Condition - Nota Final = 5 para REGULARIZA
# (cierre-cursada-quiz-recuperables-fix/design.md, isBugCondition de Bug 6).
# CRITICAL: estos tests codifican el comportamiento ESPERADO tras el fix -> DEBEN FALLAR
# sobre `calcular_estado_cierre` SIN arreglar, que hoy asigna `nota_final = None` para
# todo estado distinto de PROMOCIONA, por lo que un alumno REGULARIZA queda con la celda
# "Nota Final" en blanco (`None`) en vez de `5`. La falla confirma que el Bug 6 existe.
# NO se debe modificar `calcular_estado_cierre` (ni ningún otro código fuente) para hacer
# pasar estos tests.
#
# Bug Condition: estado == "REGULARIZA" AND nota_final != 5.
#
# NOTA sobre la discrepancia con `cierre-cursada-comision-nota-fix` (Bug 4 de esa spec,
# `test_regulariza_tiene_nota_final_none` / `test_bug_regulariza_con_numericos_...`):
# aquellos tests codifican la regla ANTERIOR (REGULARIZA -> Nota Final en blanco). Bug 6
# de esta spec sigue la instrucción explícita del usuario (REGULARIZA -> Nota Final = 5)
# y esa contradicción se resuelve en la fase de fix (tarea 9.3), donde esos tests se
# actualizarán. Ver "Decisión: Bug 6 vs modelo de referencia" en design.md.
# **Validates: Requirements 1.13**


def test_bug_regulariza_banda_global_opcional_deberia_tener_nota_final_5():
    """Bug 6: alumno REGULARIZA (parciales que cumplen la banda pero no el mínimo, con el
    global opcional ausente) -> esperado (tras el fix) `nota_final == 5`.
    HOY: `calcular_estado_cierre` asigna `nota_final = None` para todo estado != PROMOCIONA,
    así que devuelve `None` en vez de `5`."""
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=40.0, examen_id=1),  # banda 40, no minimo
        _examen(tipo="PARCIAL", nota_minima=70.0, valor_real=55.0, examen_id=2),  # banda 50, no minimo
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=None, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["nota_final"] == 5


def test_bug_regulariza_con_numericos_deberia_tener_nota_final_5():
    """Bug 6: alumno REGULARIZA con parciales y global numéricos (banda cumplida, mínimo
    no) -> esperado (tras el fix) `nota_final == 5` (valor fijo, NO la Nota Final
    ponderada). HOY: `calcular_estado_cierre` devuelve `None` para REGULARIZA."""
    examenes = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=45.0, examen_id=1),  # banda 40, no minimo
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=60.0, examen_id=2),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=9.0, examen_id=3),
    ]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"
    assert resultado["nota_final"] == 5
