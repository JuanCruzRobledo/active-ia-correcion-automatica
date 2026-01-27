"""
Custom exceptions for the Active-IA application.

This module defines custom exceptions used throughout the application
for better error handling and API responses.
"""

from typing import Any


class ActiveIAException(Exception):
    """Base exception for all Active-IA custom exceptions."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ActiveIAException):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None):
        details = {"field": field} if field else {}
        super().__init__(message, details)


class UnauthorizedError(ActiveIAException):
    """Raised when authentication fails or token is invalid."""

    pass


class ForbiddenError(ActiveIAException):
    """Raised when user lacks required permissions."""

    pass


class NotFoundError(ActiveIAException):
    """Raised when a requested resource is not found."""

    pass


class ConflictError(ActiveIAException):
    """Raised when a resource conflict occurs (e.g., duplicate username)."""

    pass


# N8N Integration Exceptions


class N8NError(ActiveIAException):
    """Base exception for N8N-related errors."""

    pass


class N8NTimeoutError(N8NError):
    """Raised when an N8N request times out."""

    pass


# Gemini/AI Exceptions


class GeminiError(ActiveIAException):
    """Base exception for Gemini API errors."""

    pass


class APIKeyInvalidError(GeminiError):
    """Raised when a Gemini API key is invalid."""

    pass


class QuotaExceededError(GeminiError):
    """Raised when Gemini API quota is exceeded."""

    pass


# External Service Exceptions


class ExternalServiceError(ActiveIAException):
    """Base exception for external service errors."""

    def __init__(self, service_name: str, message: str):
        super().__init__(f"{service_name}: {message}", {"service": service_name})
