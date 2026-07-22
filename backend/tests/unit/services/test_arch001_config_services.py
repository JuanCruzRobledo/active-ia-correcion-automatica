"""
ARCH-001 (rebanada Config): SnapshotConfigService y NotificacionConfigService
ejecutaban select + db.add + db.commit crudos. Ahora usan sus repositorios
(get/create/save). Estos tests fijan que _get_or_create pasa por el repo:
- get() devuelve la fila existente -> no se crea de nuevo
- get() devuelve None -> se crea con defaults vía create()
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.avance import SnapshotCronConfig
from app.models.notificacion import NotificacionCronConfig
from app.services.notificacion_config_service import NotificacionConfigService
from app.services.snapshot_config_service import SnapshotConfigService


# ---------------------------------------------------------------- Snapshot

@pytest.mark.asyncio
async def test_snapshot_get_or_create_usa_repo_cuando_existe():
    svc = SnapshotConfigService(db=AsyncMock())
    existente = SnapshotCronConfig(id=1, hora=5, minuto=0, activo=True)
    svc.config_repo = MagicMock()
    svc.config_repo.get = AsyncMock(return_value=existente)
    svc.config_repo.create = AsyncMock()

    config = await svc._get_or_create()

    assert config is existente
    svc.config_repo.get.assert_awaited_once()
    svc.config_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_snapshot_get_or_create_crea_default_via_repo_cuando_no_existe():
    svc = SnapshotConfigService(db=AsyncMock())
    svc.config_repo = MagicMock()
    svc.config_repo.get = AsyncMock(return_value=None)
    svc.config_repo.create = AsyncMock(side_effect=lambda c: c)

    config = await svc._get_or_create()

    svc.config_repo.create.assert_awaited_once()
    assert config.id == 1 and config.activo is False


@pytest.mark.asyncio
async def test_snapshot_actualizar_persiste_via_repo_save():
    svc = SnapshotConfigService(db=AsyncMock())
    config = SnapshotCronConfig(id=1, usuario_id=None, hora=3, minuto=0, activo=False)
    svc._get_or_create = AsyncMock(return_value=config)
    svc.config_repo = MagicMock()
    svc.config_repo.save = AsyncMock(side_effect=lambda c: c)
    from app.schemas.dashboard_gestores import CronConfigUpdate

    await svc.actualizar(CronConfigUpdate(usuario_id=None, hora=5, activo=False))

    svc.config_repo.save.assert_awaited_once_with(config)


# ------------------------------------------------------------ Notificacion

@pytest.mark.asyncio
async def test_notif_get_or_create_usa_repo_cuando_existe():
    svc = NotificacionConfigService(db=AsyncMock())
    existente = NotificacionCronConfig(id=1, dia_semana=0, hora=7, minuto=0, activo=True)
    svc.config_repo = MagicMock()
    svc.config_repo.get = AsyncMock(return_value=existente)
    svc.config_repo.create = AsyncMock()

    config = await svc._get_or_create()

    assert config is existente
    svc.config_repo.get.assert_awaited_once()
    svc.config_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_notif_get_or_create_crea_default_via_repo_cuando_no_existe():
    svc = NotificacionConfigService(db=AsyncMock())
    svc.config_repo = MagicMock()
    svc.config_repo.get = AsyncMock(return_value=None)
    svc.config_repo.create = AsyncMock(side_effect=lambda c: c)

    config = await svc._get_or_create()

    svc.config_repo.create.assert_awaited_once()
    assert config.id == 1 and config.activo is False
