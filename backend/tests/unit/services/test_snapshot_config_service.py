"""
Tests del SnapshotConfigService (config del cron — T6).

Mockea _get_or_create y los repos: se cubre la LÓGICA de validación de actualizar()
(activar requiere usuario con credenciales Moodle).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.avance import SnapshotCronConfig
from app.repositories.usuario_repository import CredencialesMoodle
from app.schemas.dashboard_gestores import CronConfigUpdate
from app.services.snapshot_config_service import SnapshotConfigService


def _make_service() -> SnapshotConfigService:
    service = SnapshotConfigService(db=AsyncMock())
    service.usuario_repo = AsyncMock()
    config = SnapshotCronConfig(id=1, usuario_id=None, universidad_id=None, hora=3, minuto=0, activo=False)
    service._get_or_create = AsyncMock(return_value=config)
    return service


@pytest.mark.asyncio
async def test_activar_sin_usuario_lanza_400():
    service = _make_service()

    with pytest.raises(HTTPException) as exc:
        await service.actualizar(CronConfigUpdate(usuario_id=None, hora=3, activo=True))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_activar_sin_universidad_lanza_400():
    """Fase 3 multi-tenant (OQ2): activar exige TAMBIÉN elegir la universidad."""
    service = _make_service()

    with pytest.raises(HTTPException) as exc:
        await service.actualizar(
            CronConfigUpdate(usuario_id=5, universidad_id=None, hora=3, activo=True)
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_activar_usuario_sin_credenciales_lanza_400():
    service = _make_service()
    service.usuario_repo.get_by_id.return_value = MagicMock()
    service.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await service.actualizar(
            CronConfigUpdate(usuario_id=5, universidad_id=1, hora=3, activo=True)
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_activar_usuario_valido_aplica_config():
    service = _make_service()
    service.usuario_repo.get_by_id.return_value = MagicMock(nombre="Admin")
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://m", "u", "enc")
    )

    result = await service.actualizar(
        CronConfigUpdate(usuario_id=5, universidad_id=1, hora=2, minuto=30, activo=True)
    )

    assert result.activo is True
    assert result.hora == 2 and result.minuto == 30
    assert result.usuario_id == 5
    assert result.universidad_id == 1
    service.usuario_repo.get_credenciales_moodle.assert_awaited_once_with(5, 1)


@pytest.mark.asyncio
async def test_desactivar_no_exige_usuario():
    service = _make_service()

    result = await service.actualizar(
        CronConfigUpdate(usuario_id=None, hora=5, activo=False)
    )

    assert result.activo is False
    assert result.hora == 5
