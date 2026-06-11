# app/schemas/perfil.py
"""
Schemas for user profile operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-PERF-01, HU-PERF-02
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import RolEnum

# Validación simple de email (evita la dependencia email-validator).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PerfilResponse(BaseModel):
    """
    User profile response with complete information.

    Includes API Key status (but not the key itself).
    """

    id: int
    username: str
    nombre: str
    email: str | None = Field(None, description="Email donde el usuario recibe notificaciones")
    rol: RolEnum
    primer_login: bool
    gemini_api_key_valid: bool
    gemini_api_key_last_4: str | None = Field(
        None,
        description="Last 4 characters of API Key if configured",
    )
    gemini_api_key_paga: bool = Field(
        default=False,
        description="Toggle manual: la API key tiene facturación habilitada (habilita 'Corregir todo')",
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


class UpdateKeyPagaRequest(BaseModel):
    """Toggle manual: marcar la API key como paga (con facturación habilitada)."""

    paga: bool


class UpdateKeyPagaResponse(BaseModel):
    message: str
    gemini_api_key_paga: bool


class UpdateEmailRequest(BaseModel):
    """Setea (o limpia) el email de notificaciones del usuario."""

    email: str | None = Field(
        None, description="Email para recibir notificaciones (vacío para quitarlo)"
    )

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None  # permite quitar el email
        if not _EMAIL_RE.match(v):
            raise ValueError("Email inválido")
        return v


class UpdateEmailResponse(BaseModel):
    message: str
    email: str | None
