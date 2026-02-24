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
import logging
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import async_session_maker

logger = logging.getLogger(__name__)


from app.core.exceptions import (
    APIKeyInvalidError,
    N8NError,
    N8NTimeoutError,
    QuotaExceededError,
    ValidationError,
)
from app.core.security import decrypt_api_key
from app.integrations.n8n_client import N8NClient
from app.models.correccion import Correccion
from app.models.enums import EstadoEntregaEnum
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.usuario_repository import UsuarioRepository
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
        self.usuario_repo = UsuarioRepository(db)
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

        # Validate entrega has content appropriate for its type
        if entrega.archivo_tipo == "pdf":
            if not entrega.pdf_contenido_b64:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La entrega PDF no tiene contenido disponible para corrección",
                )
        else:
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

        # Build payload for N8N and call appropriate webhook before updating state
        # (to avoid lazy loading issues after the state update)
        if entrega.archivo_tipo == "pdf":
            payload = self._build_pdf_correction_payload(entrega, rubrica, api_key)
        else:
            payload = self._build_correction_payload(entrega, rubrica, api_key)

        # Update entrega state to PENDIENTE
        entrega.estado = EstadoEntregaEnum.PENDIENTE
        await self.entrega_repo.update(entrega)

        # Call the appropriate N8N workflow with retry logic
        try:
            if entrega.archivo_tipo == "pdf":
                result = await self._call_n8n_pdf_with_retry(payload)
            else:
                result = await self._call_n8n_with_retry(payload)
        except N8NTimeoutError:
            # Mark as ERROR
            entrega.estado = EstadoEntregaEnum.ERROR
            await self.entrega_repo.update(entrega)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Timeout esperando respuesta del servicio de IA",
            )
        except APIKeyInvalidError:
            # Mark entrega as ERROR
            entrega.estado = EstadoEntregaEnum.ERROR
            await self.entrega_repo.update(entrega)
            # Mark user's API key as invalid in DB
            usuario = await self.usuario_repo.get_by_id(corregido_por_id)
            if usuario:
                usuario.gemini_api_key_valid = False
                await self.usuario_repo.update(usuario)
                logger.warning(
                    f"API Key de Gemini marcada como inválida para usuario {corregido_por_id}"
                )
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": "GEMINI_API_KEY_INVALID",
                    "message": (
                        "Tu API Key de Gemini expiró o es inválida. "
                        "Por favor generá una nueva en Google AI Studio "
                        "con otra cuenta de Google y actualizala en tu perfil."
                    ),
                },
            )
        except QuotaExceededError as e:
            # Mark entrega as ERROR
            entrega.estado = EstadoEntregaEnum.ERROR
            await self.entrega_repo.update(entrega)
            logger.warning(
                f"Rate limit de Gemini alcanzado corrigiendo entrega {entrega_id}: {e}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": "GEMINI_RATE_LIMIT",
                    "message": (
                        "Se alcanzó el límite de uso de la API de Gemini. "
                        "Esperá unos minutos antes de volver a corregir."
                    ),
                },
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

        # Convert CriterioGeminiSchema to CriterioEvaluado
        from app.schemas.correccion import CriterioEvaluado
        from decimal import Decimal as Dec

        criterios_evaluados = [
            CriterioEvaluado(
                id=c.id if c.id is not None else str(i),
                nombre=c.nombre,
                puntaje_obtenido=Dec(str(c.puntaje_obtenido)),
                puntaje_maximo=Dec(str(c.puntaje_maximo)),
                estado=c.estado,
                feedback=c.feedback
            )
            for i, c in enumerate(gemini_response.criterios)
        ]

        # Create new correction
        correccion_data = CorreccionCreate(
            entrega_id=entrega_id,
            nota=Decimal(str(gemini_response.nota)),
            criterios=criterios_evaluados,
            fortalezas=gemini_response.fortalezas,
            recomendaciones=gemini_response.recomendaciones,
            comentario_general=gemini_response.comentario_general,
            corregido_por_id=corregido_por_id,
            raw_response=result,
        )

        # Convert to SQLAlchemy model - map 'criterios' to 'criterios_json'
        data_dict = correccion_data.model_dump()
        criterios_list = data_dict.pop('criterios')  # Remove 'criterios'

        # Convert Decimal to float for JSON serialization
        criterios_for_json = []
        for c in criterios_list:
            criterio_dict = dict(c) if isinstance(c, dict) else c
            criterio_dict['puntaje_obtenido'] = float(criterio_dict['puntaje_obtenido'])
            criterio_dict['puntaje_maximo'] = float(criterio_dict['puntaje_maximo'])
            criterios_for_json.append(criterio_dict)

        data_dict['criterios_json'] = {
            "criterios": criterios_for_json  # Store as JSON structure with float values
        }

        correccion = Correccion(**data_dict)
        created_correccion = await self.correccion_repo.create(correccion)

        # Update entrega state to CORREGIDA
        entrega.estado = EstadoEntregaEnum.CORREGIDA
        await self.entrega_repo.update(entrega)

        # Return response
        return await self._build_correccion_response(created_correccion)

    async def encolar_lote(
        self,
        data: CorregirLoteRequest,
    ) -> list[int]:
        """
        Validate and return IDs for background processing.

        Args:
            data: Batch correction request data.

        Returns:
            List of entrega IDs to be processed asynchronously.
        """
        return list(data.entrega_ids)

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

        # Handle criterios: frontend sends 'criterios' but DB field is 'criterios_json'
        if "criterios" in update_data:
            # Convert list of CriterioEvaluado to criterios_json format
            criterios_list = update_data["criterios"]
            # Convert Decimal to float for JSON serialization
            criterios_serialized = [
                {
                    "id": c["id"],
                    "nombre": c["nombre"],
                    "puntaje_obtenido": float(c["puntaje_obtenido"]),
                    "puntaje_maximo": float(c["puntaje_maximo"]),
                    "estado": c["estado"],
                    "feedback": c["feedback"],
                }
                for c in criterios_list
            ]
            correccion.criterios_json = {"criterios": criterios_serialized}

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
        Build payload for N8N text correction webhook (/webhook/corregir).

        Used for code submissions (zip, txt, individual code files).

        Args:
            entrega: Entrega object with contenido_consolidado or contenido_preview.
            rubrica: Rubrica object.
            api_key: Decrypted Gemini API key.

        Returns:
            Payload dictionary for N8N.
        """
        # Use contenido_consolidado if available, fallback to preview for old entregas
        codigo = entrega.contenido_consolidado or entrega.contenido_preview

        return {
            "codigo": codigo,
            "rubrica": {
                "titulo": rubrica.titulo,
                "descripcion": rubrica.descripcion or "",
                "tipo": rubrica.tipo.value,
                "puntaje_maximo": rubrica.puntaje_maximo,
                "metadata": rubrica.metadata_json or {},
                "criterios": rubrica.criterios_json or [],
                "penalizaciones": rubrica.penalizaciones_json or [],
                "condiciones_desaprobacion": rubrica.condiciones_desaprobacion_json or [],
            },
            "api_key": api_key,
            "contexto": {
                "materia": entrega.comision.materia.nombre,
                "alumno": entrega.alumno_nombre,
            },
        }

    def _build_pdf_correction_payload(
        self,
        entrega: Any,
        rubrica: Any,
        api_key: str,
    ) -> dict[str, Any]:
        """
        Build payload for N8N PDF correction webhook (/webhook/corregir-pdf).

        Used for PDF submissions (e.g., handwritten exercises). Sends the raw
        PDF in Base64 instead of text, so N8N can pass it directly to Gemini's
        vision API.

        Args:
            entrega: Entrega object with pdf_contenido_b64 populated.
            rubrica: Rubrica object.
            api_key: Decrypted Gemini API key.

        Returns:
            Payload dictionary for N8N PDF correction webhook.
        """
        return {
            "pdf_base64": entrega.pdf_contenido_b64,
            "rubrica": {
                "titulo": rubrica.titulo,
                "descripcion": rubrica.descripcion or "",
                "tipo": rubrica.tipo.value,
                "puntaje_maximo": rubrica.puntaje_maximo,
                "metadata": rubrica.metadata_json or {},
                "criterios": rubrica.criterios_json or [],
                "penalizaciones": rubrica.penalizaciones_json or [],
                "condiciones_desaprobacion": rubrica.condiciones_desaprobacion_json or [],
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

            except APIKeyInvalidError:
                # Never retry on invalid API key — re-raise immediately
                raise

            except QuotaExceededError:
                # Never retry on rate limit — re-raise immediately
                raise

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

    async def _call_n8n_pdf_with_retry(
        self,
        payload: dict[str, Any],
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """
        Call N8N PDF correction webhook with retry logic.

        Args:
            payload: Payload with pdf_base64 and rubrica to send.
            max_retries: Maximum number of retries (default: 1).

        Returns:
            N8N response with correction data.

        Raises:
            N8NTimeoutError: If timeout occurs after retries.
            N8NError: If other error occurs after retries.
        """
        for attempt in range(max_retries + 1):
            try:
                result = await self.n8n_client.trigger_correction_pdf(payload)
                return result

            except APIKeyInvalidError:
                # Never retry on invalid API key — re-raise immediately
                raise

            except QuotaExceededError:
                # Never retry on rate limit — re-raise immediately
                raise

            except N8NTimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise

            except N8NError:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        # Should not reach here
        raise N8NError("Error inesperado en reintentos (PDF)")

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
        # Always reload with relations to avoid lazy loading issues in async context
        correccion = await self.correccion_repo.get_by_id_with_relations(
            correccion.id
        )

        return CorreccionResponse.model_validate(correccion)


async def procesar_lote_background(
    entrega_ids: list[int],
    api_key_encrypted: str,
    corregido_por_id: int,
) -> None:
    """
    Standalone background task to correct multiple entregas sequentially.

    This function runs AFTER the HTTP response has been sent to the client,
    so it must create its own database session instead of using the
    request-scoped session (which is already closed by the time this runs).

    Args:
        entrega_ids: List of entrega IDs to correct.
        api_key_encrypted: Encrypted Gemini API key.
        corregido_por_id: ID of user performing corrections.
    """
    logger.info(f"[BG] Iniciando corrección masiva de {len(entrega_ids)} entregas")

    async with async_session_maker() as db:
        service = CorreccionService(db)
        exitosas = 0
        fallidas = 0

        for entrega_id in entrega_ids:
            try:
                await service.corregir_individual(
                    entrega_id=entrega_id,
                    api_key_encrypted=api_key_encrypted,
                    corregido_por_id=corregido_por_id,
                )
                exitosas += 1
                logger.info(f"[BG] Entrega {entrega_id} corregida exitosamente")

                # Rate limiting: 7 seconds between corrections to stay within
                # Gemini API limits (10 RPM = 1 req every 6s, with 1s margin).
                # With free tier (10 RPM), this processes ~8 entregas/min.
                # With paid tier (150+ RPM), this is the safe steady-state rate.
                await asyncio.sleep(7)

            except HTTPException as e:
                fallidas += 1
                logger.warning(
                    f"[BG] Error corrigiendo entrega {entrega_id}: {e.detail}"
                )
                # If API Key is invalid (402) or rate-limited (429),
                # stop the entire batch immediately.
                if e.status_code in (402, 429):
                    remaining = len(entrega_ids) - exitosas - fallidas
                    reason = "API Key inválida" if e.status_code == 402 else "Rate limit alcanzado"
                    logger.error(
                        f"[BG] {reason} detectado. Deteniendo lote. "
                        f"{remaining} entregas no procesadas."
                    )
                    break
                continue
            except Exception as e:
                fallidas += 1
                logger.error(
                    f"[BG] Error inesperado corrigiendo entrega {entrega_id}: {e}"
                )
                continue

    logger.info(
        f"[BG] Corrección masiva finalizada: {exitosas} exitosas, {fallidas} fallidas"
    )
