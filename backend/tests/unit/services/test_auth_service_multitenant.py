"""
Fase 1 multi-tenant (multi-tenant-auth-jwt): `AuthService` — login en dos
pasos (resolución de membresías + ramificación) y los nuevos métodos
`seleccionar_universidad` / `switch_universidad`.

La lógica vive acá (ARCH-001): el service nunca ejecuta SQLAlchemy directo,
consume `UsuarioRepository`/`UniversidadRepository`. Se mockean ambos repos,
igual que test_arch001_auth_service.py mockea `usuario_repo`.

Ref: openspec/changes/multi-tenant-auth-jwt/design.md (D6, flujo de los 3 endpoints)
Ref: openspec/changes/multi-tenant-auth-jwt/specs/login-seleccion-universidad/spec.md
Ref: openspec/changes/multi-tenant-auth-jwt/tasks.md (6.1-6.9)
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.schemas.auth import SeleccionUniversidadRequerida, TokenResponse
from app.services.auth_service import AuthService


def _user(**over):
    u = SimpleNamespace(
        id=1, username="user1", nombre="Usuario Uno", rol=RolEnum.TUTOR,
        password_hash="hash", activo=True, locked_until=None,
        failed_login_attempts=0, primer_login=False, gemini_api_key_valid=True,
        last_login=None, updated_at=None, es_superadmin=False,
    )
    for k, v in over.items():
        setattr(u, k, v)
    return u


def _membresia(universidad_id, rol, nombre="TUPaD"):
    return SimpleNamespace(
        universidad_id=universidad_id,
        rol=rol,
        universidad=SimpleNamespace(id=universidad_id, nombre=nombre),
    )


def _svc(user=None, *, membresias=None, membresia_puntual=None, universidad_activa=None):
    svc = AuthService(MagicMock())
    svc.usuario_repo = MagicMock()
    svc.usuario_repo.get_by_username = AsyncMock(return_value=user)
    svc.usuario_repo.get_by_id_light = AsyncMock(return_value=user)
    svc.usuario_repo.get_membresias_activas = AsyncMock(return_value=membresias or [])
    svc.usuario_repo.get_membresia = AsyncMock(return_value=membresia_puntual)
    svc.usuario_repo.update = AsyncMock(side_effect=lambda u: u)
    svc.usuario_repo.save = AsyncMock(side_effect=lambda u: u)
    svc.universidad_repo = MagicMock()
    svc.universidad_repo.get_activa_by_id = AsyncMock(return_value=universidad_activa)
    return svc


async def _login_ok(svc, username="user1", password="x"):
    with patch("app.services.auth_service.verify_password", return_value=True):
        return await svc.authenticate(SimpleNamespace(username=username, password=password))


# ============================== 6.1: 1 membresía → login normal ==============================


@pytest.mark.asyncio
async def test_login_con_una_membresia_emite_token_con_esa_universidad_y_rol():
    user = _user()
    membresias = [_membresia(7, RolEnum.TUTOR)]
    svc = _svc(user, membresias=membresias)

    res = await _login_ok(svc)

    assert isinstance(res, TokenResponse)
    assert res.user.universidad_activa_id == 7
    assert res.user.rol == RolEnum.TUTOR
    assert res.user.es_superadmin is False


# ============================== 6.2: 0 membresías → 403, sin token ==============================


@pytest.mark.asyncio
async def test_login_sin_membresias_403_sin_token():
    user = _user()
    svc = _svc(user, membresias=[])

    with pytest.raises(HTTPException) as exc:
        await _login_ok(svc)
    assert exc.value.status_code == 403


# ============================== 6.3: 2+ membresías → requiere_seleccion ==============================


@pytest.mark.asyncio
async def test_login_con_dos_membresias_devuelve_requiere_seleccion():
    user = _user()
    membresias = [
        _membresia(7, RolEnum.TUTOR, "TUPaD"),
        _membresia(8, RolEnum.COORDINADOR, "Otra Uni"),
    ]
    svc = _svc(user, membresias=membresias)

    res = await _login_ok(svc)

    assert isinstance(res, SeleccionUniversidadRequerida)
    assert res.requiere_seleccion is True
    assert {u.id for u in res.universidades} == {7, 8}
    assert res.token_transicion  # no vacío


@pytest.mark.asyncio
async def test_login_con_tres_membresias_lista_las_tres_con_su_rol():
    """Triangulación adicional: 3 universidades, cada una con su propio rol."""
    user = _user()
    membresias = [
        _membresia(1, RolEnum.TUTOR, "A"),
        _membresia(2, RolEnum.COORDINADOR, "B"),
        _membresia(3, RolEnum.ADMIN, "C"),
    ]
    svc = _svc(user, membresias=membresias)

    res = await _login_ok(svc)

    assert len(res.universidades) == 3
    roles = {u.id: u.rol for u in res.universidades}
    assert roles == {1: RolEnum.TUTOR, 2: RolEnum.COORDINADOR, 3: RolEnum.ADMIN}


# ============================== 6.4: superadmin → token modo superadmin ==============================


@pytest.mark.asyncio
async def test_login_superadmin_emite_token_modo_superadmin_sin_consultar_membresias():
    user = _user(es_superadmin=True)
    svc = _svc(user)  # sin membresías configuradas

    res = await _login_ok(svc)

    assert isinstance(res, TokenResponse)
    assert res.user.es_superadmin is True
    assert res.user.universidad_activa_id is None
    assert res.user.rol is None
    svc.usuario_repo.get_membresias_activas.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_superadmin_con_membresias_reales_sigue_en_modo_superadmin():
    """Triangulación: aunque el superadmin SÍ tenga membresías reales, el login
    lo manda a modo superadmin igual (decisión OQ1: opera igual)."""
    user = _user(es_superadmin=True)
    membresias = [_membresia(7, RolEnum.TUTOR)]
    svc = _svc(user, membresias=membresias)

    res = await _login_ok(svc)

    assert res.user.universidad_activa_id is None
    assert res.user.es_superadmin is True


# =========================== 401/403 previos preservados ===========================


@pytest.mark.asyncio
async def test_login_credenciales_invalidas_sigue_siendo_401():
    svc = _svc(None)
    with pytest.raises(HTTPException) as exc:
        await _login_ok(svc)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_cuenta_deshabilitada_sigue_siendo_403():
    svc = _svc(_user(activo=False))
    with pytest.raises(HTTPException) as exc:
        await _login_ok(svc)
    assert exc.value.status_code == 403


# ============================== 6.6: seleccionar_universidad ==============================


@pytest.mark.asyncio
async def test_seleccionar_universidad_con_membresia_valida_emite_token():
    user = _user()
    membresia = _membresia(9, RolEnum.COORDINADOR)
    svc = _svc(user, membresia_puntual=membresia)

    from app.core.security import create_transitional_token

    token_transicion = create_transitional_token(user.id, user.username)

    res = await svc.seleccionar_universidad(token_transicion, 9)

    assert isinstance(res, TokenResponse)
    assert res.user.universidad_activa_id == 9
    assert res.user.rol == RolEnum.COORDINADOR


@pytest.mark.asyncio
async def test_seleccionar_universidad_sin_membresia_403():
    user = _user()
    svc = _svc(user, membresia_puntual=None)

    from app.core.security import create_transitional_token

    token_transicion = create_transitional_token(user.id, user.username)

    with pytest.raises(HTTPException) as exc:
        await svc.seleccionar_universidad(token_transicion, 999)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_seleccionar_universidad_superadmin_cualquier_universidad_activa():
    user = _user(es_superadmin=True)
    universidad = SimpleNamespace(id=42, nombre="Cualquiera")
    svc = _svc(user, universidad_activa=universidad)

    from app.core.security import create_transitional_token

    token_transicion = create_transitional_token(user.id, user.username)

    res = await svc.seleccionar_universidad(token_transicion, 42)

    assert res.user.universidad_activa_id == 42
    assert res.user.rol == RolEnum.ADMIN  # rol sintético
    assert res.user.es_superadmin is True
    svc.usuario_repo.get_membresia.assert_not_awaited()


@pytest.mark.asyncio
async def test_seleccionar_universidad_con_token_normal_no_transicion_es_rechazado():
    """El token de select debe ser el de transición (scope=seleccion), no un
    access_token normal ya emitido — evita reusar cualquier token viejo."""
    user = _user()
    svc = _svc(user)

    from app.core.security import create_access_token

    token_normal = create_access_token(
        user.id, user.username, rol="TUTOR", universidad_activa_id=1, es_superadmin=False
    )

    with pytest.raises(HTTPException) as exc:
        await svc.seleccionar_universidad(token_normal, 9)
    assert exc.value.status_code == 401


# ============================== 6.7: switch_universidad ==============================


@pytest.mark.asyncio
async def test_switch_universidad_con_membresia_valida_reemite_token():
    user = _user()
    membresia = _membresia(3, RolEnum.ADMIN)
    svc = _svc(user, membresia_puntual=membresia)

    res = await svc.switch_universidad(user, 3)

    assert res.user.universidad_activa_id == 3
    assert res.user.rol == RolEnum.ADMIN


@pytest.mark.asyncio
async def test_switch_universidad_sin_membresia_403():
    user = _user()
    svc = _svc(user, membresia_puntual=None)

    with pytest.raises(HTTPException) as exc:
        await svc.switch_universidad(user, 999)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_switch_universidad_superadmin_cualquier_universidad_activa():
    user = _user(es_superadmin=True)
    universidad = SimpleNamespace(id=5, nombre="Nueva")
    svc = _svc(user, universidad_activa=universidad)

    res = await svc.switch_universidad(user, 5)

    assert res.user.universidad_activa_id == 5
    assert res.user.rol == RolEnum.ADMIN
    assert res.user.es_superadmin is True


@pytest.mark.asyncio
async def test_switch_universidad_superadmin_a_universidad_inactiva_403():
    user = _user(es_superadmin=True)
    svc = _svc(user, universidad_activa=None)  # get_activa_by_id -> None

    with pytest.raises(HTTPException) as exc:
        await svc.switch_universidad(user, 999)
    assert exc.value.status_code == 403
