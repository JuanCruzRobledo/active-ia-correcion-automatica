# app/models/entrega.py
"""
Entrega and EntregaHistorial models for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md secciones 3.7 y 3.9
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text, text, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import EstadoEntregaEnum

if TYPE_CHECKING:
    from app.models.comision import Comision
    from app.models.correccion import Correccion
    from app.models.rubrica import Rubrica
    from app.models.usuario import Usuario


class Entrega(Base, TimestampMixin):
    """
    Entrega de alumno.

    Representa un archivo (ZIP o TXT) subido por un tutor/coordinador
    que contiene el código de un alumno para ser evaluado.

    Una entrega pertenece a una comisión y se evalúa según una rúbrica.
    El sistema permite sobrescribir entregas, guardando el historial
    en la tabla EntregaHistorial.
    """

    __tablename__ = "entregas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    comision_id: Mapped[int] = mapped_column(
        ForeignKey("comisiones.id"),
        nullable=False,
        index=True,
    )
    rubrica_id: Mapped[int] = mapped_column(
        ForeignKey("rubricas.id"),
        nullable=False,
        index=True,
    )
    alumno_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    archivo_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    archivo_ruta: Mapped[str] = mapped_column(String(500), nullable=False)
    archivo_tamanio: Mapped[int] = mapped_column(Integer, default=0)
    archivo_tipo: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )  # 'zip' o 'txt'
    contenido_preview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Primeros 500 caracteres
    contenido_consolidado: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Full consolidated content
    archivos_incluidos: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # List of files included in consolidation
    estado: Mapped[EstadoEntregaEnum] = mapped_column(
        SQLEnum(EstadoEntregaEnum, name="estadoentregaenum", create_type=True),
        default=EstadoEntregaEnum.SUBIDA,
        index=True,
    )
    hash_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    subido_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )

    __table_args__ = (
        # Índice único: solo permite una entrega por alumno y rúbrica
        Index(
            "uq_entrega_rubrica_alumno",
            "rubrica_id",
            "alumno_nombre",
            unique=True,
        ),
    )

    # Relationships
    comision: Mapped["Comision"] = relationship(
        "Comision",
        back_populates="entregas",
    )
    rubrica: Mapped["Rubrica"] = relationship(
        "Rubrica",
        back_populates="entregas",
    )
    subido_por: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="entregas_subidas",
    )
    correccion: Mapped["Correccion | None"] = relationship(
        "Correccion",
        back_populates="entrega",
        uselist=False,
    )
    historial: Mapped[list["EntregaHistorial"]] = relationship(
        "EntregaHistorial",
        back_populates="entrega_actual",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Entrega(id={self.id}, alumno='{self.alumno_nombre}', estado={self.estado})>"


class EntregaHistorial(Base):
    """
    Historial de entregas sobrescritas.

    Cuando se sobrescribe una entrega existente (mismo alumno + rúbrica),
    la versión anterior se guarda aquí para mantener trazabilidad.

    Se preserva:
    - El archivo anterior
    - La corrección anterior (si existía)
    - Quién y cuándo sobrescribió
    """

    __tablename__ = "entregas_historial"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entrega_actual_id: Mapped[int] = mapped_column(
        ForeignKey("entregas.id"),
        nullable=False,
        index=True,
    )
    alumno_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    archivo_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    archivo_ruta: Mapped[str] = mapped_column(String(500), nullable=False)
    archivo_tamanio: Mapped[int] = mapped_column(Integer, default=0)
    contenido_preview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    hash_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    nota_anterior: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    correccion_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    sobrescrito_en: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )
    sobrescrito_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )

    # Relationships
    entrega_actual: Mapped["Entrega"] = relationship(
        "Entrega",
        back_populates="historial",
    )
    sobrescrito_por: Mapped["Usuario"] = relationship(
        "Usuario",
    )

    def __repr__(self) -> str:
        return f"<EntregaHistorial(id={self.id}, alumno='{self.alumno_nombre}', sobrescrito_en={self.sobrescrito_en})>"
