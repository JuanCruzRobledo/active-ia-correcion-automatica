"""
IA-001: la nota final la calcula el BACKEND determinísticamente, no el modelo.

El bug: el responseSchema no dejaba al modelo devolver la condición de desaprobación,
así que el validador veía "no hay CD" y pisaba la nota capada (ej. 30) con la suma de
criterios (ej. 75), deshaciendo el techo en silencio. Ahora el modelo solo IDENTIFICA
qué CD se cumple (su id) y el backend calcula min(suma, techo) usando el techo de la
RÚBRICA (fuente autoritativa).
"""

from decimal import Decimal
from types import SimpleNamespace

from app.services.correccion_service import (
    _nota_deterministica,
    _penalizaciones_validas,
    _techo_de_condicion,
)


def _rubrica(cds=None, penas=None):
    return SimpleNamespace(
        condiciones_desaprobacion_json=cds or [],
        penalizaciones_json=penas or [],
    )


def _crit(p):
    return SimpleNamespace(puntaje_obtenido=Decimal(str(p)))


# ===================== _techo_de_condicion =====================


def test_techo_devuelve_nota_maxima_de_la_rubrica():
    r = _rubrica(cds=[{"id": "CD1", "condicion": "plagio", "nota_maxima": 30}])
    assert _techo_de_condicion(r, "CD1") == 30


def test_techo_none_si_no_hay_cd():
    r = _rubrica(cds=[{"id": "CD1", "nota_maxima": 30}])
    assert _techo_de_condicion(r, None) is None


def test_techo_none_si_el_id_no_existe_en_la_rubrica():
    """El modelo podría alucinar un id que no está en la rúbrica -> se ignora."""
    r = _rubrica(cds=[{"id": "CD1", "nota_maxima": 30}])
    assert _techo_de_condicion(r, "CD99") is None


# ===================== _penalizaciones_validas =====================


def test_penalizaciones_filtra_a_las_que_existen():
    r = _rubrica(penas=[{"id": "P1"}, {"id": "P2"}])
    assert _penalizaciones_validas(r, ["P1", "P99", "P2"]) == ["P1", "P2"]


def test_penalizaciones_vacio():
    assert _penalizaciones_validas(_rubrica(), None) == []


# ===================== _nota_deterministica =====================


def test_sin_cd_la_nota_es_la_suma():
    r = _rubrica()
    crits = [_crit(40), _crit(35)]  # suma 75
    resp = SimpleNamespace(condicion_desaprobacion_aplicada=None, penalizaciones_aplicadas=[])
    nota, antes, cond, penas = _nota_deterministica(crits, resp, r)
    assert nota == Decimal("75")
    assert antes is None          # sin CD no hay "antes del techo"
    assert cond is None


def test_con_cd_la_nota_se_capa_al_techo():
    """El caso del bug: suma 75, CD con techo 30 -> nota 30 (no 75)."""
    r = _rubrica(cds=[{"id": "CD1", "condicion": "plagio", "nota_maxima": 30}])
    crits = [_crit(40), _crit(35)]  # suma 75
    resp = SimpleNamespace(condicion_desaprobacion_aplicada="CD1", penalizaciones_aplicadas=[])
    nota, antes, cond, penas = _nota_deterministica(crits, resp, r)
    assert nota == Decimal("30")   # capada, NO 75
    assert antes == Decimal("75")  # se preserva la suma sin capar
    assert cond == "CD1"


def test_con_cd_pero_suma_menor_al_techo_usa_el_min():
    r = _rubrica(cds=[{"id": "CD1", "nota_maxima": 60}])
    crits = [_crit(20), _crit(25)]  # suma 45 < techo 60
    resp = SimpleNamespace(condicion_desaprobacion_aplicada="CD1", penalizaciones_aplicadas=[])
    nota, antes, cond, penas = _nota_deterministica(crits, resp, r)
    assert nota == Decimal("45")   # min(45, 60)
    assert cond == "CD1"


def test_cd_alucinada_no_capa():
    """Si el modelo devuelve un id que no está en la rúbrica, no se aplica techo."""
    r = _rubrica(cds=[{"id": "CD1", "nota_maxima": 30}])
    crits = [_crit(40), _crit(35)]  # suma 75
    resp = SimpleNamespace(condicion_desaprobacion_aplicada="CD_INVENTADA", penalizaciones_aplicadas=[])
    nota, antes, cond, penas = _nota_deterministica(crits, resp, r)
    assert nota == Decimal("75")   # sin cap
    assert cond is None


def test_penalizaciones_se_registran_pero_no_alteran_la_nota():
    r = _rubrica(penas=[{"id": "P1"}])
    crits = [_crit(40), _crit(35)]  # suma 75 (ya refleja las penalizaciones)
    resp = SimpleNamespace(condicion_desaprobacion_aplicada=None, penalizaciones_aplicadas=["P1"])
    nota, antes, cond, penas = _nota_deterministica(crits, resp, r)
    assert nota == Decimal("75")   # sin cambio
    assert penas == ["P1"]         # pero queda registrado


# ===================== regresión: schemas y prompts exponen los campos =====

def test_los_4_schemas_de_gemini_tienen_los_campos_nuevos():
    from app.integrations import gemini_correction_client as g

    for sch in (g._SCHEMA_CORRECCION_CODIGO, g._SCHEMA_CORRECCION_CODIGO_V2,
                g._SCHEMA_CORRECCION_PDF, g._SCHEMA_CORRECCION_PDF_V2):
        props = sch["properties"]
        assert "condicion_desaprobacion_aplicada" in props
        assert "penalizaciones_aplicadas" in props


def test_el_builder_de_condiciones_pide_devolver_el_id():
    from app.integrations.gemini_correction_client import _build_condiciones_texto

    texto = _build_condiciones_texto([{"id": "CD1", "condicion": "plagio", "nota_maxima": 30}])
    assert "CD1" in texto
    assert "condicion_desaprobacion_aplicada" in texto
