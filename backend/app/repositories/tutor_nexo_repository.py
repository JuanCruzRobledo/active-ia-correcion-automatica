# app/repositories/tutor_nexo_repository.py
"""
Repositorio de TutorNexo (notificaciones por email).

CRUD con soft delete. `get_activos` lo usa el NotificacionService (T6); el resto,
el ABM admin (T7). Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.3.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tutor_nexo import TutorNexo


class TutorNexoRepository:
    """Repository para TutorNexo."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_activos(self) -> list[TutorNexo]:
        """Tutores nexo activos y no eliminados (destinatarios del Excel semanal)."""
        result = await self.db.execute(
            select(TutorNexo).where(
                TutorNexo.activo.is_(True),
                TutorNexo.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def listar(self) -> list[TutorNexo]:
        """Todos los tutores nexo no eliminados, ordenados por regional (ABM)."""
        result = await self.db.execute(
            select(TutorNexo)
            .where(TutorNexo.deleted_at.is_(None))
            .order_by(TutorNexo.regional.asc(), TutorNexo.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, tutor_nexo_id: int) -> TutorNexo | None:
        result = await self.db.execute(
            select(TutorNexo).where(
                TutorNexo.id == tutor_nexo_id,
                TutorNexo.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def crear(self, tutor_nexo: TutorNexo) -> TutorNexo:
        self.db.add(tutor_nexo)
        await self.db.commit()
        await self.db.refresh(tutor_nexo)
        return tutor_nexo

    async def actualizar(self, tutor_nexo: TutorNexo) -> TutorNexo:
        await self.db.commit()
        await self.db.refresh(tutor_nexo)
        return tutor_nexo

    async def eliminar(self, tutor_nexo: TutorNexo) -> None:
        """Soft delete (regla del proyecto: nunca hard delete)."""
        tutor_nexo.deleted_at = datetime.utcnow()
        tutor_nexo.activo = False
        await self.db.commit()
