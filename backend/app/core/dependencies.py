# app/core/dependencies.py
"""
FastAPI dependencies for Active-IA.

Provides dependency injection for:
- Database sessions (async)
- Current authenticated user
- User validation and authorization

Ref: docs/specs/11-SEGURIDAD.md section 2.2
"""

import logging
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.models import Usuario, get_async_session

logger = logging.getLogger(__name__)

# =========================================
# Database Session Dependency
# =========================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.

    Yields an AsyncSession that is automatically closed after the request.

    Usage in FastAPI endpoints:
        @router.get("/users")
        async def list_users(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass

    Yields:
        AsyncSession: Database session.
    """
    async for session in get_async_session():
        yield session


# =========================================
# Authentication Dependencies
# =========================================

# HTTP Bearer token scheme for Authorization header
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """
    Dependency that extracts and validates the current user from JWT token.

    Extracts the token from the Authorization header, validates it,
    and retrieves the user from the database.

    Args:
        credentials: HTTP Bearer credentials from Authorization header.
        db: Database session.

    Returns:
        Usuario: Authenticated user object.

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found.
        HTTPException 403: If user is inactive (soft deleted).

    Usage:
        @router.get("/profile")
        async def get_profile(current_user: Usuario = Depends(get_current_user)):
            return current_user
    """
    token = credentials.credentials

    # Decode and validate JWT token
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Retrieve user from database
    from app.repositories.usuario_repository import UsuarioRepository

    user_repo = UsuarioRepository(db)
    user = await user_repo.get_by_id_light(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active (not soft deleted)
    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario deshabilitado",
        )

    return user


async def get_current_active_user(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    """
    Dependency that ensures the current user is active.

    This is an alias for get_current_user since it already checks
    for active status. Provided for semantic clarity.

    Args:
        current_user: Current authenticated user.

    Returns:
        Usuario: Active user object.

    Usage:
        @router.post("/items")
        async def create_item(
            user: Usuario = Depends(get_current_active_user)
        ):
            # user is guaranteed to be active
            pass
    """
    return current_user


# =========================================
# Optional Authentication
# =========================================


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Usuario | None:
    """
    Dependency that optionally extracts the current user.

    Returns the user if a valid token is provided, otherwise returns None.
    Does not raise an error if no token is present.

    Useful for endpoints that behave differently for authenticated vs
    unauthenticated users.

    Args:
        credentials: Optional HTTP Bearer credentials.
        db: Database session.

    Returns:
        Usuario | None: User object if authenticated, None otherwise.

    Usage:
        @router.get("/public-data")
        async def get_data(
            user: Usuario | None = Depends(get_current_user_optional)
        ):
            if user:
                # Return personalized data
                pass
            else:
                # Return public data
                pass
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = decode_token(token)
        user_id: int = payload.get("user_id")

        if user_id is None:
            return None

        from app.repositories.usuario_repository import UsuarioRepository

        user_repo = UsuarioRepository(db)
        user = await user_repo.get_by_id(user_id)

        if user is None or not user.activo:
            return None

        return user
    except JWTError:
        # Token inválido o expirado → se trata como anónimo (comportamiento esperado
        # de un auth opcional). No se loguea: es un caso de negocio normal.
        return None
    except Exception:
        # Un error inesperado (p. ej. DB no disponible) NO debe degradarse en
        # silencio: se deja traza para diagnóstico, pero se mantiene el contrato
        # opcional (None) para no romper los endpoints que lo usan.
        logger.exception("Error inesperado resolviendo el usuario opcional (auth opcional)")
        return None
