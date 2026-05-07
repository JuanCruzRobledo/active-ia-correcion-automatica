# app/schemas/comision.py
"""
Comision schemas for Active-IA.

Pydantic models for commission (comision) request/response validation.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 5
Ref: docs/specs/06-MODELO-DATOS.md seccion 3.4, 3.5
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.usuario import UsuarioListItem


class ComisionBase(BaseModel):
    """Base schema with common comision fields."""

    nombre: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Nombre de la comisión",
        examples=["Comisión A", "Turno Mañana"],
    )
    anio: int = Field(
        ...,
        ge=2020,
        le=2100,
        description="Año académico de la comisión",
        examples=[2026],
    )


class ComisionCreate(ComisionBase):
    """Schema for creating a new comision."""

    materia_id: int = Field(
        ...,
        gt=0,
        description="ID de la materia a la que pertenece la comisión",
    )
    tutor_ids: list[int] = Field(
        default_factory=list,
        description="IDs de tutores a asignar (opcional)",
    )


class ComisionUpdate(BaseModel):
    """Schema for updating an existing comision.

    All fields are optional - only provided fields will be updated.
    Note: materia_id and anio cannot be changed after creation.
    """

    nombre: str | None = Field(
        None,
        min_length=1,
        max_length=50,
        description="Nombre de la comisión",
    )
    tutor_ids: list[int] | None = Field(
        None,
        description="IDs de tutores a asignar (reemplaza asignaciones existentes)",
    )
    moodle_group_id: int | None = Field(
        None,
        description="ID del grupo en Moodle",
    )
    moodle_group_code: str | None = Field(
        None,
        max_length=50,
        description="Código del grupo Moodle (groupsearchvalue)",
    )


class TutorInfo(BaseModel):
    """Reduced info about a tutor assigned to a comision."""

    id: int
    username: str
    nombre: str
    asignado_en: datetime = Field(
        description="Fecha de asignación como tutor",
    )

    model_config = {"from_attributes": True}


class MateriaInfo(BaseModel):
    """Reduced info about the materia of a comision."""

    id: int
    codigo: str
    nombre: str

    model_config = {"from_attributes": True}


class ComisionResponse(BaseModel):
    """Schema for comision response (single comision)."""

    id: int
    materia_id: int
    nombre: str
    anio: int
    activa: bool = Field(
        description="False si la comisión fue eliminada (soft delete)",
    )
    moodle_group_id: int | None = None
    moodle_group_code: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ComisionDetailResponse(ComisionResponse):
    """Schema for detailed comision response with materia and tutors."""

    materia: MateriaInfo = Field(
        description="Información de la materia",
    )
    tutores: list[TutorInfo] = Field(
        default_factory=list,
        description="Lista de tutores asignados",
    )


class ComisionListItem(BaseModel):
    """Schema for comision in a list (reduced fields)."""

    id: int
    materia_id: int
    materia_nombre: str = Field(
        description="Nombre de la materia",
    )
    materia_codigo: str = Field(
        description="Código de la materia",
    )
    nombre: str
    anio: int
    activa: bool
    created_at: datetime
    num_tutores: int = Field(
        default=0,
        description="Cantidad de tutores asignados",
    )
    num_entregas: int = Field(
        default=0,
        description="Cantidad de entregas activas",
    )

    model_config = {"from_attributes": True}


class ComisionList(BaseModel):
    """Schema for paginated list of comisiones."""

    items: list[ComisionListItem]
    total: int = Field(
        description="Total number of comisiones matching the filter",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Current page number",
    )
    per_page: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
    )


class TutoresAssign(BaseModel):
    """Schema for assigning tutors to a comision."""

    tutor_ids: list[int] = Field(
        ...,
        min_length=1,
        description="Lista de IDs de tutores a asignar",
    )


class TutoresResponse(BaseModel):
    """Response after assigning tutors."""

    comision_id: int
    tutores: list[UsuarioListItem] = Field(
        description="Lista de tutores actualmente asignados",
    )
    message: str = Field(
        default="Tutores asignados exitosamente",
    )
