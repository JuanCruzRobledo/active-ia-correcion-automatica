# app/services/snapshot_config_service.py
"""
SnapshotConfigService — config (singleton) del cron de snapshots.

La fila id=1 existe desde la migración 014. Acá se lee y actualiza desde el
admin panel. Ref: PLAN_DASHBOARD_GESTORES.md §7 (T6).
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.avance import SnapshotCronConfig
from app.repositories.snapshot_config_repository import SnapshotConfigRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.dashboard_gestores import CronConfigResponse, CronConfigUpdate

_CONFIG_ID = 1


class SnapshotConfigService:
    """Lee/actualiza la config del cron de snapshots (singleton)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        self.config_repo = SnapshotConfigRepository(db)

    async def _get_or_create(self) -> SnapshotCronConfig:
        # ARCH-001: acceso a datos vía repo, no SQL crudo en el service.
        config = await self.config_repo.get()
        if config is None:
            config = SnapshotCronConfig(id=_CONFIG_ID, hora=3, minuto=0, activo=False)
            config = await self.config_repo.create(config)
        return config

    async def get_config(self) -> SnapshotCronConfig:
        """Devuelve el modelo de config (lo crea si no existe)."""
        return await self._get_or_create()

    async def _to_response(self, config: SnapshotCronConfig) -> CronConfigResponse:
        nombre = None
        if config.usuario_id:
            usuario = await self.usuario_repo.get_by_id(config.usuario_id)
            nombre = usuario.nombre if usuario else None
        return CronConfigResponse(
            usuario_id=config.usuario_id,
            usuario_nombre=nombre,
            hora=config.hora,
            minuto=config.minuto,
            activo=config.activo,
        )

    async def obtener(self) -> CronConfigResponse:
        config = await self._get_or_create()
        return await self._to_response(config)

    async def actualizar(self, data: CronConfigUpdate) -> CronConfigResponse:
        config = await self._get_or_create()

        # Si se activa el cron, exigir un usuario con credenciales Moodle.
        if data.activo:
            if not data.usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Para activar el cron hay que asignar un usuario",
                )
            usuario = await self.usuario_repo.get_by_id(data.usuario_id)
            if usuario is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario indicado no existe",
                )
            if not usuario.moodle_username or not usuario.moodle_password_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario elegido no tiene credenciales de Moodle configuradas",
                )

        config.usuario_id = data.usuario_id
        config.hora = data.hora
        config.minuto = data.minuto
        config.activo = data.activo
        await self.config_repo.save(config)
        return await self._to_response(config)
