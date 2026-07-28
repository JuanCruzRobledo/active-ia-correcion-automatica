# app/routers/rubricas.py
"""
Rubricas router for Active-IA.

REST API endpoints for rubric (rubrica) management.
All endpoints require authentication and admin authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import require_admin, require_any_authenticated, require_coordinador_or_admin
from app.models.enums import RolEnum, TipoRubricaEnum
from app.models.usuario import Usuario
from app.schemas.rubrica import (
    RubricaCreate,
    RubricaDetailResponse,
    RubricaDuplicar,
    RubricaList,
    RubricaPDFPreview,
    RubricaResponse,
    RubricaUpdate,
)
from app.services.rubrica_service import RubricaService
from app.services.rubrica_ia_service import RubricaIAService
from app.services.pdf_service import PDFService

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
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)
    coordinador_id = current_user.id if ctx.rol == RolEnum.COORDINADOR else None

    service = RubricaService(db)
    return await service.listar_rubricas(
        materia_id=materia_id,
        tipo=tipo.value if tipo else None,
        coordinador_id=coordinador_id,
        anio=anio,
        include_inactive=include_inactive,
        page=page,
        per_page=per_page,
        universidad_id=ctx.universidad_id,
    )


@router.post("/", response_model=RubricaResponse, status_code=status.HTTP_201_CREATED)
async def crear_rubrica(
    data: RubricaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> RubricaResponse:
    """
    Create a new rubrica V2.

    **Required fields:**
    - `materia_id`: ID of the materia
    - `tipo`: Rubrica type (TP, PARCIAL_1, PARCIAL_2, etc.)
    - `titulo`: Rubrica title (e.g., "TP2 - API REST de Productos")
    - `descripcion`: Detailed description
    - `numero`: Rubrica number (e.g., 1 for TP1)
    - `anio`: Academic year
    - `criterios_json`: Array of criterios (Criterio → Subcriterio → Evidencias)
    - `metadata_json`: Flexible metadata (optional)
    - `penalizaciones_json`: Penalizaciones (optional)
    - `condiciones_desaprobacion_json`: Condiciones de desaprobación (optional)

    **Validation:**
    - Materia must exist and be active
    - Combination of materia + tipo + numero + anio must be unique
    - Sum of criteria pesos must equal 100
    - Criteria IDs must be unique
    - Each criterio must have at least one subcriterio
    - Each subcriterio must have at least one evidencia

    **Authorization:** Admin only
    """
    require_coordinador_or_admin(ctx)

    service = RubricaService(db)
    return await service.crear_rubrica(
    data,
    current_user=current_user,
    current_user_id=current_user.id,
    universidad_id=ctx.universidad_id,
    rol=ctx.rol,
)


@router.get("/{rubrica_id}", response_model=RubricaDetailResponse)
async def obtener_rubrica(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> RubricaDetailResponse:
    """
    Get a rubrica by ID with full details.

    **Returns:**
    - Rubrica data
    - Materia info (codigo, nombre)
    - Number of associated entregas

    **Authorization:** Admin only
    """
    require_coordinador_or_admin(ctx)

    service = RubricaService(db)
    return await service.obtener_rubrica(
    rubrica_id,
    current_user=current_user,
    universidad_id=ctx.universidad_id,
    rol=ctx.rol,
)


@router.put("/{rubrica_id}", response_model=RubricaResponse)
async def actualizar_rubrica(
    rubrica_id: int,
    data: RubricaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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
    require_coordinador_or_admin(ctx)

    service = RubricaService(db)
    return await service.actualizar_rubrica(
    rubrica_id,
    data,
    current_user=current_user,
    universidad_id=ctx.universidad_id,
    rol=ctx.rol,
)


@router.delete("/{rubrica_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_rubrica(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> None:
    """
    Soft delete a rubrica.

    The rubrica is marked as inactive (activa=False) but not physically deleted.
    Can be restored using the restore endpoint.

    **Authorization:** Admin only
    """
    require_coordinador_or_admin(ctx)

    service = RubricaService(db)
    await service.eliminar_rubrica(
    rubrica_id,
    current_user=current_user,
    universidad_id=ctx.universidad_id,
    rol=ctx.rol,
)


@router.post("/{rubrica_id}/restore", response_model=RubricaResponse)
async def restaurar_rubrica(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> RubricaResponse:
    """
    Restore a soft-deleted rubrica.

    Marks the rubrica as active (activa=True).

    **Authorization:** Admin only
    """
    require_coordinador_or_admin(ctx)

    service = RubricaService(db)
    return await service.restaurar_rubrica(
    rubrica_id,
    current_user=current_user,
    universidad_id=ctx.universidad_id,
    rol=ctx.rol,
)


@router.post("/{rubrica_id}/duplicar", response_model=RubricaResponse, status_code=status.HTTP_201_CREATED)
async def duplicar_rubrica(
    rubrica_id: int,
    data: RubricaDuplicar,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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
    require_coordinador_or_admin(ctx)

    service = RubricaService(db)
    return await service.duplicar_rubrica(
    rubrica_id,
    data,
    current_user=current_user,
    universidad_id=ctx.universidad_id,
    rol=ctx.rol,
)


@router.get("/{rubrica_id}/pdf/resumido")
async def descargar_rubrica_pdf_resumido(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Download a rubrica as Student Guide PDF.

    Generates a student-friendly version showing:
    - General info (subject, type, year, maximum score)
    - Detailed criteria with ID, name, weight, description and subcriteria
    - Penalties and fail conditions

    This version is optimized for students to understand evaluation criteria.

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)

    **Returns:** PDF file as application/pdf
    """
    require_any_authenticated(current_user)

    pdf_service = PDFService(db)
    pdf_bytes = await pdf_service.generar_pdf_rubrica_resumido(rubrica_id)

    # Get rubrica for filename
    rubrica_service = RubricaService(db)
    rubrica = await rubrica_service.obtener_rubrica(rubrica_id)

    # Build filename (sanitize to ASCII-safe characters)
    import re
    import unicodedata

    codigo_safe = unicodedata.normalize('NFKD', rubrica.materia.codigo).encode('ascii', 'ignore').decode('ascii')
    codigo_safe = re.sub(r'[^\w-]', '', codigo_safe)
    filename = f"{codigo_safe}_{rubrica.tipo.value}{rubrica.numero}_{rubrica.anio}_Guia_Estudiantes.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/{rubrica_id}/pdf")
async def descargar_rubrica_pdf(
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Download a rubrica as PDF.

    Generates a professional PDF document with the complete rubrica structure
    including criteria, subcriteria, evidences, penalties, and fail conditions.

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)

    **Returns:** PDF file as application/pdf
    """
    require_any_authenticated(current_user)

    pdf_service = PDFService(db)
    pdf_bytes = await pdf_service.generar_pdf_rubrica(rubrica_id)

    # Get rubrica for filename
    rubrica_service = RubricaService(db)
    rubrica = await rubrica_service.obtener_rubrica(rubrica_id)

    # Build filename (sanitize to ASCII-safe characters)
    import re
    import unicodedata

    # Sanitize codigo in case it has unicode
    codigo_safe = unicodedata.normalize('NFKD', rubrica.materia.codigo).encode('ascii', 'ignore').decode('ascii')
    codigo_safe = re.sub(r'[^\w-]', '', codigo_safe)
    filename = f"{codigo_safe}_{rubrica.tipo.value}{rubrica.numero}_{rubrica.anio}_Rubrica.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/preview-pdf/resumido")
async def preview_rubrica_pdf_resumido(
    data: RubricaPDFPreview,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Generate a Student Guide preview PDF for a rubrica from form data.

    This endpoint generates a student-friendly PDF without saving to database.
    Useful for previewing the guide before creating the rubrica.

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)

    **Returns:** PDF file as application/pdf
    """
    require_any_authenticated(current_user)

    pdf_service = PDFService(db)
    pdf_bytes = pdf_service.generar_pdf_rubrica_resumido_preview(data.model_dump())

    # Build filename for preview (sanitize to ASCII-safe characters)
    import re
    import unicodedata

    titulo_ascii = unicodedata.normalize('NFKD', data.titulo).encode('ascii', 'ignore').decode('ascii')
    titulo_safe = re.sub(r'[^\w\s-]', '', titulo_ascii)
    titulo_safe = titulo_safe.replace(' ', '_')[:50]
    filename = f"{titulo_safe}_Guia_Estudiantes_Preview.pdf" if titulo_safe else "Guia_Estudiantes_Preview.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.post("/preview-pdf")
async def preview_rubrica_pdf(
    data: RubricaPDFPreview,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Generate a preview PDF for a rubrica from form data.

    This endpoint generates a PDF without saving the rubrica to the database.
    Useful for previewing how the rubrica will look before creating/editing it.

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)

    **Returns:** PDF file as application/pdf
    """
    require_any_authenticated(current_user)

    pdf_service = PDFService(db)
    pdf_bytes = pdf_service.generar_pdf_rubrica_preview(data.model_dump())

    # Build filename for preview (sanitize to ASCII-safe characters)
    import re
    import unicodedata

    # Normalize unicode characters to ASCII equivalents
    titulo_ascii = unicodedata.normalize('NFKD', data.titulo).encode('ascii', 'ignore').decode('ascii')
    # Remove any remaining problematic characters
    titulo_safe = re.sub(r'[^\w\s-]', '', titulo_ascii)
    # Replace spaces with underscores and limit length
    titulo_safe = titulo_safe.replace(' ', '_')[:50]
    filename = f"{titulo_safe}_Preview.pdf" if titulo_safe else "Rubrica_Preview.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.post("/desde-pdf", status_code=status.HTTP_200_OK)
async def generar_rubrica_desde_pdf(
    pdf_file: UploadFile = File(..., description="Archivo PDF con la consigna del TP"),
    tipo_rubrica: str = Form("TP", description="Tipo de rúbrica (TP, PARCIAL_1, etc.)"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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
    require_coordinador_or_admin(ctx)

    # Validate API Key is configured
    if not current_user.gemini_api_key_encrypted:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil antes de generar rúbricas con IA",
        )

    # Use RubricaIAService to generate rubrica
    ia_service = RubricaIAService(db)
    rubrica_data = await ia_service.generar_rubrica_desde_pdf(
        pdf_file=pdf_file,
        api_key_encrypted=current_user.gemini_api_key_encrypted,
        usuario=current_user,
        tipo_rubrica=tipo_rubrica,
    )

    return rubrica_data
