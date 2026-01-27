# app/schemas/materia.py
"""
Materia schemas for Active-IA.

Pydantic models for subject (materia) request/response validation.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 4
Ref: docs/specs/06-MODELO-DATOS.md seccion 3.2
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.usuario import UsuarioListItem


class MateriaBase(BaseModel):
    """Base schema with common materia fields."""

    codigo: str = Field(
        ...,
        min_length=2,
        max_length=20,
        pattern=r"^[A-Z0-9_-]+$",
        description="Código único de la materia (mayúsculas)",
        examples=["PROG1", "PROG2"],
    )
    nombre: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nombre completo de la materia",
        examples=["Programación 1"],
    )


class MateriaCreate(MateriaBase):
    """Schema for creating a new materia."""

    descripcion: str | None = Field(
        None,
        max_length=500,
        description="Descripción opcional de la materia",
    )


class MateriaUpdate(BaseModel):
    """Schema for updating an existing materia.

    All fields are optional - only provided fields will be updated.
    Note: codigo cannot be changed after creation.
    """

    nombre: str | None = Field(
        None,
        min_length=2,
        max_length=100,
        description="Nombre completo de la materia",
    )
    descripcion: str | None = Field(
        None,
        max_length=500,
        description="Descripción de la materia",
    )


class CoordinadorInfo(BaseModel):
    """Reduced info about a coordinator assigned to a materia."""

    id: int
    username: str
    nombre: str
    asignado_en: datetime = Field(
        description="Fecha de asignación como coordinador",
    )

    model_config = {"from_attributes": True}


class MateriaResponse(BaseModel):
    """Schema for materia response (single materia)."""

    id: int
    codigo: str
    nombre: str
    descripcion: str | None = None
    activa: bool = Field(
        description="False si la materia fue eliminada (soft delete)",
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MateriaDetailResponse(MateriaResponse):
    """Schema for detailed materia response with coordinators."""

    coordinadores: list[CoordinadorInfo] = Field(
        default_factory=list,
        description="Lista de coordinadores asignados",
    )


class MateriaListItem(BaseModel):
    """Schema for materia in a list (reduced fields)."""

    id: int
    codigo: str
    nombre: str
    activa: bool
    created_at: datetime
    num_coordinadores: int = Field(
        default=0,
        description="Cantidad de coordinadores asignados",
    )
    num_comisiones: int = Field(
        default=0,
        description="Cantidad de comisiones activas",
    )

    model_config = {"from_attributes": True}


class MateriaList(BaseModel):
    """Schema for paginated list of materias."""

    items: list[MateriaListItem]
    total: int = Field(
        description="Total number of materias matching the filter",
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


class CoordinadoresAssign(BaseModel):
    """Schema for assigning coordinators to a materia."""

    coordinador_ids: list[int] = Field(
        ...,
        min_length=1,
        description="Lista de IDs de coordinadores a asignar",
    )


class CoordinadoresResponse(BaseModel):
    """Response after assigning coordinators."""

    materia_id: int
    coordinadores: list[UsuarioListItem] = Field(
        description="Lista de coordinadores actualmente asignados",
    )
    message: str = Field(
        default="Coordinadores asignados exitosamente",
    )
