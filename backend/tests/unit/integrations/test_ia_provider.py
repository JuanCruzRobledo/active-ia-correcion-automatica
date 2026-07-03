"""Tests del dispatcher de proveedores de IA."""

import pytest

from app.integrations.ia_provider import (
    PROVIDER_GEMINI,
    PROVIDER_OPENROUTER,
    es_provider_valido,
    normalizar_provider,
)


class TestEsProviderValido:
    def test_gemini_valido(self):
        assert es_provider_valido(PROVIDER_GEMINI) is True

    def test_openrouter_valido(self):
        assert es_provider_valido(PROVIDER_OPENROUTER) is True

    def test_desconocido_invalido(self):
        assert es_provider_valido("anthropic") is False

    def test_none_invalido(self):
        assert es_provider_valido(None) is False


class TestNormalizarProvider:
    def test_default_es_gemini_cuando_vacio(self):
        # Un usuario sin provider explícito corrige con Gemini Studio.
        assert normalizar_provider(None) == PROVIDER_GEMINI
        assert normalizar_provider("") == PROVIDER_GEMINI

    def test_respeta_mayusculas_y_espacios(self):
        assert normalizar_provider(" OpenRouter ") == PROVIDER_OPENROUTER

    def test_desconocido_cae_a_gemini(self):
        assert normalizar_provider("foo") == PROVIDER_GEMINI
