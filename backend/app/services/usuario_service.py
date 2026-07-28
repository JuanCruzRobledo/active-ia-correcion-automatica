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


def _usuario_response(user: Usuario, rol: RolEnum | None) -> UsuarioResponse:
    """Construye `UsuarioResponse` con `rol` resuelto explícitamente.

    Fase 6 multi-tenant (D5): `Usuario` ya no tiene columna `rol` — no se
    puede construir con `UsuarioResponse.model_validate(user)` a secas (eso
    dejaría `rol=None` silenciosamente, vía el default del schema). El rol
    SIEMPRE lo resuelve el caller (de `data.rol` en un alta/cambio, o de la
    membresía vía `UsuarioRepository.get_rol_en_universidad`/
    `get_rol_mas_antiguo`) y se pasa acá.
    """
    return UsuarioResponse(
        id=user.id,
        username=user.username,
        nombre=user.nombre,
        rol=rol,
        email=user.email,
        primer_login=user.primer_login,
        gemini_api_key_valid=user.gemini_api_key_valid,
        activo=user.activo,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
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
        self.coord_materia_repo = CoordinadorMateriaRepository(db)
        self.comision_tutor_repo = ComisionTutorRepository(db)

    async def crear_usuario(
        self,
        data: UsuarioCreate,
        current_user_id: int | None = None,
        universidad_id: int | None = None,
    ) -> UsuarioCreateResponse:
        """
        Create a new user with a temporary password.

        Fase 6 multi-tenant (D4): el alta es transaccional — crea el
        `Usuario` y su membresía (`UsuarioUniversidad`) en la universidad
        activa, con el rol recibido, en la MISMA transacción. Si no hay
        universidad activa (superadmin en modo global), responde 400: debe
        elegir una universidad primero, igual que para crear una materia.

        Args:
            data: User creation data (username, nombre, rol).
            current_user_id: ID of the user creating this user (for audit log).
            universidad_id: Universidad activa del solicitante (`ctx.universidad_id`).

        Returns:
            UsuarioCreateResponse with user data and temporary password.

        Raises:
            HTTPException 400: sin universidad activa.
            HTTPException 409: Username already exists.
        """
        if universidad_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Elegí una universidad activa para crear usuarios",
            )

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
            email=data.email,
            password_hash=hash_password(temp_password),
            primer_login=True,
            activo=True,
        )

        created_user = await self.repo.create_con_membresia(user, universidad_id, data.rol)

        # Registrar actividad solo si NO es estudiante (aún no existe rol ESTUDIANTE)
        # Cuando se agregue, aquí se debe verificar: if data.rol != RolEnum.ESTUDIANTE
        actividad_service = ActividadService(self.db)
        await actividad_service.registrar_actividad(
            tipo=TipoActividadEnum.USUARIO_CREADO,
            descripcion=f"Usuario '{created_user.nombre}' ({data.rol.value}) creado",
            entidad_id=created_user.id,
            entidad_nombre=created_user.nombre,
            usuario_id=current_user_id,
        )

        return UsuarioCreateResponse(
            usuario=_usuario_response(created_user, data.rol),
            password_temporal=temp_password,
        )

    async def listar_usuarios(
        self,
        *,
        universidad_id: int | None = None,
        activo: bool | None = None,
        rol: RolEnum | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> UsuarioList:
        """
        List users with optional filters and pagination.

        Fase 6 multi-tenant (D2): `universidad_id` acota el listado a
        usuarios con membresía activa en esa universidad. `None` = sin
        filtro (modo superadmin global).

        Args:
            universidad_id: Universidad activa del solicitante. `None` = todas.
            activo: Filter by active status. None = all, True = active, False = inactive.
            rol: Filter by role.
            search: Search term for username or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            UsuarioList with paginated results.
        """
        users, total = await self.repo.get_all(
            universidad_id=universidad_id,
            activo=activo,
            rol=rol,
            search=search,
            page=page,
            per_page=per_page,
        )

        # Fase 6 multi-tenant (D5): `rol` ya no es un atributo de `Usuario` —
        # se resuelve en batch (una sola query, no N+1) contra la membresía.
        # Con `universidad_id`: el rol EN esa universidad (todo usuario en
        # `users` ya está filtrado por tener membresía activa ahí, D2). Sin
        # `universidad_id` (modo superadmin global): "mejor esfuerzo" con la
        # membresía activa más antigua (D6).
        user_ids = [u.id for u in users]
        if universidad_id is not None:
            roles = await self.repo.get_roles_en_universidad(user_ids, universidad_id)
        else:
            roles = await self.repo.get_roles_mas_antiguos(user_ids)

        items = [
            UsuarioListItem(
                id=u.id,
                username=u.username,
                nombre=u.nombre,
                rol=roles.get(u.id),
                activo=u.activo,
                created_at=u.created_at,
                last_login=u.last_login,
            )
            for u in users
        ]

        return UsuarioList(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )

    async def obtener_usuario(
        self, user_id: int, universidad_id: int | None = None
    ) -> UsuarioResponse:
        """
        Get a user by ID.

        Args:
            user_id: User's database ID.
            universidad_id: Universidad activa del solicitante (`ctx.universidad_id`),
                usada SÓLO para resolver qué rol mostrar (D5) — `None` = modo
                superadmin global, resuelve por la membresía más antigua (D6).

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

        rol = await self._resolver_rol(user_id, universidad_id)
        return _usuario_response(user, rol)

    async def _resolver_rol(self, user_id: int, universidad_id: int | None) -> RolEnum | None:
        """Resuelve el rol a mostrar para `user_id` (D5): en `universidad_id`
        si se pasa, si no la membresía activa más antigua (D6)."""
        if universidad_id is not None:
            return await self.repo.get_rol_en_universidad(user_id, universidad_id)
        return await self.repo.get_rol_mas_antiguo(user_id)

    async def actualizar_usuario(
        self,
        user_id: int,
        data: UsuarioUpdate,
        universidad_id: int | None = None,
    ) -> UsuarioResponse:
        """
        Update a user's information.

        Fase 6 multi-tenant (D5): un rol nuevo se aplica a la MEMBRESÍA en
        la universidad activa del solicitante, no a un rol global. Las
        membresías en otras universidades quedan intactas. Sin universidad
        activa → 400 (mismo criterio que el alta, D4); sin membresía activa
        en `universidad_id` → 404.

        Args:
            user_id: User's database ID.
            data: Update data (nombre, rol).
            universidad_id: Universidad activa del solicitante (`ctx.universidad_id`).
                Sólo se exige/usa si `data.rol` viene poblado.

        Returns:
            UsuarioResponse with updated user data.

        Raises:
            HTTPException 400: cambio de rol sin universidad activa.
            HTTPException 404: usuario no encontrado, o sin membresía activa
                en `universidad_id` cuando se pide cambiar el rol.
        """
        user = await self.repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        # Fase 6 multi-tenant (D5): el rol "anterior" ya no sale de
        # `user.rol` (no existe) sino de la membresía en `universidad_id`
        # (si no hay cambio de rol pedido, igual hace falta para el
        # response). Si `universidad_id` es `None` y no se pide cambio de
        # rol, no hace falta resolver nada todavía (se resuelve al final,
        # modo "más antigua").
        rol_anterior = (
            await self.repo.get_rol_en_universidad(user_id, universidad_id)
            if universidad_id is not None
            else None
        )

        # Update only provided fields
        if data.nombre is not None:
            user.nombre = data.nombre
        rol_nuevo = data.rol
        if data.rol is not None:
            if universidad_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Elegí una universidad activa para cambiar el rol",
                )
            membresia = await self.repo.update_rol_membresia(user_id, universidad_id, data.rol)
            if membresia is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El usuario no tiene una membresía activa en esta universidad",
                )
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

        rol_para_response = rol_nuevo if rol_nuevo is not None else await self._resolver_rol(
            user_id, universidad_id
        )
        return _usuario_response(updated_user, rol_para_response)

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

    async def restaurar_usuario(
        self, user_id: int, universidad_id: int | None = None
    ) -> UsuarioResponse:
        """
        Restore a soft-deleted user.

        Args:
            user_id: User's database ID.
            universidad_id: Universidad activa del solicitante (`ctx.universidad_id`),
                usada SÓLO para resolver qué rol mostrar (D5).

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

        rol = await self._resolver_rol(user_id, universidad_id)
        return _usuario_response(restored_user, rol)

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
        self, user_id: int, universidad_id: int | None, data: MoodleCredentialsUpdate
    ) -> MoodleCredentialsResponse:
        """
        Guarda las credenciales Moodle en la membresía activa `(usuario, universidad)`.

        Fase 3 multi-tenant (D4): reemplaza el viejo write-path a
        `usuarios.moodle_*`. El `moodle_host` NO se acepta acá — es propiedad
        de la `Universidad` de la membresía (read-only, se devuelve en la
        respuesta para conveniencia del caller).

        Raises:
            HTTPException 409: sin universidad activa elegida (superadmin, OQ5).
            HTTPException 404: sin membresía activa (usuario, universidad_id).
        """
        if universidad_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Elegí una universidad activa para configurar tus credenciales Moodle",
            )
        password_encrypted = encrypt_api_key(data.moodle_password)
        membresia = await self.repo.update_moodle_credentials_membresia(
            usuario_id=user_id,
            universidad_id=universidad_id,
            username=data.moodle_username,
            password_encrypted=password_encrypted,
        )
        if membresia is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay una membresía activa en la universidad activa",
            )
        return MoodleCredentialsResponse(
            moodle_username=membresia.moodle_username,
            moodle_host=membresia.universidad.moodle_host,
        )
