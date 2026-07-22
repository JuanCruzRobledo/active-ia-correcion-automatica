# app/models/cierre_cursada.py
"""
CierreCursadaRun y CierreCursadaAlumno — cierre de cursada
(PROMOCIONA/REGULARIZA/RECURSA) generado desde el admin panel, dirigido por la
configuración de exámenes de la materia (`ExamenMateria`).

  CierreCursadaRun: cabecera de una corrida (histórico, append-only — igual
    que AvanceSnapshot). Congela `examenes_snapshot` (config de exámenes usada
    en la corrida) para reproducibilidad histórica. `umbral_tp_pct` y
    `reglas_snapshot` son legacy (nullable, ya no se escriben).
  CierreCursadaAlumno: veredicto + datos por examen (`resultados_examenes`,
    `global_valor`) y Nota Final ponderada (`nota_final`) por alumno. Las
    columnas del sistema viejo (`tp_ok`, `autoeval_ok`, `p1_max`, `p2_max`,
    `tpi_max`, `parcial1_instancias`, `parcial2_instancias`, `tpi_instancias`,
    `habilitado_final`) son legacy (nullable, ya no se escriben).

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import EstadoCierreEnum

if TYPE_CHECKING:
    from app.models.comision import Comision
    from app.models.cohorte import Cuatrimestre
    from app.models.materia import Materia
    from app.models.usuario import Usuario


class CierreCursadaRun(Base, TimestampMixin):
    """Cabecera de una corrida de cierre de cursada. Append-only (histórico)."""

    __tablename__ = "cierre_cursada_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), nullable=False, index=True)
    # Fase 0 multi-tenant: denormalizada, propagada desde materia.universidad_id en
    # el backfill. Nullable por ahora (NOT NULL vía migración R7, post-backfill).
    universidad_id: Mapped[int | None] = mapped_column(
        ForeignKey("universidades.id"), nullable=True, index=True
    )
    cuatrimestre_id: Mapped[int] = mapped_column(
        ForeignKey("cuatrimestres.id"), nullable=False, index=True
    )
    umbral_tp_pct: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="LEGACY (sistema viejo de mapeo manual, ya no se escribe). "
        "% mínimo de TPs aprobados, ingresado por el usuario en esta corrida",
    )
    reglas_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="LEGACY (sistema viejo de mapeo manual, ya no se escribe). "
        "{autoeval_min_pct, parcial_promocion_min_pct, parcial_regulariza_min_pct, "
        "tpi_min_pct} CONGELADOS al momento de la corrida",
    )
    examenes_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Config de ExamenMateria (PARCIAL/GLOBAL) CONGELADA al momento de la "
        "corrida — reproducibilidad histórica del cierre dirigido por examen",
    )
    generado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    total_alumnos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_promociona: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_regulariza: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_recursa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_abandono: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

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

    # Resultado por examen principal (PARCIAL/GLOBAL), dirigido por ExamenMateria.
    resultados_examenes: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Lista por examen principal: [{examen_id, etiqueta, tipo, modo, "
        "valor_real, resultado_escala, cumple_minimo, cumple_banda, rescatado}] "
        "— auditoría dirigida por config",
    )
    global_valor: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Nota del examen GLOBAL con rescate aplicado (columna 'Global TPI' "
        "del Excel); None = 'N/E'",
    )

    # LEGACY (sistema viejo de mapeo manual por CierreCursadaItem, ya no se escribe).
    tps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    autoeval_pcts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parcial1_instancias: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parcial2_instancias: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tpi_instancias: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    tp_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    autoeval_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    p1_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    p2_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    tpi_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    estado: Mapped[EstadoCierreEnum] = mapped_column(
        SQLEnum(EstadoCierreEnum, name="estadocierreenum", create_type=True),
        nullable=False,
        index=True,
    )
    nota_final: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Nota Final ponderada 0-10 (parciales*0.4 + global*0.6, escala "
        "normalizada); se llena para todos los alumnos con insumos completos, "
        "None = 'N/E' sólo si falta algún insumo requerido",
    )
    habilitado_final: Mapped[str | None] = mapped_column(String(60), nullable=True)

    run: Mapped["CierreCursadaRun"] = relationship("CierreCursadaRun", back_populates="alumnos")
    comision: Mapped["Comision | None"] = relationship("Comision")

    def __repr__(self) -> str:
        return f"<CierreCursadaAlumno(run_id={self.run_id}, moodle_user_id={self.moodle_user_id}, estado={self.estado})>"
