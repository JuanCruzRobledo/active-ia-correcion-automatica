# app/services/rubrica_ia_service.py
"""
Rubrica IA service for Active-IA.

Business logic for AI-powered rubrica generation from PDF files.
Handles integration with N8N and Gemini for automatic criteria extraction.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-RUB-02
Ref: docs/specs/10-INTEGRACIONES.md seccion 4.3
"""

import logging
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_catalog import (
    ERROR_API_KEY_INVALID,
    ERROR_OVERLOADED,
    ERROR_RATE_LIMIT,
    ERROR_SIN_CREDITOS,
    mensaje_error,
)
from app.core.exceptions import (
    APIKeyInvalidError,
    InsufficientCreditsError,
    ModelOverloadedError,
    N8NError,
    N8NTimeoutError,
    QuotaExceededError,
    ValidationError,
)
from app.core.security import decrypt_api_key
from app.integrations.gemini_correction_client import GeminiCorrectionClient
from app.repositories.usuario_repository import UsuarioRepository

logger = logging.getLogger(__name__)

# Este flujo es Gemini-only (no multi-proveedor como corrección), así que el
# proveedor de los mensajes del catálogo es fijo.
_PROVIDER = "gemini"


class RubricaIAService:
    """Service for AI-powered rubrica generation from PDF."""

    def __init__(self, db: AsyncSession):
        """Initialize rubrica IA service.

        Args:
            db: Async database session. Necesaria para marcar la API key del
                usuario como inválida cuando el proveedor la rechaza
                (mismo contrato que `CorreccionService`).
        """
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        self.gemini_client = GeminiCorrectionClient()

    async def generar_rubrica_desde_pdf(
        self,
        pdf_file: UploadFile,
        api_key_encrypted: str,
        usuario: Any,
        tipo_rubrica: str = "TP",
    ) -> dict[str, Any]:
        """
        Generate rubrica from PDF file using AI.

        Args:
            pdf_file: Uploaded PDF file with assignment description.
            api_key_encrypted: Encrypted Gemini API key.
            usuario: Usuario dueño de la API key. Se marca su
                `gemini_api_key_valid = False` si el proveedor la rechaza.
            tipo_rubrica: Type of rubrica (TP, PARCIAL_1, etc.). Default: TP.

        Returns:
            Dictionary with rubrica data:
            - nombre_sugerido: Suggested name for the rubrica
            - descripcion: Brief description of the assignment
            - puntaje_maximo: Total points (always 100)
            - criterios: List of evaluation criteria

        Raises:
            HTTPException 400: Invalid file type or missing API key.
            HTTPException 402: API key inválida o sin créditos.
            HTTPException 429: Límite de uso (rate limit) del proveedor.
            HTTPException 502: N8N/Gemini error.
            HTTPException 503: Modelo sobrecargado.
        """
        # Validate file type
        if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser un PDF",
            )

        # Decrypt API key
        try:
            api_key = decrypt_api_key(api_key_encrypted)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error al desencriptar API Key: {str(e)}",
            )

        # Read PDF content
        try:
            pdf_content = await pdf_file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error al leer archivo PDF: {str(e)}",
            )

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(pdf_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo PDF es demasiado grande (máximo 10MB)",
            )

        # Build payload for Gemini
        payload = self._build_rubrica_payload(
            pdf_content=pdf_content,
            filename=pdf_file.filename,
            api_key=api_key,
            tipo_rubrica=tipo_rubrica,
        )

        # Call Gemini directly
        try:
            result = await self.gemini_client.generar_rubrica(payload)
        except N8NTimeoutError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Timeout esperando respuesta del servicio de IA (el PDF puede ser muy largo)",
            )
        except APIKeyInvalidError:
            # Key rechazada por el proveedor: marcarla inválida en la DB, igual que
            # correccion_service.py, para que el frontend pida regenerarla.
            if usuario is not None:
                usuario.gemini_api_key_valid = False
                await self.usuario_repo.update(usuario)
                logger.warning(
                    f"API Key de {_PROVIDER} marcada como inválida para usuario "
                    f"{getattr(usuario, 'id', '?')}"
                )
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": ERROR_API_KEY_INVALID,
                    "message": mensaje_error(ERROR_API_KEY_INVALID, _PROVIDER),
                },
            )
        except InsufficientCreditsError as e:
            logger.warning(f"Sin créditos en {_PROVIDER} generando rúbrica: {e}")
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": ERROR_SIN_CREDITOS,
                    "message": mensaje_error(ERROR_SIN_CREDITOS, _PROVIDER),
                },
            )
        except QuotaExceededError as e:
            logger.warning(f"Rate limit de {_PROVIDER} generando rúbrica: {e}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": ERROR_RATE_LIMIT,
                    "message": mensaje_error(ERROR_RATE_LIMIT, _PROVIDER),
                },
            )
        except ModelOverloadedError as e:
            logger.warning(f"Modelo de {_PROVIDER} sobrecargado generando rúbrica: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": ERROR_OVERLOADED,
                    "message": mensaje_error(ERROR_OVERLOADED, _PROVIDER),
                },
            )
        except N8NError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error en servicio de IA: {str(e)}",
            )

        # Parse and validate response
        try:
            rubrica_data = self._parse_rubrica_response(result)

            # Log para debug
            logger.info(f"✅ Rúbrica V2 generada exitosamente: {rubrica_data.get('titulo', 'Sin título')}")

        except ValidationError as e:
            logger.error(f"❌ Error validando rúbrica V2: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Respuesta de IA malformada: {e.message}",
            )

        return rubrica_data

    def _build_rubrica_payload(
        self,
        pdf_content: bytes,
        filename: str,
        api_key: str,
        tipo_rubrica: str,
    ) -> dict[str, Any]:
        """
        Build payload for N8N rubrica generation webhook.

        Args:
            pdf_content: PDF file content as bytes.
            filename: Original filename.
            api_key: Decrypted Gemini API key.
            tipo_rubrica: Type of rubrica.

        Returns:
            Payload dictionary for N8N.
        """
        # Convert PDF bytes to base64 for transmission
        import base64

        pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")

        return {
            "pdf_base64": pdf_base64,
            "filename": filename,
            "api_key": api_key,
            "tipo_rubrica": tipo_rubrica,
        }

    def _parse_rubrica_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse and validate rubrica V2 response from N8N.

        Args:
            response: Raw response from N8N.

        Returns:
            Validated rubrica V2 data.

        Raises:
            ValidationError: If response is invalid.
        """
        try:
            # Check if N8N returned success
            if not response.get("success"):
                error_msg = response.get("error", {}).get(
                    "message", "Error desconocido"
                )
                raise ValidationError(
                    message=f"N8N retornó error: {error_msg}",
                    field="n8n_response",
                )

            # Extract rubrica V2 data
            rubrica_data = response.get("rubrica", {})

            # Validate required fields (V2 schema)
            if not rubrica_data.get("titulo"):
                raise ValidationError(
                    message="Respuesta no contiene titulo",
                    field="titulo",
                )

            if not rubrica_data.get("descripcion"):
                raise ValidationError(
                    message="Respuesta no contiene descripcion",
                    field="descripcion",
                )

            if not rubrica_data.get("criterios"):
                raise ValidationError(
                    message="Respuesta no contiene criterios",
                    field="criterios",
                )

            # Validate criterios structure (V2)
            criterios = rubrica_data["criterios"]
            if not isinstance(criterios, list) or len(criterios) == 0:
                raise ValidationError(
                    message="Criterios debe ser una lista no vacía",
                    field="criterios",
                )

            # Validate each criterio (V2 schema)
            total_peso = 0
            for i, criterio in enumerate(criterios):
                if not isinstance(criterio, dict):
                    raise ValidationError(
                        message=f"Criterio {i} no es un objeto válido",
                        field=f"criterios[{i}]",
                    )

                # Validate criterio V2 fields
                if not criterio.get("id"):
                    raise ValidationError(
                        message=f"Criterio {i} no tiene id",
                        field=f"criterios[{i}].id",
                    )

                if not criterio.get("nombre"):
                    raise ValidationError(
                        message=f"Criterio {i} no tiene nombre",
                        field=f"criterios[{i}].nombre",
                    )

                if not criterio.get("descripcion"):
                    raise ValidationError(
                        message=f"Criterio {i} no tiene descripción",
                        field=f"criterios[{i}].descripcion",
                    )

                # Validate peso (not puntaje_maximo)
                peso = criterio.get("peso")
                if not isinstance(peso, (int, float)) or peso <= 0 or peso > 100:
                    raise ValidationError(
                        message=f"Criterio {i} tiene peso inválido (debe ser 1-100)",
                        field=f"criterios[{i}].peso",
                    )

                total_peso += peso

                # Validate subcriterios
                subcriterios = criterio.get("subcriterios", [])
                if not isinstance(subcriterios, list) or len(subcriterios) == 0:
                    raise ValidationError(
                        message=f"Criterio {i} debe tener al menos un subcriterio",
                        field=f"criterios[{i}].subcriterios",
                    )

                # Validate each subcriterio
                for j, sub in enumerate(subcriterios):
                    if not sub.get("id"):
                        raise ValidationError(
                            message=f"Subcriterio {j} del criterio {i} no tiene id",
                            field=f"criterios[{i}].subcriterios[{j}].id",
                        )

                    if not sub.get("descripcion"):
                        raise ValidationError(
                            message=f"Subcriterio {j} del criterio {i} no tiene descripcion",
                            field=f"criterios[{i}].subcriterios[{j}].descripcion",
                        )

                    evidencias = sub.get("evidencias", [])
                    if not isinstance(evidencias, list) or len(evidencias) == 0:
                        raise ValidationError(
                            message=f"Subcriterio {j} del criterio {i} debe tener al menos una evidencia",
                            field=f"criterios[{i}].subcriterios[{j}].evidencias",
                        )

            # Validate total peso is 100 (with tolerance of ±1)
            if abs(total_peso - 100) > 1:
                raise ValidationError(
                    message=f"La suma de pesos debe ser 100 (actual: {total_peso})",
                    field="criterios",
                )

            # Ensure puntaje_maximo is set to 100
            rubrica_data["puntaje_maximo"] = 100

            # Validate metadata exists (can be empty)
            if "metadata" not in rubrica_data:
                rubrica_data["metadata"] = {}

            # Validate penalizaciones (optional)
            if "penalizaciones" not in rubrica_data:
                rubrica_data["penalizaciones"] = []

            # Validate condiciones_desaprobacion (optional)
            if "condiciones_desaprobacion" not in rubrica_data:
                rubrica_data["condiciones_desaprobacion"] = []

            return rubrica_data

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(
                message=f"Error parseando respuesta de Gemini: {str(e)}",
                field="gemini_response",
            )
