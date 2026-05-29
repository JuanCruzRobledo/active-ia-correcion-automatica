# app/schemas/moodle_grade.py
"""Schemas para subir corrección + devolución a Moodle (Fase 3)."""

from pydantic import BaseModel, Field


class PreviewCorreccionMoodleResponse(BaseModel):
    """Datos para el modal de 'Subir corrección a Moodle' (antes de enviar)."""

    nota_a_enviar: str = Field(..., description="Nota tal como irá a Moodle (Aprobado/Desaprobado o número)")
    nota_activeia: float = Field(..., description="Nota 0-100 vigente en Active-IA")
    comentario_sugerido: str = Field(..., description="Comentario propuesto (editable)")
    requiere_comentario_tutor: bool = Field(..., description="True si el tutor debe escribir su comentario (no-TP)")
    link_devolucion: str = Field(..., description="Link público al PDF de devolución")
    ya_enviada: bool = Field(..., description="True si ya se envió antes (reenvío requiere forzar)")


class SubirCorreccionMoodleRequest(BaseModel):
    comentario: str = Field(..., description="Comentario final a publicar en Moodle")
    forzar: bool = Field(False, description="Reenviar aunque ya se haya enviado")


class SubirCorreccionMoodleResponse(BaseModel):
    estado: str
    nota_enviada: str | None = None
    intento: int
