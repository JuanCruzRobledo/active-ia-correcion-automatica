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

    async def get_ultimo_estado_por_correcciones(
        self, correccion_ids: list[int]
    ) -> dict[int, tuple[MoodleSyncEstado, str | None]]:
        """Último estado de sincronización de cada corrección (para etiquetar la lista).

        Trae el registro más reciente (mayor id) por corrección, evitando N+1.
        Las correcciones sin ningún registro simplemente no aparecen en el dict.

        Args:
            correccion_ids: IDs de corrección a consultar.

        Returns:
            Dict {correccion_id: (estado, mensaje_error)} con el último intento.
        """
        if not correccion_ids:
            return {}

        ultimos = (
            select(
                MoodleSync.correccion_id.label("correccion_id"),
                func.max(MoodleSync.id).label("max_id"),
            )
            .where(MoodleSync.correccion_id.in_(correccion_ids))
            .group_by(MoodleSync.correccion_id)
            .subquery()
        )

        result = await self.db.execute(
            select(
                MoodleSync.correccion_id,
                MoodleSync.estado,
                MoodleSync.mensaje_error,
            ).join(ultimos, MoodleSync.id == ultimos.c.max_id)
        )
        return {
            row.correccion_id: (row.estado, row.mensaje_error)
            for row in result.all()
        }

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
