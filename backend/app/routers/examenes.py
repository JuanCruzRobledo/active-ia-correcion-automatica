# app/routers/examenes.py
"""
Exámenes router — ABM de exámenes de una materia (Dashboard de Gestores).

CRUD incremental por examen (parciales/recuperatorios/extensiones/extraordinarias/
globales). Solo ADMIN. Gemelo del ABM de unidades.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import (
    require_coordinador_or_admin,
    verificar_acceso_examen,
    verificar_acceso_materia,
)
from app.models import Usuario
from app.schemas.examen import (
    ExamenMateriaCreate,
    ExamenMateriaResponse,
    ExamenMateriaUpdate,
)
from app.services.examen_service import ExamenService

router = APIRouter(tags=["examenes"])


@router.get("/materias/{materia_id}/examenes", response_model=list[ExamenMateriaResponse])
async def listar_examenes(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExamenMateriaResponse]:
    """Lista los exámenes de una materia. Admin o coordinador de la materia."""
    require_coordinador_or_admin(current_user)
    await verificar_acceso_materia(db, current_user, materia_id)
    return await ExamenService(db).listar(materia_id)


@router.post(
    "/materias/{materia_id}/examenes",
    response_model=ExamenMateriaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_examen(
    materia_id: int,
    data: ExamenMateriaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamenMateriaResponse:
    """Da de alta un examen (numeración automática). Admin o coordinador de la materia."""
    require_coordinador_or_admin(current_user)
    await verificar_acceso_materia(db, current_user, materia_id)
    return await ExamenService(db).crear(materia_id, data, usuario_id=current_user.id)


@router.put("/examenes/{examen_id}", response_model=ExamenMateriaResponse)
async def actualizar_examen(
    examen_id: int,
    data: ExamenMateriaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamenMateriaResponse:
    """Edita un examen. Admin o coordinador de la materia."""
    require_coordinador_or_admin(current_user)
    await verificar_acceso_examen(db, current_user, examen_id)
    return await ExamenService(db).actualizar(examen_id, data)


@router.delete("/examenes/{examen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_examen(
    examen_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Elimina un examen (y sus recuperatorios por cascade). Admin o coordinador de la materia."""
    require_coordinador_or_admin(current_user)
    await verificar_acceso_examen(db, current_user, examen_id)
    await ExamenService(db).eliminar(examen_id)
