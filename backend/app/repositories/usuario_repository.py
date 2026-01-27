# app/repositories/usuario_repository.py
"""
Usuario repository for Active-IA.

Handles database queries for Usuario model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Usuario
from app.models.enums import RolEnum


class UsuarioRepository:
    """
    Repository for Usuario model.

    Provides CRUD operations and common queries for users.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, user_id: int) -> Usuario | None:
        """
        Get user by ID.

        Args:
            user_id: User's database ID.

        Returns:
            Usuario object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Usuario).where(Usuario.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Usuario | None:
        """
        Get user by username.

        Args:
            username: User's username.

        Returns:
            Usuario object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Usuario).where(Usuario.username == username)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        include_inactive: bool = False,
        rol: RolEnum | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Usuario], int]:
        """
        Get all users with optional filters and pagination.

        Args:
            include_inactive: Include soft-deleted users.
            rol: Filter by role.
            search: Search term for username or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of users, total count).
        """
        # Base query
        query = select(Usuario)

        # Apply filters
        if not include_inactive:
            query = query.where(Usuario.activo == True)  # noqa: E712

        if rol is not None:
            query = query.where(Usuario.rol == rol)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Usuario.username.ilike(search_term))
                | (Usuario.nombre.ilike(search_term))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Usuario.nombre.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def get_active_by_id(self, user_id: int) -> Usuario | None:
        """
        Get active user by ID (not soft-deleted).

        Args:
            user_id: User's database ID.

        Returns:
            Usuario object if found and active, None otherwise.
        """
        result = await self.db.execute(
            select(Usuario).where(
                Usuario.id == user_id,
                Usuario.activo == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def exists_username(self, username: str) -> bool:
        """
        Check if a username already exists.

        Args:
            username: Username to check.

        Returns:
            True if username exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.username == username)
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, user: Usuario) -> Usuario:
        """
        Create a new user.

        Args:
            user: Usuario object to create.

        Returns:
            Created Usuario object with ID assigned.
        """
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: Usuario) -> Usuario:
        """
        Update an existing user.

        Args:
            user: Usuario object with updated fields.

        Returns:
            Updated Usuario object.
        """
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def soft_delete(self, user: Usuario) -> Usuario:
        """
        Soft delete a user (set activo=False).

        Args:
            user: Usuario object to delete.

        Returns:
            Updated Usuario object.
        """
        user.activo = False
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def restore(self, user: Usuario) -> Usuario:
        """
        Restore a soft-deleted user (set activo=True).

        Args:
            user: Usuario object to restore.

        Returns:
            Updated Usuario object.
        """
        user.activo = True
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_coordinadores(self) -> list[Usuario]:
        """
        Get all active coordinators.

        Returns:
            List of active users with COORDINADOR role.
        """
        result = await self.db.execute(
            select(Usuario)
            .where(
                Usuario.rol == RolEnum.COORDINADOR,
                Usuario.activo == True,  # noqa: E712
            )
            .order_by(Usuario.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_tutores(self) -> list[Usuario]:
        """
        Get all active tutors.

        Returns:
            List of active users with TUTOR role.
        """
        result = await self.db.execute(
            select(Usuario)
            .where(
                Usuario.rol == RolEnum.TUTOR,
                Usuario.activo == True,  # noqa: E712
            )
            .order_by(Usuario.nombre.asc())
        )
        return list(result.scalars().all())
