# app/services/auth_service.py
"""
Authentication service for Active-IA.

Handles user authentication, password management, and account security.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 2
Ref: docs/specs/11-SEGURIDAD.md
"""

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.usuario import Usuario
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    TokenResponse,
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

    async def authenticate(self, data: LoginRequest) -> TokenResponse:
        """
        Authenticate a user with username and password.

        Args:
            data: Login credentials (username, password).

        Returns:
            TokenResponse with JWT token and user info.

        Raises:
            HTTPException 401: Invalid credentials.
            HTTPException 403: Account locked or disabled.
        """
        # Get user by username
        stmt = select(Usuario).where(Usuario.username == data.username)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

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

        # Generate JWT token
        token = create_access_token(
            user_id=user.id,
            username=user.username,
            rol=user.rol.value,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserInfo(
                id=user.id,
                username=user.username,
                nombre=user.nombre,
                rol=user.rol,
                primer_login=user.primer_login,
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

        # Update password
        user.password_hash = hash_password(data.new_password)
        user.primer_login = False
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(user)

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

        await self.db.commit()

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

        await self.db.commit()
        await self.db.refresh(user)
