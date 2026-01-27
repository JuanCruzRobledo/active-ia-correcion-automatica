# app/repositories/entrega_historial_repository.py
"""
EntregaHistorial repository for Active-IA.

Handles database queries for EntregaHistorial model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/06-MODELO-DATOS.md seccion 3.9
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entrega import EntregaHistorial


class EntregaHistorialRepository:
    """
    Repository for EntregaHistorial model.

    Manages historical versions of entregas.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_entrega(self, entrega_id: int) -> list[EntregaHistorial]:
        """
        Get all historical versions for an entrega.

        Args:
            entrega_id: ID of the current entrega.

        Returns:
            List of EntregaHistorial objects, ordered by sobrescrito_en desc.
        """
        result = await self.db.execute(
            select(EntregaHistorial)
            .options(selectinload(EntregaHistorial.sobrescrito_por))
            .where(EntregaHistorial.entrega_actual_id == entrega_id)
            .order_by(EntregaHistorial.sobrescrito_en.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, historial_id: int) -> EntregaHistorial | None:
        """
        Get a specific historial entry by ID.

        Args:
            historial_id: ID of the historial entry.

        Returns:
            EntregaHistorial object if found, None otherwise.
        """
        result = await self.db.execute(
            select(EntregaHistorial)
            .options(selectinload(EntregaHistorial.sobrescrito_por))
            .where(EntregaHistorial.id == historial_id)
        )
        return result.scalar_one_or_none()

    async def create(self, historial: EntregaHistorial) -> EntregaHistorial:
        """
        Create a new historial entry.

        Args:
            historial: EntregaHistorial object to create.

        Returns:
            Created EntregaHistorial object with ID assigned.
        """
        self.db.add(historial)
        await self.db.commit()
        await self.db.refresh(historial)
        return historial

    async def count_by_entrega(self, entrega_id: int) -> int:
        """
        Count historical versions for an entrega.

        Args:
            entrega_id: ID of the current entrega.

        Returns:
            Number of historical versions.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(EntregaHistorial)
            .where(EntregaHistorial.entrega_actual_id == entrega_id)
        )
        return result.scalar() or 0
