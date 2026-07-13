"""Tests de los helpers puros del cliente Gemini Studio (Google)."""

import asyncio

from app.core.config import settings
from app.integrations import gemini_studio_client
from app.integrations.gemini_studio_client import (
    construir_payload_validacion,
    construir_url_validacion,
    api_key_valida_segun_status,
)


class TestConstruirPayloadValidacion:
    def test_tiene_contents_con_texto(self):
        payload = construir_payload_validacion()
        assert "contents" in payload
        assert payload["contents"][0]["parts"][0]["text"]


class TestApiKeyValidaSegunStatus:
    def test_200_es_valida(self):
        assert api_key_valida_segun_status(200) is True

    def test_400_es_invalida(self):
        # Google devuelve 400 para key inválida o mal formada.
        assert api_key_valida_segun_status(400) is False

    def test_401_403_invalidas(self):
        assert api_key_valida_segun_status(401) is False
        assert api_key_valida_segun_status(403) is False

    def test_429_es_valida(self):
        # Rate limit: la key sirve, solo está throttled.
        assert api_key_valida_segun_status(429) is True


class TestConstruirUrlValidacion:
    def test_usa_el_modelo_configurado(self):
        # BUG-001: la validación debe apuntar al MISMO modelo que corrige.
        url = construir_url_validacion(settings.GEMINI_MODEL)
        assert settings.GEMINI_MODEL in url

    def test_refleja_el_modelo_recibido(self):
        # Triangulación: la URL sigue al modelo, no hay literal fijo adentro.
        assert "gemini-x-test" in construir_url_validacion("gemini-x-test")

    def test_apunta_a_generatecontent_de_google(self):
        url = construir_url_validacion("gemini-x-test")
        assert url.startswith("https://generativelanguage.googleapis.com/")
        assert url.endswith(":generateContent")


class _FakeResponse:
    status_code = 200


class _FakeAsyncClient:
    """Sustituto de httpx.AsyncClient que solo registra la URL llamada."""

    urls: list[str] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        _FakeAsyncClient.urls.append(url)
        return _FakeResponse()


class TestValidarApiKeyUsaElModeloConfigurado:
    def test_pega_al_modelo_de_settings_y_no_a_un_literal(self, monkeypatch):
        # Test de regresión de BUG-001: si alguien vuelve a hardcodear el modelo,
        # este test lo detecta porque la URL dejaría de seguir a settings.
        _FakeAsyncClient.urls = []
        monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-x-test")
        monkeypatch.setattr(
            gemini_studio_client.httpx, "AsyncClient", _FakeAsyncClient
        )

        assert asyncio.run(gemini_studio_client.validar_api_key("una-key")) is True
        assert "gemini-x-test" in _FakeAsyncClient.urls[0]
