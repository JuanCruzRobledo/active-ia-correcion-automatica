# app/schemas/cierre_cursada.py
"""Schemas para el cierre de cursada (corridas dirigidas por ExamenMateria)."""

from datetime import datetime

from pydantic import BaseModel


class GenerarCierreRequest(BaseModel):
    cuatrimestre_id: int


class CierreRunResponse(BaseModel):
    id: int
    materia_id: int
    cuatrimestre_id: int
    umbral_tp_pct: float | None = None
    generado_por_id: int
    total_alumnos: int
    total_promociona: int
    total_regulariza: int
    total_recursa: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CierreHistorialResponse(BaseModel):
    runs: list[CierreRunResponse]
