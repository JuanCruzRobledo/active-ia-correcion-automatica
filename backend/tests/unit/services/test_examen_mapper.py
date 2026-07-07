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


def test_valor_real_es_mejor_valor_numerico_entre_base_y_rescate():
    # Parcial NUMERICO desaprobado (50) + recuperatorio NUMERICO aprobado (70) ->
    # valor_real = máximo entre base y rescates = 70.0 (no rompe `resultado`/`rescatado`).
    cfg = [
        _ex(1, "PARCIAL", 100, modo="NUMERICO", nota_minima=60.0),
        _ex(2, "RECUPERATORIO", 200, modo="NUMERICO", nota_minima=60.0, recupera=1),
    ]
    res = _por_examen(
        calcular_resultados_examenes({100: "50,00", 200: "70,00"}, cfg)
    )
    assert res[1]["valor_real"] == 70.0
    assert res[1]["resultado"] == "aprobado"
    assert res[1]["rescatado"] is True


def test_valor_real_toma_la_base_si_es_mayor_que_el_rescate():
    cfg = [
        _ex(1, "PARCIAL", 100, modo="NUMERICO", nota_minima=60.0),
        _ex(2, "RECUPERATORIO", 200, modo="NUMERICO", nota_minima=60.0, recupera=1),
    ]
    res = _por_examen(
        calcular_resultados_examenes({100: "90,00", 200: "70,00"}, cfg)
    )
    assert res[1]["valor_real"] == 90.0


def test_valor_real_none_cuando_falta_la_nota():
    cfg = [_ex(1, "PARCIAL", 100, modo="NUMERICO", nota_minima=60.0)]
    res = _por_examen(calcular_resultados_examenes({}, cfg))
    assert res[1]["valor_real"] is None
    assert res[1]["resultado"] == "ausente"


def test_valor_real_none_en_modo_escala():
    # Modo ESCALA no tiene escala numérica: valor_real siempre None, aunque el
    # `resultado` de escala sea 'aprobado'. El cierre lo evalúa por `resultado`.
    cfg = [_ex(1, "PARCIAL", 100, modo="ESCALA")]
    res = _por_examen(calcular_resultados_examenes({100: "Aprobado"}, cfg))
    assert res[1]["valor_real"] is None
    assert res[1]["resultado"] == "aprobado"


def test_modo_aprobacion_y_nota_minima_expuestos_del_principal():
    cfg = [_ex(1, "PARCIAL", 100, modo="NUMERICO", nota_minima=60.0)]
    res = _por_examen(calcular_resultados_examenes({100: "70,00"}, cfg))
    assert res[1]["modo_aprobacion"] == "NUMERICO"
    assert res[1]["nota_minima"] == 60.0


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


# ===================== Property-Based Tests (preservación — bugfix cierre-cursada-fix) =====================
#
# Metodología observación-primero: capturan el comportamiento YA EXISTENTE de
# examen_mapper (rescate + evaluación por escala) para que sigan pasando tanto ANTES
# como DESPUÉS del fix de cierre de cursada — este módulo no cambia con el fix salvo
# la extensión aditiva de `valor_real` (tarea 7).
#
# Validates: Requirements 3.1, 3.2

from hypothesis import given, strategies as st

# Precedencia documentada en bugfix.md/design.md: aprobado > sin_corregir > desaprobado
# > ausente. Se reimplementa acá (no se importa el privado del módulo) porque es la
# propiedad que se quiere preservar, no un detalle de implementación.
_PRECEDENCIA_ESPERADA = {"ausente": 0, "desaprobado": 1, "sin_corregir": 2, "aprobado": 3}

_NOTA_ESCALA = st.sampled_from(["Aprobado", "Desaprobado", "", "-"])


@given(
    base_nota=_NOTA_ESCALA,
    rescates_notas=st.lists(_NOTA_ESCALA, min_size=1, max_size=3),
)
def test_pbt_cadena_de_rescate_respeta_precedencia(base_nota, rescates_notas):
    """Property 2 (Preservación) — Req 3.1: un PARCIAL/GLOBAL con N rescates
    (recuperatorio/extensión/extraordinaria) queda con el resultado de MAYOR
    precedencia entre él y sus rescates (aprobado > sin_corregir > desaprobado >
    ausente), y `rescatado` es True sii el base no estaba aprobado pero el
    resultado final sí."""
    cfg = [_ex(1, "PARCIAL", 100)]
    notas = {100: base_nota}
    for i, nota in enumerate(rescates_notas, start=1):
        cmid_rescate = 200 + i
        cfg.append(_ex(100 + i, "RECUPERATORIO", cmid_rescate, recupera=1))
        notas[cmid_rescate] = nota

    resultado = _por_examen(calcular_resultados_examenes(notas, cfg))[1]

    interpretados = [
        interpretar_resultado(t, "ESCALA", None) for t in [base_nota, *rescates_notas]
    ]
    esperado = max(interpretados, key=lambda r: _PRECEDENCIA_ESPERADA[r])
    base_interpretado = interpretados[0]

    assert resultado["resultado"] == esperado
    assert resultado["rescatado"] == (base_interpretado != "aprobado" and esperado == "aprobado")


def test_pbt_ejemplo_documentado_desaprobado_mas_recuperatorio_aprobado():
    """Ejemplo puntual documentado en la tarea: parcial desaprobado + recuperatorio
    aprobado -> resultado == 'aprobado' y rescatado == True."""
    cfg = [_ex(1, "PARCIAL", 100), _ex(2, "RECUPERATORIO", 200, recupera=1)]
    res = _por_examen(
        calcular_resultados_examenes({100: "Desaprobado", 200: "Aprobado"}, cfg)
    )
    assert res[1]["resultado"] == "aprobado"
    assert res[1]["rescatado"] is True


_NOTA_NUMERICA_TEXTO = st.one_of(
    st.none(),
    st.just(""),
    st.just("-"),
    st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False).map(
        lambda v: f"{v:.2f}".replace(".", ",")
    ),
)


@given(
    base_texto=_NOTA_NUMERICA_TEXTO,
    rescates_textos=st.lists(_NOTA_NUMERICA_TEXTO, min_size=1, max_size=3),
)
def test_pbt_valor_real_es_el_maximo_numerico_entre_base_y_rescates(base_texto, rescates_textos):
    """Property (tarea 7, aditiva) — Req 3.1: en modo NUMERICO, `valor_real` del principal
    es el máximo valor numérico parseable (`parsear_nota_numerica`) entre la instancia base
    y sus rescates, sin alterar `resultado`/`rescatado` (que siguen la precedencia de
    escala preexistente)."""
    cfg = [_ex(1, "PARCIAL", 100, modo="NUMERICO", nota_minima=60.0)]
    notas = {100: base_texto}
    for i, texto in enumerate(rescates_textos, start=1):
        cmid_rescate = 200 + i
        cfg.append(
            _ex(100 + i, "RECUPERATORIO", cmid_rescate, modo="NUMERICO", nota_minima=60.0, recupera=1)
        )
        notas[cmid_rescate] = texto

    resultado = _por_examen(calcular_resultados_examenes(notas, cfg))[1]

    valores = [parsear_nota_numerica(t) for t in [base_texto, *rescates_textos]]
    numericos = [v for v in valores if v is not None]
    esperado = max(numericos) if numericos else None

    assert resultado["valor_real"] == esperado


@given(nota=st.sampled_from(["Aprobado", "Desaprobado", "", "-", None]))
def test_pbt_valor_real_none_en_modo_escala(nota):
    """Property (tarea 7, aditiva) — Req 3.2: en modo ESCALA, `valor_real` siempre es
    `None` (no hay escala numérica), sin importar el `resultado` obtenido."""
    cfg = [_ex(1, "PARCIAL", 100, modo="ESCALA")]
    resultado = _por_examen(calcular_resultados_examenes({100: nota}, cfg))[1]
    assert resultado["valor_real"] is None


_ESCALA_TEXTOS = st.sampled_from(
    [
        "Aprobado", "APROBADO", "aprobado", "  Aprobado  ",
        "Desaprobado", "DESAPROBADO", "desaprobado", "  Desaprobado  ",
        "", "-", "   ", None,
    ]
)


@given(
    nota=_ESCALA_TEXTOS,
    nota_minima=st.one_of(st.none(), st.floats(min_value=-50, max_value=200, allow_nan=False)),
)
def test_pbt_examen_escala_se_evalua_por_escala_no_por_nota_numerica(nota, nota_minima):
    """Property 2 (Preservación) — Req 3.2: un examen en modo ESCALA se evalúa por
    'Aprobado'/'Desaprobado'/vacío -> aprobado/desaprobado/ausente, y el resultado NO
    depende de `nota_minima` (a diferencia de NUMERICO)."""
    resultado = interpretar_resultado(nota, "ESCALA", nota_minima)

    t = (nota or "").strip().lower()
    if not t or t == "-":
        esperado = "ausente"
    elif "desaprob" in t:
        esperado = "desaprobado"
    else:
        esperado = "aprobado"

    assert resultado == esperado
    # nota_minima es irrelevante en modo ESCALA.
    assert resultado == interpretar_resultado(nota, "ESCALA", None)
