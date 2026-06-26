"""Detección de errores en el body de n8n, para Gemini Studio y OpenRouter.

El workflow OpenRouter envuelve los errores como:
  {"success": false, "error": {"code": "OPENROUTER_ERROR",
                               "message": "Error de OpenRouter [4xx]: ...", "retry": ...}}
"""

import pytest

from app.core.exceptions import (
    APIKeyInvalidError,
    InsufficientCreditsError,
    ModelOverloadedError,
    N8NError,
    QuotaExceededError,
)
from app.integrations.n8n_client import N8NClient


def _check(body: dict) -> None:
    N8NClient()._check_response_body_for_errors(body)


def _or_error(message: str) -> dict:
    return {"success": False, "error": {"code": "OPENROUTER_ERROR", "message": message}}


class TestOpenRouterErrors:
    def test_401_es_api_key_invalida(self):
        with pytest.raises(APIKeyInvalidError):
            _check(_or_error("Error de OpenRouter [401]: No auth credentials found"))

    def test_402_es_sin_creditos(self):
        with pytest.raises(InsufficientCreditsError):
            _check(_or_error("Error de OpenRouter [402]: insufficient credits"))

    def test_429_es_rate_limit(self):
        with pytest.raises(QuotaExceededError):
            _check(_or_error("Error de OpenRouter [429]: rate limited"))

    def test_503_es_overloaded(self):
        with pytest.raises(ModelOverloadedError):
            _check(_or_error("Error de OpenRouter [503]: provider overloaded"))

    def test_parsing_error_es_n8n_error(self):
        with pytest.raises(N8NError):
            _check(
                {
                    "success": False,
                    "error": {"code": "PARSING_ERROR", "message": "no 'choices'"},
                }
            )


class TestGeminiSigueAndando:
    def test_gemini_429_sigue_siendo_rate_limit(self):
        with pytest.raises(QuotaExceededError):
            _check({"error": {"status": 429, "message": "Too many requests"}})

    def test_gemini_api_key_invalid_por_reason(self):
        with pytest.raises(APIKeyInvalidError):
            _check(
                {
                    "error": {
                        "status": 400,
                        "message": "bad",
                        "details": [{"reason": "API_KEY_INVALID"}],
                    }
                }
            )

    def test_sin_error_no_lanza(self):
        # Respuesta exitosa: no debe lanzar nada.
        _check({"success": True, "correccion": {"nota": 8}})
