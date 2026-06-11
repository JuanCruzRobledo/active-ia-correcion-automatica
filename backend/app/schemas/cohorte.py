# app/schemas/cohorte.py
"""
Pydantic schemas for Cohorte and Cuatrimestre (Dashboard de Gestores).

Ref: PLAN_DASHBOARD_GESTORES.md §5, §8 (T2)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ===================== Cuatrimestre =====================


class CuatrimestreCreate(BaseModel):
    """Datos para crear un cuatrimestre dentro de una cohorte."""

    numero: int = Field(..., ge=1, le=4, description="Número de cuatrimestre (1..4)")
    nombre: str | None = Field(None, max_length=50)


class CuatrimestreUpdate(BaseModel):
    """Datos para actualizar un cuatrimestre (campos opcionales)."""

    numero: int | None = Field(None, ge=1, le=4)
    nombre: str | None = Field(None, max_length=50)


class CuatrimestreResponse(BaseModel):
    """Cuatrimestre serializado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cohorte_id: int
    numero: int
    nombre: str | None = None


# ===================== Cohorte =====================


class CohorteCreate(BaseModel):
    """Datos para crear una cohorte."""

    codigo: str = Field(..., min_length=1, max_length=10, description="Ej: 'M25', 'A26'")
    nombre: str | None = Field(None, max_length=50)

    @field_validator("codigo")
    @classmethod
    def _codigo_upper(cls, v: str) -> str:
        return v.strip().upper()


class CohorteUpdate(BaseModel):
    """Datos para actualizar una cohorte (campos opcionales)."""

    nombre: str | None = Field(None, max_length=50)
    activa: bool | None = None


class CohorteResponse(BaseModel):
    """Cohorte serializada (sin cuatrimestres)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str | None = None
    activa: bool
    created_at: datetime


class CohorteDetailResponse(BaseModel):
    """Cohorte con sus cuatrimestres anidados (para los selectores del dashboard)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str | None = None
    activa: bool
    created_at: datetime
    cuatrimestres: list[CuatrimestreResponse] = []
