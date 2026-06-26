"""Tests de los helpers puros del cliente OpenRouter (validación de API key)."""

from app.integrations.openrouter_client import (
    construir_payload_validacion,
    api_key_valida_segun_status,
)


class TestConstruirPayloadValidacion:
    def test_usa_el_modelo_indicado(self):
        payload = construir_payload_validacion("google/gemini-3.5-flash")
        assert payload["model"] == "google/gemini-3.5-flash"

    def test_pide_la_minima_generacion_posible(self):
        # Para no gastar tokens de más en un simple health check.
        payload = construir_payload_validacion("google/gemini-3.5-flash")
        assert payload["max_tokens"] == 1
        assert isinstance(payload["messages"], list)
        assert payload["messages"][0]["role"] == "user"

    def test_modelo_distinto_se_refleja(self):
        payload = construir_payload_validacion("openai/gpt-4o-mini")
        assert payload["model"] == "openai/gpt-4o-mini"


class TestApiKeyValidaSegunStatus:
    def test_200_es_valida(self):
        assert api_key_valida_segun_status(200) is True

    def test_429_rate_limit_es_valida(self):
        # La key funciona, solo está throttled: no la rechazamos.
        assert api_key_valida_segun_status(429) is True

    def test_401_no_autorizada_es_invalida(self):
        assert api_key_valida_segun_status(401) is False

    def test_403_prohibida_es_invalida(self):
        assert api_key_valida_segun_status(403) is False

    def test_402_sin_creditos_es_invalida(self):
        # Sin créditos la corrección fallaría: no sirve como key válida.
        assert api_key_valida_segun_status(402) is False

    def test_400_bad_request_es_invalida(self):
        assert api_key_valida_segun_status(400) is False
