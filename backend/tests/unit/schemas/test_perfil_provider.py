"""Tests del schema de API key multi-proveedor."""

import pytest
from pydantic import ValidationError

from app.schemas.perfil import (
    UpdateApiKeyRequest,
    UpdateCorrectionProviderRequest,
)


class TestUpdateApiKeyRequest:
    def test_provider_default_es_gemini(self):
        req = UpdateApiKeyRequest(gemini_api_key="x" * 25)
        assert req.provider == "gemini"

    def test_acepta_openrouter(self):
        req = UpdateApiKeyRequest(gemini_api_key="x" * 25, provider="openrouter")
        assert req.provider == "openrouter"

    def test_rechaza_provider_desconocido(self):
        with pytest.raises(ValidationError):
            UpdateApiKeyRequest(gemini_api_key="x" * 25, provider="anthropic")

    def test_key_corta_falla(self):
        with pytest.raises(ValidationError):
            UpdateApiKeyRequest(gemini_api_key="corta", provider="gemini")


class TestUpdateCorrectionProviderRequest:
    def test_normaliza_mayusculas(self):
        req = UpdateCorrectionProviderRequest(provider="OpenRouter")
        assert req.provider == "openrouter"

    def test_rechaza_invalido(self):
        with pytest.raises(ValidationError):
            UpdateCorrectionProviderRequest(provider="foo")
