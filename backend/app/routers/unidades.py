# app/routers/unidades.py
"""
Unidades / config de dashboard router for Active-IA (Dashboard de Gestores).

ABM de unidades de una materia + config de dashboard (cuatrimestre, unidad_actual,
tope) + vínculo rúbrica→unidad. Solo ADMIN.

Ref: PLAN_DASHBOARD_GESTORES.md §8 (T3)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_admin
from app.models import Usuario
from app.schemas.unidad import (
    MateriaDashboardConfig,
    MateriaDashboardConfigResponse,
    MoodleSeccionesSugeridas,
    RubricaUnidadAssign,
    UnidadCreate,
    UnidadesSyncRequest,
    UnidadResponse,
    UnidadUpdate,
)
from app.services.unidad_service import UnidadService

router = APIRouter(tags=["unidades"])


@router.get(
    "/materias/{materia_id}/moodle-secciones",
    response_model=MoodleSeccionesSugeridas,
)
async def sugerir_secciones_moodle(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MoodleSeccionesSugeridas:
    """Trae las secciones del curso de Moodle con las cabeceras de unidad auto-detectadas.

    Alimenta el ABM de unidades (auto-detección + confirmación). Solo admin.
    """
    require_admin(current_user)
    service = UnidadService(db)
    return await service.sugerir_secciones_moodle(materia_id, current_user)


# ===================== Unidades (sub-recurso de materia) =====================


@router.get("/materias/{materia_id}/unidades", response_model=list[UnidadResponse])
async def listar_unidades(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UnidadResponse]:
    """Lista las unidades de una materia (ordenadas por número). Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    return await service.listar_unidades(materia_id)


@router.post(
    "/materias/{materia_id}/unidades",
    response_model=UnidadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_unidad(
    materia_id: int,
    data: UnidadCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnidadResponse:
    """Crea una unidad (numero y moodle_section_id únicos en la materia). Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    return await service.crear_unidad(materia_id, data)


@router.put("/unidades/{unidad_id}", response_model=UnidadResponse)
async def actualizar_unidad(
    unidad_id: int,
    data: UnidadUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnidadResponse:
    """Actualiza una unidad. Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    return await service.actualizar_unidad(unidad_id, data)


@router.put("/materias/{materia_id}/unidades/sync", response_model=list[UnidadResponse])
async def sincronizar_unidades(
    materia_id: int,
    data: UnidadesSyncRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UnidadResponse]:
    """Reemplaza las unidades de la materia por las secciones tildadas (numeradas por orden). Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    return await service.sincronizar_unidades(materia_id, data)


@router.delete("/unidades/{unidad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_unidad(
    unidad_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Elimina una unidad (desvincula sus rúbricas). Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    await service.eliminar_unidad(unidad_id)


# ===================== Config dashboard de la Materia =====================


@router.get(
    "/materias/{materia_id}/dashboard-config",
    response_model=MateriaDashboardConfigResponse,
)
async def get_dashboard_config(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriaDashboardConfigResponse:
    """Config actual de dashboard de la materia (cuatrimestre, unidad_actual, tope). Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    return await service.get_config_materia(materia_id)


@router.put(
    "/materias/{materia_id}/dashboard-config",
    response_model=MateriaDashboardConfigResponse,
)
async def set_dashboard_config(
    materia_id: int,
    data: MateriaDashboardConfig,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriaDashboardConfigResponse:
    """Setea cuatrimestre, unidad_actual y tope de la materia para el dashboard. Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    return await service.set_config_materia(materia_id, data)


# ===================== Vínculo Rúbrica → Unidad =====================


@router.patch("/rubricas/{rubrica_id}/unidad", status_code=status.HTTP_204_NO_CONTENT)
async def vincular_rubrica_unidad(
    rubrica_id: int,
    data: RubricaUnidadAssign,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Vincula (o desvincula con null) la unidad de una rúbrica. Solo admin."""
    require_admin(current_user)
    service = UnidadService(db)
    await service.vincular_rubrica_unidad(rubrica_id, data.unidad_id)
