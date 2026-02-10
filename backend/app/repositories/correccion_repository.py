# app/repositories/correccion_repository.py
"""
Correccion repository for Active-IA.

Handles database queries for Correccion model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/06-MODELO-DATOS.md seccion 3.8
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 8
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.correccion import Correccion


class CorreccionRepository:
    """
    Repository for Correccion model.

    Provides CRUD operations and common queries for correcciones.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, correccion_id: int) -> Correccion | None:
        """
        Get correccion by ID.

        Args:
            correccion_id: Correccion's database ID.

        Returns:
            Correccion object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Correccion).where(Correccion.id == correccion_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(
        self, correccion_id: int
    ) -> Correccion | None:
        """
        Get correccion by ID with all relations loaded.

        Loads nested relations needed for PDF generation:
        - entrega (with comision, materia, rubrica)
        - corregido_por

        Args:
            correccion_id: Correccion's database ID.

        Returns:
            Correccion object with relations if found, None otherwise.
        """
        from app.models.entrega import Entrega
        from app.models.comision import Comision

        result = await self.db.execute(
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
                selectinload(Correccion.corregido_por),
            )
            .where(Correccion.id == correccion_id)
        )
        return result.scalar_one_or_none()

    async def get_by_entrega_id(self, entrega_id: int) -> Correccion | None:
        """
        Get correccion by entrega ID.

        Since Correccion has a 1:1 relationship with Entrega,
        this returns the unique correccion for a given entrega.

        Args:
            entrega_id: ID of the entrega.

        Returns:
            Correccion object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Correccion).where(Correccion.entrega_id == entrega_id)
        )
        return result.scalar_one_or_none()

    async def get_by_entrega_id_with_relations(
        self, entrega_id: int
    ) -> Correccion | None:
        """
        Get correccion by entrega ID with all relations loaded.

        Loads nested relations needed for PDF generation:
        - entrega (with comision, materia, rubrica)
        - corregido_por

        Args:
            entrega_id: ID of the entrega.

        Returns:
            Correccion object with relations if found, None otherwise.
        """
        from app.models.entrega import Entrega
        from app.models.comision import Comision

        result = await self.db.execute(
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
                selectinload(Correccion.corregido_por),
            )
            .where(Correccion.entrega_id == entrega_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        comision_id: int | None = None,
        rubrica_id: int | None = None,
        corregido_por_id: int | None = None,
        editado_manualmente: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Correccion], int]:
        """
        Get all correcciones with optional filters and pagination.

        Args:
            comision_id: Filter by comision ID (via entrega).
            rubrica_id: Filter by rubrica ID (via entrega).
            corregido_por_id: Filter by user who corrected.
            editado_manualmente: Filter by manual edit flag.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of correcciones, total count).
        """
        # Import here to avoid circular dependency
        from app.models.entrega import Entrega

        # Base query with nested relations for PDF generation
        from app.models.comision import Comision

        query = select(Correccion).options(
            selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
            selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
            selectinload(Correccion.corregido_por),
        )

        # Apply filters
        if comision_id is not None:
            query = query.join(Entrega).where(Entrega.comision_id == comision_id)

        if rubrica_id is not None:
            if comision_id is None:
                query = query.join(Entrega)
            query = query.where(Entrega.rubrica_id == rubrica_id)

        if corregido_por_id is not None:
            query = query.where(Correccion.corregido_por_id == corregido_por_id)

        if editado_manualmente is not None:
            query = query.where(
                Correccion.editado_manualmente == editado_manualmente
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Correccion.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        correcciones = list(result.scalars().all())

        return correcciones, total

    async def exists_by_entrega_id(self, entrega_id: int) -> bool:
        """
        Check if a correccion exists for a given entrega.

        Args:
            entrega_id: Entrega ID.

        Returns:
            True if correccion exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Correccion)
            .where(Correccion.entrega_id == entrega_id)
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, correccion: Correccion) -> Correccion:
        """
        Create a new correccion.

        Args:
            correccion: Correccion object to create.

        Returns:
            Created Correccion object with ID assigned.
        """
        self.db.add(correccion)
        await self.db.commit()
        await self.db.refresh(correccion)
        return correccion

    async def update(self, correccion: Correccion) -> Correccion:
        """
        Update an existing correccion.

        Args:
            correccion: Correccion object with updated fields.

        Returns:
            Updated Correccion object.
        """
        correccion.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(correccion)
        return correccion

    async def delete(self, correccion: Correccion) -> None:
        """
        Hard delete a correccion.

        Note: Correcciones do not use soft delete.
        This is typically used when re-correcting an entrega.

        Args:
            correccion: Correccion object to delete.
        """
        await self.db.delete(correccion)
        await self.db.commit()

    async def get_statistics_by_rubrica(
        self, rubrica_id: int
    ) -> dict[str, float]:
        """
        Get statistics for correcciones of a specific rubrica.

        Args:
            rubrica_id: Rubrica ID.

        Returns:
            Dictionary with statistics (avg_nota, min_nota, max_nota, count).
        """
        # Import here to avoid circular dependency
        from app.models.entrega import Entrega

        result = await self.db.execute(
            select(
                func.avg(Correccion.nota).label("avg_nota"),
                func.min(Correccion.nota).label("min_nota"),
                func.max(Correccion.nota).label("max_nota"),
                func.count(Correccion.id).label("count"),
            )
            .select_from(Correccion)
            .join(Entrega)
            .where(Entrega.rubrica_id == rubrica_id)
        )

        row = result.one()

        return {
            "avg_nota": float(row.avg_nota) if row.avg_nota else 0.0,
            "min_nota": float(row.min_nota) if row.min_nota else 0.0,
            "max_nota": float(row.max_nota) if row.max_nota else 0.0,
            "count": int(row.count) if row.count else 0,
        }

    async def get_by_ids(self, correccion_ids: list[int]) -> list[Correccion]:
        """
        Get multiple correcciones by their IDs.

        Loads nested relations needed for PDF generation:
        - entrega (with comision, materia, rubrica)
        - corregido_por

        Args:
            correccion_ids: List of correccion IDs.

        Returns:
            List of Correccion objects.
        """
        from app.models.entrega import Entrega
        from app.models.comision import Comision

        result = await self.db.execute(
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
                selectinload(Correccion.corregido_por),
            )
            .where(Correccion.id.in_(correccion_ids))
        )
        return list(result.scalars().all())
