# app/repositories/materia_repository.py
"""
Materia repository for Active-IA.

Handles database queries for Materia and CoordinadorMateria models.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 4
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.materia import CoordinadorMateria, Materia


class MateriaRepository:
    """
    Repository for Materia model.

    Provides CRUD operations and common queries for materias.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, materia_id: int) -> Materia | None:
        """
        Get materia by ID.

        Args:
            materia_id: Materia's database ID.

        Returns:
            Materia object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Materia).where(Materia.id == materia_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_coordinadores(self, materia_id: int) -> Materia | None:
        """
        Get materia by ID with coordinadores loaded.

        Args:
            materia_id: Materia's database ID.

        Returns:
            Materia object with coordinadores if found, None otherwise.
        """
        result = await self.db.execute(
            select(Materia)
            .options(selectinload(Materia.coordinadores))
            .where(Materia.id == materia_id)
        )
        return result.scalar_one_or_none()

    async def get_by_codigo(self, codigo: str) -> Materia | None:
        """
        Get materia by codigo.

        Args:
            codigo: Materia's unique code.

        Returns:
            Materia object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Materia).where(Materia.codigo == codigo.upper())
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        include_inactive: bool = False,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Materia], int]:
        """
        Get all materias with optional filters and pagination.

        Args:
            include_inactive: Include soft-deleted materias.
            search: Search term for codigo or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of materias, total count).
        """
        # Base query
        query = select(Materia)

        # Apply filters
        if not include_inactive:
            query = query.where(Materia.activa == True)  # noqa: E712

        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Materia.codigo.ilike(search_term))
                | (Materia.nombre.ilike(search_term))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Materia.nombre.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        materias = list(result.scalars().all())

        return materias, total

    async def get_active_by_id(self, materia_id: int) -> Materia | None:
        """
        Get active materia by ID (not soft-deleted).

        Args:
            materia_id: Materia's database ID.

        Returns:
            Materia object if found and active, None otherwise.
        """
        result = await self.db.execute(
            select(Materia).where(
                Materia.id == materia_id,
                Materia.activa == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def exists_codigo(self, codigo: str) -> bool:
        """
        Check if a codigo already exists.

        Args:
            codigo: Codigo to check.

        Returns:
            True if codigo exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Materia)
            .where(Materia.codigo == codigo.upper())
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, materia: Materia) -> Materia:
        """
        Create a new materia.

        Args:
            materia: Materia object to create.

        Returns:
            Created Materia object with ID assigned.
        """
        self.db.add(materia)
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def update(self, materia: Materia) -> Materia:
        """
        Update an existing materia.

        Args:
            materia: Materia object with updated fields.

        Returns:
            Updated Materia object.
        """
        materia.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def soft_delete(self, materia: Materia) -> Materia:
        """
        Soft delete a materia (set activa=False).

        Args:
            materia: Materia object to delete.

        Returns:
            Updated Materia object.
        """
        materia.activa = False
        materia.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def restore(self, materia: Materia) -> Materia:
        """
        Restore a soft-deleted materia (set activa=True).

        Args:
            materia: Materia object to restore.

        Returns:
            Updated Materia object.
        """
        materia.activa = True
        materia.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def get_by_coordinador(self, coordinador_id: int) -> list[Materia]:
        """
        Get all active materias assigned to a coordinator.

        Args:
            coordinador_id: ID of the coordinator user.

        Returns:
            List of active materias for the coordinator.
        """
        result = await self.db.execute(
            select(Materia)
            .join(CoordinadorMateria)
            .where(
                CoordinadorMateria.coordinador_id == coordinador_id,
                Materia.activa == True,  # noqa: E712
            )
            .order_by(Materia.nombre.asc())
        )
        return list(result.scalars().all())


class CoordinadorMateriaRepository:
    """
    Repository for CoordinadorMateria model.

    Manages the N:M relationship between coordinators and materias.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_coordinadores_for_materia(
        self,
        materia_id: int,
    ) -> list[CoordinadorMateria]:
        """
        Get all coordinator assignments for a materia.

        Args:
            materia_id: ID of the materia.

        Returns:
            List of CoordinadorMateria records.
        """
        result = await self.db.execute(
            select(CoordinadorMateria)
            .where(CoordinadorMateria.materia_id == materia_id)
            .order_by(CoordinadorMateria.asignado_en.desc())
        )
        return list(result.scalars().all())

    async def exists(self, coordinador_id: int, materia_id: int) -> bool:
        """
        Check if a coordinator is already assigned to a materia.

        Args:
            coordinador_id: ID of the coordinator.
            materia_id: ID of the materia.

        Returns:
            True if assignment exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(CoordinadorMateria)
            .where(
                CoordinadorMateria.coordinador_id == coordinador_id,
                CoordinadorMateria.materia_id == materia_id,
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def create(
        self,
        coordinador_id: int,
        materia_id: int,
    ) -> CoordinadorMateria:
        """
        Create a coordinator-materia assignment.

        Args:
            coordinador_id: ID of the coordinator.
            materia_id: ID of the materia.

        Returns:
            Created CoordinadorMateria record.
        """
        assignment = CoordinadorMateria(
            coordinador_id=coordinador_id,
            materia_id=materia_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def delete_all_for_materia(self, materia_id: int) -> int:
        """
        Delete all coordinator assignments for a materia.

        Args:
            materia_id: ID of the materia.

        Returns:
            Number of records deleted.
        """
        result = await self.db.execute(
            select(CoordinadorMateria).where(
                CoordinadorMateria.materia_id == materia_id
            )
        )
        assignments = result.scalars().all()
        count = len(assignments)

        for assignment in assignments:
            await self.db.delete(assignment)

        await self.db.commit()
        return count

    async def delete(self, coordinador_id: int, materia_id: int) -> bool:
        """
        Delete a specific coordinator-materia assignment.

        Args:
            coordinador_id: ID of the coordinator.
            materia_id: ID of the materia.

        Returns:
            True if deleted, False if not found.
        """
        result = await self.db.execute(
            select(CoordinadorMateria).where(
                CoordinadorMateria.coordinador_id == coordinador_id,
                CoordinadorMateria.materia_id == materia_id,
            )
        )
        assignment = result.scalar_one_or_none()

        if assignment:
            await self.db.delete(assignment)
            await self.db.commit()
            return True

        return False
