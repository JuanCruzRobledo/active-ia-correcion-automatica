# app/routers/cohortes.py
"""
Cohorte/Cuatrimestre router for Active-IA (Dashboard de Gestores).

ABM de cohortes y cuatrimestres. Solo ADMIN.
Ref: PLAN_DASHBOARD_GESTORES.md §8 (T2)
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import require_admin, require_coordinador_or_admin
from app.models import Usuario
from app.schemas.cohorte import (
    CohorteCreate,
    CohorteDetailResponse,
    CohorteUpdate,
    CuatrimestreCreate,
    CuatrimestreResponse,
    CuatrimestreUpdate,
)
from app.services.cohorte_service import CohorteService

router = APIRouter(prefix="/cohortes", tags=["cohortes"])


# ===================== Cohorte =====================


@router.get("/", response_model=list[CohorteDetailResponse])
async def listar_cohortes(
    include_inactive: bool = Query(False, description="Incluir cohortes inactivas"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> list[CohorteDetailResponse]:
    """Lista las cohortes con sus cuatrimestres. Lectura: admin o coordinador (para
    elegir el cuatrimestre al configurar su materia). Crear/editar sigue siendo admin."""
    require_coordinador_or_admin(ctx)
    service = CohorteService(db)
    return await service.listar_cohortes(include_inactive=include_inactive)


@router.post("/", response_model=CohorteDetailResponse, status_code=status.HTTP_201_CREATED)
async def crear_cohorte(
    data: CohorteCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CohorteDetailResponse:
    """Crea una cohorte (código único). Solo admin."""
    require_admin(ctx)
    service = CohorteService(db)
    return await service.crear_cohorte(data, usuario_id=current_user.id)


@router.get("/{cohorte_id}", response_model=CohorteDetailResponse)
async def obtener_cohorte(
    cohorte_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CohorteDetailResponse:
    """Obtiene una cohorte por ID. Solo admin."""
    require_admin(ctx)
    service = CohorteService(db)
    return await service.obtener_cohorte(cohorte_id)


@router.put("/{cohorte_id}", response_model=CohorteDetailResponse)
async def actualizar_cohorte(
    cohorte_id: int,
    data: CohorteUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CohorteDetailResponse:
    """Actualiza nombre/estado de una cohorte. Solo admin."""
    require_admin(ctx)
    service = CohorteService(db)
    return await service.actualizar_cohorte(cohorte_id, data)


@router.delete("/{cohorte_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_cohorte(
    cohorte_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> None:
    """Elimina una cohorte (solo si no tiene materias vinculadas). Solo admin."""
    require_admin(ctx)
    service = CohorteService(db)
    await service.eliminar_cohorte(cohorte_id)


# ===================== Cuatrimestre =====================


@router.post(
    "/{cohorte_id}/cuatrimestres",
    response_model=CuatrimestreResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_cuatrimestre(
    cohorte_id: int,
    data: CuatrimestreCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CuatrimestreResponse:
    """Crea un cuatrimestre en la cohorte (numero único en la cohorte). Solo admin."""
    require_admin(ctx)
    service = CohorteService(db)
    return await service.crear_cuatrimestre(cohorte_id, data)


@router.put("/cuatrimestres/{cuatrimestre_id}", response_model=CuatrimestreResponse)
async def actualizar_cuatrimestre(
    cuatrimestre_id: int,
    data: CuatrimestreUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CuatrimestreResponse:
    """Actualiza un cuatrimestre. Solo admin."""
    require_admin(ctx)
    service = CohorteService(db)
    return await service.actualizar_cuatrimestre(cuatrimestre_id, data)


@router.delete(
    "/cuatrimestres/{cuatrimestre_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def eliminar_cuatrimestre(
    cuatrimestre_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> None:
    """Elimina un cuatrimestre (solo si no tiene materias). Solo admin."""
    require_admin(ctx)
    service = CohorteService(db)
    await service.eliminar_cuatrimestre(cuatrimestre_id)
