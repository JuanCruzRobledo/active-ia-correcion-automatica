"""Cliente de Gemini Studio (Google) para validar la API key del usuario.

Corresponde al modo de corrección ``correction_provider == "gemini"``. La key es
una API key de Google AI Studio y se valida pegándole directo a
``generativelanguage.googleapis.com`` con ``?key=...`` (NO auth Bearer).
"""

import httpx

# Modelo liviano para el health check (solo importa que la key autentique).
_VALIDATION_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

# 200 = OK; 429 = rate limit (la key es válida, solo throttled).
_STATUS_VALIDOS = {200, 429}


def construir_payload_validacion() -> dict:
    """Body mínimo para validar la key contra Gemini Studio."""
    return {"contents": [{"parts": [{"text": "Responde OK"}]}]}


def api_key_valida_segun_status(status_code: int) -> bool:
    """Interpreta el status HTTP de Google como key válida/inválida.

    Válida: 200 y 429 (rate limit). Inválida: 400 (key mal formada/no
    autorizada), 401, 403 y cualquier otro.
    """
    return status_code in _STATUS_VALIDOS


async def validar_api_key(api_key: str) -> bool:
    """Valida una API key de Gemini Studio con una llamada de prueba a Google."""
    payload = construir_payload_validacion()
    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{_VALIDATION_URL}?key={api_key}",
                json=payload,
                headers=headers,
            )
            return api_key_valida_segun_status(response.status_code)
    except httpx.TimeoutException:
        return False
    except Exception:
        return False
