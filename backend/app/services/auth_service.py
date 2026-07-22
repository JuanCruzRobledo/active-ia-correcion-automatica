# app/services/auth_service.py
"""
Authentication service for Active-IA.

Handles user authentication, password management, and account security.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 2
Ref: docs/specs/11-SEGURIDAD.md
"""

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_transitional_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import RolEnum
from app.models.usuario import Usuario
from app.repositories.universidad_repository import UniversidadRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    SeleccionUniversidadRequerida,
    TokenResponse,
    UniversidadDisponible,
    UserInfo,
)

# Account lockout settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize auth service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        self.universidad_repo = UniversidadRepository(db)

    async def authenticate(self, data: LoginRequest) -> LoginResponse:
        """
        Authenticate a user with username and password (login en dos pasos).

        Fase 1 multi-tenant (multi-tenant-auth-jwt): tras validar credenciales
        (lógica intacta), resuelve las membresías activas del usuario y
        ramifica:

        - `es_superadmin=true` → token "modo superadmin" (`universidad_activa_id`
          y `rol` en `None`), SIN mirar sus membresías (decisión OQ1: opera igual).
        - No-superadmin con 0 membresías activas → 403, sin token.
        - No-superadmin con 1 membresía activa → token con esa universidad + rol.
        - No-superadmin con 2+ membresías activas → respuesta intermedia
          `SeleccionUniversidadRequerida` (sin access_token final).

        Args:
            data: Login credentials (username, password).

        Returns:
            `TokenResponse` (login directo) o `SeleccionUniversidadRequerida`
            (requiere segundo paso).

        Raises:
            HTTPException 401: Invalid credentials.
            HTTPException 403: Account locked/disabled, o sin universidad asignada.
        """
        # Get user by username (ARCH-001: vía repo, no SQL crudo en el service)
        user = await self.usuario_repo.get_by_username(data.username)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas",
            )

        # Check if account is disabled (soft delete)
        if not user.activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta deshabilitada",
            )

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining_minutes = int(
                (user.locked_until - datetime.utcnow()).total_seconds() // 60
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cuenta bloqueada. Intenta en {remaining_minutes} minutos.",
            )

        # Verify password
        if not verify_password(data.password, user.password_hash):
            await self._handle_failed_login(user)
            remaining = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Credenciales inválidas. {remaining} intentos restantes.",
            )

        # Successful login: reset counters
        await self._handle_successful_login(user)

        # --- Superadmin: modo superadmin, sin mirar membresías (decisión OQ1) ---
        if user.es_superadmin:
            return self._emitir_token(
                user, universidad_id=None, rol=None, es_superadmin=True
            )

        # --- No-superadmin: ramificar por cantidad de membresías activas ---
        membresias = await self.usuario_repo.get_membresias_activas(user.id)

        if len(membresias) == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario sin universidad asignada. Contactá al administrador.",
            )

        if len(membresias) == 1:
            membresia = membresias[0]
            return self._emitir_token(
                user,
                universidad_id=membresia.universidad_id,
                rol=membresia.rol,
                es_superadmin=False,
            )

        # 2+ membresías: respuesta intermedia con token de transición
        return SeleccionUniversidadRequerida(
            universidades=[
                UniversidadDisponible(
                    id=m.universidad_id, nombre=m.universidad.nombre, rol=m.rol
                )
                for m in membresias
            ],
            token_transicion=create_transitional_token(user.id, user.username),
        )

    async def seleccionar_universidad(
        self, token_transicion: str, universidad_id: int
    ) -> TokenResponse:
        """
        Segundo paso del login en dos pasos: emite el token final.

        Args:
            token_transicion: Token corto (`scope="seleccion"`) emitido por
                `authenticate` cuando el login devolvió `requiere_seleccion`.
            universidad_id: Universidad elegida.

        Returns:
            TokenResponse con el token final (universidad + rol de membresía).

        Raises:
            HTTPException 401: Token de transición inválido/expirado o de otro scope.
            HTTPException 403: Sin membresía activa en la universidad elegida
                (superadmin: solo si la universidad no existe o está inactiva).
        """
        try:
            payload = decode_token(token_transicion)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de selección inválido o expirado",
            )

        if payload.get("scope") != "seleccion":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de selección inválido",
            )

        user_id = payload.get("user_id")
        user = await self.usuario_repo.get_by_id_light(user_id)
        if user is None or not user.activo:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
            )

        return await self._resolver_y_emitir(user, universidad_id)

    async def switch_universidad(
        self, current_user: Usuario, universidad_id: int
    ) -> TokenResponse:
        """
        Cambia la universidad activa de una sesión ya autenticada.

        Args:
            current_user: Usuario autenticado (vía get_current_user).
            universidad_id: Universidad a la que se quiere cambiar.

        Returns:
            TokenResponse con el token re-emitido (nueva universidad + rol).

        Raises:
            HTTPException 403: Sin membresía activa en la universidad elegida
                (superadmin: solo si la universidad no existe o está inactiva).
        """
        return await self._resolver_y_emitir(current_user, universidad_id)

    async def _resolver_y_emitir(self, user: Usuario, universidad_id: int) -> TokenResponse:
        """
        Valida acceso a `universidad_id` y emite el token final.

        Un superadmin omite la validación de membresía (bypass, decisión OQ2)
        y recibe un `rol` sintético `ADMIN`; el resto requiere membresía activa.
        """
        if user.es_superadmin:
            universidad = await self.universidad_repo.get_activa_by_id(universidad_id)
            if universidad is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Universidad no encontrada o inactiva",
                )
            return self._emitir_token(
                user, universidad_id=universidad.id, rol=RolEnum.ADMIN, es_superadmin=True
            )

        membresia = await self.usuario_repo.get_membresia(user.id, universidad_id)
        if membresia is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No sos miembro activo de esa universidad",
            )

        return self._emitir_token(
            user,
            universidad_id=membresia.universidad_id,
            rol=membresia.rol,
            es_superadmin=False,
        )

    def _emitir_token(
        self,
        user: Usuario,
        *,
        universidad_id: int | None,
        rol: RolEnum | None,
        es_superadmin: bool,
    ) -> TokenResponse:
        """Arma el JWT + UserInfo para una universidad activa (o modo superadmin)."""
        token = create_access_token(
            user.id,
            user.username,
            rol=rol.value if rol is not None else None,
            universidad_activa_id=universidad_id,
            es_superadmin=es_superadmin,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserInfo(
                id=user.id,
                username=user.username,
                nombre=user.nombre,
                rol=rol,
                primer_login=user.primer_login,
                gemini_api_key_valid=user.gemini_api_key_valid,
                universidad_activa_id=universidad_id,
                es_superadmin=es_superadmin,
            ),
        )

    async def change_password(
        self,
        user: Usuario,
        data: ChangePasswordRequest,
    ) -> ChangePasswordResponse:
        """
        Change user password.

        Args:
            user: Current authenticated user.
            data: Password change request with current and new passwords.

        Returns:
            ChangePasswordResponse with success message.

        Raises:
            HTTPException 400: Password validation failed.
            HTTPException 401: Current password incorrect.
        """
        # Verify current password
        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Contraseña actual incorrecta",
            )

        # Validate new password matches confirmation
        if data.new_password != data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña y su confirmación no coinciden",
            )

        # Validate new password is different from current
        if data.current_password == data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe ser diferente a la actual",
            )

        # Validate password policy (at least one number)
        if not any(char.isdigit() for char in data.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña debe contener al menos un número",
            )

        # Update password (ARCH-001: persistencia vía repo; update() bumpea updated_at)
        user.password_hash = hash_password(data.new_password)
        user.primer_login = False

        await self.usuario_repo.update(user)

        return ChangePasswordResponse()

    async def _handle_failed_login(self, user: Usuario) -> None:
        """
        Handle a failed login attempt.

        Increments failed attempts counter and locks account if threshold reached.

        Args:
            user: The user who failed to login.
        """
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + LOCKOUT_DURATION

        # ARCH-001: persistencia vía repo. save() NO bumpea updated_at (el estado de
        # login no cuenta como 'modificación' del registro).
        await self.usuario_repo.save(user)

    async def _handle_successful_login(self, user: Usuario) -> None:
        """
        Handle a successful login.

        Resets failed attempts counter and updates last login time.

        Args:
            user: The user who logged in successfully.
        """
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()

        # ARCH-001: persistencia vía repo. save() NO bumpea updated_at.
        await self.usuario_repo.save(user)
