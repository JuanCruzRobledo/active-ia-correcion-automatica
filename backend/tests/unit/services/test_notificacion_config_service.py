"""
Tests del NotificacionConfigService (T8 — config del cron semanal). Mock de _get_or_create y usuario_repo.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.notificacion import NotificacionCronConfig
from app.repositories.usuario_repository import CredencialesMoodle
from app.schemas.notificacion import NotifCronConfigUpdate
from app.services.notificacion_config_service import NotificacionConfigService


def _service(cfg=None):
    service = NotificacionConfigService(db=AsyncMock())
    service.usuario_repo = AsyncMock()
    cfg = cfg or NotificacionCronConfig(id=1, dia_semana=0, hora=7, minuto=0, activo=False)
    service._get_or_create = AsyncMock(return_value=cfg)
    return service


@pytest.mark.asyncio
async def test_obtener_devuelve_defaults():
    service = _service()
    resp = await service.obtener()
    assert resp.dia_semana == 0
    assert resp.hora == 7
    assert resp.activo is False


@pytest.mark.asyncio
async def test_activar_sin_usuario_lanza_400():
    service = _service()
    with pytest.raises(HTTPException) as exc:
        await service.actualizar(NotifCronConfigUpdate(activo=True, usuario_id=None))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_activar_sin_universidad_lanza_400():
    """Fase 3 multi-tenant (OQ2): activar exige TAMBIÉN elegir la universidad."""
    service = _service()
    with pytest.raises(HTTPException) as exc:
        await service.actualizar(
            NotifCronConfigUpdate(activo=True, usuario_id=5, universidad_id=None)
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_activar_con_usuario_sin_moodle_lanza_400():
    service = _service()
    service.usuario_repo.get_by_id.return_value = type("U", (), {"nombre": "X"})()
    service.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await service.actualizar(
            NotifCronConfigUpdate(activo=True, usuario_id=5, universidad_id=1)
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_actualizar_ok_persiste_dia_y_hora():
    service = _service()
    service.usuario_repo.get_by_id.return_value = type("U", (), {"nombre": "Juan"})()
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://m", "u", "enc")
    )
    resp = await service.actualizar(
        NotifCronConfigUpdate(
            activo=True, usuario_id=5, universidad_id=1, dia_semana=2, hora=9, minuto=30
        )
    )
    assert resp.activo is True
    assert resp.dia_semana == 2
    assert resp.hora == 9
    assert resp.minuto == 30
    assert resp.usuario_nombre == "Juan"
    assert resp.universidad_id == 1
    service.usuario_repo.get_credenciales_moodle.assert_awaited_once_with(5, 1)
