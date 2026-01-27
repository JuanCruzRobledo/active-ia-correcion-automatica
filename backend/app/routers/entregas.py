# app/routers/entregas.py
"""
Entregas router for Active-IA.

REST API endpoints for student submission (entrega) management.
Endpoints require authentication and appropriate authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_admin
from app.models.enums import EstadoEntregaEnum
from app.models.usuario import Usuario
from app.schemas.entrega import (
    EntregaCreate,
    EntregaDetailResponse,
    EntregaList,
    EntregaResponse,
)
from app.services.entrega_service import EntregaService

router = APIRouter(
    prefix="/entregas",
    tags=["entregas"],
)


@router.get("/", response_model=EntregaList)
async def listar_entregas(
    comision_id: int | None = Query(None, description="Filtrar por comisión"),
    rubrica_id: int | None = Query(None, description="Filtrar por rúbrica"),
    estado: EstadoEntregaEnum | None = Query(None, description="Filtrar por estado"),
    include_inactive: bool = Query(False, description="Incluir entregas eliminadas"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Items por página"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntregaList:
    """
    List all entregas with optional filters and pagination.

    **Filters:**
    - `comision_id`: Filter by comision ID
    - `rubrica_id`: Filter by rubrica ID
    - `estado`: Filter by estado (SUBIDA, PENDIENTE, CORREGIDA, ERROR)
    - `include_inactive`: Include soft-deleted entregas

    **Pagination:**
    - `page`: Page number (1-indexed)
    - `per_page`: Items per page (max 100)

    **Authorization:** Admin only (for now)
    """
    require_admin(current_user)

    service = EntregaService(db)
    return await service.listar_entregas(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
        estado=estado.value if estado else None,
        include_inactive=include_inactive,
        page=page,
        per_page=per_page,
    )


@router.post("/", response_model=EntregaResponse, status_code=status.HTTP_201_CREATED)
async def crear_entrega(
    comision_id: int = Form(..., description="ID de la comisión"),
    rubrica_id: int = Form(..., description="ID de la rúbrica"),
    alumno_nombre: str = Form(..., description="Nombre del alumno"),
    sobrescribir: bool = Form(False, description="Sobrescribir entrega existente"),
    archivo: UploadFile = File(..., description="Archivo ZIP o TXT"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntregaResponse:
    """
    Create a new entrega (individual upload).

    **Required fields:**
    - `comision_id`: ID of the comision
    - `rubrica_id`: ID of the rubrica
    - `alumno_nombre`: Student's full name
    - `archivo`: ZIP or TXT file

    **Optional:**
    - `sobrescribir`: If True, overwrites existing entrega (saves to history)

    **Validation:**
    - Comision and Rubrica must exist and be active
    - File must be ZIP or TXT
    - If entrega exists and sobrescribir=False, returns 409 Conflict

    **Authorization:** Admin only (for now)
    """
    require_admin(current_user)

    # Build EntregaCreate schema
    data = EntregaCreate(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
        alumno_nombre=alumno_nombre,
    )

    service = EntregaService(db)
    return await service.crear_entrega_individual(
        data=data,
        archivo=archivo,
        subido_por_id=current_user.id,
        sobrescribir=sobrescribir,
    )


@router.get("/{entrega_id}", response_model=EntregaDetailResponse)
async def obtener_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntregaDetailResponse:
    """
    Get an entrega by ID with full details.

    **Returns:**
    - Entrega data
    - Comision info (nombre, materia)
    - Rubrica info (nombre, tipo, numero)
    - Subido por info (nombre, email)
    - Number of previous versions in history

    **Authorization:** Admin only (for now)
    """
    require_admin(current_user)

    service = EntregaService(db)
    return await service.obtener_entrega(entrega_id)


@router.delete("/{entrega_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete an entrega.

    The entrega is marked as inactive (activo=False) but not physically deleted.

    **Authorization:** Admin only (for now)
    """
    require_admin(current_user)

    service = EntregaService(db)
    await service.eliminar_entrega(entrega_id)
