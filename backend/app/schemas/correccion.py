"""
Schemas for correction data structures.

This module defines Pydantic schemas for:
- Correction responses (CorreccionResponse)
- Correction updates (CorreccionUpdate)
- Criterion evaluation (CriterioEvaluado)
- Gemini API responses (GeminiResponse, CriterioGeminiSchema)
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime
from decimal import Decimal


class CriterioEvaluado(BaseModel):
    """Schema for an evaluated criterion in a correction."""

    id: str = Field(..., description="Criterion ID from rubric")
    nombre: str = Field(..., description="Criterion name")
    puntaje_obtenido: Decimal = Field(..., ge=0, description="Points obtained")
    puntaje_maximo: Decimal = Field(..., ge=1, description="Maximum points for criterion")
    estado: Literal["OK", "WARNING", "ERROR"] = Field(..., description="Criterion status")
    feedback: str = Field(..., min_length=1, description="Specific feedback for this criterion")


class CriterioGeminiSchema(BaseModel):
    """Schema for parsing criterion evaluation from Gemini response."""

    id: str
    nombre: str
    puntaje_obtenido: int = Field(ge=0)
    puntaje_maximo: int = Field(ge=1)
    estado: Literal["OK", "WARNING", "ERROR"]
    feedback: str = Field(min_length=1)


class GeminiResponse(BaseModel):
    """Schema for parsing complete Gemini API response."""

    nota: int = Field(ge=0, le=100, description="Total grade")
    criterios: list[CriterioGeminiSchema] = Field(..., description="Evaluated criteria")
    fortalezas: list[str] = Field(default_factory=list, description="Strengths identified")
    recomendaciones: list[str] = Field(default_factory=list, description="Recommendations")
    comentario_general: str = Field(..., description="General feedback comment")

    @field_validator('nota')
    @classmethod
    def validate_nota_sum(cls, v, info):
        """Validate that nota matches sum of criteria (with tolerance)."""
        if 'criterios' in info.data:
            suma = sum(c.puntaje_obtenido for c in info.data['criterios'])
            if abs(v - suma) > 1:  # Tolerance of 1 point
                return suma
        return v


class CorreccionResponse(BaseModel):
    """Schema for correction API response."""

    id: int
    entrega_id: int
    nota: Decimal = Field(..., description="Final grade (0-100)")
    criterios: list[CriterioEvaluado] = Field(..., alias="criterios_json", description="Evaluated criteria")
    fortalezas: list[str] = Field(default_factory=list, description="Code strengths")
    recomendaciones: list[str] = Field(default_factory=list, description="Improvement recommendations")
    comentario_general: str = Field(..., description="General pedagogical feedback")
    editado_manualmente: bool = Field(default=False, description="True if manually edited by tutor")
    corregido_por_id: int = Field(..., description="ID of user who corrected/edited")
    created_at: datetime = Field(..., serialization_alias="fecha_correccion", description="Correction date")
    updated_at: datetime = Field(..., description="Last modification date")

    @field_validator('criterios', mode='before')
    @classmethod
    def extract_criterios_from_json(cls, v):
        """Extract criterios array from criterios_json dict if needed."""
        # If coming from SQLAlchemy model, criterios_json is a dict like {"criterios": [...]}
        if isinstance(v, dict) and 'criterios' in v:
            return [CriterioEvaluado(**c) for c in v['criterios']]
        # If already a list, return as is
        return v

    class Config:
        from_attributes = True
        populate_by_name = True


class CorreccionUpdate(BaseModel):
    """Schema for updating an existing correction."""

    nota: Optional[Decimal] = Field(None, ge=0, le=100, description="Final grade")
    criterios: Optional[list[CriterioEvaluado]] = Field(None, description="Updated criteria")
    fortalezas: Optional[list[str]] = Field(None, description="Updated strengths")
    recomendaciones: Optional[list[str]] = Field(None, description="Updated recommendations")
    comentario_general: Optional[str] = Field(None, description="Updated general comment")

    @field_validator('criterios')
    @classmethod
    def validate_criterios_sum(cls, v):
        """Validate that criteria sum to 100 if provided."""
        if v is not None:
            suma = sum(c.puntaje_obtenido for c in v)
            if abs(suma - 100) > 1:  # Tolerance of 1 point
                raise ValueError(f"La suma de puntajes debe ser 100, es {suma}")
        return v


class CorreccionCreate(BaseModel):
    """Schema for creating a correction (rarely used, mostly AI-generated)."""

    entrega_id: int = Field(..., description="ID of the submission")
    nota: Decimal = Field(..., ge=0, le=100, description="Final grade")
    criterios: list[CriterioEvaluado] = Field(..., description="Evaluated criteria")
    fortalezas: list[str] = Field(default_factory=list, description="Code strengths")
    recomendaciones: list[str] = Field(default_factory=list, description="Recommendations")
    comentario_general: str = Field(..., description="General feedback")
    corregido_por_id: int = Field(..., description="ID of user who corrected")
    raw_response: Optional[dict] = Field(None, description="Raw Gemini API response")

    @field_validator('criterios')
    @classmethod
    def validate_criterios_sum(cls, v, info):
        """Validate that sum of puntaje_obtenido matches nota."""
        if 'nota' not in info.data:
            return v

        nota = float(info.data['nota'])
        suma = sum(float(c.puntaje_obtenido) for c in v)

        if abs(suma - nota) > 1:  # Tolerance of 1 point
            raise ValueError(
                f"La suma de puntajes obtenidos ({suma}) debe ser igual a la nota ({nota})"
            )
        return v


class CorreccionListItem(BaseModel):
    """Schema for correction list items (lightweight)."""

    id: int
    entrega_id: int
    nota: Decimal
    editado_manualmente: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CorregirLoteRequest(BaseModel):
    """Schema for batch correction request."""

    entrega_ids: list[int] = Field(..., min_length=1, max_length=50, description="IDs of submissions to correct")


class CorregirLoteResponse(BaseModel):
    """Schema for batch correction response."""

    total: int = Field(..., description="Total submissions requested")
    exitosas: int = Field(..., description="Successfully corrected")
    fallidas: int = Field(..., description="Failed corrections")
    correcciones: list[CorreccionResponse] = Field(default_factory=list, description="Successful corrections")
    errores: list[dict] = Field(default_factory=list, description="Error details for failed corrections")
