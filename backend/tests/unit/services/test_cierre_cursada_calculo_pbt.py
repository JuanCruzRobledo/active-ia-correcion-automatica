"""
Tests basados en propiedades (PBT, `hypothesis`) de las funciones PURAS del
cierre de cursada — clasificación (`calcular_estado_cierre`) y Nota Final
(`calcular_nota_final`).

**Nota de organización (AGENTS.md, máximo 500 LOC por archivo)**: estas
propiedades se extrajeron a un archivo separado de
`test_cierre_cursada_calculo.py` (que ya contiene los tests unitarios
puntuales de las tareas 3, 4 y 5) para no superar el límite de 500 LOC.

Cubre las 12 propiedades de diseño ("Property-Based Tests" en `design.md`):

Clasificación (Property 1 — Requirements 2.1, 2.2, 2.3, 2.4, 2.5):
  1. Monotonía: cumple el mínimo en todos los exámenes (incl. GLOBAL) => PROMOCIONA.
  2. Regular ⊇ banda: cumple la banda en todos los no-globales y NO promociona => REGULARIZA.
  3. Recursa por defecto: algún no-global no cumple la banda => RECURSA.
  4. Borde en el mínimo: `valor == nota_minima` cumple el mínimo (`>=`, no `>`).
  5. Borde en la banda: `valor == nota_minima - banda` cumple la banda (4=6-2, 40=60-20).
  6. Escala 10 vs 100 no se cruzan: un valor válido en una escala da el mismo
     veredicto que su equivalente en la otra escala.
  7. Rescate => cumple_minimo: si alguna instancia (base o rescate) alcanza el
     mínimo, el `valor_real` (máximo entre todas) cumple el mínimo.
  8. Global: quitar el GLOBAL nunca cambia el veredicto REGULARIZA; agregar un
     GLOBAL no cumplido nunca permite PROMOCIONA.

Nota Final (Property 4 — Requirements 2.11, 2.13):
  9.  Rango [0, 10] cuando la NF no es `N/E`.
  10. `N/E` sólo por guard estructural (0 parciales o != 1 global) — un insumo
      faltante ya no produce `N/E`, cuenta como 0 (bugfix comisión-nota-fix).
  11. Monotonía no decreciente en cada insumo (antes de redondear).
  12. La escala no se filtra: el mismo examen en escala 100 o en escala 10
      produce la misma NF.
"""

from hypothesis import given, strategies as st

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
)

# nota_minima ∈ {6, 60, 50, 70} por indicación de la tarea (escala 10 y 100,
# incluyendo mínimos distintos de los "canónicos" 6/60).
NOTA_MINIMA_CHOICES = (6.0, 60.0, 50.0, 70.0)


def _examen(
    tipo="PARCIAL",
    modo="NUMERICO",
    nota_minima=60.0,
    valor_real=None,
    resultado_escala=None,
    examen_id=1,
):
    return {
        "examen_id": examen_id,
        "tipo": tipo,
        "modo_aprobacion": modo,
        "nota_minima": nota_minima,
        "valor_real": valor_real,
        "resultado_escala": resultado_escala,
    }


def _max_valor_por_escala(nota_minima):
    escala = detectar_escala(nota_minima)
    return 100.0 if escala == 100 else 10.0


# ===================== generadores (hypothesis) =====================


@st.composite
def _examen_cumple_minimo(draw, tipo):
    """Examen (PARCIAL/GLOBAL) que cumple su mínimo, en modo NUMERICO o ESCALA."""
    modo = draw(st.sampled_from(["NUMERICO", "ESCALA"]))
    examen_id = draw(st.integers(min_value=1, max_value=10_000))
    if modo == "ESCALA":
        return _examen(
            tipo=tipo, modo="ESCALA", nota_minima=None,
            resultado_escala="aprobado", examen_id=examen_id,
        )
    nota_minima = draw(st.sampled_from(NOTA_MINIMA_CHOICES))
    extra = draw(st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False))
    return _examen(
        tipo=tipo, modo="NUMERICO", nota_minima=nota_minima,
        valor_real=nota_minima + extra, examen_id=examen_id,
    )


@st.composite
def _examen_cumple_banda(draw, tipo, forzar_no_minimo=False):
    """Examen que cumple la banda de Regular.

    Si `forzar_no_minimo=True`, el examen cumple la banda pero NO el mínimo
    (sólo posible en modo NUMERICO: en ESCALA banda == mínimo).
    """
    modo = "NUMERICO" if forzar_no_minimo else draw(st.sampled_from(["NUMERICO", "ESCALA"]))
    examen_id = draw(st.integers(min_value=1, max_value=10_000))
    if modo == "ESCALA":
        return _examen(
            tipo=tipo, modo="ESCALA", nota_minima=None,
            resultado_escala="aprobado", examen_id=examen_id,
        )
    nota_minima = draw(st.sampled_from(NOTA_MINIMA_CHOICES))
    banda = banda_regular(nota_minima)
    if forzar_no_minimo:
        # `exclude_max=True` en el límite superior de un float no garantiza que
        # `nota_minima - banda + delta < nota_minima` una vez sumado: el resultado
        # puede redondear exactamente a `nota_minima` por precisión de floats
        # (p. ej. banda=2.0, delta=1.9999999999999998 -> 6.0 - 2.0 + delta == 6.0).
        # Se deja un margen explícito (1% de la banda, con piso 1e-6) para que el
        # valor generado quede estrictamente por debajo del mínimo, preservando la
        # premisa `forzar_no_minimo=True` (cumple banda, NO cumple mínimo).
        margen = max(banda * 0.01, 1e-6)
        delta = draw(
            st.floats(min_value=0.0, max_value=banda - margen, allow_nan=False, allow_infinity=False)
        )
        valor_real = nota_minima - banda + delta
        assert valor_real < nota_minima
    else:
        extra = draw(st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False))
        valor_real = nota_minima + extra
    return _examen(
        tipo=tipo, modo="NUMERICO", nota_minima=nota_minima,
        valor_real=valor_real, examen_id=examen_id,
    )


@st.composite
def _examen_no_cumple_banda(draw, tipo):
    """Examen que NO cumple la banda (por lo tanto tampoco el mínimo)."""
    modo = draw(st.sampled_from(["NUMERICO", "ESCALA"]))
    examen_id = draw(st.integers(min_value=1, max_value=10_000))
    if modo == "ESCALA":
        resultado_escala = draw(st.sampled_from(["desaprobado", "ausente"]))
        return _examen(
            tipo=tipo, modo="ESCALA", nota_minima=None,
            resultado_escala=resultado_escala, examen_id=examen_id,
        )
    nota_minima = draw(st.sampled_from(NOTA_MINIMA_CHOICES))
    banda = banda_regular(nota_minima)
    delta = draw(st.floats(min_value=0.001, max_value=50.0, allow_nan=False, allow_infinity=False))
    valor_real = nota_minima - banda - delta
    return _examen(
        tipo=tipo, modo="NUMERICO", nota_minima=nota_minima,
        valor_real=valor_real, examen_id=examen_id,
    )


@st.composite
def _examen_cualquiera(draw, tipo):
    """Examen con estado arbitrario (cumple o no cumple mínimo/banda)."""
    return draw(st.one_of(_examen_cumple_minimo(tipo), _examen_cumple_banda(tipo), _examen_no_cumple_banda(tipo)))


@st.composite
def _examen_numerico_valido(draw, tipo):
    """Examen NUMERICO con `valor_real` numérico válido en su escala (para NF)."""
    nota_minima = draw(st.sampled_from(NOTA_MINIMA_CHOICES))
    max_val = _max_valor_por_escala(nota_minima)
    valor_real = draw(st.floats(min_value=0.0, max_value=max_val, allow_nan=False, allow_infinity=False))
    examen_id = draw(st.integers(min_value=1, max_value=10_000))
    return _examen(tipo=tipo, modo="NUMERICO", nota_minima=nota_minima, valor_real=valor_real, examen_id=examen_id)


@st.composite
def _examen_generico_con_faltantes(draw, tipo):
    """Examen NUMERICO/ESCALA que puede o no tener `valor_real` (para N/E)."""
    modo = draw(st.sampled_from(["NUMERICO", "ESCALA"]))
    examen_id = draw(st.integers(min_value=1, max_value=10_000))
    if modo == "ESCALA":
        resultado_escala = draw(st.sampled_from(["aprobado", "desaprobado", "ausente"]))
        return _examen(
            tipo=tipo, modo="ESCALA", nota_minima=None,
            resultado_escala=resultado_escala, examen_id=examen_id,
        )
    nota_minima = draw(st.sampled_from(NOTA_MINIMA_CHOICES))
    max_val = _max_valor_por_escala(nota_minima)
    valor_real = draw(
        st.one_of(
            st.none(),
            st.floats(min_value=0.0, max_value=max_val, allow_nan=False, allow_infinity=False),
        )
    )
    return _examen(tipo=tipo, modo="NUMERICO", nota_minima=nota_minima, valor_real=valor_real, examen_id=examen_id)


# ===================== Property 1: monotonía => PROMOCIONA =====================
# **Validates: Requirements 2.1, 2.2, 2.3**


@given(
    parciales=st.lists(_examen_cumple_minimo("PARCIAL"), min_size=1, max_size=4),
    incluir_global=st.booleans(),
    global_examen=_examen_cumple_minimo("GLOBAL"),
)
def test_prop1_cumple_minimo_en_todos_siempre_promociona(parciales, incluir_global, global_examen):
    examenes = list(parciales)
    if incluir_global:
        examenes.append(global_examen)
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "PROMOCIONA"


# ===================== Property 2: Regular ⊇ banda =====================
# **Validates: Requirements 2.1, 2.3, 2.4**


@given(
    resto_parciales=st.lists(_examen_cumple_banda("PARCIAL", forzar_no_minimo=False), min_size=0, max_size=3),
    parcial_no_minimo=_examen_cumple_banda("PARCIAL", forzar_no_minimo=True),
    incluir_global=st.booleans(),
    global_examen=_examen_cumple_minimo("GLOBAL"),
)
def test_prop2_cumple_banda_en_no_globales_y_no_promociona_regulariza(
    resto_parciales, parcial_no_minimo, incluir_global, global_examen
):
    parciales = resto_parciales + [parcial_no_minimo]
    examenes = list(parciales)
    if incluir_global:
        examenes.append(global_examen)
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "REGULARIZA"


# ===================== Property 3: Recursa por defecto =====================
# **Validates: Requirements 2.1, 2.3**


@given(
    parcial_que_falla=_examen_no_cumple_banda("PARCIAL"),
    resto_parciales=st.lists(_examen_cualquiera("PARCIAL"), min_size=0, max_size=3),
    incluir_global=st.booleans(),
    global_examen=_examen_cualquiera("GLOBAL"),
)
def test_prop3_algun_no_global_sin_banda_siempre_recursa(
    parcial_que_falla, resto_parciales, incluir_global, global_examen
):
    examenes = [parcial_que_falla] + resto_parciales
    if incluir_global:
        examenes.append(global_examen)
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] == "RECURSA"


# ===================== Property 4: borde en el mínimo (>=) =====================
# **Validates: Requirements 2.4**


@given(nota_minima=st.sampled_from(NOTA_MINIMA_CHOICES))
def test_prop4_borde_exacto_en_el_minimo_cumple_inclusive(nota_minima):
    examen = _examen(nota_minima=nota_minima, valor_real=nota_minima)
    assert cumple_minimo(examen) is True


# ===================== Property 5: borde en la banda =====================
# **Validates: Requirements 2.4**


@given(nota_minima=st.sampled_from(NOTA_MINIMA_CHOICES))
def test_prop5_borde_exacto_en_la_banda_cumple_inclusive(nota_minima):
    banda = banda_regular(nota_minima)
    examen = _examen(nota_minima=nota_minima, valor_real=nota_minima - banda)
    assert cumple_banda(examen) is True


# ===================== Property 6: escalas 10 vs 100 no se cruzan =====================
# **Validates: Requirements 2.4, 2.5**


@given(v=st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False))
def test_prop6_valor_equivalente_en_otra_escala_da_mismo_veredicto(v):
    examen_escala_10 = _examen(nota_minima=6.0, valor_real=v)
    examen_escala_100 = _examen(nota_minima=60.0, valor_real=v * 10)
    assert cumple_minimo(examen_escala_10) == cumple_minimo(examen_escala_100)
    assert cumple_banda(examen_escala_10) == cumple_banda(examen_escala_100)


# ===================== Property 7: rescate => cumple_minimo =====================
# **Validates: Requirements 2.4** (bugfix 3.1 — cadena de rescate)


@given(
    nota_minima=st.sampled_from(NOTA_MINIMA_CHOICES),
    intentos=st.lists(
        st.one_of(st.none(), st.floats(min_value=0.0, max_value=150.0, allow_nan=False, allow_infinity=False)),
        min_size=1,
        max_size=4,
    ),
)
def test_prop7_alguna_instancia_de_rescate_alcanza_el_minimo_implica_cumple(nota_minima, intentos):
    valor_real = max_o_none(intentos)
    examen = _examen(nota_minima=nota_minima, valor_real=valor_real)
    algun_intento_alcanza_el_minimo = any(v is not None and v >= nota_minima for v in intentos)
    if algun_intento_alcanza_el_minimo:
        assert cumple_minimo(examen) is True


# ===================== Property 8: GLOBAL opcional para Regular / obligatorio para Promociona =====================
# **Validates: Requirements 2.2**


@given(
    resto_parciales=st.lists(_examen_cumple_banda("PARCIAL", forzar_no_minimo=False), min_size=0, max_size=2),
    parcial_no_minimo=_examen_cumple_banda("PARCIAL", forzar_no_minimo=True),
    global_examen=_examen_cualquiera("GLOBAL"),
)
def test_prop8a_quitar_el_global_no_cambia_el_veredicto_regular(resto_parciales, parcial_no_minimo, global_examen):
    parciales = resto_parciales + [parcial_no_minimo]

    estado_sin_global = calcular_estado_cierre(list(parciales))["estado"]
    estado_con_global = calcular_estado_cierre(list(parciales) + [global_examen])["estado"]

    assert estado_sin_global == "REGULARIZA"
    assert estado_con_global == "REGULARIZA"


@given(
    parciales=st.lists(_examen_cumple_minimo("PARCIAL"), min_size=1, max_size=3),
    global_no_cumplido=_examen_no_cumple_banda("GLOBAL"),
)
def test_prop8b_agregar_un_global_no_cumplido_bloquea_promociona(parciales, global_no_cumplido):
    examenes = list(parciales) + [global_no_cumplido]
    resultado = calcular_estado_cierre(examenes)
    assert resultado["estado"] != "PROMOCIONA"


# ===================== Property 9: rango [0, 10] de la Nota Final =====================
# **Validates: Requirements 2.11, 2.13**


@given(
    parciales=st.lists(_examen_numerico_valido("PARCIAL"), min_size=1, max_size=4),
    global_examen=_examen_numerico_valido("GLOBAL"),
)
def test_prop9_nota_final_siempre_en_rango_0_10(parciales, global_examen):
    examenes = list(parciales) + [global_examen]
    nf = calcular_nota_final(examenes)
    assert nf is not None
    assert 0 <= nf <= 10


# ===================== Property 10: N/E sólo por guard estructural =====================
#
# Tras el fix de la Nota Final (tarea 3.2, design.md "Bug 2 — Nota Final con no
# entregados como 0"), un insumo faltante (parcial sin nota, global sin nota, o
# ESCALA no aprobado) YA NO produce `None` ("N/E") — cuenta como 0 en la
# ponderación. `calcular_nota_final` SHALL devolver `None` únicamente por el
# guard estructural (0 parciales o != 1 global); en cualquier otro caso SHALL
# devolver SIEMPRE un `int` 0-10, sin importar cuántos insumos falten.
# **Validates: Requirements 2.3, 2.4, 2.6, 2.13**


@given(
    parciales=st.lists(_examen_generico_con_faltantes("PARCIAL"), min_size=0, max_size=3),
    globales=st.lists(_examen_generico_con_faltantes("GLOBAL"), min_size=0, max_size=2),
)
def test_prop10_ne_solo_por_guard_estructural(parciales, globales):
    examenes = parciales + globales
    nf = calcular_nota_final(examenes)

    guard_estructural = len(parciales) == 0 or len(globales) != 1

    if guard_estructural:
        assert nf is None
    else:
        assert nf is not None
        assert isinstance(nf, int)
        assert 0 <= nf <= 10


# ===================== Property 11: monotonía no decreciente =====================
# **Validates: Requirements 2.11**


@given(
    parciales=st.lists(_examen_numerico_valido("PARCIAL"), min_size=1, max_size=3),
    global_examen=_examen_numerico_valido("GLOBAL"),
    indice=st.integers(min_value=0, max_value=99),
    delta=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
def test_prop11_subir_un_insumo_nunca_reduce_la_nota_final(parciales, global_examen, indice, delta):
    examenes = list(parciales) + [global_examen]
    nf_base = calcular_nota_final(examenes)
    assert nf_base is not None

    idx = indice % len(examenes)
    examenes_subidos = [dict(e) for e in examenes]
    objetivo = examenes_subidos[idx]
    max_val = _max_valor_por_escala(objetivo["nota_minima"])
    objetivo["valor_real"] = min(objetivo["valor_real"] + delta, max_val)

    nf_subido = calcular_nota_final(examenes_subidos)
    assert nf_subido is not None
    assert nf_subido >= nf_base


# ===================== Property 12: la escala no se filtra =====================
# **Validates: Requirements 2.11, 2.13**


@given(
    v_parcial=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    v_global=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_prop12_misma_nota_final_en_escala_10_o_100(v_parcial, v_global):
    examenes_escala_10 = [
        _examen(tipo="PARCIAL", nota_minima=6.0, valor_real=v_parcial, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=6.0, valor_real=v_global, examen_id=2),
    ]
    examenes_escala_100 = [
        _examen(tipo="PARCIAL", nota_minima=60.0, valor_real=v_parcial * 10, examen_id=1),
        _examen(tipo="GLOBAL", nota_minima=60.0, valor_real=v_global * 10, examen_id=2),
    ]
    nf_10 = calcular_nota_final(examenes_escala_10)
    nf_100 = calcular_nota_final(examenes_escala_100)
    assert nf_10 == nf_100


# ===================== Property 13 (tarea 2, preservación): fórmula ponderada =====================
#
# Preservation (design.md, cierre-cursada-comision-nota-fix) — Req 3.4: para alumnos con
# TODOS sus exámenes numéricos (Bug 2 no se dispara), `calcular_nota_final` SHALL seguir
# devolviendo exactamente la fórmula ponderada actual (promedio de parciales normalizados
# a 0-10 al 40% + global normalizado a 0-10 al 60%, `round_half_up`), tanto antes como
# después del fix (que sólo cambia el tratamiento de los faltantes, no la fórmula en sí).
# Se recalcula la fórmula de forma independiente (sin reusar `calcular_nota_final`) y se
# compara contra el resultado observado -- cubre muchos casos, bordes de redondeo y
# escalas mixtas (parciales/global en escalas distintas entre sí).
# **Validates: Requirements 3.4**


@given(
    parciales=st.lists(_examen_numerico_valido("PARCIAL"), min_size=1, max_size=5),
    global_examen=_examen_numerico_valido("GLOBAL"),
)
def test_prop13_todo_numerico_coincide_con_formula_ponderada_normalizada(parciales, global_examen):
    examenes = list(parciales) + [global_examen]

    nf_observado = calcular_nota_final(examenes)

    parciales_norm_esperados = [
        normalizar_a_10(e["valor_real"], e["nota_minima"]) for e in parciales
    ]
    global_norm_esperado = normalizar_a_10(global_examen["valor_real"], global_examen["nota_minima"])
    promedio_esperado = sum(parciales_norm_esperados) / len(parciales_norm_esperados)
    nf_esperado = round_half_up(promedio_esperado * 0.4 + global_norm_esperado * 0.6)

    assert nf_observado == nf_esperado


# ===================== Property 6 (tarea 6, exploración, ANTES del fix) =====================
#
# Property 6: Bug Condition - Nota Final sólo para PROMOCIONA (design.md,
# isBugCondition_nota_no_promociona). CRITICAL: este test codifica el comportamiento
# ESPERADO tras el fix de Bug 4 -> DEBE FALLAR sobre `calcular_estado_cierre` SIN
# arreglar, que hoy devuelve `nota_final` numérica para CUALQUIER estado (no sólo
# PROMOCIONA), en vez de gatearla por `estado == "PROMOCIONA"`. La falla confirma que
# el Bug 4 existe. NO se debe modificar `calcular_estado_cierre` (ni ningún otro código
# fuente) para hacer pasar este test.
#
# Se generan >=1 PARCIAL + exactamente 1 GLOBAL (ambos con estado arbitrario vía
# `_examen_cualquiera`) para asegurar que el guard estructural de `calcular_nota_final`
# (0 parciales o != 1 global) NO se dispare -- así el veredicto SIEMPRE trae una Nota
# Final numérica salvo que el gate por estado (Bug 4) esté implementado.
# **Validates: Requirements 1.8, 1.9**


@given(
    parciales=st.lists(_examen_cualquiera("PARCIAL"), min_size=1, max_size=4),
    global_examen=_examen_cualquiera("GLOBAL"),
)
def test_prop6_bug_nota_final_solo_deberia_estar_presente_en_promociona(parciales, global_examen):
    # Nota: `_examen_cualquiera` reutiliza los generadores de clasificación de arriba
    # (Property 1-3), que permiten un `extra` sin acotar al techo de la escala -- válido
    # para esas propiedades (sólo comparan `>=`), pero puede producir un `valor_real`
    # fuera de 0-10/0-100 (ej. 12.0 en escala 10). Por eso acá NO se repite el chequeo de
    # rango 0-10 de la Nota Final para PROMOCIONA (ya cubierto por Property 9, que usa
    # `_examen_numerico_valido`, correctamente acotado a la escala); esta propiedad se
    # acota, como indica la tarea, a lo que hoy falla por el Bug 4: que `nota_final` NO
    # sea `None` para estados distintos de PROMOCIONA.
    examenes = list(parciales) + [global_examen]
    resultado = calcular_estado_cierre(examenes)
    nf = resultado["nota_final"]

    if resultado["estado"] == "PROMOCIONA":
        assert isinstance(nf, int)
    else:
        assert nf is None
