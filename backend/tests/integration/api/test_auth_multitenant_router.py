"""
Fase 1 multi-tenant (multi-tenant-auth-jwt): contrato HTTP de
`POST /auth/login` (modificado) y los endpoints nuevos
`POST /auth/select-universidad` / `POST /auth/switch-universidad`.

Nivel 1 (contrato HTTP) — mismo patrón que test_cierre_cursada.py: se mockea
`AuthService` a nivel de router (`patch("app.routers.auth.AuthService")`), se
sobreescribe `get_current_user`/`get_db`, y se usa `AsyncClient` +
`ASGITransport(app=app)`. La lógica real de `AuthService` ya está cubierta en
`tests/unit/services/test_auth_service_multitenant.py`; acá se fija el
contrato HTTP (status codes, forma del JSON, quién delega a quién).

Ref: openspec/changes/multi-tenant-auth-jwt/specs/login-seleccion-universidad/spec.md
Ref: openspec/changes/multi-tenant-auth-jwt/tasks.md (7.1-7.4)
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.enums import RolEnum
from app.schemas.auth import (
    SeleccionUniversidadRequerida,
    TokenResponse,
    UniversidadDisponible,
    UserInfo,
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _token_response(**over):
    base = dict(
        id=1, username="tutor1", nombre="Tutor Uno", rol=RolEnum.TUTOR,
        primer_login=False, universidad_activa_id=7, es_superadmin=False,
    )
    base.update(over)
    return TokenResponse(access_token="JWT", user=UserInfo(**base))


def _admin_user(**attrs):
    base = {"id": 1, "rol": RolEnum.ADMIN, "activo": True}
    base.update(attrs)
    user = MagicMock(**base)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    return user


# =============================== POST /auth/login ===============================


@pytest.mark.asyncio
async def test_login_con_una_universidad_devuelve_200_con_token():
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.authenticate = AsyncMock(return_value=_token_response())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/login", json={"username": "tutor1", "password": "x"}
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "JWT"
    assert body["user"]["universidad_activa_id"] == 7


@pytest.mark.asyncio
async def test_login_sin_universidades_devuelve_403():
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.authenticate = AsyncMock(
            side_effect=HTTPException(
                status.HTTP_403_FORBIDDEN, detail="Usuario sin universidad asignada"
            )
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/login", json={"username": "tutor1", "password": "x"}
            )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_con_dos_universidades_devuelve_200_con_requiere_seleccion():
    seleccion = SeleccionUniversidadRequerida(
        universidades=[
            UniversidadDisponible(id=1, nombre="TUPaD", rol=RolEnum.TUTOR),
            UniversidadDisponible(id=2, nombre="Otra", rol=RolEnum.COORDINADOR),
        ],
        token_transicion="tok-transicion",
    )
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.authenticate = AsyncMock(return_value=seleccion)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/login", json={"username": "multiuni", "password": "x"}
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requiere_seleccion"] is True
    assert len(body["universidades"]) == 2
    assert "access_token" not in body


@pytest.mark.asyncio
async def test_login_superadmin_devuelve_200_con_token_modo_superadmin():
    token = _token_response(
        rol=None, universidad_activa_id=None, es_superadmin=True, username="root"
    )
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.authenticate = AsyncMock(return_value=token)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/login", json={"username": "root", "password": "x"}
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["es_superadmin"] is True
    assert body["user"]["universidad_activa_id"] is None


@pytest.mark.asyncio
async def test_login_credenciales_invalidas_sigue_devolviendo_401():
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.authenticate = AsyncMock(
            side_effect=HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/login", json={"username": "tutor1", "password": "mala"}
            )
    assert resp.status_code == 401


# ======================== POST /auth/select-universidad ========================


@pytest.mark.asyncio
async def test_select_universidad_valida_devuelve_200_con_token():
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.seleccionar_universidad = AsyncMock(return_value=_token_response())
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/select-universidad",
                json={"universidad_id": 7},
                headers={"Authorization": "Bearer tok-transicion"},
            )
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "JWT"
    cls.return_value.seleccionar_universidad.assert_awaited_once_with("tok-transicion", 7)


@pytest.mark.asyncio
async def test_select_universidad_sin_membresia_devuelve_403():
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.seleccionar_universidad = AsyncMock(
            side_effect=HTTPException(status.HTTP_403_FORBIDDEN, detail="No sos miembro activo")
        )
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/select-universidad",
                json={"universidad_id": 999},
                headers={"Authorization": "Bearer tok-transicion"},
            )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_select_universidad_superadmin_cualquier_universidad():
    token = _token_response(rol=RolEnum.ADMIN, universidad_activa_id=42, es_superadmin=True)
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.seleccionar_universidad = AsyncMock(return_value=token)
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/select-universidad",
                json={"universidad_id": 42},
                headers={"Authorization": "Bearer tok-transicion"},
            )
    assert resp.status_code == 200
    assert resp.json()["user"]["es_superadmin"] is True


@pytest.mark.asyncio
async def test_select_universidad_sin_bearer_token_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/v1/auth/select-universidad", json={"universidad_id": 1})
    assert resp.status_code in (401, 403)  # HTTPBearer sin credenciales


# ======================== POST /auth/switch-universidad ========================


@pytest.mark.asyncio
async def test_switch_universidad_valida_devuelve_200_con_nuevo_token():
    _admin_user()
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.switch_universidad = AsyncMock(
            return_value=_token_response(universidad_activa_id=3)
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/switch-universidad", json={"universidad_id": 3}
            )
    assert resp.status_code == 200
    assert resp.json()["user"]["universidad_activa_id"] == 3


@pytest.mark.asyncio
async def test_switch_universidad_sin_membresia_devuelve_403():
    _admin_user()
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.switch_universidad = AsyncMock(
            side_effect=HTTPException(status.HTTP_403_FORBIDDEN, detail="No sos miembro activo")
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/switch-universidad", json={"universidad_id": 999}
            )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_switch_universidad_superadmin_ok():
    _admin_user(es_superadmin=True)
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.switch_universidad = AsyncMock(
            return_value=_token_response(es_superadmin=True, rol=RolEnum.ADMIN)
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/switch-universidad", json={"universidad_id": 5}
            )
    assert resp.status_code == 200
    assert resp.json()["user"]["es_superadmin"] is True


@pytest.mark.asyncio
async def test_switch_universidad_requiere_autenticacion():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/v1/auth/switch-universidad", json={"universidad_id": 1})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_switch_universidad_acepta_universidad_id_nulo_modo_global():
    """0.2/2.0: D6 exige que el endpoint acepte universidad_id=null (modo global)."""
    _admin_user(es_superadmin=True)
    with patch("app.routers.auth.AuthService") as cls:
        cls.return_value.switch_universidad = AsyncMock(
            return_value=_token_response(
                es_superadmin=True, rol=None, universidad_activa_id=None
            )
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/switch-universidad", json={"universidad_id": None}
            )
    assert resp.status_code == 200
    assert resp.json()["user"]["universidad_activa_id"] is None
