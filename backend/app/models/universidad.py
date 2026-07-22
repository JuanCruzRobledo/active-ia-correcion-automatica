# app/models/universidad.py
"""
Universidad model for Active-IA — Fase 0 del feature multi-tenant.

Introduce Universidad como tenant de primer nivel. Este change SOLO agrega el
modelo y su migración; el CRUD/endpoint de universidades es de una fase
posterior.

Ref: openspec/changes/multi-tenant-modelo-datos/design.md
Ref: openspec/changes/multi-tenant-modelo-datos/specs/universidad-entidad/spec.md
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.usuario_universidad import UsuarioUniversidad


class Universidad(Base, TimestampMixin):
    """
    Universidad/tenant de primer nivel.

    Fase 0 de un feature multi-tenant de 6 fases: por ahora hay una sola
    universidad semilla (TUPaD) y el resto del sistema sigue funcionando
    igual (convivencia con los campos viejos de Usuario).
    """

    __tablename__ = "universidades"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
        index=True,
    )
    moodle_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activa: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # Relationships
    # PERF-001: mismo criterio que Usuario.universidades — nada la lee todavía en
    # Fase 0, lazy="raise" evita precargarla en cada query de Universidad.
    membresias: Mapped[list["UsuarioUniversidad"]] = relationship(
        "UsuarioUniversidad",
        back_populates="universidad",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Universidad(id={self.id}, nombre='{self.nombre}')>"
