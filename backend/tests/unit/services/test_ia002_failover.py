"""
IA-002: failover acotado entre proveedores de IA.

El brief prometía primario/fallback (Gemini → OpenRouter) pero el código ruteaba
el 100% al proveedor elegido, sin caída. Ahora, ante un error RECUPERABLE
(timeout / 503 / 5xx) y solo si el tutor tiene key VÁLIDA del secundario, la
corrección de código cae al otro proveedor. Nunca ante errores no recuperables
(401/403/402/429) y nunca en PDF (OpenRouter no lo soporta).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    APIKeyInvalidError,
    InsufficientCreditsError,
    ModelOverloadedError,
    N8NError,
    N8NTimeoutError,
    QuotaExceededError,
)
from app.services.correccion_service import CorreccionService


def _service() -> CorreccionService:
    svc = CorreccionService(MagicMock())
    svc.usuario_repo = MagicMock()
    svc._build_correction_payload = MagicMock(return_value={"api_key": "SEC"})
    return svc


def _usuario(*, gem_enc="gem-enc", gem_valid=True, or_enc="or-enc", or_valid=True):
    u = MagicMock()
    u.gemini_api_key_encrypted = gem_enc
    u.gemini_api_key_valid = gem_valid
    u.openrouter_api_key_encrypted = or_enc
    u.openrouter_api_key_valid = or_valid
    return u


# ---------------------------------------------------------------- _otro_provider

def test_otro_provider_es_el_opuesto():
    svc = _service()
    assert svc._otro_provider("gemini") == "openrouter"
    assert svc._otro_provider("openrouter") == "gemini"


# ------------------------------------------------------- _credencial_secundaria

@pytest.mark.asyncio
async def test_credencial_secundaria_devuelve_key_si_valida():
    svc = _service()
    svc.usuario_repo.get_by_id = AsyncMock(return_value=_usuario(or_enc="X", or_valid=True))
    with patch(
        "app.services.correccion_service.decrypt_api_key", return_value="plain-or"
    ):
        key = await svc._credencial_secundaria(1, "openrouter")
    assert key == "plain-or"


@pytest.mark.asyncio
async def test_credencial_secundaria_none_si_flag_invalido():
    svc = _service()
    svc.usuario_repo.get_by_id = AsyncMock(return_value=_usuario(or_enc="X", or_valid=False))
    assert await svc._credencial_secundaria(1, "openrouter") is None


@pytest.mark.asyncio
async def test_credencial_secundaria_none_si_no_hay_key():
    svc = _service()
    svc.usuario_repo.get_by_id = AsyncMock(return_value=_usuario(or_enc=None, or_valid=True))
    assert await svc._credencial_secundaria(1, "openrouter") is None


# ------------------------------------------------- _corregir_codigo_con_failover

@pytest.mark.asyncio
@pytest.mark.parametrize("error", [N8NTimeoutError("t"), ModelOverloadedError("503"), N8NError("5xx")])
async def test_failover_ante_error_recuperable_usa_secundario(error):
    svc = _service()
    svc.usuario_repo.get_by_id = AsyncMock(return_value=_usuario())

    async def call(payload, provider="gemini", **kw):
        if provider == "gemini":
            raise error
        return {"metadata": {"modo": "openrouter"}, "ok": True}

    svc._call_ia_with_retry = AsyncMock(side_effect=call)
    with patch("app.services.correccion_service.decrypt_api_key", return_value="plain"):
        result, efectivo = await svc._corregir_codigo_con_failover(
            {"api_key": "PRIM"}, MagicMock(), MagicMock(), "gemini", 7
        )
    assert efectivo == "openrouter"
    assert result["ok"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [APIKeyInvalidError("401"), InsufficientCreditsError("402"), QuotaExceededError("429")]
)
async def test_sin_failover_ante_error_no_recuperable(error):
    svc = _service()
    svc.usuario_repo.get_by_id = AsyncMock(return_value=_usuario())
    llamadas = []

    async def call(payload, provider="gemini", **kw):
        llamadas.append(provider)
        raise error

    svc._call_ia_with_retry = AsyncMock(side_effect=call)
    with pytest.raises(type(error)):
        await svc._corregir_codigo_con_failover(
            {"api_key": "PRIM"}, MagicMock(), MagicMock(), "gemini", 7
        )
    # nunca se intentó el secundario
    assert llamadas == ["gemini"]


@pytest.mark.asyncio
async def test_sin_failover_si_secundario_no_valido_relanza_error_primario():
    svc = _service()
    svc.usuario_repo.get_by_id = AsyncMock(return_value=_usuario(or_valid=False))

    async def call(payload, provider="gemini", **kw):
        if provider == "gemini":
            raise ModelOverloadedError("503")
        return {"ok": True}

    svc._call_ia_with_retry = AsyncMock(side_effect=call)
    with pytest.raises(ModelOverloadedError):
        await svc._corregir_codigo_con_failover(
            {"api_key": "PRIM"}, MagicMock(), MagicMock(), "gemini", 7
        )


@pytest.mark.asyncio
async def test_sin_error_devuelve_provider_primario():
    svc = _service()
    svc._call_ia_with_retry = AsyncMock(return_value={"ok": True})
    result, efectivo = await svc._corregir_codigo_con_failover(
        {"api_key": "PRIM"}, MagicMock(), MagicMock(), "gemini", 7
    )
    assert efectivo == "gemini"
    assert result["ok"] is True
