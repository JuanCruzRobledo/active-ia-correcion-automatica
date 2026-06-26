"""Cliente de OpenRouter para validar la API key del usuario.

El workflow de n8n corrige usando OpenRouter como proveedor (modelo
``google/gemini-3.5-flash`` hardcodeado). La API key del usuario es una key de
OpenRouter (``sk-or-v1-...``) que se usa con autenticación ``Bearer``, NO una
key de Google. Por eso la validación debe pegarle a OpenRouter, no a
``generativelanguage.googleapis.com``.
"""

import httpx

from app.core.config import settings

# Statuses que indican que la KEY funciona (aunque la request puntual no genere).
# 200 = OK; 429 = rate limit (la key es válida, solo throttled).
_STATUS_VALIDOS = {200, 429}


def construir_payload_validacion(model: str) -> dict:
    """Arma el body mínimo para validar la key contra OpenRouter.

    Pide la generación más chica posible (``max_tokens=1``) para no gastar
    tokens de más en un simple health check.
    """
    return {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }


def api_key_valida_segun_status(status_code: int) -> bool:
    """Interpreta el status HTTP de OpenRouter como key válida/ inválida.

    Válida: 200 (OK) y 429 (rate limit: la key sirve, solo está throttled).
    Inválida: 401 (no autorizada), 403 (prohibida), 402 (sin créditos),
    400 (bad request) y cualquier otro.
    """
    return status_code in _STATUS_VALIDOS


def _construir_headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        # OpenRouter recomienda enviar estos para atribución de la app.
        "HTTP-Referer": "https://app.active-ia.com",
        "X-Title": "Active-IA",
    }


async def validar_api_key(api_key: str) -> bool:
    """Valida una API key de OpenRouter haciendo una consulta real al modelo.

    Pega a ``/chat/completions`` con ``google/gemini-3.5-flash`` (el mismo
    modelo que usa el workflow de corrección) y una generación mínima.

    Returns:
        True si la key es válida (auth OK), False en caso contrario.
    """
    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    payload = construir_payload_validacion(settings.OPENROUTER_MODEL)
    headers = _construir_headers(api_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            return api_key_valida_segun_status(response.status_code)
    except httpx.TimeoutException:
        # Timeout no implica key inválida, pero somos conservadores.
        return False
    except Exception:
        return False
