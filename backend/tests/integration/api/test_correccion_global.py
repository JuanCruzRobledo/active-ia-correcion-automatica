"""Integration tests para corrección masiva global + toggle key paga (Fase 4)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user, get_db


def _set_user(**attrs):
    base = {"id": 1, "gemini_api_key_encrypted": "enc", "gemini_api_key_paga": True}
    base.update(attrs)
    user = MagicMock(**base)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    return user


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_global_sin_key_paga_es_403():
    _set_user(gemini_api_key_paga=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/correcciones/global")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_global_sin_key_configurada_es_400():
    _set_user(gemini_api_key_encrypted=None, gemini_api_key_paga=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/correcciones/global")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_global_con_key_paga_encola():
    _set_user(gemini_api_key_paga=True)
    with patch("app.routers.correcciones.EntregaRepository") as repo_cls, \
         patch("app.routers.correcciones.procesar_global_background", MagicMock()):
        repo_cls.return_value.get_subidas_ids_by_tutor = AsyncMock(return_value=[1, 2, 3, 4, 5])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/correcciones/global")
    assert resp.status_code == 202
    assert resp.json()["total_encoladas"] == 5


@pytest.mark.asyncio
async def test_global_sin_subidas_devuelve_0():
    _set_user(gemini_api_key_paga=True)
    with patch("app.routers.correcciones.EntregaRepository") as repo_cls:
        repo_cls.return_value.get_subidas_ids_by_tutor = AsyncMock(return_value=[])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/correcciones/global")
    assert resp.status_code == 202
    assert resp.json()["total_encoladas"] == 0


@pytest.mark.asyncio
async def test_progreso_global():
    _set_user()
    with patch("app.routers.correcciones.EntregaRepository") as repo_cls:
        repo_cls.return_value.contar_estados_by_tutor = AsyncMock(
            return_value={"SUBIDA": 5, "PENDIENTE": 1, "CORREGIDA": 2, "ERROR": 0}
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/correcciones/global/progreso")
    assert resp.status_code == 200
    body = resp.json()
    assert body["subidas"] == 5
    assert body["corregidas"] == 2
    assert body["total"] == 8


@pytest.mark.asyncio
async def test_toggle_key_paga():
    _set_user(gemini_api_key_paga=False)
    with patch("app.routers.perfil.UsuarioRepository") as repo_cls:
        repo_cls.return_value.update = AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/v1/perfil/key-paga", json={"paga": True})
    assert resp.status_code == 200
    assert resp.json()["gemini_api_key_paga"] is True
