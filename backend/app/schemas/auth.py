# app/schemas/auth.py
"""
Authentication schemas for Active-IA.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 2
"""

from pydantic import BaseModel, Field, field_validator

from app.models.enums import RolEnum


class LoginRequest(BaseModel):
    """Request body for login endpoint."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nombre de usuario",
        examples=["jperez"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Contraseña del usuario",
    )

    @field_validator("username")
    @classmethod
    def _username_a_minuscula(cls, v: str) -> str:
        # CRUD-009: el login hacía match exacto contra usernames guardados en
        # minúscula, así que quien tipeaba "JPerez" no podía entrar. Normalizar acá
        # hace el login case-insensitive. Verificado en la DB real: 0 usuarios con
        # mayúsculas, así que no rompe ningún acceso existente.
        return v.lower()


class TokenResponse(BaseModel):
    """Response body for successful login."""

    access_token: str = Field(
        ...,
        description="JWT token para autenticación",
    )
    token_type: str = Field(
        default="bearer",
        description="Tipo de token",
    )
    user: "UserInfo" = Field(
        ...,
        description="Información del usuario autenticado",
    )


class UserInfo(BaseModel):
    """Basic user information returned after login."""

    id: int
    username: str
    nombre: str
    rol: RolEnum
    primer_login: bool = Field(
        ...,
        description="True si el usuario debe cambiar su contraseña",
    )
    gemini_api_key_valid: bool = Field(
        default=False,
        description="True si la API Key de Gemini es válida",
    )


class ChangePasswordRequest(BaseModel):
    """Request body for password change."""

    current_password: str = Field(
        ...,
        min_length=1,
        description="Contraseña actual",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="Nueva contraseña (mínimo 8 caracteres)",
    )
    confirm_password: str = Field(
        ...,
        min_length=8,
        description="Confirmación de la nueva contraseña",
    )


class ChangePasswordResponse(BaseModel):
    """Response for successful password change."""

    message: str = Field(
        default="Contraseña actualizada exitosamente",
        description="Mensaje de confirmación",
    )


# Update forward reference
TokenResponse.model_rebuild()
