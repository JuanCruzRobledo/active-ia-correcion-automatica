# app/schemas/notificacion.py
"""
Schemas de la feature de notificaciones por email (cron-config, historial, preview).

Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.4-5.5 (T8).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EstadoEnvioEnum, TipoNotificacionEnum


# ===================== Cron config =====================


class NotifCronConfigResponse(BaseModel):
    """Config actual del cron semanal de notificaciones."""

    usuario_id: int | None = None
    usuario_nombre: str | None = None
    # Fase 3 multi-tenant (OQ2): universidad activa del cron (sin JWT/ctx).
    universidad_id: int | None = None
    dia_semana: int
    hora: int
    minuto: int
    activo: bool
    remitente: str | None = None


class NotifCronConfigUpdate(BaseModel):
    """Actualización de la config del cron semanal."""

    usuario_id: int | None = None
    # Fase 3 multi-tenant (OQ2): universidad activa del cron (sin JWT/ctx). Se
    # exige junto con usuario_id al activar (NotificacionConfigService.actualizar).
    universidad_id: int | None = None
    dia_semana: int = Field(0, ge=0, le=6, description="0=lunes … 6=domingo")
    hora: int = Field(7, ge=0, le=23)
    minuto: int = Field(0, ge=0, le=59)
    activo: bool = False
    remitente: str | None = Field(None, max_length=150)


# ===================== Historial / corrida =====================


class EnvioEmailLogResponse(BaseModel):
    """Una fila del historial de envíos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tanda_id: str
    tipo: TipoNotificacionEnum
    destinatario_email: str
    destinatario_ref: str | None = None
    asunto: str | None = None
    estado: EstadoEnvioEnum
    resend_id: str | None = None
    error: str | None = None
    intentos: int
    created_at: datetime
    enviado_en: datetime | None = None


class CorridaResumenResponse(BaseModel):
    """Resumen de una corrida (manual o cron)."""

    tanda_id: str
    alumnos: int
    tutores: int
    nexos: int


class EnviarPruebaRequest(BaseModel):
    """Pide un email de prueba a una casilla (valida el canal Resend)."""

    email: str = Field(..., max_length=150)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Email inválido")
        return v
