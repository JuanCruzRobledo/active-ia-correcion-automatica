# app/models/cierre_cursada.py
"""
CierreCursadaItem, CierreCursadaRun y CierreCursadaAlumno — cierre de cursada
(PROMOCIONA/REGULARIZA/RECURSA) generado desde el admin panel.

  CierreCursadaItem: mapeo confirmado (materia, cuatrimestre, ítem de Moodle)
    → categoría (TP/AUTOEVAL/PARCIAL_1/PARCIAL_2/TPI/IGNORAR). Se sugiere por
    regex (cierre_cursada_calculo.sugerir_categoria) pero SIEMPRE se calcula
    con la fila confirmada acá, nunca con la sugerencia sin revisar.
  CierreCursadaRun: cabecera de una corrida (histórico, append-only — igual
    que AvanceSnapshot).
  CierreCursadaAlumno: veredicto + datos crudos de auditoría por alumno.

Ref: plan "Cierre de Cursada — reporte automático en el admin panel".
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CategoriaItemCierreEnum, EstadoCierreEnum

if TYPE_CHECKING:
    from app.models.comision import Comision
    from app.models.cohorte import Cuatrimestre
    from app.models.materia import Materia
    from app.models.usuario import Usuario


class CierreCursadaItem(Base, TimestampMixin):
    """Mapeo confirmado de un ítem del calificador de Moodle a una categoría.

    Clave (materia, cuatrimestre, cmid): los nombres/ids de ítem cambian de
    cohorte a cohorte, así que el mapeo NUNCA se comparte entre cuatrimestres.
    """

    __tablename__ = "cierre_cursada_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), nullable=False, index=True)
    cuatrimestre_id: Mapped[int] = mapped_column(
        ForeignKey("cuatrimestres.id"), nullable=False, index=True
    )
    moodle_cmid: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre_moodle: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria: Mapped[CategoriaItemCierreEnum] = mapped_column(
        SQLEnum(CategoriaItemCierreEnum, name="categoriaitemcierreenum", create_type=True),
        nullable=False,
    )
    unidad: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Número de unidad (TP/AUTOEVAL); NULL para PARCIAL/TPI/IGNORAR"
    )
    opcional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Excluida del denominador de tp_ok/autoeval_ok (ej. Unidad 9/10)",
    )
    orden: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Orden real en el curso de Moodle, para la UI de revisión"
    )

    __table_args__ = (
        UniqueConstraint(
            "materia_id", "cuatrimestre_id", "moodle_cmid",
            name="uq_cierre_item_materia_cuatri_cmid",
        ),
    )

    materia: Mapped["Materia"] = relationship("Materia")
    cuatrimestre: Mapped["Cuatrimestre"] = relationship("Cuatrimestre")

    def __repr__(self) -> str:
        return f"<CierreCursadaItem(materia_id={self.materia_id}, cmid={self.moodle_cmid}, categoria={self.categoria})>"


class CierreCursadaRun(Base, TimestampMixin):
    """Cabecera de una corrida de cierre de cursada. Append-only (histórico)."""

    __tablename__ = "cierre_cursada_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), nullable=False, index=True)
    cuatrimestre_id: Mapped[int] = mapped_column(
        ForeignKey("cuatrimestres.id"), nullable=False, index=True
    )
    umbral_tp_pct: Mapped[float] = mapped_column(
        Float, nullable=False, comment="% mínimo de TPs aprobados, ingresado por el usuario en esta corrida"
    )
    reglas_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="{autoeval_min_pct, parcial_promocion_min_pct, parcial_regulariza_min_pct, "
        "tpi_min_pct} CONGELADOS al momento de la corrida — reproducibilidad histórica",
    )
    generado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    total_alumnos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_promociona: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_regulariza: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_recursa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    materia: Mapped["Materia"] = relationship("Materia")
    cuatrimestre: Mapped["Cuatrimestre"] = relationship("Cuatrimestre")
    generado_por: Mapped["Usuario"] = relationship("Usuario")
    alumnos: Mapped[list["CierreCursadaAlumno"]] = relationship(
        "CierreCursadaAlumno",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CierreCursadaRun(id={self.id}, materia_id={self.materia_id}, total_alumnos={self.total_alumnos})>"


class CierreCursadaAlumno(Base):
    """Veredicto de cierre de un alumno dentro de una corrida, con los datos
    crudos que lo justifican (auditoría — nunca se calcula "a ojo")."""

    __tablename__ = "cierre_cursada_alumnos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cierre_cursada_runs.id"), nullable=False, index=True)
    moodle_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    apellido: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)

    comision_id: Mapped[int | None] = mapped_column(ForeignKey("comisiones.id"), nullable=True)
    comision_nombre: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Denormalizado: 'Sin comisión asignada' si no matcheó ningún grupo"
    )
    tutor_nombre: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Datos crudos de auditoría (ver cierre_cursada_calculo.calcular_estado para el
    # shape que consume cada uno).
    tps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    autoeval_pcts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parcial1_instancias: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parcial2_instancias: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tpi_instancias: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    tp_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    autoeval_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    p1_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    p2_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    tpi_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    estado: Mapped[EstadoCierreEnum] = mapped_column(
        SQLEnum(EstadoCierreEnum, name="estadocierreenum", create_type=True),
        nullable=False,
        index=True,
    )
    nota_final: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="0-10, solo si PROMOCIONA; None = 'N/E' en el reporte"
    )
    habilitado_final: Mapped[str] = mapped_column(String(60), nullable=False)

    run: Mapped["CierreCursadaRun"] = relationship("CierreCursadaRun", back_populates="alumnos")
    comision: Mapped["Comision | None"] = relationship("Comision")

    def __repr__(self) -> str:
        return f"<CierreCursadaAlumno(run_id={self.run_id}, moodle_user_id={self.moodle_user_id}, estado={self.estado})>"
