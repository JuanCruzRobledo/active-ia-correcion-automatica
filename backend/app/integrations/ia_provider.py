"""Dispatcher de proveedores de IA para la corrección automática.

El tutor elige el modo de corrección (``correction_provider``):
- ``"gemini"``     → Gemini Studio (Google), key directa a generativelanguage.
- ``"openrouter"`` → OpenRouter (modelo google/gemini-3.5-flash), auth Bearer.

Cada modo guarda su propia API key por separado y valida contra su proveedor.
"""

from app.integrations import gemini_studio_client, openrouter_client

PROVIDER_GEMINI = "gemini"
PROVIDER_OPENROUTER = "openrouter"

PROVIDERS_VALIDOS = frozenset({PROVIDER_GEMINI, PROVIDER_OPENROUTER})

# Path del webhook de corrección de texto en n8n, por proveedor.
# gemini → workflow histórico (Gemini Studio directo);
# openrouter → workflow nuevo (OpenRouter, modelo google/gemini-3.5-flash).
_WEBHOOK_PATHS = {
    PROVIDER_GEMINI: "corregir",
    PROVIDER_OPENROUTER: "corregir-openrouter",
}


def es_provider_valido(provider: str | None) -> bool:
    """True si el provider es uno de los soportados."""
    return provider in PROVIDERS_VALIDOS


def normalizar_provider(provider: str | None) -> str:
    """Normaliza el provider; cae a Gemini Studio si es vacío/desconocido.

    Gemini Studio es el modo histórico/por defecto: un usuario sin provider
    explícito (o con un valor raro) corrige con Gemini.
    """
    if not provider:
        return PROVIDER_GEMINI
    limpio = provider.strip().lower()
    return limpio if limpio in PROVIDERS_VALIDOS else PROVIDER_GEMINI


def webhook_path(provider: str | None) -> str:
    """Path del webhook de corrección de n8n para el proveedor dado."""
    return _WEBHOOK_PATHS[normalizar_provider(provider)]


async def validar_api_key(provider: str, api_key: str) -> bool:
    """Valida la API key contra el proveedor correspondiente."""
    if normalizar_provider(provider) == PROVIDER_OPENROUTER:
        return await openrouter_client.validar_api_key(api_key)
    return await gemini_studio_client.validar_api_key(api_key)
