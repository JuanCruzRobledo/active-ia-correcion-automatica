# app/models/cohorte.py
"""
Cohorte and Cuatrimestre models for Active-IA.

Estructura académica para el Dashboard de Gestores:
    Cohorte (1:N) Cuatrimestre (1:N) Materia

- Cohorte: agrupación de ingreso (ej: M25 = marzo 2025, A26 = agosto 2026).
- Cuatrimestre: subdivisión de una cohorte (numero 1..4).

Ref: PLAN_DASHBOARD_GESTORES.md §5
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.materia import Materia


class Cohorte(Base, TimestampMixin):
    """
    Cohorte académica (ej: M25, A25, M26, A26).

    El admin las da de alta. Cada cohorte agrupa varios cuatrimestres.
    """

    __tablename__ = "cohortes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True,
        comment="Código de la cohorte (ej: 'M25', 'A26')",
    )
    nombre: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activa: Mapped[bool] = mapped_column(default=True, index=True)

    # Relationships
    cuatrimestres: Mapped[list["Cuatrimestre"]] = relationship(
        "Cuatrimestre",
        back_populates="cohorte",
        lazy="selectin",
        order_by="Cuatrimestre.numero",
    )

    def __repr__(self) -> str:
        return f"<Cohorte(id={self.id}, codigo='{self.codigo}')>"


class Cuatrimestre(Base, TimestampMixin):
    """
    Cuatrimestre de una cohorte (numero 1..4).

    Agrupa las materias que se cursan en ese período de la cohorte.
    """

    __tablename__ = "cuatrimestres"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cohorte_id: Mapped[int] = mapped_column(
        ForeignKey("cohortes.id"),
        nullable=False,
        index=True,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint("cohorte_id", "numero", name="uq_cuatrimestre_cohorte_numero"),
    )

    # Relationships
    cohorte: Mapped["Cohorte"] = relationship(
        "Cohorte",
        back_populates="cuatrimestres",
    )
    materias: Mapped[list["Materia"]] = relationship(
        "Materia",
        back_populates="cuatrimestre",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Cuatrimestre(id={self.id}, cohorte_id={self.cohorte_id}, numero={self.numero})>"
