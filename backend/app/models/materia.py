# app/models/materia.py
"""
Materia and CoordinadorMateria models for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.2, 3.3
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.cohorte import Cuatrimestre
    from app.models.trabajo_practico import TrabajoPractico
    from app.models.comision import Comision
    from app.models.examen_materia import ExamenMateria
    from app.models.rubrica import Rubrica
    from app.models.unidad import Unidad
    from app.models.usuario import Usuario


class Materia(Base, TimestampMixin):
    """
    Materia académica.

    Representa una materia/curso (ej: Programación 1).
    Las rúbricas se definen a nivel de materia y son compartidas
    por todas las comisiones del mismo año.
    """

    __tablename__ = "materias"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Fase 0 multi-tenant (openspec/changes/multi-tenant-modelo-datos): denormalizada
    # en cascada, raíz del árbol (el resto de las tablas la propagan desde acá).
    # NOT NULL desde migración R7 (Fase 0); Fase 4 alinea el type hint.
    universidad_id: Mapped[int] = mapped_column(
        ForeignKey("universidades.id"),
        nullable=False,
        index=True,
    )
    codigo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activa: Mapped[bool] = mapped_column(default=True, index=True)
    moodle_course_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Identificador externo del sistema cliente (change trabajos-practicos-y-external-ref).
    # OPCIONAL: las materias del flujo de Moodle no tienen ninguno. Cadena opaca:
    # se guarda y se compara, nunca se interpreta.
    external_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ===== Dashboard de Gestores (PLAN_DASHBOARD_GESTORES.md) =====
    cuatrimestre_id: Mapped[int | None] = mapped_column(
        ForeignKey("cuatrimestres.id"),
        nullable=True,
        index=True,
        comment="Cuatrimestre (y vía él, cohorte) al que pertenece la materia",
    )
    unidad_actual: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Número de unidad que se está cursando (lo setea el admin)",
    )
    moodle_section_fin_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "ID de la 1ª sección de Moodle que YA NO es unidad de contenido "
            "(ej: 'Trabajo Integrador'). Actividades en secciones con section# >= "
            "el de ésta NO cuentan para el avance (parciales/integrador). NULL = sin tope."
        ),
    )
    etiqueta_unidad: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Unidad",
        comment=(
            "Cómo se llama la progresión en esta materia para los reportes "
            "(Excel/PDF/emails): 'Unidad' (default) o 'Semana' (ej. PYE)."
        ),
    )
    # Umbrales de riesgo configurables por materia (en "unidades/semanas de atraso").
    # delta = unidad_actual − unidad_alcanzada. delta < medio → AL_DIA; medio <= delta <
    # alto → RIESGO_MEDIO; delta >= alto → RIESGO_ALTO. Defaults (1, 2) = regla histórica;
    # una materia por semanas (Estadística, 13 semanas) puede aflojar a 3 y 5.
    riesgo_medio_desde: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Atraso (delta) a partir del cual el alumno entra en RIESGO_MEDIO",
    )
    riesgo_alto_desde: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        server_default="2",
        comment="Atraso (delta) a partir del cual el alumno entra en RIESGO_ALTO (> medio)",
    )

    __table_args__ = (
        # Fase 0 multi-tenant: reemplaza el unique global de `codigo` (D5 del
        # design.md) — dos universidades pueden compartir código de materia.
        UniqueConstraint(
            "universidad_id",
            "codigo",
            name="uq_materias_universidad_id_codigo",
        ),
        # El identificador externo es único DENTRO de su universidad. Parcial
        # sobre no nulos: la enorme mayoría de las materias (las de Moodle) no
        # tienen ninguno, y varios NULL no deben colisionar entre sí.
        Index(
            "uq_materia_universidad_external_ref",
            "universidad_id",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref IS NOT NULL"),
            sqlite_where=text("external_ref IS NOT NULL"),
        ),
    )

    # Relationships
    cuatrimestre: Mapped["Cuatrimestre | None"] = relationship(
        "Cuatrimestre",
        back_populates="materias",
    )
    unidades: Mapped[list["Unidad"]] = relationship(
        "Unidad",
        back_populates="materia",
        lazy="selectin",
        order_by="Unidad.numero",
        cascade="all, delete-orphan",
    )
    examenes: Mapped[list["ExamenMateria"]] = relationship(
        "ExamenMateria",
        back_populates="materia",
        lazy="selectin",
        order_by="ExamenMateria.orden",
        cascade="all, delete-orphan",
    )
    coordinadores: Mapped[list["CoordinadorMateria"]] = relationship(
        "CoordinadorMateria",
        back_populates="materia",
        lazy="selectin",
    )
    comisiones: Mapped[list["Comision"]] = relationship(
        "Comision",
        back_populates="materia",
        lazy="selectin",
    )
    # SIN `lazy="selectin"`, a diferencia de sus hermanas de acá arriba. Con
    # selectin, CADA carga de una materia en toda la app dispara un SELECT extra
    # contra `trabajos_practicos` — una tabla que hoy no lee ningún camino del
    # flujo de Moodle, que es la enorme mayoría del tráfico. Los repositorios que
    # sí la necesiten piden `selectinload(Materia.trabajos_practicos)` explícito.
    trabajos_practicos: Mapped[list["TrabajoPractico"]] = relationship(
        "TrabajoPractico",
        back_populates="materia",
    )
    rubricas: Mapped[list["Rubrica"]] = relationship(
        "Rubrica",
        back_populates="materia",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Materia(id={self.id}, codigo='{self.codigo}', nombre='{self.nombre}')>"


class CoordinadorMateria(Base):
    """
    Relación N:M entre Coordinador y Materia.

    Un coordinador puede estar asignado a varias materias.
    Una materia puede tener varios coordinadores.
    """

    __tablename__ = "coordinador_materia"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    coordinador_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
    )
    asignado_en: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "coordinador_id",
            "materia_id",
            name="uq_coordinador_materia",
        ),
    )

    # Relationships
    coordinador: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="materias_coordinadas",
    )
    materia: Mapped["Materia"] = relationship(
        "Materia",
        back_populates="coordinadores",
    )

    def __repr__(self) -> str:
        return f"<CoordinadorMateria(coordinador_id={self.coordinador_id}, materia_id={self.materia_id})>"
