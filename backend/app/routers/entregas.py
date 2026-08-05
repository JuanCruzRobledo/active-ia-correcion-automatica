# app/routers/entregas.py
"""
Entregas router for Active-IA.

REST API endpoints for student submission (entrega) management.
Endpoints require authentication and appropriate authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
"""

import json
from datetime import date
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import (
    comisiones_visibles_para,
    filtrar_entregas_accesibles,
    verificar_acceso_comision_o_materia,
    verificar_acceso_entrega,
)
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
from app.services.moodle_url_parser import parsear_url_entrega

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
    search: str | None = Query(None, description="Buscar por nombre del alumno (parcial, case-insensitive)"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Items por página"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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

    **Authorization:** Admin ve todo. Tutor y coordinador ven solo las entregas
    de las comisiones a las que pertenecen (por asignación o por materia).
    """
    # SEC-002: con comisión explícita es un 403; SIN ella hay que FILTRAR, porque
    # el listado sin filtro devolvía entregas de todas las comisiones del sistema.
    if comision_id is not None:
        await verificar_acceso_comision_o_materia(db, current_user, ctx, comision_id)
        comisiones_visibles = None
    else:
        comisiones_visibles = await comisiones_visibles_para(db, current_user, ctx)

    service = EntregaService(db)
    return await service.listar_entregas(
        comision_id=comision_id,
        comisiones_visibles=comisiones_visibles,
        rubrica_id=rubrica_id,
        estado=estado.value if estado else None,
        include_archivadas=include_archivadas,
        solo_archivadas=solo_archivadas,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        search=search,
        page=page,
        per_page=per_page,
        universidad_id=ctx.universidad_id,
    )


@router.post("/", response_model=EntregaResponse, status_code=status.HTTP_201_CREATED)
async def crear_entrega(
    comision_id: int = Form(..., description="ID de la comisión"),
    rubrica_id: int = Form(..., description="ID de la rúbrica"),
    alumno_nombre: str = Form(..., description="Nombre del alumno"),
    sobrescribir: bool = Form(False, description="Sobrescribir entrega existente"),
    modo_consolidacion: str | None = Form(None, description="Modo de procesamiento. Si se omite, se usa el de la rúbrica"),
    extensiones_personalizadas: str | None = Form(None, description="JSON array de extensiones para modo personalizado"),
    moodle_url: str | None = Form(None, description="URL de la entrega en Moodle (para habilitar 'Subir a Moodle')"),
    archivo: UploadFile = File(..., description="Archivo ZIP o TXT"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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

    **Authorization:** Admin, tutor asignado a la comisión, o coordinador de su materia.
    """
    # SEC-002: el guard va ANTES de tocar el upload. Sin esto se podía crear
    # (y consolidar) una entrega en cualquier comisión ajena.
    await verificar_acceso_comision_o_materia(db, current_user, ctx, comision_id)

    # Parse custom extensions JSON if provided
    ext_list: list[str] | None = None
    if extensiones_personalizadas:
        try:
            ext_list = json.loads(extensiones_personalizadas)
        except (json.JSONDecodeError, ValueError):
            ext_list = None

    # URL de Moodle (item #4): extraemos el userid para habilitar "Subir a Moodle" en
    # entregas cargadas a mano. El cmid de la URL no se usa acá (lo aporta la rúbrica).
    moodle_user_id = parsear_url_entrega(moodle_url)["userid"] if moodle_url else None

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
        modo_consolidacion=modo_consolidacion.lower() if modo_consolidacion else None,
        extensiones_personalizadas=ext_list,
        moodle_user_id=moodle_user_id,
    )


@router.post("/masiva", response_model=CargaMasivaResponse, status_code=status.HTTP_201_CREATED)
async def crear_entregas_masivas(
    comision_id: int = Form(..., description="ID de la comisión"),
    rubrica_id: int = Form(..., description="ID de la rúbrica"),
    sobrescribir: bool = Form(False, description="Sobrescribir entregas existentes"),
    modo_consolidacion: str | None = Form(None, description="Modo de procesamiento. Si se omite, se usa el de la rúbrica"),
    extensiones_personalizadas: str | None = Form(None, description="JSON array de extensiones para modo personalizado"),
    archivo_zip: UploadFile = File(..., description="ZIP con carpetas de alumnos"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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

    **Authorization:** Admin, tutor asignado a la comisión, o coordinador de su materia.
    """
    # SEC-002: el guard va ANTES de descomprimir. Sin esto, un ZIP-bomb sobre
    # una comisión ajena era gratis (combinado con SEC-005).
    await verificar_acceso_comision_o_materia(db, current_user, ctx, comision_id)

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
        modo_consolidacion=modo_consolidacion.lower() if modo_consolidacion else None,
        extensiones_personalizadas=ext_list_masiva,
    )


@router.patch("/archivar", response_model=EntregaAccionMasivaResponse)
async def archivar_entregas(
    body: EntregaArchivarRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> EntregaAccionMasivaResponse:
    """
    Archive or unarchive multiple entregas.

    Archived entregas are hidden from the default list view and only appear
    when `include_archivadas=true` is passed (i.e., when estado filter is TODOS).

    **Body:**
    - `ids`: List of entrega IDs (1–100)
    - `archivado`: True to archive, False to unarchive

    **Authorization:** Admin, o tutor/coordinador de las entregas. El lote se aplica
    solo sobre las accesibles; las omitidas se informan en la respuesta.
    """
    # SEC-002: partición en UNA query. Se opera solo sobre lo accesible.
    permitidos, denegados = await filtrar_entregas_accesibles(db, current_user, ctx, body.ids)
    if not permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a ninguna de las entregas solicitadas",
        )

    service = EntregaService(db)
    resultado = await service.archivar_entregas(
        ids=sorted(permitidos), archivado=body.archivado
    )
    return resultado.model_copy(
        update={"omitidas": len(denegados), "ids_omitidos": sorted(denegados)}
    )


@router.delete("/masivo", response_model=EntregaAccionMasivaResponse)
async def eliminar_entregas_masivo(
    body: EntregaDeleteMasivoRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> EntregaAccionMasivaResponse:
    """
    Bulk delete multiple entregas permanently.

    **Body:**
    - `ids`: List of entrega IDs (1–100)

    **Authorization:** Admin, o tutor/coordinador de las entregas. El lote se aplica
    solo sobre las accesibles; las omitidas se informan en la respuesta.
    """
    # SEC-002 + CRUD-001: este borrado es FÍSICO e irreversible. La partición va
    # antes del service: el service nunca ve un ID que el usuario no pueda borrar.
    permitidos, denegados = await filtrar_entregas_accesibles(db, current_user, ctx, body.ids)
    if not permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a ninguna de las entregas solicitadas",
        )

    service = EntregaService(db)
    resultado = await service.eliminar_entregas_masivo(
        ids=sorted(permitidos), actor_id=current_user.id
    )
    return resultado.model_copy(
        update={"omitidas": len(denegados), "ids_omitidos": sorted(denegados)}
    )


@router.get("/{entrega_id}", response_model=EntregaDetailResponse)
async def obtener_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> EntregaDetailResponse:
    """
    Get an entrega by ID with full details.

    **Returns:**
    - Entrega data
    - Comision info (nombre, materia)
    - Rubrica info (nombre, tipo, numero)
    - Subido por info (nombre, email)
    - Number of previous versions in history

    **Authorization:** Admin, tutor asignado a la comisión, o coordinador de su materia.
    """
    await verificar_acceso_entrega(db, current_user, ctx, entrega_id)

    service = EntregaService(db)
    return await service.obtener_entrega(entrega_id, universidad_id=ctx.universidad_id)


@router.get("/{entrega_id}/contenido", response_model=ContenidoEntrega)
async def obtener_contenido_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
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

    **Authorization:** Admin, tutor asignado a la comisión, o coordinador de su materia.
    """
    # SEC-002: este endpoint devuelve el código fuente completo del alumno.
    # Era el peor filtrado de datos de los 20 endpoints.
    await verificar_acceso_entrega(db, current_user, ctx, entrega_id)

    service = EntregaService(db)
    return await service.obtener_contenido(entrega_id, universidad_id=ctx.universidad_id)


@router.delete("/{entrega_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> None:
    """
    Elimina una entrega.

    CRUD-001: por defecto es soft delete (deleted_at) — la entrega desaparece del
    listado pero es recuperable vía POST /{id}/restore y queda auditada. Solo si
    ALLOW_HARD_DELETE está activo el borrado es físico e irreversible (con cascada).

    **Authorization:** Admin, tutor asignado a la comisión, o coordinador de su materia.
    """
    # SEC-002 + CRUD-001: soft delete por defecto (recuperable + auditado);
    # físico solo si ALLOW_HARD_DELETE.
    await verificar_acceso_entrega(db, current_user, ctx, entrega_id)

    service = EntregaService(db)
    await service.eliminar_entrega(
        entrega_id, actor_id=current_user.id, universidad_id=ctx.universidad_id
    )


@router.post("/{entrega_id}/restore", response_model=EntregaDetailResponse)
async def restaurar_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> EntregaDetailResponse:
    """
    Restaura una entrega eliminada (soft delete): vuelve a aparecer con su corrección.

    **Authorization:** Admin, tutor asignado a la comisión, o coordinador de su materia.
    """
    # CRUD-001: verificar_acceso_entrega ve las entregas borradas (no filtra
    # deleted_at), así que sirve como guard del restore. Pertenencia, no solo-admin.
    await verificar_acceso_entrega(db, current_user, ctx, entrega_id)

    service = EntregaService(db)
    await service.restaurar_entrega(
        entrega_id, actor_id=current_user.id, universidad_id=ctx.universidad_id
    )
    return await service.obtener_entrega(entrega_id, universidad_id=ctx.universidad_id)
