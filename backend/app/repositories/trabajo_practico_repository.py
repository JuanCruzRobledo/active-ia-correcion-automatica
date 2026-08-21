# app/repositories/trabajo_practico_repository.py
"""
TrabajoPractico repository for Active-IA.

Change: `trabajos-practicos-y-external-ref`.

Solo operaciones de base de datos, sin lógica de negocio (Clean Architecture).
Toda consulta filtra por universidad y excluye los registros dados de baja: son
las dos garantías de las que depende la integración para no cruzar datos.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.trabajo_practico import TrabajoPractico


class TrabajoPracticoRepository:
    """Repository for TrabajoPractico model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self, trabajo_practico_id: int, *, universidad_id: int | None = None
    ) -> TrabajoPractico | None:
        stmt = select(TrabajoPractico).where(
            TrabajoPractico.id == trabajo_practico_id,
            TrabajoPractico.deleted_at.is_(None),
        )
        if universidad_id is not None:
            stmt = stmt.where(TrabajoPractico.universidad_id == universidad_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_external_ref(
        self,
        external_ref: str | None,
        *,
        materia_id: int,
        universidad_id: int | None = None,
    ) -> TrabajoPractico | None:
        """TP vigente con ese identificador externo dentro de la materia.

        Devuelve None —y no una fila cualquiera— cuando el identificador es nulo:
        varias materias de Moodle podrían no tener ninguno, y un `IS NULL` los
        haría colisionar a todos.
        """
        if not external_ref:
            return None

        stmt = (
            select(TrabajoPractico)
            .where(
                TrabajoPractico.external_ref == external_ref,
                TrabajoPractico.materia_id == materia_id,
                TrabajoPractico.deleted_at.is_(None),
            )
            .options(selectinload(TrabajoPractico.ejercicios))
        )
        if universidad_id is not None:
            stmt = stmt.where(TrabajoPractico.universidad_id == universidad_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(self, trabajo_practico: TrabajoPractico) -> TrabajoPractico:
        self.db.add(trabajo_practico)
        await self.db.flush()
        return trabajo_practico

    async def save(self, trabajo_practico: TrabajoPractico) -> TrabajoPractico:
        self.db.add(trabajo_practico)
        await self.db.flush()
        return trabajo_practico
