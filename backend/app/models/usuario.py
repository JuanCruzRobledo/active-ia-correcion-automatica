# app/models/usuario.py
"""
Usuario model for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.1
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import RolEnum

if TYPE_CHECKING:
    from app.models.actividad import Actividad
    from app.models.comision import ComisionTutor
    from app.models.correccion import Correccion
    from app.models.entrega import Entrega
    from app.models.materia import CoordinadorMateria


class Usuario(Base, TimestampMixin, SoftDeleteMixin):
    """
    Usuario del sistema.

    Representa a los usuarios que interactúan con la plataforma:
    - ADMIN: Gestión total del sistema
    - COORDINADOR: Gestiona rúbricas y comisiones de sus materias
    - TUTOR: Corrige entregas de sus comisiones
    """

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolEnum] = mapped_column(
        SQLEnum(RolEnum, name="rol_enum", create_type=True),
        nullable=False,
        index=True,
    )

    # API Key de Gemini (encriptada con AES-256)
    gemini_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Credenciales Moodle (password cifrado con AES-256)
    moodle_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    moodle_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    moodle_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gemini_api_key_valid: Mapped[bool] = mapped_column(default=False)

    # Proveedor de corrección preferido (ej: 'gemini', 'openai', 'anthropic')
    correction_provider: Mapped[str] = mapped_column(
        String(50),
        default="gemini",
        server_default="gemini",
        nullable=False,
    )

    # Control de primer login
    primer_login: Mapped[bool] = mapped_column(default=True)

    # Control de bloqueo por intentos fallidos
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(nullable=True)

    # Soft delete
    activo: Mapped[bool] = mapped_column(default=True, index=True)

    # Relationships
    materias_coordinadas: Mapped[list["CoordinadorMateria"]] = relationship(
        "CoordinadorMateria",
        back_populates="coordinador",
        lazy="selectin",
    )
    comisiones_asignadas: Mapped[list["ComisionTutor"]] = relationship(
        "ComisionTutor",
        back_populates="tutor",
        lazy="selectin",
    )
    entregas_subidas: Mapped[list["Entrega"]] = relationship(
        "Entrega",
        back_populates="subido_por",
        lazy="selectin",
    )
    correcciones_realizadas: Mapped[list["Correccion"]] = relationship(
        "Correccion",
        back_populates="corregido_por",
        lazy="selectin",
    )
    actividades_realizadas: Mapped[list["Actividad"]] = relationship(
        "Actividad",
        back_populates="usuario",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, username='{self.username}', rol={self.rol})>"
