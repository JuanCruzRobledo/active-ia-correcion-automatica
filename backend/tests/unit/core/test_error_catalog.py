"""
Tests del catálogo de errores de corrección (item #1).

Traduce el código técnico del fallo (n8n/Gemini) a un mensaje claro y accionable en
español para el usuario. Es lógica pura (sin I/O).
"""

import pytest

from app.core.error_catalog import (
    ERROR_API_KEY_INVALID,
    ERROR_IA_RESPUESTA_INVALIDA,
    ERROR_N8N_TIMEOUT,
    ERROR_OVERLOADED,
    ERROR_RATE_LIMIT,
    mensaje_error,
)


@pytest.mark.parametrize(
    "code,fragmento",
    [
        (ERROR_RATE_LIMIT, "saturado"),
        (ERROR_OVERLOADED, "sobrecargado"),
        (ERROR_API_KEY_INVALID, "API Key"),
        (ERROR_N8N_TIMEOUT, "tardó"),
        (ERROR_IA_RESPUESTA_INVALIDA, "inválida"),
    ],
)
def test_mensaje_por_codigo_conocido(code, fragmento):
    msg = mensaje_error(code)
    assert fragmento.lower() in msg.lower()
    assert msg  # nunca vacío


def test_codigo_desconocido_devuelve_mensaje_generico():
    msg = mensaje_error("ALGO_RARO")
    assert msg
    assert "error" in msg.lower()


def test_codigo_none_devuelve_mensaje_generico():
    assert mensaje_error(None)
