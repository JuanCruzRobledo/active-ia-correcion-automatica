# app/routers/correcciones.py
"""
Correcciones router for Active-IA.

REST API endpoints for AI-powered correction management.
Endpoints require authentication and tutor/admin authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 8
Ref: skills/correccion-ia/SKILL.md
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_tutor
from app.models.usuario import Usuario
from app.schemas.correccion import (
    CorreccionResponse,
    CorreccionUpdate,
    CorregirLoteRequest,
    CorregirLoteResponse,
)
from app.services.correccion_service import CorreccionService

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
    if not current_user.api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil antes de corregir",
        )

    service = CorreccionService(db)
    return await service.corregir_individual(
        entrega_id=entrega_id,
        api_key_encrypted=current_user.api_key_encrypted,
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

    if not current_user.api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil",
        )

    service = CorreccionService(db)
    return await service.recorregir(
        entrega_id=entrega_id,
        api_key_encrypted=current_user.api_key_encrypted,
        corregido_por_id=current_user.id,
    )


@router.post(
    "/lote",
    response_model=CorregirLoteResponse,
)
async def corregir_lote(
    data: CorregirLoteRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorregirLoteResponse:
    """
    Correct multiple entregas in batch.

    **Process:**
    - Processes each entrega sequentially
    - Continues on individual errors (doesn't stop batch)
    - Rate limiting: 2 seconds between corrections

    **Limits:**
    - Maximum 50 entregas per batch (validated in schema)

    **Response:**
    - Summary: total, exitosas, fallidas
    - List of successful corrections
    - List of errors with entrega_id and error message

    **Authorization:** Tutor or Admin with API Key configured
    """
    require_tutor(current_user)

    if not current_user.api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes configurar tu API Key de Gemini en tu perfil",
        )

    service = CorreccionService(db)
    return await service.corregir_lote(
        data=data,
        api_key_encrypted=current_user.api_key_encrypted,
        corregido_por_id=current_user.id,
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
