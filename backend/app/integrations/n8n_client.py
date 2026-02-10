"""
N8N client for triggering AI workflows.

This module provides integration with N8N for:
- Code correction workflows (Gemini evaluation)
- Rubric generation from PDF documents
- Health checks
"""

import httpx
from typing import Any

from app.core.config import settings
from app.core.exceptions import N8NError, N8NTimeoutError


class N8NClient:
    """Client for interacting with N8N webhooks."""

    def __init__(self):
        """Initialize the N8N client with base URL and timeout settings."""
        self.base_url = settings.N8N_BASE_URL
        self.correction_timeout = 90.0  # 90 seconds for corrections
        self.rubric_timeout = 120.0  # 2 minutes for PDF processing
        self.health_timeout = 10.0  # 10 seconds for health checks

    async def trigger_correction(self, payload: dict) -> dict[str, Any]:
        """
        Trigger the correction workflow in N8N.

        Args:
            payload: Dictionary containing:
                - codigo: Consolidated code content
                - rubrica: Rubric with evaluation criteria
                - api_key: User's Gemini API key
                - contexto: Additional context (materia, lenguaje, etc.)

        Returns:
            Dictionary with correction results:
                - success: bool
                - correccion: Correction data (if successful)
                - error: Error details (if failed)

        Raises:
            N8NTimeoutError: If the request times out
            N8NError: For other N8N-related errors
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/webhook/corregir",
                    json=payload,
                    timeout=self.correction_timeout,
                )
                response.raise_for_status()

                # Try to parse JSON response
                try:
                    return response.json()
                except Exception as json_error:
                    # Log the raw response for debugging
                    raise N8NError(
                        f"Error parseando respuesta JSON de N8N. "
                        f"Status: {response.status_code}, "
                        f"Content-Type: {response.headers.get('content-type', 'unknown')}, "
                        f"Body (first 500 chars): {response.text[:500]}"
                    )

            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout esperando respuesta de N8N")

            except httpx.HTTPStatusError as e:
                raise N8NError(f"Error HTTP {e.response.status_code}: {e.response.text}")

            except httpx.RequestError as e:
                raise N8NError(f"Error de conexión: {str(e)}")

    async def trigger_rubric_generation(self, payload: dict) -> dict[str, Any]:
        """
        Trigger the rubric generation workflow from PDF.

        Args:
            payload: Dictionary containing:
                - pdf_base64: Base64-encoded PDF content
                - api_key: User's Gemini API key
                - instrucciones: Instructions for rubric extraction

        Returns:
            Dictionary with rubric generation results:
                - success: bool
                - rubrica: Generated rubric data (if successful)
                - error: Error details (if failed)

        Raises:
            N8NTimeoutError: If the request times out
            N8NError: For other N8N-related errors
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/webhook/generar-rubrica",
                    json=payload,
                    timeout=self.rubric_timeout,
                )
                response.raise_for_status()
                result = response.json()

                # N8N returns an array with a single object, extract it
                if isinstance(result, list) and len(result) > 0:
                    return result[0]

                return result

            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout generando rúbrica desde PDF")

            except httpx.HTTPStatusError as e:
                raise N8NError(f"Error HTTP {e.response.status_code}: {e.response.text}")

            except httpx.RequestError as e:
                raise N8NError(f"Error de conexión: {str(e)}")

    async def health_check(self, api_key: str) -> dict[str, Any]:
        """
        Check N8N and Gemini availability.

        Args:
            api_key: Gemini API key to test

        Returns:
            Dictionary with health status:
                - status: "ok" or "degraded"
                - n8n_version: N8N version
                - gemini_available: bool
                - gemini_error: Error message (if gemini_available is False)
                - timestamp: ISO timestamp

        Raises:
            N8NTimeoutError: If the request times out
            N8NError: For other N8N-related errors
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/webhook/health",
                    json={"api_key": api_key},
                    timeout=self.health_timeout,
                )
                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout en health check de N8N")

            except httpx.HTTPStatusError as e:
                raise N8NError(f"Error HTTP {e.response.status_code}: {e.response.text}")

            except httpx.RequestError as e:
                raise N8NError(f"Error de conexión: {str(e)}")
