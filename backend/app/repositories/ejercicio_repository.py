# app/repositories/ejercicio_repository.py
"""
Ejercicio repository for Active-IA.

Change: `trabajos-practicos-y-external-ref`.

Solo operaciones de base de datos, sin lógica de negocio (Clean Architecture).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ejercicio import Ejercicio


class EjercicioRepository:
    """Repository for Ejercicio model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self, ejercicio_id: int, *, universidad_id: int | None = None
    ) -> Ejercicio | None:
        stmt = select(Ejercicio).where(
            Ejercicio.id == ejercicio_id, Ejercicio.deleted_at.is_(None)
        )
        if universidad_id is not None:
            stmt = stmt.where(Ejercicio.universidad_id == universidad_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_external_ref(
        self,
        external_ref: str | None,
        *,
        universidad_id: int | None = None,
        materia_id: int | None = None,
    ) -> Ejercicio | None:
        """Ejercicio vigente con ese identificador externo.

        `materia_id` es opcional porque el endpoint de corrección identifica el
        ejercicio solo por su referencia: es única por materia, y el scoping por
        universidad ya acota el universo.
        """
        if not external_ref:
            return None

        stmt = (
            select(Ejercicio)
            .where(
                Ejercicio.external_ref == external_ref,
                Ejercicio.deleted_at.is_(None),
            )
            .options(selectinload(Ejercicio.rubrica))
        )
        if universidad_id is not None:
            stmt = stmt.where(Ejercicio.universidad_id == universidad_id)
        if materia_id is not None:
            stmt = stmt.where(Ejercicio.materia_id == materia_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_por_ref_incluyendo_borrados(
        self, external_ref: str, *, trabajo_practico_id: int
    ) -> Ejercicio | None:
        """Ejercicio del TP con ese identificador, VIVO O DADO DE BAJA.

        La usa la reconciliación: si el cliente reenvía el identificador de un
        ejercicio que había dado de baja, hay que revivirlo en vez de crear un
        duplicado — que además el índice único parcial rechazaría.
        """
        stmt = (
            select(Ejercicio)
            .where(
                Ejercicio.external_ref == external_ref,
                Ejercicio.trabajo_practico_id == trabajo_practico_id,
            )
            .options(selectinload(Ejercicio.rubrica))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def listar_vigentes_de_tp(self, trabajo_practico_id: int) -> list[Ejercicio]:
        """Ejercicios no borrados del TP, ordenados por su orden."""
        stmt = (
            select(Ejercicio)
            .where(
                Ejercicio.trabajo_practico_id == trabajo_practico_id,
                Ejercicio.deleted_at.is_(None),
            )
            .order_by(Ejercicio.orden)
            .options(selectinload(Ejercicio.rubrica))
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, ejercicio: Ejercicio) -> Ejercicio:
        self.db.add(ejercicio)
        await self.db.flush()
        return ejercicio

    async def save(self, ejercicio: Ejercicio) -> Ejercicio:
        self.db.add(ejercicio)
        await self.db.flush()
        return ejercicio
