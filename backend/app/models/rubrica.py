# app/models/rubrica.py
"""
Rubrica model for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.6
Ref: docs/specs/Rubrica.md (V2 schema)
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import ARRAY, Enum as SQLEnum, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import FuenteRubricaEnum, TipoRubricaEnum

if TYPE_CHECKING:
    from app.models.entrega import Entrega
    from app.models.materia import Materia


class Rubrica(Base, TimestampMixin):
    """
    Rúbrica de evaluación V2.

    Define los criterios de evaluación para un trabajo/examen con estructura jerárquica.
    Las rúbricas pertenecen a una materia y son compartidas por
    todas las comisiones del mismo año académico.

    Estructura V2 (ver docs/specs/Rubrica.md):
    - Campos estructurados: titulo, descripcion, puntaje_maximo
    - Metadata flexible (JSONB): materia, carrera, lenguaje, framework, etc.
    - Criterios jerárquicos (JSONB): Criterio → Subcriterio → Evidencias
    - Penalizaciones (JSONB): descuentos por incumplimientos
    - Condiciones de desaprobación (JSONB): reglas automáticas de nota final
    """

    __tablename__ = "rubricas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[TipoRubricaEnum] = mapped_column(
        SQLEnum(TipoRubricaEnum, name="tiporubricaenum", create_type=True),
        nullable=False,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    anio: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # ===== Campos V2 =====
    titulo: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Título descriptivo de la rúbrica (ej: 'TP2 - API REST de Productos')"
    )
    descripcion: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Descripción detallada de qué evalúa esta rúbrica"
    )
    puntaje_maximo: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="Puntaje máximo de la rúbrica (siempre 100)"
    )

    # ===== Campos JSONB V2 =====
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Metadata flexible: materia, carrera, lenguaje, framework, formato_entrega, etc."
    )
    criterios_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Array de criterios jerárquicos (Criterio → Subcriterio → Evidencias)"
    )
    penalizaciones_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Array de penalizaciones con descuento_porcentaje"
    )
    condiciones_desaprobacion_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Array de condiciones automáticas de desaprobación"
    )

    # ===== Campos de control =====
    fuente: Mapped[FuenteRubricaEnum] = mapped_column(
        SQLEnum(FuenteRubricaEnum, name="fuenterubricaenum", create_type=True),
        default=FuenteRubricaEnum.MANUAL,
    )
    archivo_original: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    activa: Mapped[bool] = mapped_column(default=True, index=True)
    moodle_assign_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Modo de consolidación del código para las entregas de esta rúbrica.
    # Determina qué extensiones se incluyen al consolidar el código antes de corregir.
    # Valores: 'solo_codigo' | 'web_completo' | 'proyecto_completo' | 'personalizado'.
    # Lo usan la importación desde Moodle (automática) y la carga manual (pre-selección).
    modo_consolidacion: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="solo_codigo",
        server_default="solo_codigo",
    )
    # Extensiones a incluir cuando modo_consolidacion == 'personalizado' (ej: ['.ipynb', '.sql']).
    extensiones_personalizadas: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "materia_id",
            "tipo",
            "numero",
            "anio",
            name="uq_rubrica_materia_tipo_numero_anio",
        ),
    )

    # Relationships
    materia: Mapped["Materia"] = relationship(
        "Materia",
        back_populates="rubricas",
    )
    entregas: Mapped[list["Entrega"]] = relationship(
        "Entrega",
        back_populates="rubrica",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Rubrica(id={self.id}, titulo='{self.titulo}', tipo={self.tipo})>"
