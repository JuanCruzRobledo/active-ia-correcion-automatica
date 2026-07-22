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
from dataclasses import dataclass
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.models import Usuario, get_async_session
from app.models.enums import RolEnum

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


# =========================================
# Universidad Activa Dependency (Fase 1 multi-tenant)
# =========================================


@dataclass
class ContextoUniversidad:
    """
    Contexto de la universidad activa resuelto desde el token + la base.

    `rol` se relee de `usuario_universidad` (o es un rol sintético ADMIN para
    superadmin operando sin membresía real) — NUNCA se confía en el claim
    `rol` del token para autorizar, así que revocar una membresía tiene
    efecto inmediato (D3, multi-tenant-auth-jwt).
    """

    universidad_id: int | None
    rol: RolEnum | None
    es_superadmin: bool


async def get_universidad_activa(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContextoUniversidad:
    """
    Dependency que resuelve y valida la universidad activa del usuario.

    Fase 1 multi-tenant (multi-tenant-auth-jwt): se agrega **sin tocar**
    `get_current_user`/`get_current_user_optional` — este dependency los
    reusa (Depends(get_current_user) ya valida el usuario) y agrega:

    1. Lee `universidad_activa_id` del token.
    2. Si falta (token viejo, o superadmin que aún no eligió universidad):
       - Superadmin (`current_user.es_superadmin`): modo superadmin puro,
         sin universidad ni membresía exigida.
       - No-superadmin: retrocompat — si tiene exactamente 1 membresía
         activa la auto-resuelve; con 0 o 2+ pide reautenticación (409).
    3. Si viene poblado: valida membresía activa `(current_user, universidad)`
       vía repositorio, salvo superadmin (bypass total: solo exige que la
       universidad exista y esté `activa`). Sin acceso → 403.

    Es **opt-in por endpoint**: en Fase 1 no se monta en ningún router
    existente (eso es Fase 2/4); se entrega listo para consumir y cubierto
    por tests.

    Args:
        credentials: HTTP Bearer credentials (para releer el claim del token).
        current_user: Usuario autenticado (vía get_current_user, sin cambios).
        db: Database session.

    Returns:
        ContextoUniversidad: universidad activa + rol de membresía (de la
        base) + flag superadmin.

    Raises:
        HTTPException 403: Sin membresía activa en la universidad pedida, o
            universidad inexistente/inactiva.
        HTTPException 409: Token viejo ambiguo (0 o 2+ membresías activas)
            que requiere reautenticación para elegir universidad.
    """
    from app.repositories.universidad_repository import UniversidadRepository
    from app.repositories.usuario_repository import UsuarioRepository

    token = credentials.credentials
    payload = decode_token(token)
    universidad_activa_id: int | None = payload.get("universidad_activa_id")

    usuario_repo = UsuarioRepository(db)

    # --- Token sin universidad_activa_id: retrocompat / modo superadmin puro ---
    if universidad_activa_id is None:
        if current_user.es_superadmin:
            return ContextoUniversidad(universidad_id=None, rol=None, es_superadmin=True)

        membresias = await usuario_repo.get_membresias_activas(current_user.id)
        if len(membresias) == 1:
            membresia = membresias[0]
            return ContextoUniversidad(
                universidad_id=membresia.universidad_id,
                rol=membresia.rol,
                es_superadmin=False,
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reautenticá para elegir universidad",
        )

    # --- Token con universidad_activa_id: validar acceso ---
    if current_user.es_superadmin:
        universidad_repo = UniversidadRepository(db)
        universidad = await universidad_repo.get_activa_by_id(universidad_activa_id)
        if universidad is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Universidad no encontrada o inactiva",
            )
        return ContextoUniversidad(
            universidad_id=universidad.id,
            rol=RolEnum.ADMIN,
            es_superadmin=True,
        )

    membresia = await usuario_repo.get_membresia(current_user.id, universidad_activa_id)
    if membresia is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No sos miembro activo de esta universidad",
        )

    return ContextoUniversidad(
        universidad_id=membresia.universidad_id,
        rol=membresia.rol,
        es_superadmin=False,
    )
