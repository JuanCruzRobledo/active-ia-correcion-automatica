# app/models/materia.py
"""
Materia and CoordinadorMateria models for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.2, 3.3
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.comision import Comision
    from app.models.rubrica import Rubrica
    from app.models.usuario import Usuario


class Materia(Base, TimestampMixin):
    """
    Materia académica.

    Representa una materia/curso (ej: Programación 1).
    Las rúbricas se definen a nivel de materia y son compartidas
    por todas las comisiones del mismo año.
    """

    __tablename__ = "materias"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activa: Mapped[bool] = mapped_column(default=True, index=True)

    # Relationships
    coordinadores: Mapped[list["CoordinadorMateria"]] = relationship(
        "CoordinadorMateria",
        back_populates="materia",
        lazy="selectin",
    )
    comisiones: Mapped[list["Comision"]] = relationship(
        "Comision",
        back_populates="materia",
        lazy="selectin",
    )
    rubricas: Mapped[list["Rubrica"]] = relationship(
        "Rubrica",
        back_populates="materia",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Materia(id={self.id}, codigo='{self.codigo}', nombre='{self.nombre}')>"


class CoordinadorMateria(Base):
    """
    Relación N:M entre Coordinador y Materia.

    Un coordinador puede estar asignado a varias materias.
    Una materia puede tener varios coordinadores.
    """

    __tablename__ = "coordinador_materia"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    coordinador_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
    )
    asignado_en: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "coordinador_id",
            "materia_id",
            name="uq_coordinador_materia",
        ),
    )

    # Relationships
    coordinador: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="materias_coordinadas",
    )
    materia: Mapped["Materia"] = relationship(
        "Materia",
        back_populates="coordinadores",
    )

    def __repr__(self) -> str:
        return f"<CoordinadorMateria(coordinador_id={self.coordinador_id}, materia_id={self.materia_id})>"
