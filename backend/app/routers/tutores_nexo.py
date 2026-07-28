# app/routers/tutores_nexo.py
"""
Router del ABM de Tutores Nexo (solo ADMIN). Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.4 (T7).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import require_admin
from app.models import Usuario
from app.schemas.tutor_nexo import (
    TutorNexoCreate,
    TutorNexoResponse,
    TutorNexoUpdate,
)
from app.services.tutor_nexo_service import TutorNexoService

router = APIRouter(prefix="/tutores-nexo", tags=["tutores-nexo"])


@router.get("/", response_model=list[TutorNexoResponse])
async def listar_tutores_nexo(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> list[TutorNexoResponse]:
    """Lista los tutores nexo. Solo admin."""
    require_admin(ctx)
    return await TutorNexoService(db).listar()


@router.post("/", response_model=TutorNexoResponse, status_code=status.HTTP_201_CREATED)
async def crear_tutor_nexo(
    data: TutorNexoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> TutorNexoResponse:
    """Crea un tutor nexo. Solo admin."""
    require_admin(ctx)
    return await TutorNexoService(db).crear(data, usuario_id=current_user.id)


@router.get("/{tutor_nexo_id}", response_model=TutorNexoResponse)
async def obtener_tutor_nexo(
    tutor_nexo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> TutorNexoResponse:
    """Obtiene un tutor nexo por ID. Solo admin."""
    require_admin(ctx)
    return await TutorNexoService(db).obtener(tutor_nexo_id)


@router.put("/{tutor_nexo_id}", response_model=TutorNexoResponse)
async def actualizar_tutor_nexo(
    tutor_nexo_id: int,
    data: TutorNexoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> TutorNexoResponse:
    """Actualiza un tutor nexo. Solo admin."""
    require_admin(ctx)
    return await TutorNexoService(db).actualizar(tutor_nexo_id, data)


@router.delete("/{tutor_nexo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_tutor_nexo(
    tutor_nexo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> None:
    """Elimina (soft) un tutor nexo. Solo admin."""
    require_admin(ctx)
    await TutorNexoService(db).eliminar(tutor_nexo_id)
