"""
IA-007: la respuesta del LLM no se validaba contra la rúbrica. Alucinaciones del
modelo (criterio faltante o inventado, peso cambiado, puntaje inflado) se persistían
como corrección válida. Ahora se valida post-parse; ante divergencia se marca
IA_RESPUESTA_INVALIDA en vez de guardar una nota corrupta.
"""

from types import SimpleNamespace

from app.services.correccion_service import _problemas_respuesta_vs_rubrica


def _rubrica(crits):
    return SimpleNamespace(criterios_json=crits)


def _c(id, obt, maxi):
    return SimpleNamespace(id=id, puntaje_obtenido=obt, puntaje_maximo=maxi)


def test_respuesta_coherente_sin_problemas():
    r = _rubrica([{"id": "C1", "peso": 60}, {"id": "C2", "peso": 40}])
    resp = [_c("C1", 50, 60), _c("C2", 30, 40)]
    assert _problemas_respuesta_vs_rubrica(resp, r) == []


def test_criterio_faltante_es_problema():
    r = _rubrica([{"id": "C1", "peso": 60}, {"id": "C2", "peso": 40}])
    resp = [_c("C1", 50, 60)]  # falta C2
    problemas = _problemas_respuesta_vs_rubrica(resp, r)
    assert any("faltante" in p.lower() or "C2" in p for p in problemas)


def test_criterio_inventado_es_problema():
    r = _rubrica([{"id": "C1", "peso": 100}])
    resp = [_c("C1", 90, 100), _c("C_FALSO", 10, 10)]  # inventó uno
    problemas = _problemas_respuesta_vs_rubrica(resp, r)
    assert any("invent" in p.lower() or "C_FALSO" in p for p in problemas)


def test_puntaje_maximo_distinto_del_peso_es_problema():
    r = _rubrica([{"id": "C1", "peso": 60}])
    resp = [_c("C1", 50, 80)]  # el modelo cambió el techo del criterio a 80
    problemas = _problemas_respuesta_vs_rubrica(resp, r)
    assert any("peso" in p.lower() or "maximo" in p.lower() for p in problemas)


def test_puntaje_obtenido_mayor_al_maximo_es_problema():
    r = _rubrica([{"id": "C1", "peso": 60}])
    resp = [_c("C1", 75, 60)]  # obtuvo más que el máximo
    problemas = _problemas_respuesta_vs_rubrica(resp, r)
    assert any("fuera" in p.lower() or "75" in p for p in problemas)


def test_puntaje_negativo_es_problema():
    r = _rubrica([{"id": "C1", "peso": 60}])
    resp = [_c("C1", -5, 60)]
    assert _problemas_respuesta_vs_rubrica(resp, r) != []


def test_pdf_sin_ids_solo_valida_rangos():
    """En PDF los criterios pueden venir sin id: no se valida el set, pero sí los rangos."""
    r = _rubrica([{"id": "C1", "peso": 60}])
    resp = [_c(None, 50, 60)]      # sin id, dentro de rango -> OK
    assert _problemas_respuesta_vs_rubrica(resp, r) == []
    resp_mal = [_c(None, 99, 60)]  # sin id, fuera de rango -> problema
    assert _problemas_respuesta_vs_rubrica(resp_mal, r) != []
