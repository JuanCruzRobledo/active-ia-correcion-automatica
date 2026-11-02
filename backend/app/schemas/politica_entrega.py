"""Validación acotada de las excepciones dentro de la metadata de una rúbrica."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.politica_archivos import DIRECTORIOS_PENALIZABLES


class PoliticaEntregaRubrica(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directorios_permitidos: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("directorios_permitidos")
    @classmethod
    def validar_directorios(cls, value: list[str]) -> list[str]:
        normalized = {item.casefold() for item in value}
        if not normalized.issubset(DIRECTORIOS_PENALIZABLES):
            raise ValueError("Las excepciones deben ser nombres exactos: node_modules, dist, target, build, out o bin")
        return sorted(normalized)


def validar_metadata_politica(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None or "politica_entrega" not in value:
        return value
    policy = PoliticaEntregaRubrica.model_validate(value["politica_entrega"])
    return {**value, "politica_entrega": policy.model_dump()}
