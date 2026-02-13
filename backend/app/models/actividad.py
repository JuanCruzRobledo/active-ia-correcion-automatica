# app/models/actividad.py
"""
Modelo de Actividad para auditoría del sistema.

Registra acciones importantes como creación de usuarios, materias,
comisiones y rúbricas para mostrar en el Dashboard Admin.

Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import TipoActividadEnum


class Actividad(Base):
    """
    Registro de actividades/auditoría del sistema.

    Registra acciones importantes como creación de usuarios, materias,
    comisiones y rúbricas para mostrar en el Dashboard Admin.
    """

    __tablename__ = "actividades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Tipo de actividad
    tipo: Mapped[TipoActividadEnum] = mapped_column(
        SQLEnum(TipoActividadEnum, create_type=False), nullable=False, index=True
    )

    # Usuario que realizó la acción
    usuario_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,  # Puede ser NULL si el usuario se elimina
    )

    # Descripción de la actividad (ej: "Usuario 'Juan Pérez' creado")
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)

    # ID de la entidad afectada (ej: id del usuario creado)
    entidad_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Nombre de la entidad afectada (ej: nombre del usuario, materia, etc.)
    entidad_nombre: Mapped[str] = mapped_column(String(255), nullable=False)

    # Datos adicionales en formato JSON (opcional)
    metadatos: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps - use PostgreSQL server time to avoid timezone issues
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relaciones
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="actividades_realizadas")
