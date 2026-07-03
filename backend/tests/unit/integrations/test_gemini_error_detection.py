"""Tests del mapeo de errores HTTP de Gemini a excepciones de dominio.

GeminiCorrectionClient llama directamente a la API de Gemini. Los errores
llegan como respuestas HTTP con un dict {"error": {"code": int, "message":
str, "status": str}} en vez de ser proxeados por N8N.

Verificamos que _detect_gemini_error() mapee correctamente cada escenario.
"""

import pytest

from app.core.exceptions import (
    APIKeyInvalidError,
    InsufficientCreditsError,
    ModelOverloadedError,
    N8NError,
    QuotaExceededError,
)
from app.integrations.gemini_correction_client import _detect_gemini_error


def _check(status_code: int, error: dict) -> None:
    _detect_gemini_error(status_code, error)


class TestAPIKeyInvalidError:
    def test_401_invalida(self):
        with pytest.raises(APIKeyInvalidError):
            _check(401, {"message": "Request had invalid authentication credentials", "status": "UNAUTHENTICATED"})

    def test_403_permission_denied(self):
        with pytest.raises(APIKeyInvalidError):
            _check(403, {"message": "Permission denied", "status": "PERMISSION_DENIED"})

    def test_400_api_key_not_valid(self):
        with pytest.raises(APIKeyInvalidError):
            _check(400, {"message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"})

    def test_400_api_key_expired(self):
        with pytest.raises(APIKeyInvalidError):
            _check(400, {"message": "API key expired", "status": "INVALID_ARGUMENT"})

    def test_unauthenticated_status(self):
        with pytest.raises(APIKeyInvalidError):
            _check(401, {"message": "No auth credentials", "status": "UNAUTHENTICATED"})


class TestQuotaExceededError:
    def test_429_rate_limit(self):
        with pytest.raises(QuotaExceededError):
            _check(429, {"message": "Quota exceeded for quota metric", "status": "RESOURCE_EXHAUSTED"})

    def test_resource_exhausted_status(self):
        with pytest.raises(QuotaExceededError):
            _check(429, {"message": "Too many requests", "status": "RESOURCE_EXHAUSTED"})


class TestModelOverloadedError:
    def test_503_unavailable(self):
        with pytest.raises(ModelOverloadedError):
            _check(503, {"message": "The model is overloaded. Please try again later.", "status": "UNAVAILABLE"})

    def test_unavailable_status(self):
        with pytest.raises(ModelOverloadedError):
            _check(503, {"message": "Service unavailable", "status": "UNAVAILABLE"})

    def test_overloaded_in_message(self):
        with pytest.raises(ModelOverloadedError):
            _check(200, {"message": "Model overloaded. High demand.", "status": "UNAVAILABLE"})


class TestInsufficientCreditsError:
    def test_402_sin_creditos(self):
        with pytest.raises(InsufficientCreditsError):
            _check(402, {"message": "Insufficient credits", "status": "FAILED_PRECONDITION"})


class TestGenericN8NError:
    def test_500_error_generico(self):
        with pytest.raises(N8NError):
            _check(500, {"message": "Internal error", "status": "INTERNAL"})

    def test_400_otro_error(self):
        with pytest.raises(N8NError):
            _check(400, {"message": "Request too large", "status": "INVALID_ARGUMENT"})
