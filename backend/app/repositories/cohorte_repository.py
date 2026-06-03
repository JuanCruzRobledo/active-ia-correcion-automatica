# app/repositories/cohorte_repository.py
"""
Repositories for Cohorte and Cuatrimestre (Dashboard de Gestores).

Solo operaciones de base de datos, sin lógica de negocio.
Ref: PLAN_DASHBOARD_GESTORES.md §5, §8 (T2)
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cohorte import Cohorte, Cuatrimestre
from app.models.materia import Materia


class CohorteRepository:
    """Repository for Cohorte model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, cohorte_id: int) -> Cohorte | None:
        result = await self.db.execute(
            select(Cohorte)
            .options(selectinload(Cohorte.cuatrimestres))
            .where(Cohorte.id == cohorte_id)
        )
        return result.scalar_one_or_none()

    async def get_by_codigo(self, codigo: str) -> Cohorte | None:
        result = await self.db.execute(
            select(Cohorte).where(Cohorte.codigo == codigo.upper())
        )
        return result.scalar_one_or_none()

    async def get_all(self, *, include_inactive: bool = False) -> list[Cohorte]:
        query = select(Cohorte).options(selectinload(Cohorte.cuatrimestres))
        if not include_inactive:
            query = query.where(Cohorte.activa == True)  # noqa: E712
        query = query.order_by(Cohorte.codigo.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def exists_codigo(self, codigo: str) -> bool:
        result = await self.db.execute(
            select(func.count())
            .select_from(Cohorte)
            .where(Cohorte.codigo == codigo.upper())
        )
        return (result.scalar() or 0) > 0

    async def count_materias(self, cohorte_id: int) -> int:
        """Cuántas materias están vinculadas (vía cuatrimestre) a esta cohorte."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Materia)
            .join(Cuatrimestre, Materia.cuatrimestre_id == Cuatrimestre.id)
            .where(Cuatrimestre.cohorte_id == cohorte_id)
        )
        return result.scalar() or 0

    async def create(self, cohorte: Cohorte) -> Cohorte:
        self.db.add(cohorte)
        await self.db.commit()
        await self.db.refresh(cohorte)
        return cohorte

    async def update(self, cohorte: Cohorte) -> Cohorte:
        cohorte.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(cohorte)
        return cohorte

    async def delete(self, cohorte: Cohorte) -> None:
        await self.db.delete(cohorte)
        await self.db.commit()


class CuatrimestreRepository:
    """Repository for Cuatrimestre model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, cuatrimestre_id: int) -> Cuatrimestre | None:
        result = await self.db.execute(
            select(Cuatrimestre).where(Cuatrimestre.id == cuatrimestre_id)
        )
        return result.scalar_one_or_none()

    async def exists_numero(self, cohorte_id: int, numero: int) -> bool:
        result = await self.db.execute(
            select(func.count())
            .select_from(Cuatrimestre)
            .where(
                Cuatrimestre.cohorte_id == cohorte_id,
                Cuatrimestre.numero == numero,
            )
        )
        return (result.scalar() or 0) > 0

    async def count_materias(self, cuatrimestre_id: int) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Materia)
            .where(Materia.cuatrimestre_id == cuatrimestre_id)
        )
        return result.scalar() or 0

    async def create(self, cuatrimestre: Cuatrimestre) -> Cuatrimestre:
        self.db.add(cuatrimestre)
        await self.db.commit()
        await self.db.refresh(cuatrimestre)
        return cuatrimestre

    async def update(self, cuatrimestre: Cuatrimestre) -> Cuatrimestre:
        cuatrimestre.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(cuatrimestre)
        return cuatrimestre

    async def delete(self, cuatrimestre: Cuatrimestre) -> None:
        await self.db.delete(cuatrimestre)
        await self.db.commit()
