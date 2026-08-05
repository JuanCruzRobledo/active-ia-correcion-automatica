"""Tests de DELETE /perfil/api-key/{provider} — eliminar la key sin reemplazarla.

Bug reportado: el toggle de proveedor solo cambia CUÁL key se usa, nunca las borra;
no había forma de sacarse una key ya cargada sin pisarla con otra. Verifica que
borrar deja al usuario en el mismo estado que "nunca configuró la key" (para que
`_resolver_credenciales_ia` vuelva a pedirla) y que no toca la key del otro
proveedor ni el modo de corrección activo.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.routers.perfil import delete_api_key


def _usuario(**overrides):
    base = dict(
        id=1,
        gemini_api_key_encrypted="enc-gemini",
        gemini_api_key_valid=True,
        gemini_api_key_paga=True,
        openrouter_api_key_encrypted="enc-openrouter",
        openrouter_api_key_valid=True,
        correction_provider="gemini",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_borrar_gemini_limpia_solo_gemini():
    user = _usuario()
    db = AsyncMock()

    with patch(
        "app.routers.perfil.UsuarioRepository.update", new_callable=AsyncMock
    ):
        resp = await delete_api_key("gemini", current_user=user, db=db)

    assert resp.provider == "gemini"
    assert user.gemini_api_key_encrypted is None
    assert user.gemini_api_key_valid is False
    assert user.gemini_api_key_paga is False
    # No toca la key del otro proveedor.
    assert user.openrouter_api_key_encrypted == "enc-openrouter"
    assert user.openrouter_api_key_valid is True


@pytest.mark.asyncio
async def test_borrar_openrouter_limpia_solo_openrouter():
    user = _usuario()
    db = AsyncMock()

    with patch(
        "app.routers.perfil.UsuarioRepository.update", new_callable=AsyncMock
    ):
        resp = await delete_api_key("openrouter", current_user=user, db=db)

    assert resp.provider == "openrouter"
    assert user.openrouter_api_key_encrypted is None
    assert user.openrouter_api_key_valid is False
    # No toca la key ni el modo del otro proveedor.
    assert user.gemini_api_key_encrypted == "enc-gemini"
    assert user.correction_provider == "gemini"


@pytest.mark.asyncio
async def test_provider_invalido_da_400():
    user = _usuario()
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await delete_api_key("anthropic", current_user=user, db=db)

    assert exc.value.status_code == 400
