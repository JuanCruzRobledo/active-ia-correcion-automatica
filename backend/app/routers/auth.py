# app/routers/auth.py
"""
Authentication router for Active-IA.

Handles user authentication and password management endpoints.

Endpoints:
    POST /auth/login - Authenticate user and get JWT token
    POST /auth/change-password - Change user password

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 2
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models import Usuario
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión",
    description="Autentica un usuario con username y contraseña, retorna JWT token.",
    responses={
        200: {"description": "Login exitoso"},
        401: {"description": "Credenciales inválidas"},
        403: {"description": "Cuenta bloqueada o deshabilitada"},
    },
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user and return JWT token.

    Args:
        data: Login credentials (username, password).
        db: Database session.

    Returns:
        TokenResponse with JWT token and user info.

    Raises:
        HTTPException 401: Invalid credentials.
        HTTPException 403: Account locked or disabled.
    """
    service = AuthService(db)
    return await service.authenticate(data)


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Cambiar contraseña",
    description="Permite al usuario cambiar su contraseña. Requiere autenticación.",
    responses={
        200: {"description": "Contraseña actualizada exitosamente"},
        400: {"description": "Validación fallida (contraseñas no coinciden, etc.)"},
        401: {"description": "Contraseña actual incorrecta o no autenticado"},
    },
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangePasswordResponse:
    """
    Change the password for the current authenticated user.

    This endpoint is used both for:
    - First login password change (primer_login=True)
    - Regular password change from profile

    Args:
        data: Password change request with current and new passwords.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        ChangePasswordResponse with success message.

    Raises:
        HTTPException 400: New password doesn't meet requirements.
        HTTPException 401: Current password is incorrect.
    """
    service = AuthService(db)
    return await service.change_password(current_user, data)
