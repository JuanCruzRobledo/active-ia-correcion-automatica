# app/repositories/unidad_repository.py
"""
Unidad repository for Active-IA (Dashboard de Gestores).

Solo operaciones de base de datos. Ref: PLAN_DASHBOARD_GESTORES.md §8 (T3)
"""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rubrica import Rubrica
from app.models.unidad import Unidad


class UnidadRepository:
    """Repository for Unidad model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, unidad_id: int) -> Unidad | None:
        result = await self.db.execute(select(Unidad).where(Unidad.id == unidad_id))
        return result.scalar_one_or_none()

    async def get_by_materia(self, materia_id: int) -> list[Unidad]:
        result = await self.db.execute(
            select(Unidad)
            .where(Unidad.materia_id == materia_id)
            .order_by(Unidad.numero.asc())
        )
        return list(result.scalars().all())

    async def exists_numero(
        self, materia_id: int, numero: int, *, exclude_id: int | None = None
    ) -> bool:
        query = select(func.count()).select_from(Unidad).where(
            Unidad.materia_id == materia_id, Unidad.numero == numero
        )
        if exclude_id is not None:
            query = query.where(Unidad.id != exclude_id)
        result = await self.db.execute(query)
        return (result.scalar() or 0) > 0

    async def exists_section(
        self, materia_id: int, moodle_section_id: int, *, exclude_id: int | None = None
    ) -> bool:
        query = select(func.count()).select_from(Unidad).where(
            Unidad.materia_id == materia_id,
            Unidad.moodle_section_id == moodle_section_id,
        )
        if exclude_id is not None:
            query = query.where(Unidad.id != exclude_id)
        result = await self.db.execute(query)
        return (result.scalar() or 0) > 0

    async def create(self, unidad: Unidad) -> Unidad:
        self.db.add(unidad)
        await self.db.commit()
        await self.db.refresh(unidad)
        return unidad

    async def update(self, unidad: Unidad) -> Unidad:
        unidad.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(unidad)
        return unidad

    async def desvincular_rubricas(self, unidad_id: int) -> None:
        """Pone unidad_id=NULL en las rúbricas que apuntaban a esta unidad."""
        await self.db.execute(
            update(Rubrica).where(Rubrica.unidad_id == unidad_id).values(unidad_id=None)
        )

    async def delete(self, unidad: Unidad) -> None:
        # Desvincular rúbricas primero (la FK rubricas.unidad_id no tiene ON DELETE)
        await self.desvincular_rubricas(unidad.id)
        await self.db.delete(unidad)
        await self.db.commit()

    async def sincronizar(
        self, materia_id: int, nuevas: list[tuple[int, int, str | None]]
    ) -> list[Unidad]:
        """Reemplaza TODAS las unidades de la materia por `nuevas` en una transacción.

        `nuevas` = lista de (numero, moodle_section_id, nombre). Borra las viejas
        (desvinculando sus rúbricas) y crea las nuevas. Borrar+recrear evita choques
        con el UNIQUE(materia_id, numero) al renumerar.
        """
        actuales = await self.get_by_materia(materia_id)
        for u in actuales:
            await self.desvincular_rubricas(u.id)
            await self.db.delete(u)
        await self.db.flush()  # aplica los DELETE antes de los INSERT (evita choque de unique)

        creadas: list[Unidad] = []
        for numero, section_id, nombre in nuevas:
            unidad = Unidad(
                materia_id=materia_id,
                numero=numero,
                moodle_section_id=section_id,
                nombre=nombre,
            )
            self.db.add(unidad)
            creadas.append(unidad)
        await self.db.commit()
        for u in creadas:
            await self.db.refresh(u)
        return creadas
