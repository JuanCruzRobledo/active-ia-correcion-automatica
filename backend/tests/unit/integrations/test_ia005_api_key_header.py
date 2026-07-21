"""
IA-005: la API key de Gemini NO debe viajar en el query string de la URL (httpx
loguea la URL completa a nivel INFO -> fuga latente de credenciales de los tutores
hacia logs/observabilidad). Debe ir en el header x-goog-api-key.
"""


def test_url_de_generate_no_contiene_la_key():
    from app.integrations.gemini_correction_client import GeminiCorrectionClient

    client = GeminiCorrectionClient()
    url = client._generate_url("SECRETA-123")
    assert "SECRETA-123" not in url
    assert "?key=" not in url


def test_url_de_upload_no_contiene_la_key():
    from app.integrations.gemini_correction_client import GeminiCorrectionClient

    client = GeminiCorrectionClient()
    url = client._upload_url("SECRETA-123")
    assert "SECRETA-123" not in url
    assert "?key=" not in url


def test_los_posts_usan_el_header_x_goog_api_key():
    import inspect

    from app.integrations import gemini_correction_client, gemini_studio_client

    for mod in (gemini_correction_client, gemini_studio_client):
        src = inspect.getsource(mod)
        assert "x-goog-api-key" in src


def test_validacion_no_pone_la_key_en_la_url():
    import inspect

    from app.integrations import gemini_studio_client

    src = inspect.getsource(gemini_studio_client)
    assert "?key=" not in src
