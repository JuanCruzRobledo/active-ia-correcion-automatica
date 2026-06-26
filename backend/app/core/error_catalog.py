# app/core/error_catalog.py
"""
Catálogo de errores de corrección (item #1, multi-proveedor).

Traduce el código técnico del fallo (n8n / Gemini Studio / OpenRouter) a un mensaje
CLARO y accionable en español, listo para mostrarle al usuario. Una sola fuente de
verdad para el texto, así backend (persistencia + HTTP) y frontend (toast/tabla) dicen
lo mismo. El mensaje se adapta al proveedor activo: en modo OpenRouter NO hablamos de
"Gemini", y viceversa.
"""

# Códigos de error (se persisten en entrega.error_code y viajan al frontend).
# Se mantienen los nombres históricos (con prefijo GEMINI_) para no romper datos ya
# guardados ni el resumen del frontend; el texto sí es ahora provider-aware.
ERROR_RATE_LIMIT = "GEMINI_RATE_LIMIT"
ERROR_OVERLOADED = "GEMINI_OVERLOADED"
ERROR_API_KEY_INVALID = "GEMINI_API_KEY_INVALID"
ERROR_SIN_CREDITOS = "SIN_CREDITOS"
ERROR_N8N_TIMEOUT = "N8N_TIMEOUT"
ERROR_N8N = "N8N_ERROR"
ERROR_IA_RESPUESTA_INVALIDA = "IA_RESPUESTA_INVALIDA"

_GENERICO = "Ocurrió un error al corregir. Reintentá; si persiste, avisá al equipo."

# Nombre visible del proveedor para los mensajes.
_PROVIDER_LABEL = {
    "gemini": "Gemini",
    "openrouter": "OpenRouter",
}


def _label(provider: str | None) -> str:
    return _PROVIDER_LABEL.get((provider or "gemini").strip().lower(), "Gemini")


# Mensajes que dependen del proveedor (reciben el label).
_MENSAJES_POR_PROVEEDOR: dict[str, str] = {
    ERROR_RATE_LIMIT: (
        "{label} saturado: alcanzaste el límite de uso de tu API. "
        "Esperá unos minutos y volvé a intentar."
    ),
    ERROR_OVERLOADED: (
        "El modelo de {label} está sobrecargado en este momento. "
        "Reintentá en unos minutos."
    ),
    ERROR_API_KEY_INVALID: (
        "Tu API Key de {label} no es válida o expiró. "
        "Generá una nueva y actualizala en tu perfil."
    ),
}

# Mensajes neutros (no dependen del proveedor).
_MENSAJES_NEUTROS: dict[str, str] = {
    ERROR_SIN_CREDITOS: (
        "Tu cuenta de OpenRouter no tiene créditos suficientes. "
        "Cargá créditos y volvé a intentar."
    ),
    ERROR_N8N_TIMEOUT: (
        "El servicio de IA tardó demasiado en responder. Reintentá la corrección."
    ),
    ERROR_N8N: _GENERICO,
    ERROR_IA_RESPUESTA_INVALIDA: (
        "La IA devolvió una respuesta inválida. Reintentá la corrección."
    ),
}


def mensaje_error(code: str | None, provider: str | None = "gemini") -> str:
    """Código de error → mensaje claro en español, adaptado al proveedor.

    Args:
        code: Código del catálogo (ERROR_*). Genérico si no se reconoce.
        provider: Proveedor activo ("gemini" | "openrouter"); ajusta el texto de
            los mensajes que nombran al proveedor. Default "gemini" (retrocompat).
    """
    if not code:
        return _GENERICO
    if code in _MENSAJES_POR_PROVEEDOR:
        return _MENSAJES_POR_PROVEEDOR[code].format(label=_label(provider))
    return _MENSAJES_NEUTROS.get(code, _GENERICO)
