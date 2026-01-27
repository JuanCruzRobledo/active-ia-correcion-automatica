# app/services/rubrica_ia_service.py
"""
Rubrica IA service for Active-IA.

Business logic for AI-powered rubrica generation from PDF files.
Handles integration with N8N and Gemini for automatic criteria extraction.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-RUB-02
Ref: docs/specs/10-INTEGRACIONES.md seccion 4.3
"""

from typing import Any

from fastapi import HTTPException, UploadFile, status

from app.core.exceptions import N8NError, N8NTimeoutError, ValidationError
from app.core.security import decrypt_api_key
from app.integrations.n8n_client import N8NClient


class RubricaIAService:
    """Service for AI-powered rubrica generation from PDF."""

    def __init__(self):
        """Initialize rubrica IA service."""
        self.n8n_client = N8NClient()

    async def generar_rubrica_desde_pdf(
        self,
        pdf_file: UploadFile,
        api_key_encrypted: str,
        tipo_rubrica: str = "TP",
    ) -> dict[str, Any]:
        """
        Generate rubrica from PDF file using AI.

        Args:
            pdf_file: Uploaded PDF file with assignment description.
            api_key_encrypted: Encrypted Gemini API key.
            tipo_rubrica: Type of rubrica (TP, PARCIAL_1, etc.). Default: TP.

        Returns:
            Dictionary with rubrica data:
            - nombre_sugerido: Suggested name for the rubrica
            - descripcion: Brief description of the assignment
            - puntaje_maximo: Total points (always 100)
            - criterios: List of evaluation criteria

        Raises:
            HTTPException 400: Invalid file type or missing API key.
            HTTPException 502: N8N/Gemini error.
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

        # Build payload for N8N
        payload = self._build_rubrica_payload(
            pdf_content=pdf_content,
            filename=pdf_file.filename,
            api_key=api_key,
            tipo_rubrica=tipo_rubrica,
        )

        # Call N8N
        try:
            result = await self.n8n_client.trigger_rubric_generation(payload)
        except N8NTimeoutError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Timeout esperando respuesta del servicio de IA (el PDF puede ser muy largo)",
            )
        except N8NError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error en servicio de IA: {str(e)}",
            )

        # Parse and validate response
        try:
            rubrica_data = self._parse_rubrica_response(result)
        except ValidationError as e:
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
        Parse and validate rubrica response from N8N.

        Args:
            response: Raw response from N8N.

        Returns:
            Validated rubrica data.

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

            # Extract rubrica data
            rubrica_data = response.get("rubrica", {})

            # Validate required fields
            if not rubrica_data.get("nombre_sugerido"):
                raise ValidationError(
                    message="Respuesta no contiene nombre sugerido",
                    field="nombre_sugerido",
                )

            if not rubrica_data.get("criterios"):
                raise ValidationError(
                    message="Respuesta no contiene criterios",
                    field="criterios",
                )

            # Validate criterios structure
            criterios = rubrica_data["criterios"]
            if not isinstance(criterios, list) or len(criterios) == 0:
                raise ValidationError(
                    message="Criterios debe ser una lista no vacía",
                    field="criterios",
                )

            # Validate each criterio
            total_puntaje = 0
            for i, criterio in enumerate(criterios):
                if not isinstance(criterio, dict):
                    raise ValidationError(
                        message=f"Criterio {i} no es un objeto válido",
                        field=f"criterios[{i}]",
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

                puntaje = criterio.get("puntaje_maximo")
                if not isinstance(puntaje, (int, float)) or puntaje <= 0:
                    raise ValidationError(
                        message=f"Criterio {i} tiene puntaje inválido",
                        field=f"criterios[{i}].puntaje_maximo",
                    )

                total_puntaje += puntaje

            # Validate total score is 100 (with tolerance)
            if abs(total_puntaje - 100) > 5:
                raise ValidationError(
                    message=f"La suma de puntajes debe ser 100 (actual: {total_puntaje})",
                    field="criterios",
                )

            # Ensure puntaje_maximo is set to 100
            rubrica_data["puntaje_maximo"] = 100

            # Add default description if missing
            if not rubrica_data.get("descripcion"):
                rubrica_data["descripcion"] = ""

            return rubrica_data

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(
                message=f"Error parseando respuesta de Gemini: {str(e)}",
                field="gemini_response",
            )
