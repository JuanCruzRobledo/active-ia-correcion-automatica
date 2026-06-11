# app/repositories/examen_repository.py
"""
ExamenMateria repository — solo operaciones de base de datos.

CRUD por examen (alta incremental) + helper para el `orden` de alta. El número visible
por tipo lo deriva el service (no se persiste).
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.examen_materia import ExamenMateria


class ExamenRepository:
    """Repository for ExamenMateria model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, examen_id: int) -> ExamenMateria | None:
        result = await self.db.execute(
            select(ExamenMateria).where(ExamenMateria.id == examen_id)
        )
        return result.scalar_one_or_none()

    async def get_by_materia(self, materia_id: int) -> list[ExamenMateria]:
        result = await self.db.execute(
            select(ExamenMateria)
            .where(ExamenMateria.materia_id == materia_id)
            .order_by(ExamenMateria.orden.asc(), ExamenMateria.id.asc())
        )
        return list(result.scalars().all())

    async def max_orden(self, materia_id: int) -> int:
        """Mayor `orden` de los exámenes de la materia (-1 si no hay)."""
        result = await self.db.execute(
            select(func.max(ExamenMateria.orden)).where(
                ExamenMateria.materia_id == materia_id
            )
        )
        maximo = result.scalar()
        return maximo if maximo is not None else -1

    async def create(self, examen: ExamenMateria) -> ExamenMateria:
        self.db.add(examen)
        await self.db.commit()
        await self.db.refresh(examen)
        return examen

    async def update(self, examen: ExamenMateria) -> ExamenMateria:
        examen.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(examen)
        return examen

    async def delete(self, examen: ExamenMateria) -> None:
        # Los recu/ext/extraordinaria que apuntan a este parcial caen por FK CASCADE.
        await self.db.delete(examen)
        await self.db.commit()
