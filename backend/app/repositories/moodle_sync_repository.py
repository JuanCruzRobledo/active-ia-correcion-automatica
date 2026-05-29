# app/repositories/moodle_sync_repository.py
"""Repository para MoodleSync (auditoría + idempotencia de envíos a Moodle)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MoodleSyncEstado
from app.models.moodle_sync import MoodleSync


class MoodleSyncRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_ultimo_enviado(self, correccion_id: int) -> MoodleSync | None:
        """Último registro ENVIADO de la corrección (para anti doble-envío)."""
        result = await self.db.execute(
            select(MoodleSync)
            .where(
                MoodleSync.correccion_id == correccion_id,
                MoodleSync.estado == MoodleSyncEstado.ENVIADO,
            )
            .order_by(MoodleSync.id.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def contar_por_correccion(self, correccion_id: int) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(MoodleSync)
            .where(MoodleSync.correccion_id == correccion_id)
        )
        return int(result.scalar() or 0)

    async def create(self, sync: MoodleSync) -> MoodleSync:
        self.db.add(sync)
        await self.db.commit()
        await self.db.refresh(sync)
        return sync
