# app/repositories/snapshot_config_repository.py
"""
SnapshotConfigRepository — acceso a datos de la config (singleton id=1) del cron
de snapshots. Solo operaciones de base de datos, sin lógica de negocio.

Ref: ARCH-001 (Services no deben ejecutar SQLAlchemy directo).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.avance import SnapshotCronConfig

# La fila es un singleton: existe desde la migración 014 con id=1.
CONFIG_ID = 1


class SnapshotConfigRepository:
    """Repositorio de la config (singleton) del cron de snapshots."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> SnapshotCronConfig | None:
        """Devuelve la fila de config (id=1) o None si aún no existe."""
        result = await self.db.execute(
            select(SnapshotCronConfig).where(SnapshotCronConfig.id == CONFIG_ID)
        )
        return result.scalar_one_or_none()

    async def create(self, config: SnapshotCronConfig) -> SnapshotCronConfig:
        """Inserta la fila de config y la devuelve refrescada."""
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def save(self, config: SnapshotCronConfig) -> SnapshotCronConfig:
        """Persiste cambios ya aplicados sobre la config cargada (commit + refresh)."""
        await self.db.commit()
        await self.db.refresh(config)
        return config
