# app/schemas/auth.py
"""
Authentication schemas for Active-IA.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 2
"""

from typing import Literal

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
    """Basic user information returned after login.

    Fase 1 multi-tenant (multi-tenant-auth-jwt): `rol` deja de reflejar el rol
    global `usuarios.rol` y pasa a reflejar el rol del usuario EN LA
    UNIVERSIDAD ACTIVA (`usuario_universidad.rol`). Es `None` únicamente para
    un superadmin que todavía no eligió universidad.
    """

    id: int
    username: str
    nombre: str
    rol: RolEnum | None = Field(
        default=None,
        description="Rol del usuario en la universidad activa. None solo en "
        "modo superadmin sin universidad elegida.",
    )
    primer_login: bool = Field(
        ...,
        description="True si el usuario debe cambiar su contraseña",
    )
    gemini_api_key_valid: bool = Field(
        default=False,
        description="True si la API Key de Gemini es válida",
    )
    universidad_activa_id: int | None = Field(
        default=None,
        description="Universidad en la que el usuario está operando. None "
        "solo en modo superadmin sin universidad elegida.",
    )
    es_superadmin: bool = Field(
        default=False,
        description="True si el usuario es admin global (bypass multi-tenant).",
    )


class UniversidadDisponible(BaseModel):
    """Una opción del selector de universidad (login en dos pasos)."""

    id: int = Field(..., description="ID de la universidad")
    nombre: str = Field(..., description="Nombre de la universidad")
    rol: RolEnum = Field(
        ...,
        description="Rol del usuario en esa universidad (de su membresía activa)",
    )


class SeleccionarUniversidadRequest(BaseModel):
    """Request body para POST /auth/select-universidad y /auth/switch-universidad.

    Fase 5 multi-tenant (D6): `universidad_id` acepta `None` para el modo
    global del superadmin ("Todas las universidades"). Sólo válido para
    `POST /auth/switch-universidad` con un usuario `es_superadmin`; un
    no-superadmin que lo intenta recibe 403 (no existe "modo global" fuera
    del superadmin).
    """

    universidad_id: int | None = Field(
        ...,
        description="ID de la universidad a seleccionar/activar. `null` sólo "
        "para el modo global del superadmin en switch-universidad.",
    )


class SeleccionUniversidadRequerida(BaseModel):
    """Respuesta intermedia de login cuando el usuario tiene 2+ membresías activas.

    NO incluye `access_token`: el cliente debe llamar a
    POST /auth/select-universidad con la universidad elegida para obtener el
    token final.
    """

    requiere_seleccion: Literal[True] = Field(
        default=True,
        description="Marca que la respuesta requiere un segundo paso de selección",
    )
    universidades: list[UniversidadDisponible] = Field(
        ...,
        description="Universidades donde el usuario tiene membresía activa",
    )
    token_transicion: str = Field(
        ...,
        description="Token corto (no es el access_token final) para identificar "
        "al usuario en POST /auth/select-universidad",
    )


# Respuesta de POST /auth/login: o el token final (0/1 universidad, o
# superadmin), o la respuesta intermedia que pide elegir universidad (2+
# membresías activas). Discriminada en runtime por la presencia de
# `requiere_seleccion` (D4: se resuelve la mecánica Pydantic en apply).
LoginResponse = TokenResponse | SeleccionUniversidadRequerida


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
