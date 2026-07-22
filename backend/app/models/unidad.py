# app/models/unidad.py
"""
Unidad model for Active-IA (Dashboard de Gestores).

Una Unidad mapea una unidad de contenido de la materia a su SECCIÓN CABECERA
de Moodle (la sección "N- Tema"). El bloque de secciones de la unidad NO se
persiste: se DERIVA en runtime ordenando las cabeceras por section# (una
actividad pertenece a la unidad de la cabecera con mayor section# <= el de su
sección). Ver PLAN_DASHBOARD_GESTORES.md §5 y §6.1.

⚠️ `moodle_section_id` es el id de la sección CABECERA, NO el de un TP.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.componente_unidad import ComponenteUnidad
    from app.models.materia import Materia
    from app.models.rubrica import Rubrica


class Unidad(Base, TimestampMixin):
    """
    Unidad de contenido de una materia, anclada a la sección cabecera de Moodle.
    """

    __tablename__ = "unidades"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
        index=True,
    )
    # Fase 0 multi-tenant: denormalizada, propagada desde materia.universidad_id en
    # el backfill. Nullable por ahora (NOT NULL vía migración R7, post-backfill).
    universidad_id: Mapped[int | None] = mapped_column(
        ForeignKey("universidades.id"),
        nullable=True,
        index=True,
    )
    numero: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Número de unidad (1..N), define el orden",
    )
    moodle_section_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="ID de la sección CABECERA de Moodle (la sección 'N- Tema')",
    )
    nombre: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("materia_id", "numero", name="uq_unidad_materia_numero"),
        UniqueConstraint(
            "materia_id", "moodle_section_id", name="uq_unidad_materia_section"
        ),
    )

    # Relationships
    materia: Mapped["Materia"] = relationship(
        "Materia",
        back_populates="unidades",
    )
    rubricas: Mapped[list["Rubrica"]] = relationship(
        "Rubrica",
        back_populates="unidad",
    )
    # Componentes evaluables (TP/Quiz/Autoeval/Cierre), configurados a mano en el ABM.
    # §9.bis F. lazy="selectin" para que el snapshot acceda a u.componentes sin eager
    # load explícito (igual que materia.unidades).
    componentes: Mapped[list["ComponenteUnidad"]] = relationship(
        "ComponenteUnidad",
        back_populates="unidad",
        cascade="all, delete-orphan",
        order_by="ComponenteUnidad.orden",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Unidad(id={self.id}, materia_id={self.materia_id}, numero={self.numero})>"
