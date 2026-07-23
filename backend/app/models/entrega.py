# app/models/entrega.py
"""
Entrega and EntregaHistorial models for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md secciones 3.7 y 3.9
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text, text, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import EstadoEntregaEnum

if TYPE_CHECKING:
    from app.models.comision import Comision
    from app.models.correccion import Correccion
    from app.models.rubrica import Rubrica
    from app.models.usuario import Usuario


class Entrega(Base, TimestampMixin, SoftDeleteMixin):
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
    # Fase 0 multi-tenant: denormalizada, propagada desde comision.universidad_id
    # en el backfill. NOT NULL desde migración R7 (Fase 0); Fase 4 alinea el type hint.
    universidad_id: Mapped[int] = mapped_column(
        ForeignKey("universidades.id"),
        nullable=False,
        index=True,
    )
    alumno_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    archivo_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    archivo_tamanio: Mapped[int] = mapped_column(Integer, default=0)
    archivo_tipo: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )  # 'zip' o 'txt'
    contenido_preview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Primeros 500 caracteres
    # PERF-002/PERF-006: columna GIGANTE (código completo consolidado). Se lee sólo en
    # la corrección y en el endpoint de contenido, nunca en los listados → deferred=True
    # para que NO se arrastre en cada select(Entrega). Los consumidores que la necesitan
    # la cargan explícitamente con undefer() (entrega_repository.get_by_id[_with_relations]
    # (load_contenido=True)). Acceder a ella fuera de una query que la undefiera dispara un
    # lazy load que en async es MissingGreenlet.
    contenido_consolidado: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        deferred=True,
    )  # Full consolidated content
    archivos_incluidos: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # List of files included in consolidation
    # PERF-002/PERF-006: columna GIGANTE (PDF en Base64, ~MB). Mismo criterio que
    # contenido_consolidado: deferred=True + undefer() en los consumidores.
    pdf_contenido_b64: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        deferred=True,
    )  # PDF content encoded in Base64 (only for archivo_tipo='pdf')
    estado: Mapped[EstadoEntregaEnum] = mapped_column(
        SQLEnum(EstadoEntregaEnum, name="estadoentregaenum", create_type=True),
        default=EstadoEntregaEnum.SUBIDA,
        index=True,
    )
    archivado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text('false'),
        index=True,
    )
    hash_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    subido_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
    )
    # ID del usuario en Moodle (poblado al importar desde Moodle). Necesario para
    # publicar la nota/feedback de vuelta al alumno correcto vía mod_assign_save_grade.
    moodle_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    # Detalle del ÚLTIMO error de corrección (item #1). NULL si nunca falló o tras una
    # corrección exitosa (se limpian al pasar a CORREGIDA). error_code = código del
    # catálogo (app/core/error_catalog); error_mensaje = texto ya traducido al usuario.
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        # Índice único: solo permite una entrega por alumno y rúbrica
        Index(
            "uq_entrega_rubrica_alumno",
            "rubrica_id",
            "alumno_nombre",
            unique=True,
        ),
        # PERF-016: el listado de entregas ordena por created_at DESC
        # (entrega_repository.py:152); sin índice es un seq scan + sort.
        Index(
            "ix_entregas_created_at",
            "created_at",
        ),
        # PERF-015: el polling de novedades (EntregaRepository.version) hace
        # MAX(updated_at)+COUNT(id) sobre entregas cada ~45s por cliente; sin índice
        # es un scan completo. El TimestampMixin (base.py) NO indexa updated_at —
        # está COMPARTIDO por muchas tablas, así que el índice se declara SCOPED acá,
        # solo para entregas (mismo patrón que ix_entregas_created_at).
        Index(
            "ix_entregas_updated_at",
            "updated_at",
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
        cascade="all, delete-orphan",
    )
    historial: Mapped[list["EntregaHistorial"]] = relationship(
        "EntregaHistorial",
        back_populates="entrega_actual",
        lazy="selectin",
        cascade="all, delete-orphan",
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
    archivo_tamanio: Mapped[int] = mapped_column(Integer, default=0)
    contenido_preview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # CRUD-005: el contenido REAL de la versión anterior (antes solo se guardaba el
    # preview de 500 chars y el trabajo del alumno se perdía al sobrescribir).
    # deferred=True: los listados del historial no lo necesitan.
    contenido_consolidado: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        deferred=True,
    )
    pdf_contenido_b64: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        deferred=True,
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
