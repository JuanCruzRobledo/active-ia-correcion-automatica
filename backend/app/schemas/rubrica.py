# app/schemas/rubrica.py
"""
Rubrica schemas for Active-IA.

Pydantic schemas for rubric (rubrica) management with hierarchical criteria structure.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
Ref: docs/specs/06-MODELO-DATOS.md seccion 4.1
Ref: docs/specs/Rubrica.md
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import FuenteRubricaEnum, TipoRubricaEnum


# ============================================================================
# Schemas de Estructura de Criterios
# ============================================================================


class Subcriterio(BaseModel):
    """
    Subcriterio dentro de un criterio.

    Representa un aspecto específico a evaluar con evidencias verificables.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^[A-Z0-9]+\.[0-9]+$",
        description="Identificador único del subcriterio (ej: 'C1.1', 'C2.3')",
        examples=["C1.1", "C2.3"],
    )
    descripcion: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descripción del subcriterio",
        examples=["package.json con dependencias correctas"],
    )
    evidencias: list[str] = Field(
        ...,
        min_length=1,
        description="Checklist de evidencias verificables por la IA",
        examples=[["Archivo package.json existe", "Dependencia express presente"]],
    )

    @field_validator("evidencias")
    @classmethod
    def validar_evidencias_no_vacias(cls, v: list[str]) -> list[str]:
        """Valida que todas las evidencias tengan contenido."""
        if not v:
            raise ValueError("Debe haber al menos una evidencia")
        for evidencia in v:
            if not evidencia.strip():
                raise ValueError("Las evidencias no pueden estar vacías")
        return v


class Criterio(BaseModel):
    """
    Criterio de evaluación dentro de una rúbrica.

    Define un aspecto a evaluar con peso porcentual y subcriterios.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^[A-Z0-9]+$",
        description="Identificador único del criterio (ej: 'C1', 'C2')",
        examples=["C1", "C2", "C3"],
    )
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del criterio",
        examples=["Estructura del proyecto", "Endpoints CRUD"],
    )
    descripcion: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descripción detallada del criterio",
        examples=["Organización correcta de archivos y configuración inicial"],
    )
    peso: int = Field(
        ...,
        ge=1,
        le=100,
        description="Peso porcentual del criterio (la suma total debe ser 100)",
        examples=[15, 40, 25],
    )
    instrucciones_puntuacion: str | None = Field(
        None,
        max_length=500,
        description="Instrucciones opcionales para asignar puntaje dentro del criterio",
        examples=["Dividir proporcionalmente entre subcriterios"],
    )
    subcriterios: list[Subcriterio] = Field(
        ...,
        min_length=1,
        description="Lista de subcriterios con evidencias",
    )

    @model_validator(mode="after")
    def validar_subcriterio_ids_unicos(self) -> "Criterio":
        """Valida que los IDs de subcriterios sean únicos dentro del criterio."""
        ids = [s.id for s in self.subcriterios]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Los IDs de subcriterios en {self.id} deben ser únicos")
        return self


class Penalizacion(BaseModel):
    """
    Penalización que se puede aplicar a una evaluación.

    Define un descuento porcentual por incumplimientos específicos.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^P[0-9]+$",
        description="Identificador único de la penalización (ej: 'P1', 'P2')",
        examples=["P1", "P2"],
    )
    descripcion: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descripción de la penalización",
        examples=["Repositorio privado o inaccesible"],
    )
    descuento_porcentaje: int = Field(
        ...,
        ge=0,
        le=100,
        description="Descuento porcentual a aplicar (0-100)",
        examples=[100, 50, 20],
    )


class CondicionDesaprobacion(BaseModel):
    """
    Condición automática de desaprobación.

    Define reglas que establecen una nota final específica automáticamente.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^CD[0-9]+$",
        description="Identificador único de la condición (ej: 'CD1', 'CD2')",
        examples=["CD1", "CD2"],
    )
    condicion: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descripción de la condición de desaprobación",
        examples=["Plagio detectado", "No implementa al menos 3 endpoints CRUD"],
    )
    nota_final: int = Field(
        ...,
        ge=0,
        le=100,
        description="Nota final a asignar si se cumple la condición",
        examples=[0, 30],
    )


class CriteriosStructure(BaseModel):
    """
    Estructura completa de una rúbrica.

    Incluye información general, metadata flexible, criterios jerárquicos,
    penalizaciones y condiciones de desaprobación.
    """

    titulo: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Título descriptivo de la rúbrica",
        examples=["TP2 - API REST de Productos"],
    )
    descripcion: str = Field(
        ...,
        min_length=1,
        description="Descripción detallada de qué evalúa esta rúbrica",
        examples=["Desarrollo de una API REST con Express.js..."],
    )
    puntaje_maximo: int = Field(
        default=100,
        description="Puntaje máximo total (siempre 100)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata flexible: materia, carrera, lenguaje, framework, etc.",
        examples=[{"materia": "Programación Backend", "lenguaje": "JavaScript"}],
    )
    criterios: list[Criterio] = Field(
        ...,
        min_length=1,
        description="Lista de criterios de evaluación",
    )
    penalizaciones: list[Penalizacion] = Field(
        default_factory=list,
        description="Lista de penalizaciones opcionales",
    )
    condiciones_desaprobacion: list[CondicionDesaprobacion] = Field(
        default_factory=list,
        description="Lista de condiciones de desaprobación automáticas",
    )

    @field_validator("puntaje_maximo")
    @classmethod
    def validar_puntaje_maximo(cls, v: int) -> int:
        """Valida que el puntaje máximo sea exactamente 100."""
        if v != 100:
            raise ValueError("El puntaje máximo de la rúbrica debe ser exactamente 100")
        return v

    @model_validator(mode="after")
    def validar_suma_pesos(self) -> "CriteriosStructure":
        """Valida que la suma de pesos de criterios sea exactamente 100."""
        suma = sum(c.peso for c in self.criterios)
        if suma != 100:
            raise ValueError(
                f"La suma de pesos de criterios ({suma}) debe ser exactamente 100"
            )
        return self

    @model_validator(mode="after")
    def validar_ids_unicos(self) -> "CriteriosStructure":
        """Valida que todos los IDs sean únicos en sus respectivos niveles."""
        # IDs de criterios
        criterio_ids = [c.id for c in self.criterios]
        if len(criterio_ids) != len(set(criterio_ids)):
            raise ValueError("Los IDs de criterios deben ser únicos")

        # IDs de penalizaciones
        if self.penalizaciones:
            pen_ids = [p.id for p in self.penalizaciones]
            if len(pen_ids) != len(set(pen_ids)):
                raise ValueError("Los IDs de penalizaciones deben ser únicos")

        # IDs de condiciones de desaprobación
        if self.condiciones_desaprobacion:
            cond_ids = [c.id for c in self.condiciones_desaprobacion]
            if len(cond_ids) != len(set(cond_ids)):
                raise ValueError("Los IDs de condiciones de desaprobación deben ser únicos")

        return self


# ============================================================================
# Schemas Base de Rúbrica
# ============================================================================


class RubricaBase(BaseModel):
    """Base schema for Rubrica with common fields."""

    tipo: TipoRubricaEnum = Field(
        ...,
        description="Tipo de rúbrica (TP, PARCIAL_1, etc.)",
    )
    numero: int = Field(
        ...,
        ge=1,
        description="Número de la rúbrica dentro del tipo",
        examples=[1, 2, 3],
    )
    anio: int = Field(
        ...,
        ge=2020,
        le=2100,
        description="Año académico",
        examples=[2026],
    )


class RubricaCreate(RubricaBase):
    """Schema for creating a new Rubrica."""

    materia_id: int = Field(
        ...,
        gt=0,
        description="ID de la materia a la que pertenece la rúbrica",
    )
    titulo: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Título de la rúbrica",
        examples=["TP2 - API REST de Productos"],
    )
    descripcion: str = Field(
        ...,
        min_length=1,
        description="Descripción de la rúbrica",
    )
    puntaje_maximo: int = Field(
        default=100,
        description="Puntaje máximo (siempre 100)",
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata flexible",
    )
    criterios_json: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Array de criterios jerárquicos",
    )
    penalizaciones_json: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array de penalizaciones",
    )
    condiciones_desaprobacion_json: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array de condiciones de desaprobación",
    )
    fuente: FuenteRubricaEnum = Field(
        default=FuenteRubricaEnum.MANUAL,
        description="Fuente de la rúbrica (MANUAL o IA)",
    )
    archivo_original: str | None = Field(
        None,
        max_length=255,
        description="Ruta del archivo original (si fuente es IA)",
    )

    @model_validator(mode="after")
    def validar_estructura_completa(self) -> "RubricaCreate":
        """Valida la estructura completa usando CriteriosStructure."""
        try:
            CriteriosStructure(
                titulo=self.titulo,
                descripcion=self.descripcion,
                puntaje_maximo=self.puntaje_maximo,
                metadata=self.metadata_json,
                criterios=[Criterio(**c) for c in self.criterios_json],
                penalizaciones=[Penalizacion(**p) for p in self.penalizaciones_json],
                condiciones_desaprobacion=[
                    CondicionDesaprobacion(**cd) for cd in self.condiciones_desaprobacion_json
                ],
            )
        except Exception as e:
            raise ValueError(f"Error en la estructura de la rúbrica: {str(e)}")
        return self


class RubricaUpdate(BaseModel):
    """Schema for updating an existing Rubrica ."""

    titulo: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Nuevo título de la rúbrica",
    )
    descripcion: str | None = Field(
        None,
        min_length=1,
        description="Nueva descripción",
    )
    metadata_json: dict[str, Any] | None = Field(
        None,
        description="Nueva metadata",
    )
    criterios_json: list[dict[str, Any]] | None = Field(
        None,
        description="Nuevos criterios",
    )
    penalizaciones_json: list[dict[str, Any]] | None = Field(
        None,
        description="Nuevas penalizaciones",
    )
    condiciones_desaprobacion_json: list[dict[str, Any]] | None = Field(
        None,
        description="Nuevas condiciones de desaprobación",
    )

    @model_validator(mode="after")
    def validar_estructura_si_presente(self) -> "RubricaUpdate":
        """Valida la estructura si se proporcionan criterios."""
        if self.criterios_json is not None:
            try:
                # Construir estructura temporal para validar
                estructura = {
                    "titulo": self.titulo or "Temporal",
                    "descripcion": self.descripcion or "Temporal",
                    "puntaje_maximo": 100,
                    "metadata": self.metadata_json or {},
                    "criterios": self.criterios_json,
                    "penalizaciones": self.penalizaciones_json or [],
                    "condiciones_desaprobacion": self.condiciones_desaprobacion_json or [],
                }
                CriteriosStructure(**estructura)
            except Exception as e:
                raise ValueError(f"Error en la estructura de criterios: {str(e)}")
        return self


# ============================================================================
# Schemas de Respuesta
# ============================================================================


class RubricaResponse(BaseModel):
    """Schema for Rubrica  response with all fields."""

    id: int
    materia_id: int
    tipo: TipoRubricaEnum
    numero: int
    anio: int
    titulo: str
    descripcion: str
    puntaje_maximo: int
    metadata_json: dict[str, Any]
    criterios_json: list[dict[str, Any]]
    penalizaciones_json: list[dict[str, Any]]
    condiciones_desaprobacion_json: list[dict[str, Any]]
    fuente: FuenteRubricaEnum
    archivo_original: str | None
    activa: bool
    created_at: str
    updated_at: str

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        """Convierte datetime a string ISO format."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v if v else ""

    model_config = {"from_attributes": True}


class MateriaInfo(BaseModel):
    """Información reducida de una materia."""

    id: int
    codigo: str
    nombre: str

    model_config = {"from_attributes": True}


class RubricaDetailResponse(RubricaResponse):
    """Schema for detailed Rubrica response with relations."""

    materia: MateriaInfo = Field(
        description="Información de la materia",
    )
    num_entregas: int = Field(
        default=0,
        description="Cantidad de entregas asociadas a esta rúbrica",
    )


class RubricaListItem(BaseModel):
    """Schema for Rubrica  list item with denormalized data."""

    id: int
    materia_id: int
    materia_nombre: str
    materia_codigo: str
    tipo: TipoRubricaEnum
    titulo: str
    numero: int
    anio: int
    puntaje_maximo: int = Field(
        description="Puntaje máximo (siempre 100)",
    )
    num_criterios: int = Field(
        description="Cantidad de criterios en la rúbrica",
    )
    num_entregas: int = Field(
        default=0,
        description="Cantidad de entregas asociadas",
    )
    activa: bool
    created_at: str

    @field_validator("created_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        """Convierte datetime a string ISO format."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v if v else ""

    model_config = {"from_attributes": True}


class RubricaList(BaseModel):
    """Schema for paginated Rubrica list."""

    items: list[RubricaListItem]
    total: int = Field(description="Total de rúbricas")
    page: int = Field(description="Página actual")
    per_page: int = Field(description="Items por página")


# ============================================================================
# Schemas Especiales
# ============================================================================


class RubricaDuplicar(BaseModel):
    """Schema for duplicating a Rubrica to a new year."""

    nuevo_anio: int = Field(
        ...,
        ge=2020,
        le=2100,
        description="Año académico para la rúbrica duplicada",
        examples=[2027],
    )
    nuevo_titulo: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Nuevo título opcional (si no se provee, se usa el original)",
    )


class RubricaPDFPreview(BaseModel):
    """Schema for generating a PDF preview of a rubrica."""

    materia_nombre: str = Field(
        default="N/A",
        description="Nombre de la materia (para preview)",
    )
    tipo: str = Field(
        default="TP",
        description="Tipo de rúbrica",
    )
    numero: int = Field(
        default=1,
        description="Número de la rúbrica",
    )
    anio: int = Field(
        default=2026,
        description="Año académico",
    )
    titulo: str = Field(
        default="Sin título",
        description="Título de la rúbrica",
    )
    descripcion: str = Field(
        default="Sin descripción",
        description="Descripción de la rúbrica",
    )
    puntaje_maximo: int = Field(
        default=100,
        description="Puntaje máximo",
    )
    criterios: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array de criterios",
    )
    penalizaciones: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array de penalizaciones",
    )
    condiciones_desaprobacion: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array de condiciones de desaprobación",
    )
