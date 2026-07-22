"""
ARCH-001 (rebanada Auth): AuthService dejaba de respetar la capa Repository —
ejecutaba select(Usuario) y db.commit() crudos contra la sesión. Ahora consume
UsuarioRepository (get_by_username / update / save). Estos tests fijan el
comportamiento (red de seguridad): la lógica de negocio NO cambia, solo la vía
de acceso a datos.

Regla de persistencia:
- change_password -> update()  (SÍ bumpea updated_at, como hoy)
- login handlers  -> save()    (NO bumpea updated_at, como hoy)
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.services.auth_service import AuthService, MAX_LOGIN_ATTEMPTS


def _user(**over):
    u = SimpleNamespace(
        id=1, username="admin", nombre="Admin", rol=RolEnum.ADMIN,
        password_hash="hash", activo=True, locked_until=None,
        failed_login_attempts=0, primer_login=False, gemini_api_key_valid=True,
        last_login=None, updated_at=None,
    )
    for k, v in over.items():
        setattr(u, k, v)
    return u


def _svc(user=None):
    svc = AuthService(MagicMock())
    svc.usuario_repo = MagicMock()
    svc.usuario_repo.get_by_username = AsyncMock(return_value=user)
    svc.usuario_repo.update = AsyncMock(side_effect=lambda u: u)
    svc.usuario_repo.save = AsyncMock(side_effect=lambda u: u)
    return svc


# ------------------------------------------------------------- authenticate

@pytest.mark.asyncio
async def test_authenticate_ok_usa_repo_y_devuelve_token():
    user = _user()
    svc = _svc(user)
    with patch("app.services.auth_service.verify_password", return_value=True), patch(
        "app.services.auth_service.create_access_token", return_value="JWT"
    ):
        res = await svc.authenticate(SimpleNamespace(username="admin", password="x"))
    svc.usuario_repo.get_by_username.assert_awaited_once_with("admin")
    assert res.access_token == "JWT"


@pytest.mark.asyncio
async def test_authenticate_usuario_desconocido_401():
    svc = _svc(None)
    with pytest.raises(HTTPException) as e:
        await svc.authenticate(SimpleNamespace(username="nope", password="x"))
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_cuenta_inactiva_403():
    svc = _svc(_user(activo=False))
    with pytest.raises(HTTPException) as e:
        await svc.authenticate(SimpleNamespace(username="admin", password="x"))
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_authenticate_cuenta_bloqueada_403():
    user = _user(locked_until=datetime.utcnow() + timedelta(minutes=10))
    svc = _svc(user)
    with pytest.raises(HTTPException) as e:
        await svc.authenticate(SimpleNamespace(username="admin", password="x"))
    assert e.value.status_code == 403


# -------------------------------------------------- login handlers -> save()

@pytest.mark.asyncio
async def test_login_fallido_incrementa_y_persiste_via_save():
    user = _user(failed_login_attempts=0)
    svc = _svc(user)
    with patch("app.services.auth_service.verify_password", return_value=False):
        with pytest.raises(HTTPException) as e:
            await svc.authenticate(SimpleNamespace(username="admin", password="mala"))
    assert e.value.status_code == 401
    assert user.failed_login_attempts == 1
    svc.usuario_repo.save.assert_awaited()
    svc.usuario_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_quinto_fallo_bloquea_la_cuenta():
    user = _user(failed_login_attempts=MAX_LOGIN_ATTEMPTS - 1)
    svc = _svc(user)
    with patch("app.services.auth_service.verify_password", return_value=False):
        with pytest.raises(HTTPException):
            await svc.authenticate(SimpleNamespace(username="admin", password="mala"))
    assert user.failed_login_attempts == MAX_LOGIN_ATTEMPTS
    assert user.locked_until is not None


@pytest.mark.asyncio
async def test_login_exitoso_resetea_via_save():
    user = _user(failed_login_attempts=3, locked_until=datetime.utcnow())
    svc = _svc(user)
    with patch("app.services.auth_service.verify_password", return_value=True), patch(
        "app.services.auth_service.create_access_token", return_value="JWT"
    ):
        await svc.authenticate(SimpleNamespace(username="admin", password="x"))
    assert user.failed_login_attempts == 0
    assert user.locked_until is None
    assert user.last_login is not None
    svc.usuario_repo.save.assert_awaited()


# --------------------------------------------- change_password -> update()

@pytest.mark.asyncio
async def test_change_password_persiste_via_update():
    user = _user(password_hash="viejo")
    svc = _svc(user)
    data = SimpleNamespace(
        current_password="vieja1", new_password="nueva123", confirm_password="nueva123"
    )
    with patch("app.services.auth_service.verify_password", return_value=True), patch(
        "app.services.auth_service.hash_password", return_value="nuevo_hash"
    ):
        await svc.change_password(user, data)
    assert user.password_hash == "nuevo_hash"
    assert user.primer_login is False
    svc.usuario_repo.update.assert_awaited_once_with(user)
    svc.usuario_repo.save.assert_not_called()
