# app/schemas/perfil.py
"""
Schemas for user profile operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-PERF-01, HU-PERF-02
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.integrations.ia_provider import (
    PROVIDER_GEMINI,
    PROVIDERS_VALIDOS,
    normalizar_provider,
)
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
    # Modo de corrección elegido: "gemini" (Gemini Studio) | "openrouter".
    correction_provider: str = Field(
        default=PROVIDER_GEMINI,
        description="Proveedor de corrección activo: 'gemini' o 'openrouter'",
    )
    openrouter_api_key_valid: bool = Field(
        default=False,
        description="True si la API key de OpenRouter está configurada y validada",
    )
    openrouter_api_key_last_4: str | None = Field(
        None,
        description="Últimos 4 caracteres de la API key de OpenRouter si está configurada",
    )
    moodle_username: str | None = Field(
        None, description="Usuario Moodle configurado (de la membresía en la universidad activa)"
    )
    moodle_host: str | None = Field(
        None,
        description=(
            "Host Moodle de la universidad activa — READ-ONLY (Fase 3 multi-tenant: "
            "propiedad de la Universidad, no editable desde el perfil)"
        ),
    )
    moodle_configured: bool = Field(
        default=False,
        description="True si la membresía activa tiene credenciales Moodle configuradas",
    )
    activo: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None

    class Config:
        from_attributes = True


class UpdateApiKeyRequest(BaseModel):
    """Request para configurar la API Key de un proveedor de corrección."""

    gemini_api_key: str = Field(
        ...,
        min_length=20,
        description="API Key del proveedor (Gemini Studio u OpenRouter)",
    )
    provider: str = Field(
        default=PROVIDER_GEMINI,
        description="Proveedor al que pertenece la key: 'gemini' o 'openrouter'",
    )

    @field_validator("provider")
    @classmethod
    def _validar_provider(cls, v: str) -> str:
        normalizado = normalizar_provider(v)
        # normalizar_provider nunca falla (cae a gemini), pero si mandan algo
        # explícitamente inválido lo rechazamos para no guardar en el lado equivocado.
        if v and v.strip().lower() not in PROVIDERS_VALIDOS:
            raise ValueError(f"Proveedor inválido: {v}")
        return normalizado


class UpdateApiKeyResponse(BaseModel):
    """Response after updating API Key."""

    message: str
    valid: bool


class DeleteApiKeyResponse(BaseModel):
    """Response tras eliminar la API Key de un proveedor."""

    message: str
    provider: str


class UpdateCorrectionProviderRequest(BaseModel):
    """Request para cambiar el modo de corrección activo (slider del perfil)."""

    provider: str = Field(..., description="Proveedor a activar: 'gemini' o 'openrouter'")

    @field_validator("provider")
    @classmethod
    def _validar_provider(cls, v: str) -> str:
        if v.strip().lower() not in PROVIDERS_VALIDOS:
            raise ValueError(f"Proveedor inválido: {v}")
        return v.strip().lower()


class UpdateCorrectionProviderResponse(BaseModel):
    message: str
    correction_provider: str


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
