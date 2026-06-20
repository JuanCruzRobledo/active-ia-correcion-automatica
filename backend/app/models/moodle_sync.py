# app/models/moodle_sync.py
"""
MoodleSync model for Active-IA.

Registra cada intento de sincronización de una corrección hacia Moodle
(publicar nota + feedback vía mod_assign_save_grade).

Sirve para:
- Auditoría: quién envió, cuándo, con qué nota/comentario, y el error si falló.
- Idempotencia / anti doble-envío: si existe un registro ENVIADO para la corrección,
  no se reenvía salvo que el usuario fuerce explícitamente.

Relación N:1 con Correccion (se conserva el historial de intentos).
"""

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import MoodleSyncEstado

if TYPE_CHECKING:
    from app.models.correccion import Correccion
    from app.models.usuario import Usuario


class MoodleSync(Base, TimestampMixin):
    """Registro de un intento de envío de una corrección a Moodle."""

    __tablename__ = "moodle_sync"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    correccion_id: Mapped[int] = mapped_column(
        ForeignKey("correcciones.id"),
        nullable=False,
        index=True,
    )
    estado: Mapped[MoodleSyncEstado] = mapped_column(
        SQLEnum(MoodleSyncEstado, name="moodlesyncestado", create_type=False),
        nullable=False,
        index=True,
    )
    # Nota efectivamente enviada: numérica ("90.00") o cualitativa ("Aprobado"/"Desaprobado").
    nota_enviada: Mapped[str | None] = mapped_column(String(50), nullable=True)
    comentario_enviado: Mapped[str | None] = mapped_column(Text, nullable=True)
    moodle_assignment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moodle_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mensaje_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    intento: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enviado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
    )

    # Relationships
    correccion: Mapped["Correccion"] = relationship(
        "Correccion",
        back_populates="moodle_syncs",
    )
    enviado_por: Mapped["Usuario"] = relationship("Usuario")

    def __repr__(self) -> str:
        return (
            f"<MoodleSync(id={self.id}, correccion_id={self.correccion_id}, "
            f"estado={self.estado})>"
        )
