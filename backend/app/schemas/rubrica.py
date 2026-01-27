# app/schemas/rubrica.py
"""
Rubrica schemas for Active-IA.

Pydantic schemas for rubric (rubrica) management with hierarchical criteria structure.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
Ref: docs/specs/06-MODELO-DATOS.md seccion 4.1
"""

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import FuenteRubricaEnum, TipoRubricaEnum


# ============================================================================
# Schemas de Estructura de Criterios (Jerárquica)
# ============================================================================


class NivelDesempeno(BaseModel):
    """
    Nivel de desempeño dentro de un criterio.

    Representa un nivel específico de logro con su puntaje y descripción.
    Ejemplo: "Excelente (40 pts)", "Bueno (30 pts)", etc.
    """

    puntaje: int = Field(
        ...,
        ge=0,
        le=100,
        description="Puntaje para este nivel de desempeño",
        examples=[40, 30, 20],
    )
    descripcion: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descripción del nivel de desempeño",
        examples=["Excelente: todas las funciones operan correctamente"],
    )


class CriterioBase(BaseModel):
    """
    Criterio de evaluación dentro de una rúbrica.

    Define un aspecto a evaluar con su puntaje máximo y opcionalmente
    niveles de desempeño específicos.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^[a-z0-9_]+$",
        description="Identificador único del criterio (ej: 'c1', 'funcionalidad')",
        examples=["c1", "funcionalidad", "estilo"],
    )
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del criterio",
        examples=["Funcionalidad correcta", "Estilo y legibilidad"],
    )
    descripcion: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descripción detallada del criterio",
        examples=["El programa realiza todas las operaciones solicitadas"],
    )
    puntaje_maximo: int = Field(
        ...,
        ge=1,
        le=100,
        description="Puntaje máximo para este criterio",
        examples=[40, 30, 20],
    )
    niveles: list[NivelDesempeno] | None = Field(
        None,
        description="Niveles de desempeño opcionales con puntajes específicos",
    )

    @field_validator("niveles")
    @classmethod
    def validar_niveles(
        cls,
        niveles: list[NivelDesempeno] | None,
        info,
    ) -> list[NivelDesempeno] | None:
        """Valida que los puntajes de niveles no excedan el puntaje máximo del criterio."""
        if niveles is None:
            return niveles

        # Obtener puntaje_maximo del contexto
        puntaje_maximo = info.data.get("puntaje_maximo")
        if puntaje_maximo is None:
            return niveles

        # Validar que ningún nivel exceda el puntaje máximo
        for nivel in niveles:
            if nivel.puntaje > puntaje_maximo:
                raise ValueError(
                    f"El puntaje del nivel ({nivel.puntaje}) no puede exceder "
                    f"el puntaje máximo del criterio ({puntaje_maximo})"
                )

        return niveles


class CriteriosStructure(BaseModel):
    """
    Estructura completa de criterios de una rúbrica.

    Contiene el puntaje máximo total (debe ser 100) y la lista de criterios.
    """

    puntaje_maximo: int = Field(
        ...,
        description="Puntaje máximo total de la rúbrica (debe ser 100)",
        examples=[100],
    )
    criterios: list[CriterioBase] = Field(
        ...,
        min_length=1,
        description="Lista de criterios de evaluación",
    )

    @field_validator("puntaje_maximo")
    @classmethod
    def validar_puntaje_maximo(cls, v: int) -> int:
        """Valida que el puntaje máximo sea exactamente 100."""
        if v != 100:
            raise ValueError("El puntaje máximo de la rúbrica debe ser exactamente 100")
        return v

    @model_validator(mode="after")
    def validar_suma_puntajes(self) -> "CriteriosStructure":
        """Valida que la suma de puntajes de criterios sea igual al puntaje máximo."""
        suma = sum(c.puntaje_maximo for c in self.criterios)
        if suma != self.puntaje_maximo:
            raise ValueError(
                f"La suma de puntajes de criterios ({suma}) debe ser igual "
                f"al puntaje máximo ({self.puntaje_maximo})"
            )
        return self

    @model_validator(mode="after")
    def validar_ids_unicos(self) -> "CriteriosStructure":
        """Valida que los IDs de criterios sean únicos."""
        ids = [c.id for c in self.criterios]
        if len(ids) != len(set(ids)):
            raise ValueError("Los IDs de criterios deben ser únicos")
        return self


# ============================================================================
# Schemas Base de Rúbrica
# ============================================================================


class RubricaBase(BaseModel):
    """Base schema for Rubrica with common fields."""

    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre de la rúbrica",
        examples=["TP1 - Listas en Python", "Parcial 1 - Programación"],
    )
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
    criterios_json: CriteriosStructure = Field(
        ...,
        description="Estructura de criterios de evaluación",
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


class RubricaUpdate(BaseModel):
    """Schema for updating an existing Rubrica."""

    nombre: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Nuevo nombre de la rúbrica",
    )
    criterios_json: CriteriosStructure | None = Field(
        None,
        description="Nueva estructura de criterios",
    )


# ============================================================================
# Schemas de Respuesta
# ============================================================================


class RubricaResponse(BaseModel):
    """Schema for Rubrica response with all fields."""

    id: int
    materia_id: int
    tipo: TipoRubricaEnum
    nombre: str
    numero: int
    anio: int
    criterios_json: dict  # Devolvemos como dict para flexibilidad en frontend
    fuente: FuenteRubricaEnum
    archivo_original: str | None
    activa: bool
    created_at: str
    updated_at: str

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
    """Schema for Rubrica list item with denormalized data."""

    id: int
    materia_id: int
    materia_nombre: str
    materia_codigo: str
    tipo: TipoRubricaEnum
    nombre: str
    numero: int
    anio: int
    puntaje_maximo: int = Field(
        description="Puntaje máximo (extraído de criterios_json)",
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
    nuevo_nombre: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Nuevo nombre opcional (si no se provee, se usa el original)",
    )
