"""
Tests del SnapshotConfigService (config del cron — T6).

Mockea _get_or_create y los repos: se cubre la LÓGICA de validación de actualizar()
(activar requiere usuario con credenciales Moodle).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.avance import SnapshotCronConfig
from app.schemas.dashboard_gestores import CronConfigUpdate
from app.services.snapshot_config_service import SnapshotConfigService


def _make_service() -> SnapshotConfigService:
    service = SnapshotConfigService(db=AsyncMock())
    service.usuario_repo = AsyncMock()
    config = SnapshotCronConfig(id=1, usuario_id=None, hora=3, minuto=0, activo=False)
    service._get_or_create = AsyncMock(return_value=config)
    return service


@pytest.mark.asyncio
async def test_activar_sin_usuario_lanza_400():
    service = _make_service()

    with pytest.raises(HTTPException) as exc:
        await service.actualizar(CronConfigUpdate(usuario_id=None, hora=3, activo=True))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_activar_usuario_sin_credenciales_lanza_400():
    service = _make_service()
    service.usuario_repo.get_by_id.return_value = MagicMock(
        moodle_username=None, moodle_password_encrypted=None
    )

    with pytest.raises(HTTPException) as exc:
        await service.actualizar(CronConfigUpdate(usuario_id=5, hora=3, activo=True))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_activar_usuario_valido_aplica_config():
    service = _make_service()
    service.usuario_repo.get_by_id.return_value = MagicMock(
        nombre="Admin", moodle_username="u", moodle_password_encrypted="enc"
    )

    result = await service.actualizar(
        CronConfigUpdate(usuario_id=5, hora=2, minuto=30, activo=True)
    )

    assert result.activo is True
    assert result.hora == 2 and result.minuto == 30
    assert result.usuario_id == 5


@pytest.mark.asyncio
async def test_desactivar_no_exige_usuario():
    service = _make_service()

    result = await service.actualizar(
        CronConfigUpdate(usuario_id=None, hora=5, activo=False)
    )

    assert result.activo is False
    assert result.hora == 5
