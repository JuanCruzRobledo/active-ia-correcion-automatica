"""Tests de get_enrolled_users_full + get_enrolled_users_with_status (T4).

Validan la llamada a core_enrol_get_enrolled_users (campos, opción onlyactive,
errores) y la resolución de activo/suspendido por DOBLE llamada — porque Moodle
NO expone el estado de matriculación por usuario (confirmado en T0).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.moodle_service import (
    MoodleService,
    MoodleAuthError,
    MoodleConnectionError,
)


@pytest.fixture
def service():
    svc = MoodleService(AsyncMock())
    svc._token_cache.clear()
    return svc


def _mock_get(captured: dict, payload):
    """Arma un httpx.AsyncClient mockeado cuyo .get captura los params y devuelve payload."""
    mr = MagicMock()
    mr.json.return_value = payload
    mr.raise_for_status = MagicMock()

    async def fake_get(url, *a, **kw):
        captured["url"] = url
        captured["params"] = kw.get("params")
        return mr

    mc = AsyncMock()
    mc.__aenter__ = AsyncMock(return_value=mc)
    mc.__aexit__ = AsyncMock(return_value=None)
    mc.get = AsyncMock(side_effect=fake_get)
    return mc


@pytest.mark.asyncio
async def test_full_pide_courseid_y_devuelve_data(service):
    captured = {}
    payload = [{"id": 101, "email": "a@b.com", "lastcourseaccess": 123,
                "roles": [{"shortname": "student"}], "groups": [{"name": "R-Mendoza"}]}]
    with patch("httpx.AsyncClient", return_value=_mock_get(captured, payload)):
        users = await service.get_enrolled_users_full("t", "https://m", 38)

    assert users[0]["id"] == 101
    assert captured["params"]["wsfunction"] == "core_enrol_get_enrolled_users"
    assert captured["params"]["courseid"] == 38
    # only_active=False (default) → NO manda la opción onlyactive
    assert "options[0][name]" not in captured["params"]


@pytest.mark.asyncio
async def test_full_only_active_envia_opcion_onlyactive(service):
    captured = {}
    with patch("httpx.AsyncClient", return_value=_mock_get(captured, [])):
        await service.get_enrolled_users_full("t", "https://m", 38, only_active=True)

    assert captured["params"]["options[0][name]"] == "onlyactive"
    assert str(captured["params"]["options[0][value]"]) == "1"


@pytest.mark.asyncio
async def test_full_exception_de_moodle_lanza_connection_error(service):
    captured = {}
    payload = {"exception": "required_capability_exception", "message": "No permission"}
    with patch("httpx.AsyncClient", return_value=_mock_get(captured, payload)):
        with pytest.raises(MoodleConnectionError):
            await service.get_enrolled_users_full("t", "https://m", 38)


@pytest.mark.asyncio
async def test_full_invalidtoken_lanza_auth_error(service):
    captured = {}
    payload = {"exception": "moodle_exception", "errorcode": "invalidtoken",
               "message": "Invalid token"}
    with patch("httpx.AsyncClient", return_value=_mock_get(captured, payload)):
        with pytest.raises(MoodleAuthError):
            await service.get_enrolled_users_full("t", "https://m", 38)


@pytest.mark.asyncio
async def test_full_timeout_lanza_connection_error(service):
    import httpx

    mc = AsyncMock()
    mc.__aenter__ = AsyncMock(return_value=mc)
    mc.__aexit__ = AsyncMock(return_value=None)
    mc.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    with patch("httpx.AsyncClient", return_value=mc):
        with pytest.raises(MoodleConnectionError):
            await service.get_enrolled_users_full("t", "https://m", 38)


@pytest.mark.asyncio
async def test_with_status_marca_suspendidos_por_diferencia(service):
    # Moodle no da 'suspended' por usuario → se deduce: todos - activos = suspendidos.
    todos = [{"id": 1}, {"id": 2}, {"id": 3}]
    activos = [{"id": 1}, {"id": 3}]

    async def fake_full(token, host, course_id, *, only_active=False):
        return activos if only_active else todos

    with patch.object(service, "get_enrolled_users_full", AsyncMock(side_effect=fake_full)):
        users = await service.get_enrolled_users_with_status("t", "https://m", 38)

    estado = {u["id"]: u["suspendido"] for u in users}
    assert estado == {1: False, 2: True, 3: False}


# =========================================================================
# _get_group_member_ids — debe contar SOLO matriculaciones activas
# (un alumno suspendido no aparece en el calificador de Moodle, así que
#  tampoco debe contar como pendiente en /pendientes)
# =========================================================================


@pytest.mark.asyncio
async def test_group_member_ids_pide_solo_activos(service):
    captured = {}
    payload = [{"id": 101, "roles": [{"shortname": "student"}]}]
    with patch("httpx.AsyncClient", return_value=_mock_get(captured, payload)):
        ids = await service._get_group_member_ids("t", "https://m", 44, 4190)

    assert ids == {101}
    p = captured["params"]
    # options[0] = groupid (ya existía); debe sumarse onlyactive=1
    opts = {p[f"options[{i}][name]"]: str(p[f"options[{i}][value]"])
            for i in range(5) if f"options[{i}][name]" in p}
    assert opts.get("groupid") == "4190"
    assert opts.get("onlyactive") == "1", f"falta onlyactive=1; opciones enviadas: {opts}"
