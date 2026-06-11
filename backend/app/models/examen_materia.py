# app/models/examen_materia.py
"""
ExamenMateria model — seguimiento de exámenes de una materia.

A diferencia de ComponenteUnidad (que mide AVANCE de contenido por unidad), un examen
es una evaluación sumativa de la MATERIA (no de una unidad). Por eso cuelga de la
materia y NO entra en el cálculo de unidad_alcanzada.

Numeración: el número visible ("Parcial 1", "Parcial 2"…) se DERIVA del `orden` entre
los exámenes del mismo `tipo` de la materia (no se persiste), así borrar uno deja la
secuencia contigua sin renumerar.

Rescate: RECUPERATORIO/EXTENSION/EXTRAORDINARIA apuntan con `recupera_examen_id` al
PARCIAL que recuperan. Un parcial queda aprobado si lo aprobó O si aprobó alguno de
sus recuperatorios/extensiones/extraordinarias (lógica en examen_mapper).
"""

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ModoAprobacionEnum, TipoExamenEnum

if TYPE_CHECKING:
    from app.models.materia import Materia


class ExamenMateria(Base, TimestampMixin):
    """Un examen de una materia (parcial/recu/extensión/extraordinaria/global)."""

    __tablename__ = "examenes_materia"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[TipoExamenEnum] = mapped_column(
        SQLEnum(TipoExamenEnum, name="tipoexamenenum", create_type=True),
        nullable=False,
    )
    moodle_cmid: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="cmid de la actividad de Moodle del examen"
    )
    modo_aprobacion: Mapped[ModoAprobacionEnum] = mapped_column(
        SQLEnum(ModoAprobacionEnum, name="modoaprobacionenum", create_type=True),
        nullable=False,
        comment="ESCALA (Aprobado/Desaprobado) | NUMERICO (nota >= nota_minima)",
    )
    nota_minima: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Mínimo para aprobar (solo si modo NUMERICO)"
    )
    recupera_examen_id: Mapped[int | None] = mapped_column(
        ForeignKey("examenes_materia.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="PARCIAL que recupera (solo recuperatorio/extensión/extraordinaria)",
    )
    orden: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Orden de alta; deriva el número visible por tipo (Parcial 1, 2…)",
    )

    materia: Mapped["Materia"] = relationship("Materia", back_populates="examenes")
    # Adjacency-list: `recuperan` = los recu/ext/extraordinaria que rescatan a ESTE
    # parcial (one-to-many); el backref `recupera` = el parcial que este examen recupera
    # (many-to-one, remote_side en el id padre).
    recuperan: Mapped[list["ExamenMateria"]] = relationship(
        "ExamenMateria",
        backref=backref("recupera", remote_side=[id]),
    )

    def __repr__(self) -> str:
        return (
            f"<ExamenMateria(id={self.id}, materia_id={self.materia_id}, "
            f"tipo={self.tipo}, cmid={self.moodle_cmid})>"
        )
