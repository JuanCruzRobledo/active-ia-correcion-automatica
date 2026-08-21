# app/schemas/trabajo_practico.py
"""
Schemas del Trabajo Práctico.

Change: `trabajos-practicos-y-external-ref`.

La materia se identifica por `materia_external_ref` y no por su id numérico de
Active-IA: un id ajeno obligaría al cliente a mantener de su lado un mapeo de
identificadores que vencen sin avisar, que es justo el problema que el
identificador externo viene a resolver.
"""

from pydantic import BaseModel, Field, model_validator

from app.schemas.ejercicio import EjercicioResponse, EjercicioWriteRequest

# Tope explícito de ejercicios por TP. El cliente describe TPs de cuatro
# ejercicios; 50 deja muchísimo margen y a la vez pone un límite conocido, en vez
# de descubrirlo como un timeout o un payload que revienta con un docente
# esperando. Si el uso real lo pide, se sube a propósito.
MAX_EJERCICIOS_POR_TP = 50


class TrabajoPracticoWriteRequest(BaseModel):
    """Cuerpo de alta o de actualización de un TP con sus ejercicios anidados."""

    external_ref: str = Field(..., min_length=1, max_length=64)
    materia_external_ref: str = Field(..., min_length=1, max_length=64)
    titulo: str = Field(..., min_length=1, max_length=200)
    descripcion: str | None = None
    # Sin `min_length`: un TP puede existir sin ejercicios como estado
    # intermedio durante su creación.
    ejercicios: list[EjercicioWriteRequest] = Field(
        default_factory=list, max_length=MAX_EJERCICIOS_POR_TP
    )

    @model_validator(mode="after")
    def _refs_de_ejercicio_unicas(self) -> "TrabajoPracticoWriteRequest":
        """Dos ejercicios con la misma referencia vuelven ambigua la reconciliación.

        El emparejamiento entre publicaciones es por `external_ref`: con dos
        iguales no hay forma de decidir cuál actualiza a cuál. El índice único
        parcial los rechazaría de todos modos, pero acá el error puede nombrar el
        identificador infractor en vez de ser un choque de integridad.
        """
        vistos: set[str] = set()
        for ejercicio in self.ejercicios:
            if ejercicio.external_ref in vistos:
                raise ValueError(
                    f"el cuerpo repite la referencia externa de ejercicio "
                    f"'{ejercicio.external_ref}'"
                )
            vistos.add(ejercicio.external_ref)
        return self


class TrabajoPracticoResponse(BaseModel):
    """TP en la respuesta, con sus ejercicios vigentes y sus rúbricas."""

    id: int
    external_ref: str
    materia_id: int
    titulo: str
    descripcion: str | None = None
    ejercicios: list[EjercicioResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
