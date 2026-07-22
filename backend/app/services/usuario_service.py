# app/services/usuario_service.py
"""
Usuario service for Active-IA.

Business logic for user management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_api_key, generate_temp_password, hash_password
from app.models import Usuario
from app.models.enums import RolEnum, TipoActividadEnum
from app.repositories.comision_repository import ComisionTutorRepository
from app.repositories.materia_repository import CoordinadorMateriaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import (
    MoodleCredentialsResponse,
    MoodleCredentialsUpdate,
    ResetPasswordResponse,
    UsuarioCreate,
    UsuarioCreateResponse,
    UsuarioList,
    UsuarioListItem,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.services.actividad_service import ActividadService


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
        self.coord_materia_repo = CoordinadorMateriaRepository(db)
        self.comision_tutor_repo = ComisionTutorRepository(db)

    async def crear_usuario(
        self, data: UsuarioCreate, current_user_id: int | None = None
    ) -> UsuarioCreateResponse:
        """
        Create a new user with a temporary password.

        Args:
            data: User creation data (username, nombre, rol).
            current_user_id: ID of the user creating this user (for audit log).

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
            email=data.email,
            password_hash=hash_password(temp_password),
            primer_login=True,
            activo=True,
        )

        created_user = await self.repo.create(user)

        # Registrar actividad solo si NO es estudiante (aún no existe rol ESTUDIANTE)
        # Cuando se agregue, aquí se debe verificar: if created_user.rol != RolEnum.ESTUDIANTE
        actividad_service = ActividadService(self.db)
        await actividad_service.registrar_actividad(
            tipo=TipoActividadEnum.USUARIO_CREADO,
            descripcion=f"Usuario '{created_user.nombre}' ({created_user.rol.value}) creado",
            entidad_id=created_user.id,
            entidad_nombre=created_user.nombre,
            usuario_id=current_user_id,
        )

        return UsuarioCreateResponse(
            usuario=UsuarioResponse.model_validate(created_user),
            password_temporal=temp_password,
        )

    async def listar_usuarios(
        self,
        *,
        activo: bool | None = None,
        rol: RolEnum | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> UsuarioList:
        """
        List users with optional filters and pagination.

        Args:
            activo: Filter by active status. None = all, True = active, False = inactive.
            rol: Filter by role.
            search: Search term for username or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            UsuarioList with paginated results.
        """
        users, total = await self.repo.get_all(
            activo=activo,
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
        rol_anterior = user.rol
        if data.nombre is not None:
            user.nombre = data.nombre
        if data.rol is not None:
            user.rol = data.rol
        # CRUD-010: email es nullable -> model_fields_set para poder vaciarlo.
        if "email" in data.model_fields_set:
            user.email = data.email

        updated_user = await self.repo.update(user)

        # CRUD-013: al cambiar el rol, limpiar las asignaciones incompatibles con el
        # rol nuevo, para no dejar filas huérfanas (un ex-coordinador seguía
        # figurando como coordinador; un ex-tutor conservaba sus comisiones).
        if data.rol is not None and data.rol != rol_anterior:
            if data.rol != RolEnum.COORDINADOR:
                await self.coord_materia_repo.delete_all_for_coordinador(user_id)
            if data.rol != RolEnum.TUTOR:
                await self.comision_tutor_repo.delete_all_for_tutor(user_id)

        return UsuarioResponse.model_validate(updated_user)

    async def eliminar_usuario(self, user_id: int) -> None:
        """
        Delete a user — soft or hard depending on ALLOW_HARD_DELETE setting.

        When ALLOW_HARD_DELETE=false (default):
            Soft delete: sets activo=False. Reversible via restaurar_usuario.
        When ALLOW_HARD_DELETE=true:
            Hard delete: physically removes the user from DB.
            - SET NULL on Entrega.subido_por_id and Correccion.corregido_por_id
            - DELETE CoordinadorMateria, ComisionTutor, Actividad rows
            - DELETE Usuario row — IRREVERSIBLE.

        Args:
            user_id: User's database ID.

        Raises:
            HTTPException 404: User not found.
            HTTPException 400: (soft delete only) Cannot delete already-deleted user.
        """
        from app.core.config import settings

        user = await self.repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        # CRUD-002: soft delete SIEMPRE (se eliminó el flag ALLOW_HARD_DELETE).
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

    async def update_moodle_credentials(
        self, user_id: int, data: MoodleCredentialsUpdate
    ) -> MoodleCredentialsResponse:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        password_encrypted = encrypt_api_key(data.moodle_password)
        updated = await self.repo.update_moodle_credentials(
            user_id=user_id,
            username=data.moodle_username,
            password_encrypted=password_encrypted,
            host=data.moodle_host,
        )
        return MoodleCredentialsResponse(
            moodle_username=updated.moodle_username,
            moodle_host=updated.moodle_host,
        )
