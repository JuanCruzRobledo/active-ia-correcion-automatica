# app/models/comision.py
"""
Comision and ComisionTutor models for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.4, 3.5
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.entrega import Entrega
    from app.models.materia import Materia
    from app.models.usuario import Usuario


class Comision(Base, TimestampMixin):
    """
    Comisión de una materia.

    Representa un grupo de alumnos de una materia en un año académico.
    Una comisión puede tener varios tutores asignados.
    """

    __tablename__ = "comisiones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
        index=True,
    )
    # Fase 0 multi-tenant: denormalizada, propagada desde materia.universidad_id en
    # el backfill. NOT NULL desde migración R7 (Fase 0); Fase 4 alinea el type hint.
    universidad_id: Mapped[int] = mapped_column(
        ForeignKey("universidades.id"),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    activa: Mapped[bool] = mapped_column(default=True, index=True)
    moodle_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moodle_group_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Identificador externo del sistema cliente (change correccion-por-ejercicio-con-tests).
    # OPCIONAL: las comisiones del flujo de Moodle no tienen ninguno. Permite que un
    # cliente externo modele sus cohortes si quiere; si no, se usa la comisión de
    # integración configurada en la materia.
    external_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "materia_id",
            "nombre",
            "anio",
            name="uq_comision_materia_nombre_anio",
        ),
        # Parcial sobre no nulos: la enorme mayoría de las comisiones (las de
        # Moodle) no tienen identificador externo, y varios NULL no deben colisionar.
        Index(
            "uq_comision_materia_external_ref",
            "materia_id",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref IS NOT NULL"),
            sqlite_where=text("external_ref IS NOT NULL"),
        ),
    )

    # Relationships
    # `foreign_keys` explicito: desde que `Materia` gano
    # `comision_integracion_id`, hay DOS FKs entre materias y comisiones y
    # SQLAlchemy no puede inferir cual usa este join.
    materia: Mapped["Materia"] = relationship(
        "Materia",
        back_populates="comisiones",
        foreign_keys="Comision.materia_id",
    )
    tutores: Mapped[list["ComisionTutor"]] = relationship(
        "ComisionTutor",
        back_populates="comision",
        lazy="selectin",
    )
    entregas: Mapped[list["Entrega"]] = relationship(
        "Entrega",
        back_populates="comision",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Comision(id={self.id}, nombre='{self.nombre}', anio={self.anio})>"


class ComisionTutor(Base):
    """
    Relación N:M entre Comision y Tutor.

    Un tutor puede estar asignado a varias comisiones.
    Una comisión puede tener varios tutores.
    """

    __tablename__ = "comision_tutor"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    comision_id: Mapped[int] = mapped_column(
        ForeignKey("comisiones.id"),
        nullable=False,
    )
    tutor_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )
    asignado_en: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "comision_id",
            "tutor_id",
            name="uq_comision_tutor",
        ),
    )

    # Relationships
    comision: Mapped["Comision"] = relationship(
        "Comision",
        back_populates="tutores",
    )
    tutor: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="comisiones_asignadas",
    )

    def __repr__(self) -> str:
        return f"<ComisionTutor(comision_id={self.comision_id}, tutor_id={self.tutor_id})>"
