"""
Schemas for correction data structures.

This module defines Pydantic schemas for:
- Correction responses (CorreccionResponse)
- Correction updates (CorreccionUpdate)
- Criterion evaluation (CriterioEvaluado)
- Gemini API responses (GeminiResponse, CriterioGeminiSchema)
"""

import logging

from pydantic import BaseModel, Field, field_validator, model_validator, BeforeValidator
from typing import Annotated, Literal, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


def _round_to_int(v) -> int:
    """Round float to int before Pydantic validation.

    Gemini sometimes returns decimal scores (e.g. 91.12 instead of 91).
    This validator ensures we always store clean integer scores.
    """
    if isinstance(v, float):
        return round(v)
    return v


# Annotated type: accepts float from JSON, converts to rounded int
RoundedInt = Annotated[int, BeforeValidator(_round_to_int)]


class SubcriterioEvaluado(BaseModel):
    """Schema for an evaluated subcriterion within a correction (API/persistence level).

    Only populated for rubricas `schema_version = 2` (peso-por-subcriterio):
    the subcriterios desglosan el puntaje del criterio, no lo alteran (el
    puntaje_obtenido del criterio sigue siendo la suma de sus subcriterios).
    Uses `Decimal`, coherente con `CriterioEvaluado.puntaje_obtenido`.
    """

    id: str = Field(..., description="Subcriterion ID from rubric (ej: 'C1.1')")
    puntaje_obtenido: Decimal = Field(..., ge=0, description="Points obtained")
    puntaje_maximo: Decimal = Field(..., ge=1, description="Maximum points for subcriterion")
    estado: Literal["OK", "WARNING", "ERROR"] = Field(..., description="Subcriterion status")
    feedback: str = Field(..., min_length=1, description="Specific feedback for this subcriterion")
    evidencia: Optional[str] = Field(
        default=None,
        description=(
            "Cita textual del codigo que respalda el puntaje (change "
            "motor-anti-falsos-positivos). Ausente en correcciones previas."
        ),
    )


class SubcriterioGeminiSchema(BaseModel):
    """Schema for parsing subcriterion evaluation from the raw Gemini/OpenRouter response.

    Mirrors `CriterioGeminiSchema`: uses `RoundedInt` because the AI sometimes
    returns decimal scores. Only present for rubricas `schema_version = 2`.
    """

    id: str = Field(..., description="Subcriterion ID from rubric (ej: 'C1.1')")
    puntaje_obtenido: RoundedInt = Field(ge=0)
    puntaje_maximo: RoundedInt = Field(ge=1)
    estado: Literal["OK", "WARNING", "ERROR"]
    feedback: str = Field(min_length=1)
    evidencia: Optional[str] = Field(
        default=None,
        description=(
            "Cita textual del codigo del alumno que respalda el puntaje. Opcional: "
            "un criterio cerrado en 0 no tiene que citar nada, y las correcciones "
            "viejas no la traen."
        ),
    )


class CriterioEvaluado(BaseModel):
    """Schema for an evaluated criterion in a correction."""

    id: str = Field(..., description="Criterion ID from rubric")
    nombre: str = Field(..., description="Criterion name")
    puntaje_obtenido: Decimal = Field(..., ge=0, description="Points obtained")
    puntaje_maximo: Decimal = Field(..., ge=1, description="Maximum points for criterion")
    estado: Literal["OK", "WARNING", "ERROR"] = Field(..., description="Criterion status")
    feedback: str = Field(..., min_length=1, description="Specific feedback for this criterion")
    subcriterios_evaluados: Optional[list[SubcriterioEvaluado]] = Field(
        default=None,
        description=(
            "Desglose de puntaje por subcriterio (solo rubricas schema_version=2). "
            "Ausente en correcciones viejas o de rubricas v1 — no rompe el parseo."
        ),
    )
    evidencia: Optional[str] = Field(
        default=None,
        description=(
            "Cita textual del código del alumno que respalda el puntaje (change "
            "motor-anti-falsos-positivos). Ausente en correcciones previas."
        ),
    )


class CriterioGeminiSchema(BaseModel):
    """Schema for parsing criterion evaluation from Gemini response.

    The `id` field is optional because the PDF correction webhook
    (/webhook/corregir-pdf) does not include it in its response,
    while the text correction webhook (/webhook/corregir) does.
    """

    id: Optional[str] = Field(default=None)
    nombre: str
    puntaje_obtenido: RoundedInt = Field(ge=0)
    puntaje_maximo: RoundedInt = Field(ge=1)
    estado: Literal["OK", "WARNING", "ERROR"]
    feedback: str = Field(min_length=1)
    subcriterios_evaluados: Optional[list[SubcriterioGeminiSchema]] = Field(
        default=None,
        description=(
            "Desglose de puntaje por subcriterio devuelto por la IA (solo "
            "rubricas schema_version=2). Ausente en v1 o si el modelo lo omite."
        ),
    )
    evidencia: Optional[str] = Field(
        default=None,
        description=(
            "Cita textual del codigo del alumno que respalda el puntaje. Opcional: "
            "un criterio cerrado en 0 no tiene que citar nada, y las correcciones "
            "viejas no la traen."
        ),
    )


class GeminiResponse(BaseModel):
    """Schema for parsing complete Gemini API response."""

    nota: RoundedInt = Field(ge=0, le=100, description="Final grade (may be 0 if CD applies)")
    nota_antes_penalizaciones: Optional[RoundedInt] = Field(default=None, description="Merit score before penalties/CD")
    condicion_desaprobacion_aplicada: Optional[str] = Field(default=None, description="ID of applied failing condition")
    penalizaciones_aplicadas: list[str] = Field(default_factory=list, description="IDs of applied penalties")
    criterios: list[CriterioGeminiSchema] = Field(..., description="Evaluated criteria")
    fortalezas: list[str] = Field(default_factory=list, description="Strengths identified")
    recomendaciones: list[str] = Field(default_factory=list, description="Recommendations")
    comentario_general: str = Field(..., description="General feedback comment")
    # IA-010: el modelo marca si detectó un intento de prompt injection en el código.
    injection_detectada: bool = Field(default=False, description="True if a prompt-injection attempt was detected")

    # IA-008: se eliminó validate_nota_sum. Era código muerto (por el orden de
    # campos de Pydantic, `criterios` aún no está en info.data cuando corre el
    # validador de `nota`) y además quedó irrelevante con IA-001: la nota final la
    # calcula el backend determinísticamente (_nota_deterministica), ignorando la
    # nota que devuelve el modelo.


class CorreccionResponse(BaseModel):
    """Schema for correction API response."""

    id: int
    entrega_id: int
    nota: Decimal = Field(..., description="Final grade (0-100)")
    nota_antes_penalizaciones: Optional[Decimal] = Field(None, description="Merit score before penalties/CD")
    condicion_desaprobacion_aplicada: Optional[str] = Field(None, description="ID of applied failing condition")
    condicion_desaprobacion_descripcion: Optional[str] = Field(None, description="Human-readable description of the applied CD")
    penalizaciones_aplicadas: list[str] = Field(default_factory=list, description="IDs of applied penalties")
    penalizaciones_descripciones: list[dict] = Field(default_factory=list, description="Descriptions and percentages of applied penalties")
    criterios: list[CriterioEvaluado] = Field(default_factory=list, description="Evaluated criteria")
    fortalezas: list[str] = Field(default_factory=list, description="Code strengths")
    recomendaciones: list[str] = Field(default_factory=list, description="Improvement recommendations")
    comentario_general: str = Field(..., description="General pedagogical feedback")
    editado_manualmente: bool = Field(default=False, description="True if manually edited by tutor")
    corregido_por_id: int = Field(..., description="ID of user who corrected/edited")
    created_at: datetime = Field(..., serialization_alias="fecha_correccion", description="Correction date")
    updated_at: datetime = Field(..., description="Last modification date")
    criterios_sin_ejecucion: list[str] = Field(
        default_factory=list,
        description=(
            "Ids de los criterios cerrados en 0 porque el codigo no compila "
            "(change correccion-por-ejercicio-con-tests). Vacio en toda "
            "correccion que no venga con resultado de tests."
        ),
    )

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Custom validation to extract criterios from criterios_json."""
        # If obj is a SQLAlchemy model with criterios_json attribute
        if hasattr(obj, 'criterios_json'):
            criterios_json = obj.criterios_json
            # Extract criterios array from dict structure
            if isinstance(criterios_json, dict) and 'criterios' in criterios_json:
                criterios_list = [CriterioEvaluado(**c) for c in criterios_json['criterios']]
            else:
                criterios_list = []
            # Clave hermana de `criterios`, escrita por el flujo de correccion
            # cuando el codigo no compilaba. Ausente en todo lo anterior.
            sin_ejecucion = (
                criterios_json.get('criterios_sin_ejecucion') or []
                if isinstance(criterios_json, dict)
                else []
            )

            # Create dict with all attributes
            data = {
                'id': obj.id,
                'entrega_id': obj.entrega_id,
                'nota': obj.nota,
                'nota_antes_penalizaciones': obj.nota_antes_penalizaciones,
                'condicion_desaprobacion_aplicada': obj.condicion_desaprobacion_aplicada,
                'penalizaciones_aplicadas': obj.penalizaciones_aplicadas if obj.penalizaciones_aplicadas else [],
                'criterios': criterios_list,
                'fortalezas': obj.fortalezas if obj.fortalezas else [],
                'recomendaciones': obj.recomendaciones if obj.recomendaciones else [],
                'comentario_general': obj.comentario_general if obj.comentario_general else '',
                'editado_manualmente': obj.editado_manualmente,
                'corregido_por_id': obj.corregido_por_id,
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
                'criterios_sin_ejecucion': sin_ejecucion,
            }
            return super().model_validate(data, **kwargs)

        # Otherwise, use default validation
        return super().model_validate(obj, **kwargs)

    class Config:
        from_attributes = True
        populate_by_name = True


class CorreccionUpdate(BaseModel):
    """Schema for updating an existing correction."""

    nota: Optional[Decimal] = Field(None, ge=0, le=100, description="Final grade")
    nota_antes_penalizaciones: Optional[Decimal] = Field(None, ge=0, le=100, description="Merit score")
    condicion_desaprobacion_aplicada: Optional[str] = Field(None, description="CD ID or null to clear")
    penalizaciones_aplicadas: Optional[list[str]] = Field(None, description="Penalty IDs or empty to clear")
    criterios: Optional[list[CriterioEvaluado]] = Field(None, description="Updated criteria")
    fortalezas: Optional[list[str]] = Field(None, description="Updated strengths")
    recomendaciones: Optional[list[str]] = Field(None, description="Updated recommendations")
    comentario_general: Optional[str] = Field(None, description="Updated general comment")

    # No validation here - users can edit individual criteria without constraints
    # The nota field can be manually adjusted or recalculated on frontend


class CorreccionCreate(BaseModel):
    """Schema for creating a correction (rarely used, mostly AI-generated)."""

    entrega_id: int = Field(..., description="ID of the submission")
    nota: Decimal = Field(..., ge=0, le=100, description="Final grade")
    nota_antes_penalizaciones: Optional[Decimal] = Field(None, ge=0, le=100, description="Merit score before penalties/CD")
    condicion_desaprobacion_aplicada: Optional[str] = Field(None, description="ID of applied failing condition")
    penalizaciones_aplicadas: list[str] = Field(default_factory=list, description="IDs of applied penalties")
    criterios: list[CriterioEvaluado] = Field(..., description="Evaluated criteria")
    fortalezas: list[str] = Field(default_factory=list, description="Code strengths")
    recomendaciones: list[str] = Field(default_factory=list, description="Recommendations")
    comentario_general: str = Field(..., description="General feedback")
    corregido_por_id: int = Field(..., description="ID of user who corrected")
    raw_response: Optional[dict] = Field(None, description="Raw Gemini API response")

    @model_validator(mode='after')
    def autocorrect_nota_from_criterios(self):
        """If nota and sum of criterios differ by more than 1 point, use the sum.

        ONLY applies when no CD or penalties are active — otherwise Gemini's
        nota is intentionally different from the criteria sum.
        """
        if self.condicion_desaprobacion_aplicada or self.penalizaciones_aplicadas:
            return self
        if self.criterios:
            suma = sum(float(c.puntaje_obtenido) for c in self.criterios)
            if abs(float(self.nota) - suma) > 1:
                logger.warning(
                    f"CorreccionCreate: nota ({self.nota}) difiere de la suma de criterios "
                    f"({suma}). Autocorrigiendo nota a {suma}."
                )
                self.nota = Decimal(str(suma))
        return self


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


class CorregirLoteAceptadoResponse(BaseModel):
    """Immediate response schema for async batch correction endpoint.

    The endpoint returns this right away (202 Accepted) while corrections
    are processed in the background, avoiding HTTP timeouts on large batches.
    """

    mensaje: str = Field(..., description="Status message for the user")
    total_encoladas: int = Field(..., description="Number of submissions queued for correction")
    entrega_ids: list[int] = Field(..., description="IDs of the queued submissions")
    # SEC-001: el lote se encola SOLO sobre las entregas accesibles. Lo omitido se
    # informa (default -> contrato aditivo, backend despliega antes que el frontend).
    omitidas: int = Field(
        default=0, description="Entregas omitidas por falta de permisos"
    )
    entrega_ids_omitidos: list[int] = Field(
        default_factory=list, description="IDs omitidos por falta de permisos"
    )


class CorreccionAceptadaResponse(BaseModel):
    """IA-012: respuesta inmediata (202) de la corrección individual asíncrona.

    El endpoint agenda la corrección en background y responde al toque, sin
    bloquear el request HTTP hasta ~3 min. El frontend pollea el estado de la
    entrega (PENDIENTE → CORREGIDA/ERROR), igual que con el lote.
    """

    mensaje: str = Field(..., description="Status message for the user")
    entrega_id: int = Field(..., description="ID de la entrega en corrección")
    estado: str = Field(
        default="PENDIENTE",
        description="Estado de la entrega tras encolar (PENDIENTE)",
    )


class CorregirGlobalAceptadoResponse(BaseModel):
    """Respuesta 202 de la corrección masiva global (todas las SUBIDA del tutor)."""

    mensaje: str
    total_encoladas: int


class ProgresoGlobalResponse(BaseModel):
    """Conteo de estados de las entregas del tutor (para el progreso de 'Corregir todo')."""

    subidas: int = 0
    pendientes: int = 0
    corregidas: int = 0
    error: int = 0
    total: int = 0
    # Desglose de las que están en ERROR por código (item #7), para el resumen de la masiva.
    errores_por_codigo: dict[str, int] = {}


# ============================================================================
# CRUD-003: historial de correcciones (versiones reemplazadas al recorregir)
# ============================================================================


class CorreccionHistorialItem(BaseModel):
    """Una versión histórica de la corrección de una entrega. SIN raw_response."""

    id: int
    nota: float
    editado_manualmente: bool
    comentario_general: str | None
    corregido_por_nombre: str | None
    reemplazada_por_nombre: str | None
    correccion_creada_en: datetime
    reemplazada_en: datetime

    model_config = {"from_attributes": True}


class CorreccionHistorialResponse(BaseModel):
    """Historial de correcciones de una entrega, de la más reciente a la más vieja."""

    entrega_id: int
    total_versiones: int
    versiones: list[CorreccionHistorialItem]


# ============================================================================
# Corrección por ejercicio (change correccion-por-ejercicio-con-tests)
#
# Contrato acordado con AI-Native. Su cliente YA está escrito contra esto y corre
# contra un mock hasta que el endpoint exista: todo lo que agreguemos de nuestro
# lado tiene que ser OPCIONAL o les rompemos lo que ya construyeron.
# ============================================================================


class CasoTestResultado(BaseModel):
    """Resultado de un caso de prueba ya EJECUTADO por el cliente.

    Active-IA no ejecuta nada: recibe el veredicto de un sandbox real (Docker sin
    privilegios, sin red, 10s de límite) y lo usa como hecho establecido.
    """

    id: str = Field(..., min_length=1, max_length=50)
    paso: bool
    entrada: Optional[str] = None
    esperado: Optional[str] = None
    obtenido: Optional[str] = Field(
        default=None,
        description=(
            "Lo que realmente salió. Es lo que le permite al motor explicar el "
            "fallo en vez de solo constatarlo."
        ),
    )


class ResultadoTests(BaseModel):
    """Resultado de la corrida del código del alumno en el sandbox del cliente."""

    compila: bool = Field(
        ...,
        description=(
            "Campo PROPIO, no derivado de `pasados == 0`. No compilar (un punto y "
            "coma) y compilar fallando todo (el programa corre y hace otra cosa) "
            "son situaciones distintas y merecen devoluciones distintas."
        ),
    )
    error_compilacion: Optional[str] = Field(
        default=None,
        description="Mensaje del compilador, para poder citarlo en la devolución.",
    )
    total: int = Field(..., ge=0)
    pasados: int = Field(..., ge=0)
    casos: list[CasoTestResultado] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validar_conteos(self) -> "ResultadoTests":
        if self.pasados > self.total:
            raise ValueError(
                f"pasados ({self.pasados}) no puede superar el total ({self.total})"
            )
        return self


class CorreccionEjercicioRequest(BaseModel):
    """Cuerpo del pedido de corrección de un ejercicio."""

    alumno_ref: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "Pseudónimo del alumno. Se almacena tal cual: Active-IA NO intenta "
            "resolverlo a una persona ni cruzarlo con ningún padrón."
        ),
    )
    codigo: str = Field(..., min_length=1)
    resultado_tests: Optional[ResultadoTests] = Field(
        default=None,
        description=(
            "Opcional: un cliente que no ejecute código puede corregir igual, "
            "heredando los modos de fallo del motor."
        ),
    )
    comision_external_ref: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "OPCIONAL y agregado por Active-IA, no pedido por el cliente: "
            "`entregas.comision_id` es NOT NULL y el cliente no tiene comisiones. "
            "Si no viene, se usa la comisión de integración de la materia."
        ),
    )

    @field_validator("codigo", "alumno_ref")
    @classmethod
    def _no_solo_espacios(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("no puede estar vacío")
        return v


class CorreccionEjercicioResponse(BaseModel):
    """Corrección de UN ejercicio.

    NO expone ninguna nota agregada del trabajo práctico: el cliente dijo
    explícitamente que el promedio ponderado lo calcula él y se lo muestra
    desglosado al docente.
    """

    correccion_id: int
    entrega_id: int
    ejercicio_external_ref: str
    rubrica_id: int
    alumno_ref: str
    nota: Decimal
    criterios: list[CriterioEvaluado] = Field(default_factory=list)
    fortalezas: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)
    comentario_general: Optional[str] = None
    # Criterios forzados a 0 por no compilar, para que el cliente pueda
    # mostrárselos distinto al docente.
    criterios_sin_ejecucion: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}
