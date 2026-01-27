# app/routers/materias.py
"""
Materia router for Active-IA.

Endpoints for subject (materia) management (Admin only).

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 4
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_admin
from app.models import Usuario
from app.schemas.materia import (
    CoordinadoresAssign,
    CoordinadoresResponse,
    MateriaCreate,
    MateriaDetailResponse,
    MateriaList,
    MateriaResponse,
    MateriaUpdate,
)
from app.services.materia_service import MateriaService

router = APIRouter(prefix="/materias", tags=["materias"])


@router.get("/", response_model=MateriaList)
async def listar_materias(
    include_inactive: bool = Query(False, description="Incluir materias eliminadas"),
    search: str | None = Query(None, description="Buscar por código o nombre"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Items por página"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriaList:
    """
    Lista todas las materias con filtros y paginación.

    Solo administradores pueden acceder a este endpoint.
    """
    require_admin(current_user)

    service = MateriaService(db)
    return await service.listar_materias(
        include_inactive=include_inactive,
        search=search,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/",
    response_model=MateriaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_materia(
    data: MateriaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriaResponse:
    """
    Crea una nueva materia.

    Solo administradores pueden crear materias.
    El código debe ser único y se convierte automáticamente a mayúsculas.
    """
    require_admin(current_user)

    service = MateriaService(db)
    return await service.crear_materia(data)


@router.get("/{materia_id}", response_model=MateriaDetailResponse)
async def obtener_materia(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriaDetailResponse:
    """
    Obtiene una materia por su ID con información de coordinadores.

    Solo administradores pueden acceder a este endpoint.
    """
    require_admin(current_user)

    service = MateriaService(db)
    return await service.obtener_materia(materia_id)


@router.put("/{materia_id}", response_model=MateriaResponse)
async def actualizar_materia(
    materia_id: int,
    data: MateriaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriaResponse:
    """
    Actualiza una materia existente.

    Solo administradores pueden actualizar materias.
    Solo se actualizan los campos proporcionados.
    El código no puede ser modificado después de la creación.
    """
    require_admin(current_user)

    service = MateriaService(db)
    return await service.actualizar_materia(materia_id, data)


@router.delete("/{materia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_materia(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina una materia (soft delete).

    Solo administradores pueden eliminar materias.
    La materia se marca como inactiva pero no se elimina de la base de datos.
    """
    require_admin(current_user)

    service = MateriaService(db)
    await service.eliminar_materia(materia_id)


@router.post("/{materia_id}/restore", response_model=MateriaResponse)
async def restaurar_materia(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriaResponse:
    """
    Restaura una materia eliminada.

    Solo administradores pueden restaurar materias.
    """
    require_admin(current_user)

    service = MateriaService(db)
    return await service.restaurar_materia(materia_id)


@router.post("/{materia_id}/coordinadores", response_model=CoordinadoresResponse)
async def asignar_coordinadores(
    materia_id: int,
    data: CoordinadoresAssign,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoordinadoresResponse:
    """
    Asigna coordinadores a una materia.

    Solo administradores pueden asignar coordinadores.
    Esta operación reemplaza todos los coordinadores existentes con la nueva lista.
    Los usuarios deben tener rol COORDINADOR y estar activos.
    """
    require_admin(current_user)

    service = MateriaService(db)
    return await service.asignar_coordinadores(materia_id, data)
