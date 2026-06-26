# app/routers/comisiones.py
"""
Comisiones router for Active-IA.

REST API endpoints for commission (comision) management.
All endpoints require authentication and admin/coordinator authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 5
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import (
    require_admin,
    verificar_acceso_materia,
    verificar_acceso_materia_de_comision,
)
from app.models.enums import RolEnum
from app.models.usuario import Usuario
from app.schemas.comision import (
    ComisionCreate,
    ComisionDetailResponse,
    ComisionList,
    ComisionMoodleUpdate,
    ComisionResponse,
    ComisionUpdate,
    TutoresAssign,
    TutoresResponse,
)
from app.services.comision_service import ComisionService

router = APIRouter(
    prefix="/comisiones",
    tags=["comisiones"],
)


@router.get("/", response_model=ComisionList)
async def listar_comisiones(
    materia_id: int | None = Query(None, description="Filtrar por materia"),
    anio: int | None = Query(None, description="Filtrar por año académico"),
    include_inactive: bool = Query(False, description="Incluir comisiones eliminadas"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Items por página"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComisionList:
    """
    List all comisiones with optional filters and pagination.

    **Filters:**
    - `materia_id`: Filter by materia ID
    - `anio`: Filter by academic year
    - `include_inactive`: Include soft-deleted comisiones

    **Pagination:**
    - `page`: Page number (1-indexed)
    - `per_page`: Items per page (max 100)

    **Authorization:** All roles. Tutors see only their assigned comisiones;
    coordinadores and admins see all.
    """
    tutor_id = current_user.id if current_user.rol == RolEnum.TUTOR else None
    coordinador_id = current_user.id if current_user.rol == RolEnum.COORDINADOR else None

    service = ComisionService(db)
    return await service.listar_comisiones(
        materia_id=materia_id,
        tutor_id=tutor_id,
        coordinador_id=coordinador_id,
        anio=anio,
        include_inactive=include_inactive,
        page=page,
        per_page=per_page,
    )


@router.post("/", response_model=ComisionDetailResponse, status_code=status.HTTP_201_CREATED)
async def crear_comision(
    data: ComisionCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComisionDetailResponse:
    """
    Create a new comision with optional tutor assignments.

    **Required fields:**
    - `materia_id`: ID of the materia
    - `nombre`: Comision name (e.g., "Comisión A")
    - `anio`: Academic year (e.g., 2026)

    **Optional fields:**
    - `tutor_ids`: List of user IDs to assign as tutors

    **Validation:**
    - Materia must exist and be active
    - Combination of materia + nombre + anio must be unique
    - All tutors must exist, be active, and have TUTOR role

    **Returns:** Comision with materia info and assigned tutores

    **Authorization:** Admin (cualquier materia) o Coordinador asignado a la materia.
    """
    # Admin: cualquier materia. Coordinador: solo las que tiene asignadas (403 si no).
    # Cualquier otro rol: 403.
    await verificar_acceso_materia(db, current_user, data.materia_id)

    service = ComisionService(db)
    return await service.crear_comision(data, current_user_id=current_user.id)


@router.get("/{comision_id}", response_model=ComisionDetailResponse)
async def obtener_comision(
    comision_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComisionDetailResponse:
    """
    Get a comision by ID with full details.

    **Returns:**
    - Comision data
    - Materia info (codigo, nombre)
    - List of assigned tutores with assignment dates

    **Authorization:** Admin, coordinador, or tutor assigned to this comision.
    """
    service = ComisionService(db)

    if current_user.rol == RolEnum.TUTOR:
        if not await service.tutor_esta_asignado(current_user.id, comision_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No estás asignado a esta comisión",
            )

    return await service.obtener_comision(comision_id)


@router.patch("/{comision_id}/moodle", response_model=ComisionDetailResponse)
async def actualizar_moodle_comision(
    comision_id: int,
    data: ComisionMoodleUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComisionDetailResponse:
    """
    Update only the Moodle configuration of a comision.

    **Updatable fields:** `moodle_group_id`, `moodle_group_code`.

    **Authorization:** Admin, or tutor assigned to this comision.
    Tutors can keep Moodle config in sync without admin intervention so the
    pendientes panel works for their own assigned comisiones.
    """
    service = ComisionService(db)

    if current_user.rol == RolEnum.TUTOR:
        if not await service.tutor_esta_asignado(current_user.id, comision_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No estás asignado a esta comisión",
            )
    elif current_user.rol != RolEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permisos para modificar esta comisión",
        )

    return await service.actualizar_moodle_config(comision_id, data)


@router.put("/{comision_id}", response_model=ComisionDetailResponse)
async def actualizar_comision(
    comision_id: int,
    data: ComisionUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComisionDetailResponse:
    """
    Update an existing comision with optional tutor reassignment.

    **Updatable fields:**
    - `nombre`: Comision name
    - `tutor_ids`: List of user IDs to assign as tutors (replaces existing assignments)

    **Note:** materia_id and anio cannot be changed after creation.

    **Validation:**
    - New nombre must not conflict with existing comision for same materia+anio
    - All tutors must exist, be active, and have TUTOR role

    **Returns:** Updated comision with materia info and assigned tutores

    **Authorization:** Admin (cualquiera) o Coordinador de la materia de la comisión.
    """
    await verificar_acceso_materia_de_comision(db, current_user, comision_id)

    service = ComisionService(db)
    return await service.actualizar_comision(comision_id, data)


@router.delete("/{comision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_comision(
    comision_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete a comision.

    The comision is marked as inactive (activa=False) but not physically deleted.
    Can be restored using the restore endpoint.

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = ComisionService(db)
    await service.eliminar_comision(comision_id)


@router.post("/{comision_id}/restore", response_model=ComisionResponse)
async def restaurar_comision(
    comision_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComisionResponse:
    """
    Restore a soft-deleted comision.

    Marks the comision as active (activa=True).

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = ComisionService(db)
    return await service.restaurar_comision(comision_id)


@router.post("/{comision_id}/tutores", response_model=TutoresResponse)
async def asignar_tutores(
    comision_id: int,
    data: TutoresAssign,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TutoresResponse:
    """
    Assign tutors to a comision.

    **Replaces all existing tutor assignments** with the new list.

    **Required:**
    - `tutor_ids`: List of user IDs to assign as tutors (minimum 1)

    **Validation:**
    - All users must exist and be active
    - All users must have TUTOR role
    - Comision must exist and be active

    **Authorization:** Admin (cualquiera) o Coordinador de la materia de la comisión.
    """
    await verificar_acceso_materia_de_comision(db, current_user, comision_id)

    service = ComisionService(db)
    return await service.asignar_tutores(comision_id, data)
