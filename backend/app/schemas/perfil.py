# app/schemas/perfil.py
"""
Schemas for user profile operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-PERF-01, HU-PERF-02
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import RolEnum


class PerfilResponse(BaseModel):
    """
    User profile response with complete information.

    Includes API Key status (but not the key itself).
    """

    id: int
    username: str
    nombre: str
    rol: RolEnum
    primer_login: bool
    gemini_api_key_valid: bool
    gemini_api_key_last_4: str | None = Field(
        None,
        description="Last 4 characters of API Key if configured",
    )
    moodle_username: str | None = Field(None, description="Usuario Moodle configurado")
    moodle_host: str | None = Field(None, description="Host Moodle configurado")
    moodle_configured: bool = Field(default=False, description="True si tiene credenciales Moodle")
    activo: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None

    class Config:
        from_attributes = True


class UpdateApiKeyRequest(BaseModel):
    """Request to update Gemini API Key."""

    gemini_api_key: str = Field(
        ...,
        min_length=20,
        description="Gemini API Key",
    )


class UpdateApiKeyResponse(BaseModel):
    """Response after updating API Key."""

    message: str
    valid: bool
