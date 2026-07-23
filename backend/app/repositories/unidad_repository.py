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

    async def get_by_materia(
        self, materia_id: int, *, universidad_id: int | None = None
    ) -> list[Unidad]:
        query = select(Unidad).where(Unidad.materia_id == materia_id)
        if universidad_id is not None:
            query = query.where(Unidad.universidad_id == universidad_id)
        result = await self.db.execute(query.order_by(Unidad.numero.asc()))
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
        self,
        materia_id: int,
        nuevas: list[tuple[int, int, str | None]],
        *,
        universidad_id: int | None = None,
    ) -> list[Unidad]:
        """UPSERT de las unidades de la materia matcheando por moodle_section_id.

        `nuevas` = lista de (numero, moodle_section_id, nombre).

        CRUD-014: las unidades que siguen existiendo (mismo moodle_section_id)
        CONSERVAN su id — así las rúbricas vinculadas (unidad_id) y los componentes
        configurados a mano NO se pierden. Solo se crean las nuevas y se borran las
        ausentes de Moodle (desvinculando sus rúbricas). Antes esto era delete+recreate,
        que cambiaba los IDs en cada sync y desarmaba silenciosamente los vínculos.

        El renumerado (una unidad cambia de número) puede chocar con el
        UNIQUE(materia_id, numero); se resuelve corriendo todos los números a un
        offset temporal negativo y flusheando antes de asignar los definitivos.
        """
        actuales = await self.get_by_materia(materia_id)
        por_section = {u.moodle_section_id: u for u in actuales}
        sections_nuevas = {section_id for _, section_id, _ in nuevas}

        # 1. Borrar las ausentes de Moodle (desvinculando sus rúbricas).
        for u in actuales:
            if u.moodle_section_id not in sections_nuevas:
                await self.desvincular_rubricas(u.id)
                await self.db.delete(u)

        # 2. Liberar el espacio de números: correr los de las que se conservan a un
        #    offset temporal (negativo) para evitar choques del UNIQUE al renumerar.
        for u in actuales:
            if u.moodle_section_id in sections_nuevas:
                u.numero = -(u.numero + 1)
        await self.db.flush()

        # 3. Upsert: actualizar in place las existentes, crear las nuevas.
        resultado: list[Unidad] = []
        for numero, section_id, nombre in nuevas:
            existente = por_section.get(section_id)
            if existente is not None:
                existente.numero = numero
                existente.nombre = nombre
                resultado.append(existente)
            else:
                unidad = Unidad(
                    universidad_id=universidad_id,
                    materia_id=materia_id,
                    numero=numero,
                    moodle_section_id=section_id,
                    nombre=nombre,
                )
                self.db.add(unidad)
                resultado.append(unidad)

        await self.db.commit()
        for u in resultado:
            await self.db.refresh(u)
        return resultado
