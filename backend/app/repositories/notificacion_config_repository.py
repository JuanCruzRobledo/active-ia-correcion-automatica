# app/repositories/notificacion_config_repository.py
"""
NotificacionConfigRepository — acceso a datos de la config (singleton id=1) del
cron semanal de notificaciones. Solo operaciones de base de datos.

Ref: ARCH-001 (Services no deben ejecutar SQLAlchemy directo).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notificacion import NotificacionCronConfig

# La fila es un singleton: id=1.
CONFIG_ID = 1


class NotificacionConfigRepository:
    """Repositorio de la config (singleton) del cron de notificaciones."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> NotificacionCronConfig | None:
        """Devuelve la fila de config (id=1) o None si aún no existe."""
        result = await self.db.execute(
            select(NotificacionCronConfig).where(NotificacionCronConfig.id == CONFIG_ID)
        )
        return result.scalar_one_or_none()

    async def create(self, config: NotificacionCronConfig) -> NotificacionCronConfig:
        """Inserta la fila de config y la devuelve refrescada."""
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def save(self, config: NotificacionCronConfig) -> NotificacionCronConfig:
        """Persiste cambios ya aplicados sobre la config cargada (commit + refresh)."""
        await self.db.commit()
        await self.db.refresh(config)
        return config
