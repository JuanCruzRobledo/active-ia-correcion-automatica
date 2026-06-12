# app/schemas/unidad.py
"""
Pydantic schemas for Unidad y configuración de dashboard de la Materia.

Ref: PLAN_DASHBOARD_GESTORES.md §5, §8 (T3)
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    FuenteComponenteEnum,
    ModoAprobacionEnum,
    TipoComponenteEnum,
)


# ===================== Componentes de la unidad (§9.bis F) =====================


class ComponenteUnidadInput(BaseModel):
    """Un componente evaluable a vincular: tipo (etiqueta) + cmid + fuente de verdad.

    Si fuente=CALIFICACION se puede elegir cómo se interpreta la nota (modo_aprobacion):
    ESCALA (Aprobado/Desaprobado) o NUMERICO (nota >= nota_minima). NUMERICO exige nota_minima.
    """

    tipo: TipoComponenteEnum
    moodle_cmid: int = Field(..., description="cmid de la actividad de Moodle")
    fuente: FuenteComponenteEnum = Field(
        ..., description="SEGUIMIENTO (completion) | CALIFICACION (nota)"
    )
    modo_aprobacion: ModoAprobacionEnum = Field(
        ModoAprobacionEnum.ESCALA,
        description="ESCALA | NUMERICO (solo aplica si fuente=CALIFICACION)",
    )
    nota_minima: float | None = Field(
        None,
        ge=0,
        description="Nota mínima para aprobar si modo_aprobacion=NUMERICO (escala de Moodle)",
    )

    @model_validator(mode="after")
    def _validar_nota_minima(self) -> "ComponenteUnidadInput":
        """En modo NUMERICO la nota mínima es obligatoria (sin umbral no se puede decidir)."""
        if (
            self.fuente == FuenteComponenteEnum.CALIFICACION
            and self.modo_aprobacion == ModoAprobacionEnum.NUMERICO
            and self.nota_minima is None
        ):
            raise ValueError(
                "Un componente por calificación NUMERICO requiere una nota mínima"
            )
        return self


class ComponenteUnidadResponse(BaseModel):
    """Componente evaluable serializado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoComponenteEnum
    moodle_cmid: int
    fuente: FuenteComponenteEnum
    modo_aprobacion: ModoAprobacionEnum
    nota_minima: float | None = None
    orden: int


# ===================== Unidad =====================


class UnidadCreate(BaseModel):
    """Datos para crear una unidad (anclada a la sección cabecera de Moodle)."""

    numero: int = Field(..., ge=1, description="Número de unidad (1..N)")
    moodle_section_id: int = Field(..., description="ID de la sección CABECERA en Moodle")
    nombre: str | None = Field(None, max_length=200)


class UnidadUpdate(BaseModel):
    """Datos para actualizar una unidad (campos opcionales)."""

    numero: int | None = Field(None, ge=1)
    moodle_section_id: int | None = None
    nombre: str | None = Field(None, max_length=200)


class UnidadResponse(BaseModel):
    """Unidad serializada, con sus componentes evaluables."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    materia_id: int
    numero: int
    moodle_section_id: int
    nombre: str | None = None
    componentes: list[ComponenteUnidadResponse] = []


class UnidadComponentesUpdate(BaseModel):
    """Reemplaza el set completo de componentes evaluables de una unidad. §9.bis F."""

    componentes: list[ComponenteUnidadInput] = []


class MoodleActividadItem(BaseModel):
    """Una actividad de Moodle candidata a componente de la unidad.

    `tiene_seguimiento` False = sin seguimiento de finalización → conviene medirla
    por CALIFICACIÓN (no por seguimiento), o no podrá detectarse como realizada (E7).
    """

    cmid: int
    nombre: str
    modname: str
    tiene_seguimiento: bool = True


# ===================== Config dashboard de la Materia =====================


class MateriaDashboardConfig(BaseModel):
    """Configuración de la materia para el dashboard de gestores (PUT, valores explícitos)."""

    cuatrimestre_id: int | None = Field(None, description="Cuatrimestre al que pertenece (null = desvincular)")
    unidad_actual: int | None = Field(None, ge=1, description="Unidad que se está cursando")
    moodle_section_fin_id: int | None = Field(
        None,
        description="1ª sección de Moodle que YA NO es unidad (tope; actividades posteriores no cuentan)",
    )
    etiqueta_unidad: str = Field(
        "Unidad",
        max_length=20,
        description="Cómo se llama la progresión en los reportes: 'Unidad' o 'Semana'",
    )
    riesgo_medio_desde: int = Field(
        1,
        ge=1,
        description="Atraso (en unidades/semanas) a partir del cual el alumno entra en riesgo medio",
    )
    riesgo_alto_desde: int = Field(
        2,
        ge=2,
        description="Atraso a partir del cual entra en riesgo alto (debe ser > riesgo_medio_desde)",
    )

    @model_validator(mode="after")
    def _validar_umbrales(self) -> "MateriaDashboardConfig":
        """El umbral de riesgo alto debe ser estrictamente mayor que el de riesgo medio:
        si fueran iguales no existiría la franja de riesgo medio."""
        if self.riesgo_alto_desde <= self.riesgo_medio_desde:
            raise ValueError(
                "El umbral de riesgo alto debe ser mayor que el de riesgo medio"
            )
        return self


class MateriaDashboardConfigResponse(BaseModel):
    """Estado de la config de dashboard de una materia."""

    materia_id: int
    cuatrimestre_id: int | None = None
    unidad_actual: int | None = None
    moodle_section_fin_id: int | None = None
    etiqueta_unidad: str = "Unidad"
    riesgo_medio_desde: int = 1
    riesgo_alto_desde: int = 2


# ===================== Vínculo Rúbrica → Unidad =====================


class RubricaUnidadAssign(BaseModel):
    """Asigna (o desvincula) la unidad de una rúbrica."""

    unidad_id: int | None = Field(None, description="ID de la unidad, o null para desvincular")


# ===================== Auto-sugerencia de secciones (Moodle) =====================


class MoodleSeccionItem(BaseModel):
    """Una sección del curso de Moodle, con la sugerencia de si es cabecera de unidad."""

    moodle_section_id: int
    section: int = Field(..., description="Orden visual de la sección en Moodle (section#)")
    nombre: str
    es_cabecera_sugerida: bool
    numero_sugerido: int | None = None


class MoodleSeccionesSugeridas(BaseModel):
    """Secciones del curso + cabeceras de unidad auto-detectadas (patrón 'N- Tema')."""

    materia_id: int
    moodle_course_id: int
    secciones: list[MoodleSeccionItem]
    cabeceras_sugeridas: list[UnidadCreate]


# ===================== Sincronización de unidades (selección con checks) =====================


class SeccionUnidadInput(BaseModel):
    """Una sección elegida como unidad. El ORDEN en la lista define el número de unidad."""

    moodle_section_id: int
    nombre: str | None = None


class UnidadesSyncRequest(BaseModel):
    """Reemplaza el set de unidades de la materia por las secciones tildadas (en orden)."""

    secciones: list[SeccionUnidadInput]
