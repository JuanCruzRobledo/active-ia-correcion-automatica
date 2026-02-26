# app/routers/usuarios.py
"""
Usuario router for Active-IA.

Endpoints for user management (Admin only).

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_admin
from app.models import Usuario
from app.models.enums import RolEnum
from app.schemas.usuario import (
    ResetPasswordResponse,
    UsuarioCreate,
    UsuarioCreateResponse,
    UsuarioList,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/", response_model=UsuarioList)
async def listar_usuarios(
    activo: bool | None = Query(None, description="Filtrar por estado: true=activos, false=eliminados, omitido=todos"),
    rol: RolEnum | None = Query(None, description="Filtrar por rol"),
    search: str | None = Query(None, description="Buscar por username o nombre"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=1000, description="Items por página"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsuarioList:
    """
    Lista usuarios con filtros y paginación.

    Admin ve todos los usuarios. Coordinador solo puede consultar tutores
    (necesario para asignar tutores a comisiones).
    """
    if current_user.rol == RolEnum.COORDINADOR:
        if rol != RolEnum.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Coordinadores solo pueden consultar usuarios con rol Tutor",
            )
    else:
        require_admin(current_user)

    service = UsuarioService(db)
    return await service.listar_usuarios(
        activo=activo,
        rol=rol,
        search=search,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/",
    response_model=UsuarioCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_usuario(
    data: UsuarioCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsuarioCreateResponse:
    """
    Crea un nuevo usuario con contraseña temporal.

    Solo administradores pueden crear usuarios.
    La contraseña temporal debe ser comunicada al usuario.
    """
    require_admin(current_user)

    service = UsuarioService(db)
    return await service.crear_usuario(data, current_user_id=current_user.id)


@router.get("/{user_id}", response_model=UsuarioResponse)
async def obtener_usuario(
    user_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsuarioResponse:
    """
    Obtiene un usuario por su ID.

    Solo administradores pueden acceder a este endpoint.
    """
    require_admin(current_user)

    service = UsuarioService(db)
    return await service.obtener_usuario(user_id)


@router.put("/{user_id}", response_model=UsuarioResponse)
async def actualizar_usuario(
    user_id: int,
    data: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsuarioResponse:
    """
    Actualiza un usuario existente.

    Solo administradores pueden actualizar usuarios.
    Solo se actualizan los campos proporcionados.
    """
    require_admin(current_user)

    service = UsuarioService(db)
    return await service.actualizar_usuario(user_id, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_usuario(
    user_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina un usuario (soft delete).

    Solo administradores pueden eliminar usuarios.
    El usuario no puede eliminarse a sí mismo.
    """
    require_admin(current_user)

    # Prevent self-deletion
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta",
        )

    service = UsuarioService(db)
    await service.eliminar_usuario(user_id)


@router.post("/{user_id}/restore", response_model=UsuarioResponse)
async def restaurar_usuario(
    user_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsuarioResponse:
    """
    Restaura un usuario eliminado.

    Solo administradores pueden restaurar usuarios.
    """
    require_admin(current_user)

    service = UsuarioService(db)
    return await service.restaurar_usuario(user_id)


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def resetear_password(
    user_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """
    Resetea la contraseña de un usuario a una temporal.

    Solo administradores pueden resetear contraseñas.
    La nueva contraseña temporal debe ser comunicada al usuario.
    El usuario deberá cambiarla en su próximo login.
    """
    require_admin(current_user)

    service = UsuarioService(db)
    return await service.resetear_password(user_id)
