# app/core/error_catalog.py
"""
Catálogo de errores de corrección (item #1).

Traduce el código técnico del fallo (n8n/Gemini) a un mensaje CLARO y accionable en
español, listo para mostrarle al usuario. Una sola fuente de verdad para el texto, así
backend (persistencia + HTTP) y frontend (toast/tabla) dicen lo mismo.
"""

# Códigos de error (se persisten en entrega.error_code y viajan al frontend).
ERROR_RATE_LIMIT = "GEMINI_RATE_LIMIT"
ERROR_OVERLOADED = "GEMINI_OVERLOADED"
ERROR_API_KEY_INVALID = "GEMINI_API_KEY_INVALID"
ERROR_N8N_TIMEOUT = "N8N_TIMEOUT"
ERROR_N8N = "N8N_ERROR"
ERROR_IA_RESPUESTA_INVALIDA = "IA_RESPUESTA_INVALIDA"

_GENERICO = "Ocurrió un error al corregir. Reintentá; si persiste, avisá al equipo."

MENSAJES: dict[str, str] = {
    ERROR_RATE_LIMIT: (
        "Gemini saturado: alcanzaste el límite de uso de tu API. "
        "Esperá unos minutos y volvé a intentar."
    ),
    ERROR_OVERLOADED: (
        "El modelo de Gemini está sobrecargado en este momento. "
        "Reintentá en unos minutos."
    ),
    ERROR_API_KEY_INVALID: (
        "Tu API Key de Gemini no es válida o expiró. "
        "Generá una nueva y actualizala en tu perfil."
    ),
    ERROR_N8N_TIMEOUT: (
        "El servicio de IA tardó demasiado en responder. Reintentá la corrección."
    ),
    ERROR_N8N: _GENERICO,
    ERROR_IA_RESPUESTA_INVALIDA: (
        "La IA devolvió una respuesta inválida. Reintentá la corrección."
    ),
}


def mensaje_error(code: str | None) -> str:
    """Código de error → mensaje claro en español. Genérico si no se reconoce."""
    if not code:
        return _GENERICO
    return MENSAJES.get(code, _GENERICO)
