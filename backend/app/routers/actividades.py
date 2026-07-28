# app/routers/actividades.py
"""
Actividad (Activity/Audit) router for Active-IA.

Endpoints for retrieving system activity logs (Admin only).

Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import require_admin
from app.models import Usuario
from app.models.enums import TipoActividadEnum
from app.schemas.actividad import ActividadListResponse
from app.services.actividad_service import ActividadService

router = APIRouter(prefix="/actividades", tags=["actividades"])


@router.get(
    "/recientes",
    response_model=ActividadListResponse,
    summary="Obtener actividades recientes",
)
async def get_actividades_recientes(
    limit: int = Query(10, ge=1, le=50, description="Número máximo de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    tipo: TipoActividadEnum | None = Query(None, description="Filtrar por tipo de actividad"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> ActividadListResponse:
    """
    Obtiene las actividades más recientes del sistema.

    Solo accesible para usuarios con rol ADMIN.

    Registra acciones importantes como:
    - Creación de usuarios (Admin, Coordinador, Tutor)
    - Creación de materias
    - Creación de comisiones
    - Creación de rúbricas
    """
    # Verificar que el usuario es admin
    require_admin(ctx)

    service = ActividadService(db)
    return await service.get_actividades_recientes(
        limit=limit, offset=offset, tipo=tipo
    )
