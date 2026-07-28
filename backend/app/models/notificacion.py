# app/models/notificacion.py
"""
Modelos de la feature de notificaciones por email (Resend).

- EnvioEmailLog: cola + auditoría de cada email (idempotencia por tanda_id + estado,
  reintentos, trazabilidad del resend_id y errores). Ver PLAN_NOTIFICACIONES_EMAIL.md §4.2, §7.
- NotificacionCronConfig: singleton (fila id=1) con la configuración del cron semanal
  (día de semana + hora + usuario de servicio para refrescar snapshots). §5.5.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import EstadoEnvioEnum, TipoNotificacionEnum

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class EnvioEmailLog(Base, TimestampMixin):
    """Un email de notificación encolado/enviado. Sirve de cola y de auditoría."""

    __tablename__ = "envio_email_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Agrupa todos los envíos de una misma corrida semanal (idempotencia/reanudación).
    tanda_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tipo: Mapped[TipoNotificacionEnum] = mapped_column(
        SQLEnum(TipoNotificacionEnum, name="tiponotificacionenum", create_type=True),
        nullable=False,
        index=True,
    )
    destinatario_email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    # Referencia al destinatario según el tipo: moodle_user_id (alumno),
    # usuario_id (tutor académico) o regional (tutor nexo). Texto libre.
    destinatario_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    asunto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estado: Mapped[EstadoEnvioEnum] = mapped_column(
        SQLEnum(EstadoEnvioEnum, name="estadoenvioenum", create_type=True),
        nullable=False,
        default=EstadoEnvioEnum.PENDIENTE,
        index=True,
    )
    resend_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    intentos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    enviado_en: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EnvioEmailLog(id={self.id}, tipo={self.tipo}, "
            f"estado={self.estado}, to={self.destinatario_email})>"
        )


class NotificacionCronConfig(Base, TimestampMixin):
    """Configuración (singleton, fila id=1) del cron semanal de notificaciones.

    Editable desde el admin: día de la semana + hora (Argentina) y el usuario de
    cuyas credenciales Moodle se vale para refrescar los snapshots antes de enviar.
    Los 3 envíos (alumnos/tutores/nexos) corren en cadena. §5.5 / decisión #7.
    """

    __tablename__ = "notificacion_cron_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    # Fase 3 multi-tenant (OQ2): universidad activa para el cron (sin JWT/ctx).
    # Nullable a nivel DB (mismo patrón que usuario_id de arriba: singleton que
    # empieza sin configurar); el service exige AMBOS al activar el cron
    # (NotificacionConfigService.actualizar). R8 backfillea TUPaD en las filas
    # existentes al migrar (openspec/changes/multi-tenant-moodle-services).
    universidad_id: Mapped[int | None] = mapped_column(
        ForeignKey("universidades.id"), nullable=True
    )
    # 0 = lunes ... 6 = domingo (convención APScheduler day_of_week numérica).
    dia_semana: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    hora: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default="7")
    minuto: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Remitente; si NULL se usa EMAIL_REMITENTE de settings (sandbox por defecto).
    remitente: Mapped[str | None] = mapped_column(String(150), nullable=True)

    usuario: Mapped["Usuario | None"] = relationship("Usuario")

    def __repr__(self) -> str:
        return (
            f"<NotificacionCronConfig(dia_semana={self.dia_semana}, "
            f"hora={self.hora}:{self.minuto:02d}, activo={self.activo})>"
        )
