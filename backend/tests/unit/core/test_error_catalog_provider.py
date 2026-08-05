"""Tests del catálogo de errores consciente del proveedor (Gemini / OpenRouter)."""

from app.core.error_catalog import (
    ERROR_API_KEY_INVALID,
    ERROR_OVERLOADED,
    ERROR_RATE_LIMIT,
    ERROR_SIN_CREDITOS,
    ERROR_N8N_TIMEOUT,
    mensaje_error,
)


class TestMensajeProviderAware:
    def test_rate_limit_gemini_menciona_gemini(self):
        msg = mensaje_error(ERROR_RATE_LIMIT, "gemini")
        assert "Gemini" in msg
        assert "OpenRouter" not in msg

    def test_rate_limit_openrouter_menciona_openrouter(self):
        msg = mensaje_error(ERROR_RATE_LIMIT, "openrouter")
        assert "OpenRouter" in msg
        assert "Gemini" not in msg

    def test_api_key_invalid_openrouter(self):
        msg = mensaje_error(ERROR_API_KEY_INVALID, "openrouter")
        assert "OpenRouter" in msg
        assert "Gemini" not in msg

    def test_overloaded_openrouter(self):
        msg = mensaje_error(ERROR_OVERLOADED, "openrouter")
        assert "OpenRouter" in msg
        assert "Gemini" not in msg

    def test_default_provider_es_gemini(self):
        # Retrocompatibilidad: sin provider explícito, asume Gemini.
        assert "Gemini" in mensaje_error(ERROR_RATE_LIMIT)


class TestSinCreditos:
    def test_sin_creditos_menciona_creditos(self):
        msg = mensaje_error(ERROR_SIN_CREDITOS, "openrouter")
        assert "crédito" in msg.lower()

    def test_sin_creditos_gemini_menciona_gemini(self):
        msg = mensaje_error(ERROR_SIN_CREDITOS, "gemini")
        assert "Gemini" in msg
        assert "OpenRouter" not in msg


class TestMensajesNeutros:
    def test_timeout_no_menciona_proveedor(self):
        # El timeout es del servicio de IA, no del proveedor: mismo texto siempre.
        assert mensaje_error(ERROR_N8N_TIMEOUT, "gemini") == mensaje_error(
            ERROR_N8N_TIMEOUT, "openrouter"
        )
