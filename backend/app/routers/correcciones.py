# app/routers/correcciones.py
"""
Correcciones router for Active-IA.

REST API endpoints for AI-powered correction management.
Endpoints require authentication and tutor/admin authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 8
Ref: skills/correccion-ia/SKILL.md
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_any_authenticated
from app.models.usuario import Usuario
from app.schemas.moodle_grade import (
    PreviewCorreccionMoodleResponse,
    SubirCorreccionMoodleRequest,
    SubirCorreccionMoodleResponse,
)
from app.services.moodle_grade_service import MoodleGradeService
from app.schemas.correccion import (
    CorreccionResponse,
    CorreccionUpdate,
    CorregirGlobalAceptadoResponse,
    CorregirLoteAceptadoResponse,
    CorregirLoteRequest,
    CorregirLoteResponse,
    ProgresoGlobalResponse,
)
from app.repositories.entrega_repository import EntregaRepository
from app.services.correccion_service import (
    CorreccionService,
    procesar_global_background,
    procesar_lote_background,
)

# Límite de seguridad para la corrección masiva global (evita encolar miles de una).
GLOBAL_BATCH_MAX = 200

router = APIRouter(
    prefix="/correcciones",
    tags=["correcciones"],
)


@router.post(
    "/entregas/{entrega_id}/corregir",
    response_model=CorreccionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def corregir_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorreccionResponse:
    """
    Correct a single entrega using AI.

    **Process:**
    1. Validates that user has Gemini API Key configured
    2. Gets entrega and rubrica
    3. Sends to N8N → Gemini for evaluation
    4. Parses and validates AI response
    5. Saves correction to database
    6. Updates entrega state to CORREGIDA

    **States:**
    - Entrega goes from SUBIDA → PENDIENTE → CORREGIDA
    - On error: PENDIENTE → ERROR

    **Timeout:** 90 seconds (configurable in N8N)

    **Authorization:** Tutor or Admin with API Key configured
    """
    require_any_authenticated(current_user)

    # Validate API Key is configured
    if not current_user.gemini_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil antes de corregir",
        )

    service = CorreccionService(db)
    return await service.corregir_individual(
        entrega_id=entrega_id,
        api_key_encrypted=current_user.gemini_api_key_encrypted,
        corregido_por_id=current_user.id,
    )


@router.post(
    "/entregas/{entrega_id}/recorregir",
    response_model=CorreccionResponse,
)
async def recorregir_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorreccionResponse:
    """
    Re-correct an entrega (replaces existing correction).

    **Use cases:**
    - Rubrica was updated
    - Previous correction had errors
    - Want fresh evaluation

    **Behavior:**
    - Deletes existing correction (hard delete)
    - Generates new correction from scratch
    - Entrega goes through PENDIENTE → CORREGIDA again

    **Authorization:** Tutor or Admin with API Key configured
    """
    require_any_authenticated(current_user)

    if not current_user.gemini_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil",
        )

    service = CorreccionService(db)
    return await service.recorregir(
        entrega_id=entrega_id,
        api_key_encrypted=current_user.gemini_api_key_encrypted,
        corregido_por_id=current_user.id,
    )


@router.post(
    "/lote",
    response_model=CorregirLoteAceptadoResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def corregir_lote(
    data: CorregirLoteRequest,
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorregirLoteAceptadoResponse:
    """
    Enqueue AI correction for multiple entregas (async batch).

    **Behavior:**
    - Validates the request and returns **immediately** with 202 Accepted
    - Corrections are processed in the background (no HTTP timeout)
    - Each entrega state updates in real-time as it is corrected
    - Frontend should poll or refresh the entrega list to see progress

    **Limits:**
    - Maximum 50 entregas per batch (validated in schema)

    **Authorization:** Tutor or Admin with API Key configured
    """
    require_any_authenticated(current_user)

    if not current_user.gemini_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil",
        )

    service = CorreccionService(db)
    entrega_ids = await service.encolar_lote(data)

    # Schedule background processing — runs after response is sent
    background_tasks.add_task(
        procesar_lote_background,
        entrega_ids=entrega_ids,
        api_key_encrypted=current_user.gemini_api_key_encrypted,
        corregido_por_id=current_user.id,
    )

    return CorregirLoteAceptadoResponse(
        mensaje=f"Corrección iniciada para {len(entrega_ids)} entregas. Los estados se actualizarán automáticamente.",
        total_encoladas=len(entrega_ids),
        entrega_ids=entrega_ids,
    )


@router.get(
    "/{correccion_id}",
    response_model=CorreccionResponse,
)
async def obtener_correccion(
    correccion_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorreccionResponse:
    """
    Get a correction by ID.

    **Returns:**
    - Full correction data
    - Entrega info (alumno, archivo)
    - Corregido por info (nombre, email)
    - All evaluation details (nota, criterios, fortalezas, etc.)

    **Authorization:** Tutor or Admin
    """
    require_any_authenticated(current_user)

    service = CorreccionService(db)
    return await service.obtener_correccion(correccion_id)


@router.get(
    "/entregas/{entrega_id}",
    response_model=CorreccionResponse,
)
async def obtener_correccion_por_entrega(
    entrega_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorreccionResponse:
    """
    Get correction for a specific entrega.

    **Use case:**
    - View correction from entrega detail page
    - Check if entrega has been corrected

    **Returns:**
    - Correction data if exists
    - 404 if entrega has no correction

    **Authorization:** Tutor or Admin
    """
    require_any_authenticated(current_user)

    service = CorreccionService(db)
    return await service.obtener_por_entrega(entrega_id)


@router.put(
    "/{correccion_id}",
    response_model=CorreccionResponse,
)
async def editar_correccion(
    correccion_id: int,
    data: CorreccionUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorreccionResponse:
    """
    Manually edit a correction.

    **Editable fields:**
    - `nota`: Final grade (0-100)
    - `criterios_json`: Criteria evaluations
    - `fortalezas`: List of strengths
    - `recomendaciones`: List of recommendations
    - `comentario_general`: General feedback

    **Behavior:**
    - All fields are optional (only provided fields are updated)
    - Sets `editado_manualmente = True` for audit trail
    - Updates `corregido_por_id` to current user

    **Use cases:**
    - Adjust AI-generated evaluation
    - Fix errors in automatic correction
    - Add personalized feedback

    **Authorization:** Tutor or Admin
    """
    require_any_authenticated(current_user)

    service = CorreccionService(db)
    return await service.editar_correccion(
        correccion_id=correccion_id,
        data=data,
        editado_por_id=current_user.id,
    )


# =========================================================================
# Subir corrección + devolución a Moodle (Fase 3)
# =========================================================================


@router.get(
    "/{correccion_id}/moodle/preview",
    response_model=PreviewCorreccionMoodleResponse,
)
async def preview_correccion_moodle(
    correccion_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreviewCorreccionMoodleResponse:
    """
    Calcula lo que se enviaría a Moodle (sin enviarlo): nota mapeada, comentario
    sugerido, si el tutor debe escribir comentario, y el link de devolución.

    Permisos: tutor de la comisión o admin. Errores: 404/400/422/424/502.
    """
    from dataclasses import asdict

    service = MoodleGradeService(db)
    preview = await service.preview_correccion(
        correccion_id=correccion_id,
        usuario=current_user,
        base_url=str(request.base_url),
    )
    return PreviewCorreccionMoodleResponse(**asdict(preview))


@router.post(
    "/{correccion_id}/moodle",
    response_model=SubirCorreccionMoodleResponse,
)
async def subir_correccion_moodle(
    correccion_id: int,
    data: SubirCorreccionMoodleRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubirCorreccionMoodleResponse:
    """
    Publica nota + feedback de la corrección en Moodle.

    Permisos: tutor de la comisión o admin. Idempotente (409 si ya enviada salvo `forzar`).
    """
    service = MoodleGradeService(db)
    sync = await service.subir_correccion(
        correccion_id=correccion_id,
        comentario_final=data.comentario,
        usuario=current_user,
        base_url=str(request.base_url),
        forzar=data.forzar,
    )
    return SubirCorreccionMoodleResponse(
        estado=sync.estado.value if hasattr(sync.estado, "value") else str(sync.estado),
        nota_enviada=sync.nota_enviada,
        intento=sync.intento,
    )


# =========================================================================
# Corrección masiva global (API key paga) — Fase 4
# =========================================================================


@router.post(
    "/global",
    response_model=CorregirGlobalAceptadoResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def corregir_global(
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorregirGlobalAceptadoResponse:
    """
    Corrige TODAS las entregas SUBIDA del tutor (cross-materia/comisión/rúbrica).

    Requiere API key Gemini configurada y marcada como paga (toggle del perfil).
    Procesa en background con concurrencia controlada y resiliente a 429.
    """
    require_any_authenticated(current_user)

    if not current_user.gemini_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configurá tu API key de Gemini en tu perfil",
        )
    if not getattr(current_user, "gemini_api_key_paga", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La corrección masiva global requiere una API key paga. Activala en tu perfil.",
        )

    entrega_repo = EntregaRepository(db)
    ids = await entrega_repo.get_subidas_ids_by_tutor(current_user.id, limite=GLOBAL_BATCH_MAX)
    if not ids:
        return CorregirGlobalAceptadoResponse(
            mensaje="No hay entregas pendientes para corregir.", total_encoladas=0
        )

    background_tasks.add_task(
        procesar_global_background,
        ids,
        current_user.gemini_api_key_encrypted,
        current_user.id,
    )
    return CorregirGlobalAceptadoResponse(
        mensaje=(
            f"Corrección global iniciada para {len(ids)} entregas. "
            "Los estados se actualizarán automáticamente."
        ),
        total_encoladas=len(ids),
    )


@router.get("/global/progreso", response_model=ProgresoGlobalResponse)
async def progreso_global(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgresoGlobalResponse:
    """Conteo de estados de las entregas del tutor (para el feedback de progreso)."""
    require_any_authenticated(current_user)

    entrega_repo = EntregaRepository(db)
    counts = await entrega_repo.contar_estados_by_tutor(current_user.id)
    subidas = counts.get("SUBIDA", 0)
    pendientes = counts.get("PENDIENTE", 0)
    corregidas = counts.get("CORREGIDA", 0)
    error = counts.get("ERROR", 0)
    return ProgresoGlobalResponse(
        subidas=subidas,
        pendientes=pendientes,
        corregidas=corregidas,
        error=error,
        total=subidas + pendientes + corregidas + error,
    )
