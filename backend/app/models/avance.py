# app/models/avance.py
"""
AvanceSnapshot and AvanceAlumno models for Active-IA (Dashboard de Gestores).

Cada corrida del cron (o del botón manual) genera un AvanceSnapshot (cabecera,
fechado → histórico) con N AvanceAlumno (estado de cada alumno de la materia).
El dashboard lee el snapshot MÁS RECIENTE por materia; las tendencias leen la serie.

Los alumnos NO son usuarios de Activia: se identifican por moodle_user_id.

Ref: PLAN_DASHBOARD_GESTORES.md §5, §7
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import EstadoAvanceEnum, OrigenSnapshotEnum

if TYPE_CHECKING:
    from app.models.materia import Materia
    from app.models.usuario import Usuario


class AvanceSnapshot(Base):
    """
    Cabecera de un snapshot de avance de una materia en un instante dado.
    """

    __tablename__ = "avance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
        index=True,
    )
    generado_en: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    unidad_actual: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Valor de materia.unidad_actual CONGELADO al momento del snapshot",
    )
    origen: Mapped[OrigenSnapshotEnum] = mapped_column(
        SQLEnum(OrigenSnapshotEnum, name="origensnapshotenum", create_type=True),
        default=OrigenSnapshotEnum.CRON,
        nullable=False,
    )
    total_alumnos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    materia: Mapped["Materia"] = relationship("Materia")
    alumnos: Mapped[list["AvanceAlumno"]] = relationship(
        "AvanceAlumno",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AvanceSnapshot(id={self.id}, materia_id={self.materia_id}, generado_en={self.generado_en})>"


class AvanceAlumno(Base):
    """
    Estado de avance de un alumno (de Moodle) dentro de un snapshot.
    """

    __tablename__ = "avance_alumnos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("avance_snapshots.id"),
        nullable=False,
        index=True,
    )
    moodle_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    apellido: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    comision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Regional derivada del grupo Moodle "R-<nombre>" (gestion_parser). Se usa para
    # agrupar a los alumnos del tutor nexo. Ver PLAN_NOTIFICACIONES_EMAIL.md §4.1.
    regional: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    unidad_alcanzada: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Unidad más alta completada; NULL si no completó ninguna",
    )
    actividad_actual_nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actividad_actual_unidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actividad_actual_desaprobada: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        server_default="false",
        comment="True si la actividad de mayor unidad fue completada pero REPROBADA (state 3)",
    )
    estado: Mapped[EstadoAvanceEnum] = mapped_column(
        SQLEnum(EstadoAvanceEnum, name="estadoavanceenum", create_type=True),
        nullable=False,
        index=True,
    )
    # Actividades faltantes ya resueltas para el email (PLAN_NOTIFICACIONES_EMAIL.md §4.4):
    #   {"modo": "UNIDADES"|"ACTIVIDADES",
    #    "unidades": [int, ...],
    #    "actividades": [{"cmid": int, "nombre": str, "unidad": int}, ...]}
    # NULL/None => no le falta nada en esta materia (no se reporta).
    actividades_faltantes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Resultados de exámenes (parciales/recuperatorios/etc.) al momento del snapshot, con
    # el rescate ya aplicado (examen_mapper):
    #   {"examenes": [{"examen_id","tipo","numero","etiqueta","resultado","rescatado"}, ...]}
    # NULL/None => la materia no tiene exámenes configurados.
    resultados_examenes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    snapshot: Mapped["AvanceSnapshot"] = relationship(
        "AvanceSnapshot",
        back_populates="alumnos",
    )

    def __repr__(self) -> str:
        return f"<AvanceAlumno(id={self.id}, moodle_user_id={self.moodle_user_id}, estado={self.estado})>"


class SnapshotCronConfig(Base, TimestampMixin):
    """Configuración (singleton, fila id=1) del cron diario de snapshots.

    Editable desde el admin panel: qué usuario provee las credenciales de Moodle
    y a qué hora (Argentina) corre. Ref: PLAN_DASHBOARD_GESTORES.md §7 (T6).
    """

    __tablename__ = "snapshot_cron_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Usuario de cuyas credenciales Moodle se vale el cron (uno de la lista de usuarios).
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    hora: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    minuto: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    usuario: Mapped["Usuario | None"] = relationship("Usuario")

    def __repr__(self) -> str:
        return (
            f"<SnapshotCronConfig(usuario_id={self.usuario_id}, "
            f"hora={self.hora}:{self.minuto:02d}, activo={self.activo})>"
        )
