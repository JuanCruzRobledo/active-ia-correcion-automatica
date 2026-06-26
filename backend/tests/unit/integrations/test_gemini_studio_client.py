"""Tests de los helpers puros del cliente Gemini Studio (Google)."""

from app.integrations.gemini_studio_client import (
    construir_payload_validacion,
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
