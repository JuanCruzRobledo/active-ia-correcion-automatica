"""
Dashboard schemas for statistics responses.

Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard designs
"""

from datetime import datetime
from pydantic import BaseModel, Field


# Admin Dashboard Schemas
class AdminStatsResponse(BaseModel):
    """Admin dashboard statistics."""

    materias: int = Field(..., description="Total active materias")
    comisiones: int = Field(..., description="Total active comisiones")
    usuarios: int = Field(..., description="Total active usuarios")
    rubricas: int = Field(..., description="Total active rubricas")

    model_config = {"from_attributes": True}


# Coordinador Dashboard Schemas
class CorrectionProgressItem(BaseModel):
    """Progress of corrections for a single comision."""

    id: int
    comision: str = Field(..., description="Comision name (e.g., 'Prog1 - Comisión A')")
    tutor: str = Field(..., description="Tutor name")
    completed: int = Field(..., description="Number of corrected entregas")
    total: int = Field(..., description="Total number of entregas")
    last_activity: datetime | None = Field(None, description="Last correction timestamp")

    model_config = {"from_attributes": True}


class CoordinadorStatsResponse(BaseModel):
    """Coordinador dashboard statistics."""

    comisiones: int = Field(..., description="Total comisiones assigned to coordinador")
    rubricas: int = Field(..., description="Total rubricas for coordinador's materias")
    pendientes: int = Field(..., description="Total pending entregas across all comisiones")
    corrections_progress: list[CorrectionProgressItem] = Field(
        default_factory=list, description="Progress per comision"
    )

    model_config = {"from_attributes": True}


# Tutor Dashboard Schemas
class ComisionDetailItem(BaseModel):
    """Detail of a single comision for tutor dashboard."""

    id: int
    nombre: str = Field(..., description="Materia name")
    comision: str = Field(..., description="Comision name with year")
    alumnos: int = Field(..., description="Total number of students")
    pendientes: int = Field(..., description="Number of pending entregas")

    model_config = {"from_attributes": True}


class TutorStatsResponse(BaseModel):
    """Tutor dashboard statistics."""

    comisiones: int = Field(..., description="Total comisiones assigned to tutor")
    pendientes: int = Field(..., description="Total pending entregas")
    corregidas: int = Field(..., description="Total corrected entregas")
    comisiones_details: list[ComisionDetailItem] = Field(
        default_factory=list, description="Details of each comision"
    )

    model_config = {"from_attributes": True}

