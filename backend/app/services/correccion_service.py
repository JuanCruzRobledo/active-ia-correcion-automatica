# app/services/correccion_service.py
"""
Correccion service for Active-IA.

Business logic for AI-powered correction operations.
Handles integration with N8N and Gemini for automatic evaluation.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 8
Ref: docs/specs/10-INTEGRACIONES.md
Ref: skills/correccion-ia/SKILL.md
"""

import asyncio
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    N8NError,
    N8NTimeoutError,
    ValidationError,
)
from app.core.security import decrypt_api_key
from app.integrations.n8n_client import N8NClient
from app.models.correccion import Correccion
from app.models.enums import EstadoEntregaEnum
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.schemas.correccion import (
    CorreccionCreate,
    CorreccionListItem,
    CorreccionResponse,
    CorreccionUpdate,
    CorregirLoteRequest,
    CorregirLoteResponse,
    GeminiResponse,
)


class CorreccionService:
    """Service for AI-powered correction operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize correccion service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.correccion_repo = CorreccionRepository(db)
        self.entrega_repo = EntregaRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.n8n_client = N8NClient()

    async def corregir_individual(
        self,
        entrega_id: int,
        api_key_encrypted: str,
        corregido_por_id: int,
    ) -> CorreccionResponse:
        """
        Correct a single entrega using AI.

        Args:
            entrega_id: ID of the entrega to correct.
            api_key_encrypted: Encrypted Gemini API key.
            corregido_por_id: ID of user performing correction.

        Returns:
            CorreccionResponse with correction data.

        Raises:
            HTTPException 404: Entrega or Rubrica not found.
            HTTPException 400: Invalid entrega state or missing data.
            HTTPException 502: N8N/Gemini error.
        """
        # Get entrega with relations
        entrega = await self.entrega_repo.get_by_id_with_relations(entrega_id)
        if not entrega:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrega no encontrada",
            )

        # Validate entrega has content
        if not entrega.contenido_preview:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La entrega no tiene contenido consolidado",
            )

        # Get rubrica
        rubrica = await self.rubrica_repo.get_active_by_id(entrega.rubrica_id)
        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada o inactiva",
            )

        # Decrypt API key
        try:
            api_key = decrypt_api_key(api_key_encrypted)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error al desencriptar API Key: {str(e)}",
            )

        # Update entrega state to PENDIENTE
        entrega.estado = EstadoEntregaEnum.PENDIENTE
        await self.entrega_repo.update(entrega)

        # Build payload for N8N
        payload = self._build_correction_payload(entrega, rubrica, api_key)

        # Call N8N with retry logic
        try:
            result = await self._call_n8n_with_retry(payload)
        except N8NTimeoutError:
            # Mark as ERROR
            entrega.estado = EstadoEntregaEnum.ERROR
            await self.entrega_repo.update(entrega)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Timeout esperando respuesta del servicio de IA",
            )
        except N8NError as e:
            # Mark as ERROR
            entrega.estado = EstadoEntregaEnum.ERROR
            await self.entrega_repo.update(entrega)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error en servicio de IA: {str(e)}",
            )

        # Parse and validate Gemini response
        try:
            gemini_response = self._parse_gemini_response(result)
        except ValidationError as e:
            # Mark as ERROR
            entrega.estado = EstadoEntregaEnum.ERROR
            await self.entrega_repo.update(entrega)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Respuesta de IA malformada: {e.message}",
            )

        # Check if correction already exists (re-correction case)
        existing_correccion = await self.correccion_repo.get_by_entrega_id(
            entrega_id
        )

        if existing_correccion:
            # Delete old correction (hard delete for re-correction)
            await self.correccion_repo.delete(existing_correccion)

        # Create new correction
        correccion_data = CorreccionCreate(
            entrega_id=entrega_id,
            nota=Decimal(str(gemini_response.nota)),
            criterios_json={"criterios": [c.model_dump() for c in gemini_response.criterios]},
            fortalezas=gemini_response.fortalezas,
            recomendaciones=gemini_response.recomendaciones,
            comentario_general=gemini_response.comentario_general,
            editado_manualmente=False,
            raw_response=result,
            corregido_por_id=corregido_por_id,
        )

        correccion = Correccion(**correccion_data.model_dump())
        created_correccion = await self.correccion_repo.create(correccion)

        # Update entrega state to CORREGIDA
        entrega.estado = EstadoEntregaEnum.CORREGIDA
        await self.entrega_repo.update(entrega)

        # Return response
        return await self._build_correccion_response(created_correccion)

    async def corregir_lote(
        self,
        data: CorregirLoteRequest,
        api_key_encrypted: str,
        corregido_por_id: int,
    ) -> CorregirLoteResponse:
        """
        Correct multiple entregas in batch.

        Args:
            data: Batch correction request data.
            api_key_encrypted: Encrypted Gemini API key.
            corregido_por_id: ID of user performing corrections.

        Returns:
            CorregirLoteResponse with results.
        """
        exitosas = []
        fallidas = []

        for entrega_id in data.entrega_ids:
            try:
                correccion = await self.corregir_individual(
                    entrega_id=entrega_id,
                    api_key_encrypted=api_key_encrypted,
                    corregido_por_id=corregido_por_id,
                )
                exitosas.append(correccion)

                # Rate limiting: 2 seconds between corrections
                await asyncio.sleep(2)

            except HTTPException as e:
                fallidas.append(
                    {
                        "entrega_id": entrega_id,
                        "error": e.detail,
                    }
                )
                continue

        return CorregirLoteResponse(
            total=len(data.entrega_ids),
            exitosas=len(exitosas),
            fallidas=len(fallidas),
            correcciones=exitosas,
            errores=fallidas,
        )

    async def recorregir(
        self,
        entrega_id: int,
        api_key_encrypted: str,
        corregido_por_id: int,
    ) -> CorreccionResponse:
        """
        Re-correct an entrega (replaces existing correction).

        Args:
            entrega_id: ID of the entrega to re-correct.
            api_key_encrypted: Encrypted Gemini API key.
            corregido_por_id: ID of user performing re-correction.

        Returns:
            CorreccionResponse with new correction data.
        """
        # Re-correction is handled by corregir_individual
        # It automatically deletes the old correction
        return await self.corregir_individual(
            entrega_id=entrega_id,
            api_key_encrypted=api_key_encrypted,
            corregido_por_id=corregido_por_id,
        )

    async def editar_correccion(
        self,
        correccion_id: int,
        data: CorreccionUpdate,
        editado_por_id: int,
    ) -> CorreccionResponse:
        """
        Manually edit a correction.

        Args:
            correccion_id: ID of the correction to edit.
            data: Update data.
            editado_por_id: ID of user editing.

        Returns:
            CorreccionResponse with updated correction.

        Raises:
            HTTPException 404: Correction not found.
        """
        correccion = await self.correccion_repo.get_by_id(correccion_id)
        if not correccion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Corrección no encontrada",
            )

        # Update fields
        update_data = data.model_dump(exclude_unset=True)

        if "nota" in update_data:
            correccion.nota = Decimal(str(update_data["nota"]))

        if "criterios_json" in update_data:
            correccion.criterios_json = update_data["criterios_json"]

        if "fortalezas" in update_data:
            correccion.fortalezas = update_data["fortalezas"]

        if "recomendaciones" in update_data:
            correccion.recomendaciones = update_data["recomendaciones"]

        if "comentario_general" in update_data:
            correccion.comentario_general = update_data["comentario_general"]

        # Mark as manually edited
        correccion.editado_manualmente = True
        correccion.corregido_por_id = editado_por_id

        updated_correccion = await self.correccion_repo.update(correccion)
        return await self._build_correccion_response(updated_correccion)

    async def obtener_correccion(self, correccion_id: int) -> CorreccionResponse:
        """
        Get a correction by ID.

        Args:
            correccion_id: Correction's database ID.

        Returns:
            CorreccionResponse with correction data.

        Raises:
            HTTPException 404: Correction not found.
        """
        correccion = await self.correccion_repo.get_by_id_with_relations(
            correccion_id
        )
        if not correccion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Corrección no encontrada",
            )

        return await self._build_correccion_response(correccion)

    async def obtener_por_entrega(self, entrega_id: int) -> CorreccionResponse:
        """
        Get correction for a specific entrega.

        Args:
            entrega_id: Entrega's database ID.

        Returns:
            CorreccionResponse with correction data.

        Raises:
            HTTPException 404: Correction not found.
        """
        correccion = await self.correccion_repo.get_by_entrega_id_with_relations(
            entrega_id
        )
        if not correccion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay corrección para esta entrega",
            )

        return await self._build_correccion_response(correccion)

    def _build_correction_payload(
        self,
        entrega: Any,
        rubrica: Any,
        api_key: str,
    ) -> dict[str, Any]:
        """
        Build payload for N8N correction webhook.

        Args:
            entrega: Entrega object.
            rubrica: Rubrica object.
            api_key: Decrypted Gemini API key.

        Returns:
            Payload dictionary for N8N.
        """
        return {
            "codigo": entrega.contenido_preview,  # Full consolidated code
            "rubrica": {
                "nombre": rubrica.nombre,
                "tipo": rubrica.tipo.value,
                "puntaje_maximo": 100,
                "criterios": rubrica.criterios_json.get("criterios", []),
            },
            "api_key": api_key,
            "contexto": {
                "materia": entrega.comision.materia.nombre,
                "alumno": entrega.alumno_nombre,
            },
        }

    async def _call_n8n_with_retry(
        self,
        payload: dict[str, Any],
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """
        Call N8N with retry logic.

        Args:
            payload: Payload to send.
            max_retries: Maximum number of retries (default: 1).

        Returns:
            N8N response.

        Raises:
            N8NTimeoutError: If timeout occurs after retries.
            N8NError: If other error occurs after retries.
        """
        for attempt in range(max_retries + 1):
            try:
                result = await self.n8n_client.trigger_correction(payload)
                return result

            except N8NTimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise

            except N8NError as e:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        # Should not reach here
        raise N8NError("Error inesperado en reintentos")

    def _parse_gemini_response(self, response: dict[str, Any]) -> GeminiResponse:
        """
        Parse and validate Gemini response from N8N.

        Args:
            response: Raw response from N8N.

        Returns:
            Validated GeminiResponse.

        Raises:
            ValidationError: If response is invalid.
        """
        try:
            # Extract correction data from N8N response
            if not response.get("success"):
                error_msg = response.get("error", {}).get("message", "Error desconocido")
                raise ValidationError(
                    message=f"N8N retornó error: {error_msg}",
                    field="n8n_response",
                )

            correccion_data = response.get("correccion", {})

            # Validate with Pydantic
            gemini_response = GeminiResponse.model_validate(correccion_data)

            return gemini_response

        except Exception as e:
            raise ValidationError(
                message=f"Error parseando respuesta de Gemini: {str(e)}",
                field="gemini_response",
            )

    async def _build_correccion_response(
        self, correccion: Correccion
    ) -> CorreccionResponse:
        """
        Build CorreccionResponse from Correccion model.

        Args:
            correccion: Correccion model instance.

        Returns:
            CorreccionResponse.
        """
        # Get entrega with relations if not loaded
        if not hasattr(correccion, "entrega") or not correccion.entrega:
            correccion = await self.correccion_repo.get_by_id_with_relations(
                correccion.id
            )

        return CorreccionResponse.model_validate(correccion)
