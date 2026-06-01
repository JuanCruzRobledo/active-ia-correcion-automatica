# app/schemas/por_entregar.py
"""Schemas para la vista 'Por entregar' (correcciones pendientes de subir a Moodle)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CorreccionPorEntregaResponse(BaseModel):
    """Una corrección lista para devolver al alumno en Moodle."""

    correccion_id: int
    entrega_id: int
    alumno_nombre: str
    materia_id: int
    materia_nombre: str
    comision_id: int
    comision_nombre: str
    rubrica_id: int
    rubrica_titulo: str
    tipo_rubrica: str
    nota: float
    etiqueta_nota: str
    requiere_comentario_tutor: bool
    estado_ultimo_intento: Literal["none", "error"]
    mensaje_error: str | None = None
    corregido_at: datetime | None = None


class PorEntregarResponse(BaseModel):
    """Listado de pendientes de subir + contadores."""

    items: list[CorreccionPorEntregaResponse]
    total_pendientes: int
    total_automaticas: int
    total_requieren_comentario: int
    no_vinculadas: int
