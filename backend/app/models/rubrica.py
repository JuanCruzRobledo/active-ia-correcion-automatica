# app/models/rubrica.py
"""
Rubrica model for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.6
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import FuenteRubricaEnum, TipoRubricaEnum

if TYPE_CHECKING:
    from app.models.entrega import Entrega
    from app.models.materia import Materia


class Rubrica(Base, TimestampMixin):
    """
    Rúbrica de evaluación.

    Define los criterios de evaluación para un trabajo/examen.
    Las rúbricas pertenecen a una materia y son compartidas por
    todas las comisiones del mismo año académico.

    Estructura de criterios_json:
    {
        "puntaje_maximo": 100,
        "criterios": [
            {
                "id": "c1",
                "nombre": "Funcionalidad correcta",
                "descripcion": "El programa realiza las operaciones solicitadas",
                "puntaje_maximo": 40,
                "niveles": [
                    {"puntaje": 40, "descripcion": "Excelente"},
                    {"puntaje": 30, "descripcion": "Bueno"},
                    ...
                ]
            }
        ]
    }
    """

    __tablename__ = "rubricas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[TipoRubricaEnum] = mapped_column(
        SQLEnum(TipoRubricaEnum, name="tiporubricaenum", create_type=True),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    anio: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    criterios_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    fuente: Mapped[FuenteRubricaEnum] = mapped_column(
        SQLEnum(FuenteRubricaEnum, name="fuenterubricaenum", create_type=True),
        default=FuenteRubricaEnum.MANUAL,
    )
    archivo_original: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    activa: Mapped[bool] = mapped_column(default=True, index=True)

    __table_args__ = (
        UniqueConstraint(
            "materia_id",
            "tipo",
            "numero",
            "anio",
            name="uq_rubrica_materia_tipo_numero_anio",
        ),
    )

    # Relationships
    materia: Mapped["Materia"] = relationship(
        "Materia",
        back_populates="rubricas",
    )
    entregas: Mapped[list["Entrega"]] = relationship(
        "Entrega",
        back_populates="rubrica",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Rubrica(id={self.id}, nombre='{self.nombre}', tipo={self.tipo})>"
