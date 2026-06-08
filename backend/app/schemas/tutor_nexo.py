# app/schemas/tutor_nexo.py
"""
Pydantic schemas para TutorNexo (notificaciones por email).

Ref: PLAN_NOTIFICACIONES_EMAIL.md §4.2, §5.4 (T7)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validar_email(v: str) -> str:
    v = (v or "").strip()
    if "@" not in v or "." not in v.split("@")[-1]:
        raise ValueError("Email inválido")
    return v


class TutorNexoCreate(BaseModel):
    """Datos para dar de alta un tutor nexo."""

    nombre: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., max_length=150)
    regional: str = Field(
        ..., min_length=1, max_length=120,
        description="Nombre de la regional SIN 'R-' (ej: 'Mendoza'), como lo deriva el snapshot",
    )

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _validar_email(v)


class TutorNexoUpdate(BaseModel):
    """Actualización parcial de un tutor nexo."""

    nombre: str | None = Field(None, min_length=2, max_length=150)
    email: str | None = Field(None, max_length=150)
    regional: str | None = Field(None, min_length=1, max_length=120)
    activo: bool | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return _validar_email(v) if v is not None else None


class TutorNexoResponse(BaseModel):
    """Tutor nexo serializado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    regional: str
    activo: bool
    created_at: datetime
