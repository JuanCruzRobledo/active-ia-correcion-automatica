# app/schemas/moodle_import.py
"""Schemas para la importación de entregas desde Moodle (Fase 2)."""

from typing import Literal

from pydantic import BaseModel, Field


class ImportarMoodleRequest(BaseModel):
    """Request para importar entregas pendientes desde Moodle.

    - scope="comision_unidad": requiere rubrica_id + comision_id.
    - scope="materia":         requiere materia_id.
    - scope="tutor":           importa todas las pendientes del tutor.
    """

    scope: Literal["comision_unidad", "materia", "tutor"]
    rubrica_id: int | None = Field(None, description="Rúbrica (scope comision_unidad)")
    comision_id: int | None = Field(None, description="Comisión (scope comision_unidad)")
    materia_id: int | None = Field(None, description="Materia (scope materia)")


class ImportErrorItem(BaseModel):
    alumno: str
    motivo: str


class ImportDetalleRubrica(BaseModel):
    rubrica_id: int
    titulo: str
    comision_id: int
    cargadas: int


class ImportarMoodleResponse(BaseModel):
    """Resumen del resultado de la importación."""

    cargadas: int
    duplicadas: int
    omitidas_ya_corregidas: int
    reentregas: int
    sin_archivos: int
    errores: list[ImportErrorItem]
    detalle_por_rubrica: list[ImportDetalleRubrica]
