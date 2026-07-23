# app/schemas/universidad.py
"""
Universidad schemas for Active-IA — Fase 5 multi-tenant (multi-tenant-frontend-workspace).

Pydantic models para el listado propio (`GET /universidades/mias`, D5) y el
ABM de superadmin (`GET/POST/PUT/DELETE /universidades`, D7).

Ref: openspec/changes/multi-tenant-frontend-workspace/specs/universidades-abm/spec.md
Ref: openspec/changes/multi-tenant-frontend-workspace/design.md (D5, D7)
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import RolEnum


class UniversidadResponse(BaseModel):
    """Universidad completa (detalle de una creación/edición del ABM)."""

    id: int
    nombre: str
    moodle_host: str | None = None
    activa: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UniversidadListItem(BaseModel):
    """Item reducido para el listado paginado del ABM."""

    id: int
    nombre: str
    moodle_host: str | None = None
    activa: bool

    class Config:
        from_attributes = True


class UniversidadList(BaseModel):
    """Listado paginado de universidades (ABM de superadmin)."""

    items: list[UniversidadListItem]
    total: int = Field(description="Total de universidades que matchean el filtro")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=1000)


class UniversidadCreate(BaseModel):
    """Alta de universidad (superadmin). `activa=True` siempre al crear."""

    nombre: str = Field(..., min_length=1, max_length=200)
    moodle_host: str | None = Field(default=None, max_length=255)


class UniversidadUpdate(BaseModel):
    """Edición de universidad (superadmin). Todos los campos opcionales (PATCH-like)."""

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    moodle_host: str | None = Field(default=None, max_length=255)
    activa: bool | None = None


class UniversidadPropia(BaseModel):
    """
    Una universidad del selector propio del usuario autenticado (D5).

    `GET /universidades/mias` monta SÓLO autenticación (nunca
    `get_universidad_activa`, ver D5): es el endpoint que alimenta el
    selector, incluyendo el momento en que todavía no hay universidad activa.
    """

    id: int = Field(..., description="ID de la universidad")
    nombre: str = Field(..., description="Nombre de la universidad")
    rol: RolEnum = Field(
        ...,
        description="Rol del usuario en esa universidad (ADMIN sintético para superadmin)",
    )
