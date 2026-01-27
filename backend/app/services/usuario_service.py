# app/services/usuario_service.py
"""
Usuario service for Active-IA.

Business logic for user management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_temp_password, hash_password
from app.models import Usuario
from app.models.enums import RolEnum
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import (
    ResetPasswordResponse,
    UsuarioCreate,
    UsuarioCreateResponse,
    UsuarioList,
    UsuarioListItem,
    UsuarioResponse,
    UsuarioUpdate,
)


class UsuarioService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize usuario service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.repo = UsuarioRepository(db)

    async def crear_usuario(self, data: UsuarioCreate) -> UsuarioCreateResponse:
        """
        Create a new user with a temporary password.

        Args:
            data: User creation data (username, nombre, rol).

        Returns:
            UsuarioCreateResponse with user data and temporary password.

        Raises:
            HTTPException 409: Username already exists.
        """
        # Check if username already exists
        if await self.repo.exists_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El nombre de usuario ya existe",
            )

        # Generate temporary password
        temp_password = generate_temp_password()

        # Create user
        user = Usuario(
            username=data.username.lower(),
            nombre=data.nombre,
            rol=data.rol,
            password_hash=hash_password(temp_password),
            primer_login=True,
            activo=True,
        )

        created_user = await self.repo.create(user)

        return UsuarioCreateResponse(
            usuario=UsuarioResponse.model_validate(created_user),
            password_temporal=temp_password,
        )

    async def listar_usuarios(
        self,
        *,
        include_inactive: bool = False,
        rol: RolEnum | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> UsuarioList:
        """
        List users with optional filters and pagination.

        Args:
            include_inactive: Include soft-deleted users.
            rol: Filter by role.
            search: Search term for username or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            UsuarioList with paginated results.
        """
        users, total = await self.repo.get_all(
            include_inactive=include_inactive,
            rol=rol,
            search=search,
            page=page,
            per_page=per_page,
        )

        return UsuarioList(
            items=[UsuarioListItem.model_validate(u) for u in users],
            total=total,
            page=page,
            per_page=per_page,
        )

    async def obtener_usuario(self, user_id: int) -> UsuarioResponse:
        """
        Get a user by ID.

        Args:
            user_id: User's database ID.

        Returns:
            UsuarioResponse with user data.

        Raises:
            HTTPException 404: User not found.
        """
        user = await self.repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        return UsuarioResponse.model_validate(user)

    async def actualizar_usuario(
        self,
        user_id: int,
        data: UsuarioUpdate,
    ) -> UsuarioResponse:
        """
        Update a user's information.

        Args:
            user_id: User's database ID.
            data: Update data (nombre, rol).

        Returns:
            UsuarioResponse with updated user data.

        Raises:
            HTTPException 404: User not found.
        """
        user = await self.repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        # Update only provided fields
        if data.nombre is not None:
            user.nombre = data.nombre
        if data.rol is not None:
            user.rol = data.rol

        updated_user = await self.repo.update(user)

        return UsuarioResponse.model_validate(updated_user)

    async def eliminar_usuario(self, user_id: int) -> None:
        """
        Soft delete a user.

        Args:
            user_id: User's database ID.

        Raises:
            HTTPException 404: User not found.
            HTTPException 400: Cannot delete own account.
        """
        user = await self.repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        if not user.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya está eliminado",
            )

        await self.repo.soft_delete(user)

    async def restaurar_usuario(self, user_id: int) -> UsuarioResponse:
        """
        Restore a soft-deleted user.

        Args:
            user_id: User's database ID.

        Returns:
            UsuarioResponse with restored user data.

        Raises:
            HTTPException 404: User not found.
            HTTPException 400: User is not deleted.
        """
        user = await self.repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        if user.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario no está eliminado",
            )

        restored_user = await self.repo.restore(user)

        return UsuarioResponse.model_validate(restored_user)

    async def resetear_password(self, user_id: int) -> ResetPasswordResponse:
        """
        Reset a user's password to a new temporary password.

        Args:
            user_id: User's database ID.

        Returns:
            ResetPasswordResponse with new temporary password.

        Raises:
            HTTPException 404: User not found.
        """
        user = await self.repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        # Generate new temporary password
        temp_password = generate_temp_password()

        # Update user
        user.password_hash = hash_password(temp_password)
        user.primer_login = True

        await self.repo.update(user)

        return ResetPasswordResponse(
            password_temporal=temp_password,
        )
