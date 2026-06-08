# app/models/tutor_nexo.py
"""
TutorNexo model for Active-IA (notificaciones por email).

Un tutor nexo recibe semanalmente un Excel con los alumnos de SU regional
(agrupados por materia). NO es un Usuario del sistema (no tiene login): es una
entidad independiente con nombre + email + la regional que cubre.

La `regional` matchea el nombre derivado del grupo Moodle "R-<nombre>"
(gestion_parser.parse_regional), p. ej. "Mendoza", "Villa María".

Ref: PLAN_NOTIFICACIONES_EMAIL.md §4.2
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class TutorNexo(Base, TimestampMixin, SoftDeleteMixin):
    """Tutor nexo de una regional (destinatario del Excel semanal)."""

    __tablename__ = "tutores_nexo"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    # Nombre de la regional SIN el prefijo "R-" (como lo devuelve parse_regional).
    regional: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )

    def __repr__(self) -> str:
        return f"<TutorNexo(id={self.id}, regional='{self.regional}', email='{self.email}')>"
