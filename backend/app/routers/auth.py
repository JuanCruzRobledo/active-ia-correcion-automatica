# app/routers/auth.py
"""
Authentication router for Active-IA.

Handles user authentication and password management endpoints.

Endpoints:
    POST /auth/login - Authenticate user and get JWT token (login en dos pasos)
    POST /auth/select-universidad - Segundo paso del login cuando hay 2+ universidades
    POST /auth/switch-universidad - Cambia la universidad activa de una sesión autenticada
    POST /auth/change-password - Change user password

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 2
Ref: openspec/changes/multi-tenant-auth-jwt/ (Fase 1 multi-tenant: login en dos pasos)
"""

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, security
from app.models import Usuario
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    SeleccionarUniversidadRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión",
    description=(
        "Autentica un usuario con username y contraseña. Devuelve el JWT final "
        "(login directo: superadmin, o exactamente 1 universidad) o una "
        "respuesta intermedia `requiere_seleccion` cuando el usuario tiene 2+ "
        "universidades activas (ver POST /auth/select-universidad)."
    ),
    responses={
        200: {"description": "Login exitoso (token final o requiere_seleccion)"},
        401: {"description": "Credenciales inválidas"},
        403: {"description": "Cuenta bloqueada/deshabilitada, o sin universidad asignada"},
    },
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user and return the final JWT or an intermediate selection response.

    Args:
        data: Login credentials (username, password).
        db: Database session.

    Returns:
        TokenResponse (login directo) o SeleccionUniversidadRequerida (2+ universidades).

    Raises:
        HTTPException 401: Invalid credentials.
        HTTPException 403: Account locked/disabled, o usuario sin universidad asignada.
    """
    service = AuthService(db)
    return await service.authenticate(data)


@router.post(
    "/select-universidad",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Seleccionar universidad (paso 2 del login)",
    description=(
        "Segundo paso del login cuando POST /auth/login devolvió "
        "`requiere_seleccion=true`. Recibe el token de transición (Bearer, "
        "obtenido en la respuesta del login) y la universidad elegida; "
        "emite el token de acceso final."
    ),
    responses={
        200: {"description": "Selección válida: token final emitido"},
        401: {"description": "Token de transición inválido o expirado"},
        403: {"description": "No sos miembro activo de esa universidad"},
    },
)
async def select_universidad(
    data: SeleccionarUniversidadRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Complete the two-step login by selecting the active university.

    Args:
        data: Universidad elegida.
        credentials: Token de transición (scope="seleccion") emitido por /login.
        db: Database session.

    Returns:
        TokenResponse con el token final.

    Raises:
        HTTPException 401: Token de transición inválido/expirado.
        HTTPException 403: Sin membresía activa en la universidad elegida.
    """
    service = AuthService(db)
    return await service.seleccionar_universidad(credentials.credentials, data.universidad_id)


@router.post(
    "/switch-universidad",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Cambiar la universidad activa",
    description=(
        "Para una sesión ya autenticada, cambia la universidad activa y "
        "re-emite el token con la nueva universidad + rol de membresía."
    ),
    responses={
        200: {"description": "Switch válido: token re-emitido"},
        401: {"description": "No autenticado"},
        403: {"description": "No sos miembro activo de esa universidad"},
    },
)
async def switch_universidad(
    data: SeleccionarUniversidadRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Switch the active university for an already-authenticated session.

    Args:
        data: Universidad elegida.
        current_user: Usuario autenticado (vía get_current_user, sin cambios).
        db: Database session.

    Returns:
        TokenResponse con el token re-emitido.

    Raises:
        HTTPException 403: Sin membresía activa en la universidad elegida.
    """
    service = AuthService(db)
    return await service.switch_universidad(current_user, data.universidad_id)


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
