# app/routers/entregas.py
"""
Entregas router for Active-IA.

REST API endpoints for student submission (entrega) management.
Endpoints require authentication and appropriate authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
"""

import json
from datetime import date
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_any_authenticated
from app.models.enums import EstadoEntregaEnum
from app.models.usuario import Usuario
from app.schemas.entrega import (
    CargaMasivaResponse,
    ContenidoEntrega,
    EntregaAccionMasivaResponse,
    EntregaArchivarRequest,
    EntregaCreate,
    EntregaDeleteMasivoRequest,
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
    include_archivadas: bool = Query(False, description="Incluir entregas archivadas"),
    solo_archivadas: bool = Query(False, description="Mostrar solo entregas archivadas"),
    fecha_desde: date | None = Query(None, description="Filtrar desde esta fecha (YYYY-MM-DD, inclusive)"),
    fecha_hasta: date | None = Query(None, description="Filtrar hasta esta fecha (YYYY-MM-DD, inclusive)"),
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
    - `include_archivadas`: If true, include archived entregas (default: false)
    - `solo_archivadas`: If true, show only archived entregas
    - `fecha_desde`: Show entregas from this date (YYYY-MM-DD)
    - `fecha_hasta`: Show entregas up to this date (YYYY-MM-DD)

    **Pagination:**
    - `page`: Page number (1-indexed)
    - `per_page`: Items per page (max 100)

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    service = EntregaService(db)
    return await service.listar_entregas(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
        estado=estado.value if estado else None,
        include_archivadas=include_archivadas,
        solo_archivadas=solo_archivadas,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        page=page,
        per_page=per_page,
    )


@router.post("/", response_model=EntregaResponse, status_code=status.HTTP_201_CREATED)
async def crear_entrega(
    comision_id: int = Form(..., description="ID de la comisión"),
    rubrica_id: int = Form(..., description="ID de la rúbrica"),
    alumno_nombre: str = Form(..., description="Nombre del alumno"),
    sobrescribir: bool = Form(False, description="Sobrescribir entrega existente"),
    modo_consolidacion: str = Form("solo_codigo", description="Modo de procesamiento"),
    extensiones_personalizadas: str | None = Form(None, description="JSON array de extensiones para modo personalizado"),
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
    - `extensiones_personalizadas`: JSON array of extensions for 'personalizado' mode

    **Validation:**
    - Comision and Rubrica must exist and be active
    - File must be ZIP or TXT
    - If entrega exists and sobrescribir=False, returns 409 Conflict

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    # Parse custom extensions JSON if provided
    ext_list: list[str] | None = None
    if extensiones_personalizadas:
        try:
            ext_list = json.loads(extensiones_personalizadas)
        except (json.JSONDecodeError, ValueError):
            ext_list = None

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
        modo_consolidacion=modo_consolidacion.lower(),
        extensiones_personalizadas=ext_list,
    )


@router.post("/masiva", response_model=CargaMasivaResponse, status_code=status.HTTP_201_CREATED)
async def crear_entregas_masivas(
    comision_id: int = Form(..., description="ID de la comisión"),
    rubrica_id: int = Form(..., description="ID de la rúbrica"),
    sobrescribir: bool = Form(False, description="Sobrescribir entregas existentes"),
    modo_consolidacion: str = Form("solo_codigo", description="Modo de procesamiento"),
    extensiones_personalizadas: str | None = Form(None, description="JSON array de extensiones para modo personalizado"),
    archivo_zip: UploadFile = File(..., description="ZIP con carpetas de alumnos"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CargaMasivaResponse:
    """
    Create multiple entregas from a ZIP file (bulk upload).

    **Expected ZIP structure:**
    ```
    entregas.zip
    ├── perez_juan/
    │   └── proyecto.zip (or loose files)
    ├── gonzalez_maria/
    │   └── proyecto.zip (or loose files)
    └── rodriguez_carlos/
        └── proyecto.zip (or loose files)
    ```

    The folder name is used as the student's name (underscores replaced with spaces).

    **Required fields:**
    - `comision_id`: ID of the comision
    - `rubrica_id`: ID of the rubrica
    - `archivo_zip`: ZIP file with student folders

    **Optional:**
    - `sobrescribir`: If True, overwrites existing entregas (saves to history)
    - `modo_consolidacion`: Processing mode (solo_codigo, web_completo, etc.)

    **Response:**
    - Summary with total processed, successful, and errors
    - List of successful entregas with IDs
    - List of errors with details

    **Validation:**
    - Comision and Rubrica must exist and be active
    - File must be a valid ZIP
    - ZIP must contain at least one student folder

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    # Parse custom extensions JSON if provided
    ext_list_masiva: list[str] | None = None
    if extensiones_personalizadas:
        try:
            ext_list_masiva = json.loads(extensiones_personalizadas)
        except (json.JSONDecodeError, ValueError):
            ext_list_masiva = None

    service = EntregaService(db)
    return await service.crear_entrega_masiva(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
        archivo_zip=archivo_zip,
        subido_por_id=current_user.id,
        sobrescribir=sobrescribir,
        modo_consolidacion=modo_consolidacion.lower(),
        extensiones_personalizadas=ext_list_masiva,
    )


@router.patch("/archivar", response_model=EntregaAccionMasivaResponse)
async def archivar_entregas(
    body: EntregaArchivarRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntregaAccionMasivaResponse:
    """
    Archive or unarchive multiple entregas.

    Archived entregas are hidden from the default list view and only appear
    when `include_archivadas=true` is passed (i.e., when estado filter is TODOS).

    **Body:**
    - `ids`: List of entrega IDs (1–100)
    - `archivado`: True to archive, False to unarchive

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    service = EntregaService(db)
    return await service.archivar_entregas(ids=body.ids, archivado=body.archivado)


@router.delete("/masivo", response_model=EntregaAccionMasivaResponse)
async def eliminar_entregas_masivo(
    body: EntregaDeleteMasivoRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntregaAccionMasivaResponse:
    """
    Bulk delete multiple entregas permanently.

    **Body:**
    - `ids`: List of entrega IDs (1–100)

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    service = EntregaService(db)
    return await service.eliminar_entregas_masivo(ids=body.ids)


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

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    service = EntregaService(db)
    return await service.obtener_entrega(entrega_id)


@router.get("/{entrega_id}/contenido", response_model=ContenidoEntrega)
async def obtener_contenido_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContenidoEntrega:
    """
    Get the full consolidated content of an entrega.

    **Returns:**
    - Full code content (consolidated from ZIP or TXT)
    - List of files included in consolidation
    - Alumno name and entrega ID

    **Use case:**
    - View student's submitted code in the UI
    - Review code before/during correction

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    service = EntregaService(db)
    return await service.obtener_contenido(entrega_id)


@router.delete("/{entrega_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an entrega permanently.

    The entrega is physically deleted from the database.

    **Authorization:** Any authenticated user (Admin, Coordinador, Tutor)
    """
    require_any_authenticated(current_user)

    service = EntregaService(db)
    await service.eliminar_entrega(entrega_id)
