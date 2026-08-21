# app/schemas/ejercicio.py
"""
Schemas del Ejercicio y de sus casos de prueba.

Change: `trabajos-practicos-y-external-ref`.

El cliente (AI-Native) manda una rúbrica **plana** por ejercicio —criterios con
`nombre`, `descripcion` y `puntaje_max`— y Active-IA la persiste en su `Rubrica`,
que es jerárquica y exige pesos que sumen 100. La traducción entre las dos formas
la hace el servicio, no estos schemas: acá solo se valida lo que entra.
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TipoTestCase = Literal["stdin_stdout", "pytest_assert", "junit_assert"]

_TIPOS_DE_ASERCION = ("pytest_assert", "junit_assert")


class TestCase(BaseModel):
    """
    Caso de prueba de un ejercicio. **Active-IA NO lo ejecuta.**

    Viaja porque es parte del enunciado: le dice al motor cuál es la regla de
    negocio que se pidió. Sin eso, juzga el código sin saber qué se le pidió.
    """

    # pytest colecciona por convención de nombre cualquier clase que empiece con
    # `Test`. Ésta es un modelo de dominio, no un test: el nombre viene del
    # contrato del cliente (`test_cases`) y conviene conservarlo.
    __test__ = False

    id: str = Field(..., min_length=1, max_length=50)
    nombre: str = Field(..., min_length=1, max_length=200)
    tipo: TipoTestCase
    es_publico: bool = Field(
        ...,
        description=(
            "Los casos no públicos son los ocultos: el alumno no los ve, y son "
            "justamente los que codifican las reglas que tiene que inferir."
        ),
    )
    entrada: str | None = None
    salida_esperada: str | None = None
    asercion: str | None = None

    @field_validator("id", "nombre")
    @classmethod
    def _no_solo_espacios(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("no puede estar vacío")
        return v

    @model_validator(mode="after")
    def _validar_visibilidad_y_tipo(self) -> "TestCase":
        # --- Regla dura: el caso oculto no conserva la respuesta ---------------
        # El PDF de devolución se le entrega al alumno. Lo que el motor nunca
        # recibió no lo puede citar. Se RECHAZA en vez de descartar en silencio:
        # falla cuando el docente publica (barato) y no con un alumno esperando,
        # y no deja al cliente creyendo que su contrato se respeta mientras se le
        # limpia el payload.
        if not self.es_publico:
            if self.salida_esperada is not None:
                raise ValueError(
                    f"el caso oculto '{self.id}' no puede traer salida_esperada: "
                    "lo que el motor recibe puede terminar citado en la devolución "
                    "que lee el alumno"
                )
            if self.asercion is not None:
                raise ValueError(
                    f"el caso oculto '{self.id}' no puede traer asercion: "
                    "lo que el motor recibe puede terminar citado en la devolución "
                    "que lee el alumno"
                )

        # --- El tipo determina qué campos tienen sentido ----------------------
        # En los asserts el código ES el criterio (`assert suma(2,3) == 5`).
        # Mandarlo en `entrada` con la salida vacía haría que el motor evaluara
        # "el programa funciona" contra una aserción.
        if self.tipo in _TIPOS_DE_ASERCION:
            if self.entrada is not None or self.salida_esperada is not None:
                raise ValueError(
                    f"el caso '{self.id}' es de tipo {self.tipo}: su contenido va "
                    "en 'asercion', no en 'entrada'/'salida_esperada'"
                )
        elif self.asercion is not None:
            raise ValueError(
                f"el caso '{self.id}' es de tipo {self.tipo}: no lleva 'asercion', "
                "su contenido va en 'entrada'/'salida_esperada'"
            )

        return self

    def a_json(self) -> dict[str, Any]:
        """Forma persistible en `ejercicios.test_cases`, sin claves nulas."""
        datos = self.model_dump(exclude_none=True)
        return datos


class CriterioEjercicioInput(BaseModel):
    """Criterio tal como lo manda el cliente: plano, sin subcriterios."""

    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str = Field(..., min_length=1, max_length=500)
    puntaje_max: Decimal = Field(
        ...,
        gt=0,
        description=(
            "Puntaje del criterio en la escala del cliente. El servicio lo "
            "normaliza a los pesos que suman 100 que exige la Rubrica."
        ),
    )


class RubricaEjercicioInput(BaseModel):
    """Rúbrica del ejercicio tal como la manda el cliente."""

    criterios: list[CriterioEjercicioInput] = Field(..., min_length=1)


class EjercicioWriteRequest(BaseModel):
    """Un ejercicio dentro del cuerpo de escritura de un TP."""

    external_ref: str = Field(..., min_length=1, max_length=64)
    orden: int = Field(default=1, ge=1)
    titulo: str = Field(..., min_length=1, max_length=200)
    enunciado_md: str | None = None
    peso: Decimal = Field(
        default=Decimal("1"),
        gt=0,
        description=(
            "Peso relativo dentro del TP. NO se valida contra ningún total: "
            "Active-IA no calcula la nota final del TP."
        ),
    )
    rubrica: RubricaEjercicioInput
    test_cases: list[TestCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ids_de_caso_unicos(self) -> "EjercicioWriteRequest":
        vistos: set[str] = set()
        for caso in self.test_cases:
            if caso.id in vistos:
                raise ValueError(
                    f"el ejercicio '{self.external_ref}' repite el id de caso "
                    f"'{caso.id}'"
                )
            vistos.add(caso.id)
        return self


class EjercicioResponse(BaseModel):
    """
    Ejercicio en la respuesta.

    `rubrica_id` es el campo que le permite al cliente saber con qué rúbrica se
    corrige cada ejercicio. Sin él tendría que emparejar por orden o por título,
    que es adivinar — y elegir mal no da una nota floja: corrige otra cosa.
    """

    id: int
    external_ref: str
    orden: int
    titulo: str
    peso: Decimal
    rubrica_id: int | None
    enunciado_md: str | None = None
    test_cases: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"from_attributes": True}
