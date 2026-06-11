# app/models/componente_unidad.py
"""
ComponenteUnidad model — componentes evaluables de una unidad (§9.bis F).

Reemplaza el modelo rígido de 3 cmids fijos (TP/autoeval/cierre) por N componentes
dinámicos por unidad. Cada componente tiene:
  - tipo: etiqueta para el reporte (TP / QUIZ / AUTOEVALUACION / CIERRE).
  - moodle_cmid: la actividad de Moodle vinculada.
  - fuente: cómo se decide si está realizado (SEGUIMIENTO o CALIFICACION).

La lógica de "realizado/deuda" (avance_mapper) depende de la FUENTE, no del tipo:
así una materia sin TP (p.ej. Organización Empresarial: varios quizzes + 1 autoeval,
sin cierre) se modela simplemente con los componentes que tenga, sin casos especiales.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import FuenteComponenteEnum, TipoComponenteEnum

if TYPE_CHECKING:
    from app.models.unidad import Unidad


class ComponenteUnidad(Base, TimestampMixin):
    """Un componente evaluable de una unidad (cmid de Moodle + tipo + fuente)."""

    __tablename__ = "componentes_unidad"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    unidad_id: Mapped[int] = mapped_column(
        ForeignKey("unidades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[TipoComponenteEnum] = mapped_column(
        SQLEnum(TipoComponenteEnum, name="tipocomponenteenum", create_type=True),
        nullable=False,
    )
    moodle_cmid: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="cmid de la actividad de Moodle vinculada"
    )
    fuente: Mapped[FuenteComponenteEnum] = mapped_column(
        SQLEnum(FuenteComponenteEnum, name="fuentecomponenteenum", create_type=True),
        nullable=False,
        comment="SEGUIMIENTO (completion) | CALIFICACION (nota)",
    )
    orden: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Orden de presentación dentro de la unidad",
    )

    unidad: Mapped["Unidad"] = relationship("Unidad", back_populates="componentes")

    def __repr__(self) -> str:
        return (
            f"<ComponenteUnidad(id={self.id}, unidad_id={self.unidad_id}, "
            f"tipo={self.tipo}, fuente={self.fuente}, cmid={self.moodle_cmid})>"
        )
