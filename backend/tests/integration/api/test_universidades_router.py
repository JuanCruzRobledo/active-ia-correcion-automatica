"""
Fase 5 multi-tenant (multi-tenant-frontend-workspace): contrato HTTP de
`GET /universidades/mias` (D5: sólo autenticación, nunca `get_universidad_activa`)
y el ABM de superadmin bajo `/universidades` (D7: guard `ctx.es_superadmin`).

Nivel 1 (contrato HTTP), mismo patrón que test_auth_multitenant_router.py:
se mockea `UniversidadService` a nivel de router, se sobreescriben las
dependencies, y se usa `AsyncClient` + `ASGITransport(app=app)`.

Ref: openspec/changes/multi-tenant-frontend-workspace/specs/universidades-abm/spec.md
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.main import app
from app.models.enums import RolEnum
from app.schemas.universidad import (
    UniversidadList,
    UniversidadListItem,
    UniversidadPropia,
    UniversidadResponse,
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _mock_user(**attrs):
    base = {"id": 1, "es_superadmin": False}
    base.update(attrs)
    user = MagicMock(**base)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    return user


def _mock_ctx(**attrs):
    base = dict(universidad_id=1, rol=RolEnum.ADMIN, es_superadmin=False)
    base.update(attrs)
    ctx = ContextoUniversidad(**base)
    app.dependency_overrides[get_universidad_activa] = lambda: ctx
    return ctx


def _universidad_response(**over):
    base = dict(
        id=1, nombre="TUPaD", moodle_host=None, activa=True,
        created_at="2024-01-01T00:00:00", updated_at="2024-01-01T00:00:00",
    )
    base.update(over)
    return UniversidadResponse(**base)


# ============================ GET /universidades/mias ============================


@pytest.mark.asyncio
async def test_mias_no_monta_get_universidad_activa():
    """D5: sólo autenticación. NO overrideamos get_universidad_activa: si el
    router la montara, esta llamada explotaría (dependency sin default ni
    override) en vez de responder 200."""
    _mock_user()
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.listar_mias = AsyncMock(
            return_value=[UniversidadPropia(id=1, nombre="TUPaD", rol=RolEnum.TUTOR)]
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/v1/universidades/mias")
    assert resp.status_code == 200
    assert resp.json() == [{"id": 1, "nombre": "TUPaD", "rol": "TUTOR"}]


@pytest.mark.asyncio
async def test_mias_superadmin_en_modo_global_responde_200():
    """Superadmin sin universidad_activa_id en el token: 200, no 409."""
    _mock_user(es_superadmin=True)
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.listar_mias = AsyncMock(
            return_value=[
                UniversidadPropia(id=1, nombre="A", rol=RolEnum.ADMIN),
                UniversidadPropia(id=2, nombre="B", rol=RolEnum.ADMIN),
            ]
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/v1/universidades/mias")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_mias_sin_autenticacion_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/universidades/mias")
    assert resp.status_code in (401, 403)


# ============================ GET /universidades (ABM) ============================


@pytest.mark.asyncio
async def test_listar_superadmin_ok():
    _mock_user(es_superadmin=True)
    _mock_ctx(es_superadmin=True, universidad_id=None, rol=None)
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.listar = AsyncMock(
            return_value=UniversidadList(
                items=[UniversidadListItem(id=1, nombre="TUPaD", moodle_host=None, activa=True)],
                total=1,
                page=1,
                per_page=20,
            )
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/v1/universidades")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_listar_admin_no_superadmin_403():
    _mock_user(es_superadmin=False)
    _mock_ctx(es_superadmin=False, rol=RolEnum.ADMIN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/universidades")
    assert resp.status_code == 403


# ============================ POST /universidades ============================


@pytest.mark.asyncio
async def test_crear_superadmin_201():
    _mock_user(es_superadmin=True)
    _mock_ctx(es_superadmin=True, universidad_id=None, rol=None)
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.crear = AsyncMock(return_value=_universidad_response(id=5, nombre="Nueva"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/universidades", json={"nombre": "Nueva"})
    assert resp.status_code == 201
    assert resp.json()["nombre"] == "Nueva"


@pytest.mark.asyncio
async def test_crear_nombre_duplicado_409():
    _mock_user(es_superadmin=True)
    _mock_ctx(es_superadmin=True, universidad_id=None, rol=None)
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.crear = AsyncMock(
            side_effect=HTTPException(status.HTTP_409_CONFLICT, detail="Ya existe")
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/universidades", json={"nombre": "TUPaD"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_crear_no_superadmin_403():
    _mock_user(es_superadmin=False)
    _mock_ctx(es_superadmin=False, rol=RolEnum.ADMIN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/v1/universidades", json={"nombre": "Nueva"})
    assert resp.status_code == 403


# ============================ PUT /universidades/{id} ============================


@pytest.mark.asyncio
async def test_actualizar_superadmin_200():
    _mock_user(es_superadmin=True)
    _mock_ctx(es_superadmin=True, universidad_id=None, rol=None)
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.actualizar = AsyncMock(
            return_value=_universidad_response(id=1, nombre="Renombrada")
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put("/api/v1/universidades/1", json={"nombre": "Renombrada"})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Renombrada"


@pytest.mark.asyncio
async def test_actualizar_inexistente_404():
    _mock_user(es_superadmin=True)
    _mock_ctx(es_superadmin=True, universidad_id=None, rol=None)
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.actualizar = AsyncMock(
            side_effect=HTTPException(status.HTTP_404_NOT_FOUND, detail="No encontrada")
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put("/api/v1/universidades/999", json={"nombre": "X"})
    assert resp.status_code == 404


# ============================ DELETE /universidades/{id} ============================


@pytest.mark.asyncio
async def test_eliminar_superadmin_204():
    _mock_user(es_superadmin=True)
    _mock_ctx(es_superadmin=True, universidad_id=None, rol=None)
    with patch("app.routers.universidades.UniversidadService") as cls:
        cls.return_value.eliminar = AsyncMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete("/api/v1/universidades/1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_eliminar_no_superadmin_403():
    _mock_user(es_superadmin=False)
    _mock_ctx(es_superadmin=False, rol=RolEnum.ADMIN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete("/api/v1/universidades/1")
    assert resp.status_code == 403
