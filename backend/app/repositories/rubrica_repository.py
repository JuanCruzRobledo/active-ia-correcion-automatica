# app/repositories/rubrica_repository.py
"""
Rubrica repository for Active-IA.

Handles database queries for Rubrica model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rubrica import Rubrica


class RubricaRepository:
    """
    Repository for Rubrica model.

    Provides CRUD operations and common queries for rubricas.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, rubrica_id: int) -> Rubrica | None:
        """
        Get rubrica by ID.

        Args:
            rubrica_id: Rubrica's database ID.

        Returns:
            Rubrica object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Rubrica).where(Rubrica.id == rubrica_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, rubrica_id: int) -> Rubrica | None:
        """
        Get rubrica by ID with materia loaded.

        Args:
            rubrica_id: Rubrica's database ID.

        Returns:
            Rubrica object with relations if found, None otherwise.
        """
        result = await self.db.execute(
            select(Rubrica)
            .options(selectinload(Rubrica.materia))
            .where(Rubrica.id == rubrica_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        materia_id: int | None = None,
        tipo: str | None = None,
        anio: int | None = None,
        include_inactive: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Rubrica], int]:
        """
        Get all rubricas with optional filters and pagination.

        Args:
            materia_id: Filter by materia ID.
            tipo: Filter by rubrica type.
            anio: Filter by academic year.
            include_inactive: Include soft-deleted rubricas.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of rubricas, total count).
        """
        # Base query
        query = select(Rubrica).options(
            selectinload(Rubrica.materia),
            selectinload(Rubrica.entregas),
        )

        # Apply filters
        if not include_inactive:
            query = query.where(Rubrica.activa == True)  # noqa: E712

        if materia_id is not None:
            query = query.where(Rubrica.materia_id == materia_id)

        if tipo is not None:
            query = query.where(Rubrica.tipo == tipo)

        if anio is not None:
            query = query.where(Rubrica.anio == anio)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(
            Rubrica.anio.desc(),
            Rubrica.tipo.asc(),
            Rubrica.numero.asc(),
        )
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        rubricas = list(result.scalars().all())

        return rubricas, total

    async def get_by_materia(
        self,
        materia_id: int,
        anio: int | None = None,
    ) -> list[Rubrica]:
        """
        Get all active rubricas for a materia.

        Args:
            materia_id: ID of the materia.
            anio: Optional year filter.

        Returns:
            List of active rubricas for the materia.
        """
        query = select(Rubrica).where(
            Rubrica.materia_id == materia_id,
            Rubrica.activa == True,  # noqa: E712
        )

        if anio is not None:
            query = query.where(Rubrica.anio == anio)

        query = query.order_by(
            Rubrica.anio.desc(),
            Rubrica.tipo.asc(),
            Rubrica.numero.asc(),
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_materia_tipo_numero(
        self,
        materia_id: int,
        tipo: str,
        numero: int,
        anio: int,
    ) -> Rubrica | None:
        """
        Get rubrica by unique combination of materia, tipo, numero, and anio.

        Args:
            materia_id: ID of the materia.
            tipo: Rubrica type.
            numero: Rubrica number.
            anio: Academic year.

        Returns:
            Rubrica object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Rubrica).where(
                Rubrica.materia_id == materia_id,
                Rubrica.tipo == tipo,
                Rubrica.numero == numero,
                Rubrica.anio == anio,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_id(self, rubrica_id: int) -> Rubrica | None:
        """
        Get active rubrica by ID (not soft-deleted).

        Args:
            rubrica_id: Rubrica's database ID.

        Returns:
            Rubrica object if found and active, None otherwise.
        """
        result = await self.db.execute(
            select(Rubrica).where(
                Rubrica.id == rubrica_id,
                Rubrica.activa == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def exists(
        self,
        materia_id: int,
        tipo: str,
        numero: int,
        anio: int,
    ) -> bool:
        """
        Check if a rubrica with same materia, tipo, numero, and anio exists.

        Args:
            materia_id: Materia ID.
            tipo: Rubrica type.
            numero: Rubrica number.
            anio: Academic year.

        Returns:
            True if rubrica exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Rubrica)
            .where(
                Rubrica.materia_id == materia_id,
                Rubrica.tipo == tipo,
                Rubrica.numero == numero,
                Rubrica.anio == anio,
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def count_entregas(self, rubrica_id: int) -> int:
        """
        Count entregas associated with a rubrica.

        Args:
            rubrica_id: Rubrica's database ID.

        Returns:
            Number of entregas.
        """
        rubrica = await self.get_by_id(rubrica_id)
        if not rubrica:
            return 0

        return len(rubrica.entregas) if rubrica.entregas else 0

    async def create(self, rubrica: Rubrica) -> Rubrica:
        """
        Create a new rubrica.

        Args:
            rubrica: Rubrica object to create.

        Returns:
            Created Rubrica object with ID assigned.
        """
        self.db.add(rubrica)
        await self.db.commit()
        await self.db.refresh(rubrica)
        return rubrica

    async def update(self, rubrica: Rubrica) -> Rubrica:
        """
        Update an existing rubrica.

        Args:
            rubrica: Rubrica object with updated fields.

        Returns:
            Updated Rubrica object.
        """
        rubrica.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rubrica)
        return rubrica

    async def soft_delete(self, rubrica: Rubrica) -> Rubrica:
        """
        Soft delete a rubrica (set activa=False).

        Args:
            rubrica: Rubrica object to delete.

        Returns:
            Updated Rubrica object.
        """
        rubrica.activa = False
        rubrica.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rubrica)
        return rubrica

    async def restore(self, rubrica: Rubrica) -> Rubrica:
        """
        Restore a soft-deleted rubrica (set activa=True).

        Args:
            rubrica: Rubrica object to restore.

        Returns:
            Updated Rubrica object.
        """
        rubrica.activa = True
        rubrica.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rubrica)
        return rubrica
