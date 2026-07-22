"""
IA-014: el consumo de tokens se guardaba SOLO en raw_response (JSONB deferred), sin
agregación ni visibilidad de costos. Ahora se extrae a columnas queryables de la
corrección (tokens in/out, modelo, proveedor) para poder agregarlas sin parsear el
crudo.
"""

from app.services.correccion_service import _metricas_ia


def test_extrae_tokens_y_modelo_de_la_metadata():
    result = {
        "correccion": {},
        "metadata": {
            "modelo": "gemini-3.5-flash", "modo": "gemini",
            "tokens_entrada": 1200, "tokens_salida": 340, "tiempo_ms": 4100,
        },
    }
    m = _metricas_ia(result)
    assert m["tokens_entrada"] == 1200
    assert m["tokens_salida"] == 340
    assert m["ia_modelo"] == "gemini-3.5-flash"
    assert m["ia_proveedor"] == "gemini"


def test_openrouter_modo():
    result = {"metadata": {"modelo": "google/gemini-3.5-flash", "modo": "openrouter",
                           "tokens_entrada": 900, "tokens_salida": 200}}
    m = _metricas_ia(result)
    assert m["ia_proveedor"] == "openrouter"


def test_sin_metadata_devuelve_nulos():
    m = _metricas_ia({"correccion": {}})
    assert m["tokens_entrada"] is None
    assert m["ia_modelo"] is None


def test_result_none_no_rompe():
    m = _metricas_ia(None)
    assert m["tokens_entrada"] is None
