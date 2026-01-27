# app/routers/rubricas.py
"""
Rubricas router for Active-IA.

REST API endpoints for rubric (rubrica) management.
All endpoints require authentication and admin authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_admin
from app.models.enums import TipoRubricaEnum
from app.models.usuario import Usuario
from app.schemas.rubrica import (
    RubricaCreate,
    RubricaDetailResponse,
    RubricaDuplicar,
    RubricaList,
    RubricaResponse,
    RubricaUpdate,
)
from app.services.rubrica_service import RubricaService
from app.services.rubrica_ia_service import RubricaIAService

router = APIRouter(
    prefix="/rubricas",
    tags=["rubricas"],
)


@router.get("/", response_model=RubricaList)
async def listar_rubricas(
    materia_id: int | None = Query(None, description="Filtrar por materia"),
    tipo: TipoRubricaEnum | None = Query(None, description="Filtrar por tipo de rúbrica"),
    anio: int | None = Query(None, description="Filtrar por año académico"),
    include_inactive: bool = Query(False, description="Incluir rúbricas eliminadas"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Items por página"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricaList:
    """
    List all rubricas with optional filters and pagination.

    **Filters:**
    - `materia_id`: Filter by materia ID
    - `tipo`: Filter by rubrica type (TP, PARCIAL_1, etc.)
    - `anio`: Filter by academic year
    - `include_inactive`: Include soft-deleted rubricas

    **Pagination:**
    - `page`: Page number (1-indexed)
    - `per_page`: Items per page (max 100)

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = RubricaService(db)
    return await service.listar_rubricas(
        materia_id=materia_id,
        tipo=tipo.value if tipo else None,
        anio=anio,
        include_inactive=include_inactive,
        page=page,
        per_page=per_page,
    )


@router.post("/", response_model=RubricaResponse, status_code=status.HTTP_201_CREATED)
async def crear_rubrica(
    data: RubricaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricaResponse:
    """
    Create a new rubrica.

    **Required fields:**
    - `materia_id`: ID of the materia
    - `tipo`: Rubrica type (TP, PARCIAL_1, PARCIAL_2, etc.)
    - `nombre`: Rubrica name
    - `numero`: Rubrica number (e.g., 1 for TP1)
    - `anio`: Academic year
    - `criterios_json`: Criteria structure with puntaje_maximo=100

    **Validation:**
    - Materia must exist and be active
    - Combination of materia + tipo + numero + anio must be unique
    - Sum of criteria puntajes must equal 100
    - Criteria IDs must be unique

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = RubricaService(db)
    return await service.crear_rubrica(data)


@router.get("/{rubrica_id}", response_model=RubricaDetailResponse)
async def obtener_rubrica(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricaDetailResponse:
    """
    Get a rubrica by ID with full details.

    **Returns:**
    - Rubrica data
    - Materia info (codigo, nombre)
    - Number of associated entregas

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = RubricaService(db)
    return await service.obtener_rubrica(rubrica_id)


@router.put("/{rubrica_id}", response_model=RubricaResponse)
async def actualizar_rubrica(
    rubrica_id: int,
    data: RubricaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricaResponse:
    """
    Update an existing rubrica.

    **Updatable fields:**
    - `nombre`: Rubrica name
    - `criterios_json`: Criteria structure

    **Note:** materia_id, tipo, numero, and anio cannot be changed after creation.

    **Validation:**
    - If updating criterios_json, sum of puntajes must equal 100

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = RubricaService(db)
    return await service.actualizar_rubrica(rubrica_id, data)


@router.delete("/{rubrica_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_rubrica(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete a rubrica.

    The rubrica is marked as inactive (activa=False) but not physically deleted.
    Can be restored using the restore endpoint.

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = RubricaService(db)
    await service.eliminar_rubrica(rubrica_id)


@router.post("/{rubrica_id}/restore", response_model=RubricaResponse)
async def restaurar_rubrica(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricaResponse:
    """
    Restore a soft-deleted rubrica.

    Marks the rubrica as active (activa=True).

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = RubricaService(db)
    return await service.restaurar_rubrica(rubrica_id)


@router.post("/{rubrica_id}/duplicar", response_model=RubricaResponse, status_code=status.HTTP_201_CREATED)
async def duplicar_rubrica(
    rubrica_id: int,
    data: RubricaDuplicar,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricaResponse:
    """
    Duplicate a rubrica to a new year.

    Creates a copy of the rubrica with all its criteria for a different academic year.
    Useful for reusing rubrics across years.

    **Required:**
    - `nuevo_anio`: New academic year for the duplicate

    **Optional:**
    - `nuevo_nombre`: New name (if not provided, uses original name)

    **Validation:**
    - Original rubrica must exist
    - No rubrica with same materia+tipo+numero+nuevo_anio must exist

    **Authorization:** Admin only
    """
    require_admin(current_user)

    service = RubricaService(db)
    return await service.duplicar_rubrica(rubrica_id, data)


@router.post("/desde-pdf", status_code=status.HTTP_200_OK)
async def generar_rubrica_desde_pdf(
    pdf_file: UploadFile = File(..., description="Archivo PDF con la consigna del TP"),
    tipo_rubrica: str = Form("TP", description="Tipo de rúbrica (TP, PARCIAL_1, etc.)"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a rubrica from a PDF file using AI.

    **Process:**
    1. Validates user has Gemini API Key configured
    2. Validates PDF file (type and size)
    3. Sends PDF to N8N → Gemini for criteria extraction
    4. Returns suggested rubrica structure for review

    **Required:**
    - `pdf_file`: PDF file with assignment description (max 10MB)

    **Optional:**
    - `tipo_rubrica`: Type of rubrica (default: TP)

    **Returns:**
    - `nombre_sugerido`: Suggested name for the rubrica
    - `descripcion`: Brief description extracted from PDF
    - `puntaje_maximo`: Always 100
    - `criterios`: List of evaluation criteria with:
      - `nombre`: Criterion name
      - `descripcion`: Criterion description
      - `puntaje_maximo`: Points for this criterion

    **Next steps:**
    - Coordinator reviews and edits criteria if needed
    - Creates rubrica using POST /rubricas endpoint with the criteria

    **Validation:**
    - User must have Gemini API Key configured
    - File must be PDF format
    - File size must be ≤ 10MB
    - Sum of criteria puntajes will be validated to equal 100 (±5 tolerance)

    **Authorization:** Admin only (Coordinador in future)

    **Ref:** docs/specs/03-REQUISITOS-FUNCIONALES.md HU-RUB-02
    """
    require_admin(current_user)

    # Validate API Key is configured
    if not current_user.api_key_encrypted:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil antes de generar rúbricas con IA",
        )

    # Use RubricaIAService to generate rubrica
    ia_service = RubricaIAService()
    rubrica_data = await ia_service.generar_rubrica_desde_pdf(
        pdf_file=pdf_file,
        api_key_encrypted=current_user.api_key_encrypted,
        tipo_rubrica=tipo_rubrica,
    )

    return rubrica_data
