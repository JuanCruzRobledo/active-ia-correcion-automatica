# app/schemas/cierre_cursada.py
"""Schemas para el cierre de cursada (mapeo de ítems del calificador + corridas)."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CategoriaItemCierreEnum, EstadoCierreEnum


class CierreItemSugeridoResponse(BaseModel):
    """Un ítem del calificador de Moodle, con su categoría sugerida o ya confirmada."""

    moodle_cmid: int
    nombre_moodle: str
    orden: int | None
    categoria: CategoriaItemCierreEnum
    unidad: int | None
    opcional: bool
    confirmado: bool = Field(description="True si ya hay una fila guardada para este ítem")


class CierreItemConfirmado(BaseModel):
    """Un ítem tal como lo confirma el coordinador (request de confirmar mapping)."""

    moodle_cmid: int
    nombre_moodle: str
    categoria: CategoriaItemCierreEnum
    unidad: int | None = None
    opcional: bool = False
    orden: int | None = None


class CierreMappingConfirmRequest(BaseModel):
    cuatrimestre_id: int
    items: list[CierreItemConfirmado] = Field(min_length=1)


class CierreMappingConfirmResponse(BaseModel):
    items: list[CierreItemSugeridoResponse]


class GenerarCierreRequest(BaseModel):
    cuatrimestre_id: int
    umbral_tp_pct: float = Field(gt=0, le=100, description="% mínimo de TPs aprobados para no recursar")
    reglas: dict[str, float] | None = Field(
        None,
        description="Override puntual de autoeval_min_pct/parcial_promocion_min_pct/"
        "parcial_regulariza_min_pct/tpi_min_pct — si se omite, usa los defaults",
    )

    @model_validator(mode="after")
    def _validar_reglas_conocidas(self) -> "GenerarCierreRequest":
        claves_validas = {
            "autoeval_min_pct", "parcial_promocion_min_pct",
            "parcial_regulariza_min_pct", "tpi_min_pct",
        }
        if self.reglas and not set(self.reglas).issubset(claves_validas):
            raise ValueError(f"'reglas' solo admite las claves: {sorted(claves_validas)}")
        return self


class CierreRunResponse(BaseModel):
    id: int
    materia_id: int
    cuatrimestre_id: int
    umbral_tp_pct: float
    generado_por_id: int
    total_alumnos: int
    total_promociona: int
    total_regulariza: int
    total_recursa: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CierreHistorialResponse(BaseModel):
    runs: list[CierreRunResponse]
