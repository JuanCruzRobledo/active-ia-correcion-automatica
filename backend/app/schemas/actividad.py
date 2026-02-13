# app/schemas/actividad.py
"""
Pydantic schemas for Actividad (Activity/Audit) model.

Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoActividadEnum


class ActividadBase(BaseModel):
    """Base schema para Actividad."""

    tipo: TipoActividadEnum
    descripcion: str = Field(..., max_length=500)
    entidad_id: int
    entidad_nombre: str = Field(..., max_length=255)


class ActividadCreate(ActividadBase):
    """Schema para crear una actividad."""

    usuario_id: int | None = None
    metadatos: str | None = None


class ActividadResponse(ActividadBase):
    """Schema para respuesta de actividad."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    created_at: datetime

    # Datos del usuario que realizó la acción (opcional)
    usuario_nombre: str | None = None
    usuario_rol: str | None = None


class ActividadListResponse(BaseModel):
    """Schema para lista de actividades."""

    items: list[ActividadResponse]
    total: int
