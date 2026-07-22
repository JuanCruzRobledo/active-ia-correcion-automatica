# app/models/usuario.py
"""
Usuario model for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.1
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SQLEnum, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import RolEnum

if TYPE_CHECKING:
    from app.models.actividad import Actividad
    from app.models.comision import ComisionTutor
    from app.models.correccion import Correccion
    from app.models.entrega import Entrega
    from app.models.materia import CoordinadorMateria


class Usuario(Base, TimestampMixin):
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
    # Email del usuario. Lo usan las notificaciones por email (tutor académico
    # recibe el PDF de sus comisiones). Ver PLAN_NOTIFICACIONES_EMAIL.md §4.1.
    email: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolEnum] = mapped_column(
        SQLEnum(RolEnum, name="rol_enum", create_type=True),
        nullable=False,
        index=True,
    )

    # API Key de Gemini Studio (Google, encriptada con AES-128-CBC (Fernet)).
    # Corresponde al modo de corrección correction_provider == "gemini".
    gemini_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # API Key de OpenRouter (encriptada con AES-128-CBC (Fernet)).
    # Corresponde al modo de corrección correction_provider == "openrouter".
    # Se guarda por separado de la de Gemini Studio: el tutor mantiene ambas.
    openrouter_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Credenciales Moodle (password cifrado con AES-128-CBC (Fernet))
    moodle_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    moodle_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    moodle_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gemini_api_key_valid: Mapped[bool] = mapped_column(default=False)

    # Validez de la API key de OpenRouter (último health check OK).
    openrouter_api_key_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    # Toggle manual declarado por el tutor: indica que su API key Gemini tiene
    # facturación habilitada (paga). Habilita la corrección masiva global.
    # No se infiere automáticamente: la API de Gemini no expone el tier de billing.
    gemini_api_key_paga: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

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
    # PERF-001: estas 3 colecciones se precargaban con selectin en CADA query de
    # Usuario (actividades_realizadas es un audit log sin techo) pero NINGUN codigo
    # ni schema las lee. lazy="raise" corta la precarga inutil y, si en el futuro
    # alguien las accede sin selectinload() explicito, falla con un error claro en
    # los tests (no un MissingGreenlet silencioso en produccion).
    entregas_subidas: Mapped[list["Entrega"]] = relationship(
        "Entrega",
        back_populates="subido_por",
        lazy="raise",
    )
    correcciones_realizadas: Mapped[list["Correccion"]] = relationship(
        "Correccion",
        back_populates="corregido_por",
        lazy="raise",
    )
    actividades_realizadas: Mapped[list["Actividad"]] = relationship(
        "Actividad",
        back_populates="usuario",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, username='{self.username}', rol={self.rol})>"
