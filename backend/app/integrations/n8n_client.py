"""
N8N client for triggering AI workflows.

This module provides integration with N8N for:
- Code correction workflows (Gemini evaluation)
- Rubric generation from PDF documents
- Health checks
"""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import (
    APIKeyInvalidError,
    InsufficientCreditsError,
    ModelOverloadedError,
    N8NError,
    N8NTimeoutError,
    QuotaExceededError,
)
from app.integrations import ia_provider

logger = logging.getLogger(__name__)


class N8NClient:
    """Client for interacting with N8N webhooks."""

    def __init__(self):
        """Initialize the N8N client with base URL and timeout settings."""
        self.base_url = settings.N8N_BASE_URL
        self.correction_timeout = 90.0  # 90 seconds for corrections
        self.rubric_timeout = 120.0  # 2 minutes for PDF processing
        self.health_timeout = 10.0  # 10 seconds for health checks

    async def trigger_correction(
        self, payload: dict, provider: str = "gemini"
    ) -> dict[str, Any]:
        """
        Trigger the correction workflow in N8N.

        Args:
            payload: Dictionary containing:
                - codigo: Consolidated code content
                - rubrica: Rubric with evaluation criteria
                - api_key: User's API key (Gemini Studio or OpenRouter)
                - contexto: Additional context (materia, lenguaje, etc.)
            provider: Proveedor de corrección ("gemini" o "openrouter"). Define
                a qué webhook de n8n se rutea: gemini → /webhook/corregir;
                openrouter → /webhook/corregir-openrouter.

        Returns:
            Dictionary with correction results:
                - success: bool
                - correccion: Correction data (if successful)
                - error: Error details (if failed)

        Raises:
            N8NTimeoutError: If the request times out
            APIKeyInvalidError: If the API key is invalid/expired
            N8NError: For other N8N-related errors
        """
        path = ia_provider.webhook_path(provider)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/webhook/{path}",
                    json=payload,
                    timeout=self.correction_timeout,
                )
                response.raise_for_status()

                # Try to parse JSON response
                try:
                    result = response.json()
                except Exception:
                    raise N8NError(
                        f"Error parseando respuesta JSON de N8N. "
                        f"Status: {response.status_code}, "
                        f"Content-Type: {response.headers.get('content-type', 'unknown')}, "
                        f"Body (first 500 chars): {response.text[:500]}"
                    )

                # Check for Gemini errors in the response body
                # (N8N error branch returns errors as HTTP 200 with error data)
                # N8N wraps webhook responses in an array: [{...}] → unwrap
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]

                self._check_response_body_for_errors(result)

                return result

            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout esperando respuesta de N8N")

            except httpx.HTTPStatusError as e:
                self._check_http_error_for_api_key(e)
                raise N8NError(f"Error HTTP {e.response.status_code}: {e.response.text}")

            except (APIKeyInvalidError, InsufficientCreditsError, QuotaExceededError, ModelOverloadedError, N8NError, N8NTimeoutError):
                # Re-raise our own errors without wrapping
                raise

            except httpx.RequestError as e:
                raise N8NError(f"Error de conexión: {str(e)}")

    async def trigger_correction_pdf(self, payload: dict) -> dict[str, Any]:
        """
        Trigger the PDF correction workflow in N8N.

        Used when the student's submission is a PDF file (e.g., handwritten math
        exercises) instead of source code. Sends the raw PDF in Base64 to a
        dedicated N8N workflow that uses Gemini's vision capabilities.

        Args:
            payload: Dictionary containing:
                - pdf_base64: PDF content encoded in Base64
                - rubrica: Rubric with evaluation criteria
                - api_key: User's Gemini API key
                - contexto: Additional context (materia, alumno)

        Returns:
            Dictionary with correction results (same structure as trigger_correction):
                - success: bool
                - correccion: Correction data (if successful)
                - error: Error details (if failed)

        Raises:
            N8NTimeoutError: If the request times out
            APIKeyInvalidError: If the Gemini API key is invalid/expired
            N8NError: For other N8N-related errors
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/webhook/corregir-pdf",
                    json=payload,
                    timeout=self.correction_timeout,
                )
                response.raise_for_status()

                # Try to parse JSON response
                try:
                    result = response.json()
                    # N8N returns an array with a single object, extract it
                    if isinstance(result, list) and len(result) > 0:
                        result = result[0]
                except Exception:
                    raise N8NError(
                        f"Error parseando respuesta JSON de N8N (corrección PDF). "
                        f"Status: {response.status_code}, "
                        f"Content-Type: {response.headers.get('content-type', 'unknown')}, "
                        f"Body (first 500 chars): {response.text[:500]}"
                    )

                # Check for Gemini errors in the response body
                self._check_response_body_for_errors(result)

                return result

            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout esperando respuesta de N8N (corrección PDF)")

            except httpx.HTTPStatusError as e:
                self._check_http_error_for_api_key(e)
                raise N8NError(f"Error HTTP {e.response.status_code}: {e.response.text}")

            except (APIKeyInvalidError, InsufficientCreditsError, QuotaExceededError, ModelOverloadedError, N8NError, N8NTimeoutError):
                # Re-raise our own errors without wrapping
                raise

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

    def _check_response_body_for_errors(self, result: Any) -> None:
        """
        Check the N8N response body for Gemini API errors.

        N8N returns errors from its error branch as HTTP 200 responses with
        error details embedded in the response body. This handles two formats:

        1. Raw N8N error branch output:
           {"error": {"status": 429, "message": "...", "name": "AxiosError"}}

        2. N8N "Parsear Respuesta" processed output:
           {"success": false, "error": {"code": "GEMINI_ERROR", "message": "Error de Gemini [429]: ..."}}

        Args:
            result: Parsed JSON response from N8N.

        Raises:
            APIKeyInvalidError: If the error indicates an invalid API key.
            N8NError: If a rate-limit (429) or other Gemini error is found.
        """
        if not isinstance(result, dict):
            return

        # Check for error field in the response (N8N error branch output)
        error_data = result.get("error", {})
        if not error_data or not isinstance(error_data, dict):
            return

        # Get error info from either format
        error_status = error_data.get("status", 0)
        error_code = error_data.get("code", "")
        error_message = error_data.get("message", "")
        error_name = error_data.get("name", "")

        logger.warning(
            f"N8N response contains error: status={error_status}, "
            f"code={error_code}, name={error_name}, message={error_message[:200]}"
        )

        error_message_lower = error_message.lower()

        # --- Detect API_KEY_INVALID (Gemini Studio o OpenRouter) ---

        # Check in nested details (raw Gemini error format)
        details = error_data.get("details", [])
        if isinstance(details, list):
            reasons = [d.get("reason", "") for d in details if isinstance(d, dict)]
            if "API_KEY_INVALID" in reasons:
                raise APIKeyInvalidError("API Key inválida o expirada")

        # Patrones de API key inválida. Incluye los de Google (Gemini Studio) y los
        # de OpenRouter (HTTP 401 con textos como "No auth credentials found").
        api_key_patterns = [
            "API_KEY_INVALID",
            "API key expired",
            "API key not valid",
            "API key invalid",
            "PERMISSION_DENIED",
            "[401]",
            "no auth credentials",
            "user not found",
            "invalid api key",
            "no auth credential",
        ]
        for pattern in api_key_patterns:
            if pattern.lower() in error_message_lower:
                raise APIKeyInvalidError(
                    f"API Key inválida o expirada: {error_message}"
                )

        # Check error_code for API key indicators
        if isinstance(error_code, str) and error_code in ("API_KEY_INVALID", "PERMISSION_DENIED"):
            raise APIKeyInvalidError(
                f"API Key inválida o expirada: {error_message}"
            )

        # --- Detect sin créditos (HTTP 402, típico de OpenRouter) ---
        is_no_credits = (
            error_status == 402
            or "[402]" in error_message
            or "insufficient credit" in error_message_lower
            or "requires more credit" in error_message_lower
            or "negative credit" in error_message_lower
        )
        if is_no_credits:
            raise InsufficientCreditsError(
                "La cuenta del proveedor no tiene créditos suficientes."
            )

        # --- Detect model overloaded / high demand (503) ---
        is_overloaded = (
            error_status == 503
            or "[503]" in error_message
            or "status code 503" in error_message_lower
            or "overloaded" in error_message_lower
            or "high demand" in error_message_lower
            or "UNAVAILABLE" in error_message
        )
        if is_overloaded:
            raise ModelOverloadedError(
                "El modelo está sobrecargado. Reintentá en unos minutos."
            )

        # --- Detect rate-limit errors (429) ---
        is_rate_limit = (
            error_status == 429
            or "[429]" in error_message
            or "status code 429" in error_message_lower
            or "429" in str(error_status)
            or "spacing your requests" in error_message_lower
            or (error_code == "GEMINI_ERROR" and "ERR_BAD_REQUEST" in error_message)
        )
        if is_rate_limit:
            raise QuotaExceededError(
                "Límite de uso de la API alcanzado. "
                "Intentá nuevamente en unos minutos."
            )

        # Any other error in the body — raise as N8NError with clear message
        if error_message:
            raise N8NError(f"Error del proveedor de IA: {error_message}")

    def _check_http_error_for_api_key(self, error: httpx.HTTPStatusError) -> None:
        """
        Check if an HTTP error from N8N indicates an invalid Gemini API key.

        This handles the less common case where N8N itself returns a non-200
        HTTP status with Gemini error details in the response body.

        Args:
            error: The HTTP status error from httpx.

        Raises:
            APIKeyInvalidError: If the error indicates an invalid API key.
        """
        try:
            body = error.response.json()
        except Exception:
            try:
                body = json.loads(error.response.text)
            except Exception:
                return

        # Check if the body contains API key error indicators
        if isinstance(body, dict):
            self._check_response_body_for_errors(body)

