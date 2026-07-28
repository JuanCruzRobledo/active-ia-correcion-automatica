"""
Dashboard router - Endpoints for dashboard statistics.

Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard designs
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import require_admin, require_coordinador, require_tutor
from app.models import Usuario
from app.schemas.dashboard import (
    AdminStatsResponse,
    CoordinadorStatsResponse,
    TutorStatsResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
):
    """
    Get admin dashboard statistics.

    Returns counts of:
    - Active materias
    - Active comisiones
    - Active usuarios
    - Active rubricas

    **Permissions**: Admin only
    """
    require_admin(ctx)
    return await DashboardService.get_admin_stats(db, universidad_id=ctx.universidad_id)


@router.get("/coordinador/stats", response_model=CoordinadorStatsResponse)
async def get_coordinador_stats(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
):
    """
    Get coordinador dashboard statistics.

    Returns:
    - Number of comisiones in coordinador's materias
    - Number of rubricas for coordinador's materias
    - Number of pending entregas
    - Progress of corrections per comision

    **Permissions**: Coordinador only
    """
    require_coordinador(ctx)
    return await DashboardService.get_coordinador_stats(
        db, current_user.id, universidad_id=ctx.universidad_id
    )


@router.get("/tutor/stats", response_model=TutorStatsResponse)
async def get_tutor_stats(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
):
    """
    Get tutor dashboard statistics.

    Returns:
    - Number of comisiones assigned to tutor
    - Number of pending entregas
    - Number of corrected entregas
    - Details of each comision

    **Permissions**: Tutor only
    """
    require_tutor(ctx)
    return await DashboardService.get_tutor_stats(
        db, current_user.id, universidad_id=ctx.universidad_id
    )
