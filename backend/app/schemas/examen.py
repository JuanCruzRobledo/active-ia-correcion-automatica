# app/schemas/examen.py
"""
Pydantic schemas para el seguimiento de exámenes de una materia.

ABM incremental (CRUD por examen, NO reemplazo total) para que `recupera_examen_id`
apunte a ids ESTABLES de parciales ya dados de alta. El número visible ("Parcial 2")
se DERIVA en el response (no se persiste).
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ModoAprobacionEnum, TipoExamenEnum

# Tipos cuyo resultado se rescata vinculándose a un PARCIAL.
TIPOS_RESCATE = {
    TipoExamenEnum.RECUPERATORIO,
    TipoExamenEnum.EXTENSION,
    TipoExamenEnum.EXTRAORDINARIA,
}


class ExamenMateriaCreate(BaseModel):
    """Alta de un examen. La numeración por tipo la asigna el backend (derivada)."""

    tipo: TipoExamenEnum
    moodle_cmid: int = Field(..., description="cmid de la actividad de Moodle del examen")
    modo_aprobacion: ModoAprobacionEnum
    nota_minima: float | None = Field(
        None, description="Mínimo para aprobar (requerido si modo NUMERICO)"
    )
    recupera_examen_id: int | None = Field(
        None, description="PARCIAL que recupera (requerido para recu/ext/extraordinaria)"
    )

    @model_validator(mode="after")
    def _validar_coherencia(self) -> "ExamenMateriaCreate":
        if self.modo_aprobacion == ModoAprobacionEnum.NUMERICO and self.nota_minima is None:
            raise ValueError("nota_minima es requerida cuando el modo es NUMERICO")
        if self.tipo in TIPOS_RESCATE and self.recupera_examen_id is None:
            raise ValueError(
                "recuperatorio/extensión/extraordinaria deben vincularse a un parcial"
            )
        if self.tipo not in TIPOS_RESCATE and self.recupera_examen_id is not None:
            raise ValueError("solo recu/ext/extraordinaria pueden recuperar a un parcial")
        return self


class ExamenMateriaUpdate(BaseModel):
    """Edición de un examen (mismos campos que el alta)."""

    tipo: TipoExamenEnum
    moodle_cmid: int
    modo_aprobacion: ModoAprobacionEnum
    nota_minima: float | None = None
    recupera_examen_id: int | None = None

    @model_validator(mode="after")
    def _validar_coherencia(self) -> "ExamenMateriaUpdate":
        if self.modo_aprobacion == ModoAprobacionEnum.NUMERICO and self.nota_minima is None:
            raise ValueError("nota_minima es requerida cuando el modo es NUMERICO")
        if self.tipo in TIPOS_RESCATE and self.recupera_examen_id is None:
            raise ValueError(
                "recuperatorio/extensión/extraordinaria deben vincularse a un parcial"
            )
        if self.tipo not in TIPOS_RESCATE and self.recupera_examen_id is not None:
            raise ValueError("solo recu/ext/extraordinaria pueden recuperar a un parcial")
        return self


class ExamenMateriaResponse(BaseModel):
    """Examen serializado, con número y etiqueta derivados ('Parcial 2')."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    materia_id: int
    tipo: TipoExamenEnum
    numero: int = Field(..., description="Número derivado por tipo (Parcial 1, 2…)")
    etiqueta: str = Field(..., description="Etiqueta visible, ej. 'Parcial 2'")
    moodle_cmid: int
    modo_aprobacion: ModoAprobacionEnum
    nota_minima: float | None = None
    recupera_examen_id: int | None = None
    orden: int
