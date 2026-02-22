# app/routers/correcciones.py
"""
Correcciones router for Active-IA.

REST API endpoints for AI-powered correction management.
Endpoints require authentication and tutor/admin authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 8
Ref: skills/correccion-ia/SKILL.md
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_tutor
from app.models.usuario import Usuario
from app.schemas.correccion import (
    CorreccionResponse,
    CorreccionUpdate,
    CorregirLoteAceptadoResponse,
    CorregirLoteRequest,
    CorregirLoteResponse,
)
from app.services.correccion_service import CorreccionService, procesar_lote_background

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
    require_tutor(current_user)

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
    require_tutor(current_user)

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
    require_tutor(current_user)

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
    require_tutor(current_user)

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
    require_tutor(current_user)

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
    require_tutor(current_user)

    service = CorreccionService(db)
    return await service.editar_correccion(
        correccion_id=correccion_id,
        data=data,
        editado_por_id=current_user.id,
    )
