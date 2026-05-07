# app/schemas/pendientes.py
"""Schemas para el endpoint GET /api/pendientes/moodle."""

from pydantic import BaseModel


class ComisionPendiente(BaseModel):
    id: int
    nombre: str
    codigo: str
    groupId: int | None
    espera: int
    corregidos: int
    sinEntrega: int
    moodleGraderUrl: str | None = None


class UnidadPendiente(BaseModel):
    id: int
    titulo: str
    subtitulo: str
    cmid: int | None
    espera: int
    corregidos: int
    sinEntrega: int
    comisiones: list[ComisionPendiente]


class MateriaPendiente(BaseModel):
    id: int
    nombre: str
    totalEspera: int
    totalCorregidos: int
    totalSinEntrega: int
    unidades: list[UnidadPendiente]


class MateriasPendientesResponse(BaseModel):
    materias: list[MateriaPendiente]
