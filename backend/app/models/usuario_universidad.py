# app/models/usuario_universidad.py
"""
UsuarioUniversidad model — membresía usuario<->universidad (Fase 0 multi-tenant).

Junction con atributos, mismo patrón que ComisionTutor/CoordinadorMateria, pero
con `rol` scopeado a la membresía (un usuario puede tener rol distinto por
universidad) y credenciales Moodle por (usuario, universidad).

El tipo PG `rol_enum` ya existe (lo crea `usuarios.rol`): `create_type=False`
para NO recrearlo (mismo patrón que `componentes_unidad.modo_aprobacion` con
`modoaprobacionenum`).

Ref: openspec/changes/multi-tenant-modelo-datos/design.md (D3)
Ref: openspec/changes/multi-tenant-modelo-datos/specs/usuario-universidad-membresia/spec.md
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import RolEnum

if TYPE_CHECKING:
    from app.models.universidad import Universidad
    from app.models.usuario import Usuario


class UsuarioUniversidad(Base):
    """
    Membresía de un `Usuario` en una `Universidad`.

    Un usuario puede tener un rol distinto en cada universidad y credenciales
    Moodle propias por (usuario, universidad). El rol viejo global sigue
    viviendo en `usuarios.rol` (convivencia, Fase 0 no lo lee ni lo escribe
    desde acá).
    """

    __tablename__ = "usuario_universidad"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )
    universidad_id: Mapped[int] = mapped_column(
        ForeignKey("universidades.id"),
        nullable=False,
        index=True,
    )
    rol: Mapped[RolEnum] = mapped_column(
        SQLEnum(RolEnum, name="rol_enum", create_type=False),
        nullable=False,
    )
    moodle_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    moodle_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "universidad_id",
            name="uq_usuario_universidad",
        ),
    )

    # Relationships
    usuario: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="universidades",
    )
    universidad: Mapped["Universidad"] = relationship(
        "Universidad",
        back_populates="membresias",
    )

    def __repr__(self) -> str:
        return (
            f"<UsuarioUniversidad(usuario_id={self.usuario_id}, "
            f"universidad_id={self.universidad_id}, rol={self.rol})>"
        )
