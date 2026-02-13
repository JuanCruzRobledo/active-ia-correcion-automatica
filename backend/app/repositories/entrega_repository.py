# app/repositories/entrega_repository.py
"""
Entrega repository for Active-IA.

Handles database queries for Entrega model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comision import Comision
from app.models.entrega import Entrega


class EntregaRepository:
    """
    Repository for Entrega model.

    Provides CRUD operations and common queries for entregas.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, entrega_id: int) -> Entrega | None:
        """
        Get entrega by ID.

        Args:
            entrega_id: Entrega's database ID.

        Returns:
            Entrega object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Entrega).where(Entrega.id == entrega_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, entrega_id: int) -> Entrega | None:
        """
        Get entrega by ID with all relations loaded.

        Args:
            entrega_id: Entrega's database ID.

        Returns:
            Entrega object with relations if found, None otherwise.
        """
        result = await self.db.execute(
            select(Entrega)
            .options(
                selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Entrega.rubrica),
                selectinload(Entrega.subido_por),
                selectinload(Entrega.correccion),
                selectinload(Entrega.historial),
            )
            .where(Entrega.id == entrega_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        comision_id: int | None = None,
        rubrica_id: int | None = None,
        estado: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Entrega], int]:
        """
        Get all entregas with optional filters and pagination.

        Args:
            comision_id: Filter by comision ID.
            rubrica_id: Filter by rubrica ID.
            estado: Filter by estado.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of entregas, total count).
        """
        # Base query
        query = select(Entrega).options(
            selectinload(Entrega.comision),
            selectinload(Entrega.rubrica),
            selectinload(Entrega.subido_por),
            selectinload(Entrega.correccion),
        )

        # Apply filters
        if comision_id is not None:
            query = query.where(Entrega.comision_id == comision_id)

        if rubrica_id is not None:
            query = query.where(Entrega.rubrica_id == rubrica_id)

        if estado is not None:
            query = query.where(Entrega.estado == estado)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Entrega.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        entregas = list(result.scalars().all())

        return entregas, total

    async def get_by_rubrica_alumno(
        self,
        rubrica_id: int,
        alumno_nombre: str,
    ) -> Entrega | None:
        """
        Get entrega by rubrica and alumno nombre.

        Args:
            rubrica_id: ID of the rubrica.
            alumno_nombre: Nombre del alumno.

        Returns:
            Entrega object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Entrega)
            .options(
                selectinload(Entrega.correccion),
            )
            .where(
                Entrega.rubrica_id == rubrica_id,
                Entrega.alumno_nombre == alumno_nombre,
            )
        )
        return result.scalar_one_or_none()

    async def exists_by_rubrica_alumno(
        self,
        rubrica_id: int,
        alumno_nombre: str,
    ) -> bool:
        """
        Check if an entrega exists for rubrica and alumno.

        Args:
            rubrica_id: Rubrica ID.
            alumno_nombre: Nombre del alumno.

        Returns:
            True if entrega exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Entrega)
            .where(
                Entrega.rubrica_id == rubrica_id,
                Entrega.alumno_nombre == alumno_nombre,
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, entrega: Entrega) -> Entrega:
        """
        Create a new entrega.

        Args:
            entrega: Entrega object to create.

        Returns:
            Created Entrega object with ID assigned.
        """
        self.db.add(entrega)
        await self.db.commit()
        await self.db.refresh(entrega)
        return entrega

    async def update(self, entrega: Entrega) -> Entrega:
        """
        Update an existing entrega.

        Args:
            entrega: Entrega object with updated fields.

        Returns:
            Updated Entrega object.
        """
        entrega.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(entrega)
        return entrega

    async def delete(self, entrega: Entrega) -> None:
        """
        Physically delete an entrega (hard delete).

        Args:
            entrega: Entrega object to delete.
        """
        await self.db.delete(entrega)
        await self.db.commit()


