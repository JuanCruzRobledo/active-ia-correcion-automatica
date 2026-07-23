# app/routers/materias.py
"""
Materia router for Active-IA.

Endpoints for subject (materia) management (Admin only).

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 4
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import (
    require_admin,
    require_coordinador_or_admin,
    verificar_acceso_materia,
)
from app.models import Usuario
from app.models.enums import RolEnum
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
    activa: bool | None = Query(None, description="Filtrar por estado: true=activas, false=inactivas"),
    search: str | None = Query(None, description="Buscar por código o nombre"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Items por página"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> MateriaList:
    """
    Lista materias con filtros y paginación.

    Admin ve todas las materias. Coordinador solo ve sus materias asignadas.
    """
    require_coordinador_or_admin(ctx)

    coordinador_id = current_user.id if current_user.rol == RolEnum.COORDINADOR else None

    service = MateriaService(db)
    return await service.listar_materias(
        include_inactive=include_inactive,
        activa=activa,
        search=search,
        page=page,
        per_page=per_page,
        coordinador_id=coordinador_id,
        universidad_id=ctx.universidad_id,
    )


@router.post(
    "/",
    response_model=MateriaDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_materia(
    data: MateriaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> MateriaDetailResponse:
    """
    Crea una nueva materia con coordinadores opcionales.

    Solo administradores pueden crear materias.
    El código debe ser único y se convierte automáticamente a mayúsculas.
    Los coordinadores se pueden asignar en el mismo request.
    """
    require_admin(ctx)

    service = MateriaService(db)
    return await service.crear_materia(
        data, current_user_id=current_user.id, universidad_id=ctx.universidad_id
    )


@router.get("/{materia_id}", response_model=MateriaDetailResponse)
async def obtener_materia(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> MateriaDetailResponse:
    """
    Obtiene una materia por su ID con información de coordinadores.

    Admin: cualquier materia. Coordinador: solo las que tiene asignadas (403 si no).
    """
    require_coordinador_or_admin(ctx)
    await verificar_acceso_materia(db, current_user, ctx, materia_id)

    service = MateriaService(db)
    return await service.obtener_materia(materia_id, universidad_id=ctx.universidad_id)


@router.put("/{materia_id}", response_model=MateriaDetailResponse)
async def actualizar_materia(
    materia_id: int,
    data: MateriaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> MateriaDetailResponse:
    """
    Actualiza una materia existente con coordinadores opcionales.

    Admin: cualquier materia. Coordinador: solo las suyas (nombre/descripción).
    El código no se puede modificar. Un coordinador NO puede reasignar coordinadores
    (ese campo se ignora para él); solo el admin puede.
    """
    require_coordinador_or_admin(ctx)
    await verificar_acceso_materia(db, current_user, ctx, materia_id)

    # El coordinador no puede tocar la asignación de coordinadores de la materia.
    if current_user.rol != RolEnum.ADMIN:
        data.coordinador_ids = None

    service = MateriaService(db)
    return await service.actualizar_materia(
        materia_id, data, universidad_id=ctx.universidad_id
    )


@router.delete("/{materia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_materia(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> None:
    """
    Elimina una materia (soft delete).

    Solo administradores pueden eliminar materias.
    La materia se marca como inactiva pero no se elimina de la base de datos.
    """
    require_admin(ctx)

    service = MateriaService(db)
    await service.eliminar_materia(materia_id, universidad_id=ctx.universidad_id)


@router.post("/{materia_id}/restore", response_model=MateriaResponse)
async def restaurar_materia(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> MateriaResponse:
    """
    Restaura una materia eliminada.

    Solo administradores pueden restaurar materias.
    """
    require_admin(ctx)

    service = MateriaService(db)
    return await service.restaurar_materia(materia_id, universidad_id=ctx.universidad_id)


@router.post("/{materia_id}/coordinadores", response_model=CoordinadoresResponse)
async def asignar_coordinadores(
    materia_id: int,
    data: CoordinadoresAssign,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CoordinadoresResponse:
    """
    Asigna coordinadores a una materia.

    Solo administradores pueden asignar coordinadores.
    Esta operación reemplaza todos los coordinadores existentes con la nueva lista.
    Los usuarios deben tener rol COORDINADOR y estar activos.
    """
    require_admin(ctx)

    service = MateriaService(db)
    return await service.asignar_coordinadores(
        materia_id, data, universidad_id=ctx.universidad_id
    )
