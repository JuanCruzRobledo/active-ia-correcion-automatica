"""
IA-010: el código del alumno se delimitaba con ``` (fence anidable): si el código
contenía ```, se escapaba del bloque y el resto se interpretaba como instrucciones.
Ahora se encierra en un tag ÚNICO no adivinable por request (<CODIGO_ALUMNO_hex>...)
generado con secrets, y el modelo marca injection_detectada.
"""
import inspect

from app.integrations import gemini_correction_client as g


def test_el_codigo_se_delimita_con_tag_unico_no_con_fence():
    src = inspect.getsource(g)
    # el tag se genera con secrets (único, no adivinable) por request
    assert "secrets.token_hex" in src
    assert 'f"CODIGO_ALUMNO_{secrets.token_hex' in src
    # el código va entre <tag> y </tag>, no dentro de un ``` fence
    assert "<{tag}>" in src
    assert "{codigo}" in src
    assert "</{tag}>" in src


def test_los_4_schemas_tienen_injection_detectada():
    for sch in (g._SCHEMA_CORRECCION_CODIGO, g._SCHEMA_CORRECCION_CODIGO_V2,
                g._SCHEMA_CORRECCION_PDF, g._SCHEMA_CORRECCION_PDF_V2):
        assert "injection_detectada" in sch["properties"]


def test_gemini_response_tiene_el_flag():
    from app.schemas.correccion import GeminiResponse

    assert "injection_detectada" in GeminiResponse.model_fields
