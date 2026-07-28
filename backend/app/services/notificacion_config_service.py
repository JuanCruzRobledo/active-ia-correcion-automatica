# app/services/notificacion_config_service.py
"""
NotificacionConfigService — config (singleton id=1) del cron semanal de notificaciones.

Lee/actualiza la fila desde el admin. Si se activa, exige un usuario con credenciales
Moodle (para refrescar snapshots antes de enviar). Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.5 (T8).
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notificacion import NotificacionCronConfig
from app.repositories.notificacion_config_repository import NotificacionConfigRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.notificacion import NotifCronConfigResponse, NotifCronConfigUpdate

_CONFIG_ID = 1


class NotificacionConfigService:
    """Lee/actualiza la config del cron de notificaciones (singleton)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        self.config_repo = NotificacionConfigRepository(db)

    async def _get_or_create(self) -> NotificacionCronConfig:
        # ARCH-001: acceso a datos vía repo, no SQL crudo en el service.
        config = await self.config_repo.get()
        if config is None:
            config = NotificacionCronConfig(
                id=_CONFIG_ID, dia_semana=0, hora=7, minuto=0, activo=False
            )
            config = await self.config_repo.create(config)
        return config

    async def get_config(self) -> NotificacionCronConfig:
        return await self._get_or_create()

    async def _to_response(self, config: NotificacionCronConfig) -> NotifCronConfigResponse:
        nombre = None
        if config.usuario_id:
            usuario = await self.usuario_repo.get_by_id(config.usuario_id)
            nombre = usuario.nombre if usuario else None
        return NotifCronConfigResponse(
            usuario_id=config.usuario_id,
            usuario_nombre=nombre,
            universidad_id=config.universidad_id,
            dia_semana=config.dia_semana,
            hora=config.hora,
            minuto=config.minuto,
            activo=config.activo,
            remitente=config.remitente,
        )

    async def obtener(self) -> NotifCronConfigResponse:
        return await self._to_response(await self._get_or_create())

    async def actualizar(self, data: NotifCronConfigUpdate) -> NotifCronConfigResponse:
        config = await self._get_or_create()

        if data.activo:
            if not data.usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Para activar el cron hay que asignar un usuario de servicio",
                )
            # Fase 3 multi-tenant (OQ2): el cron corre sin request/ctx, así que
            # la universidad activa se elige explícitamente acá (no hay JWT del
            # que leerla) y se exige junto con el usuario de servicio.
            if not data.universidad_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Para activar el cron hay que elegir la universidad activa",
                )
            usuario = await self.usuario_repo.get_by_id(data.usuario_id)
            if usuario is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario indicado no existe",
                )
            # Credenciales de la MEMBRESÍA (usuario, universidad) elegida — D1/D2,
            # NUNCA usuario.moodle_* (campo global viejo).
            creds = await self.usuario_repo.get_credenciales_moodle(
                data.usuario_id, data.universidad_id
            )
            if creds is None or not creds.username or not creds.password_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "El usuario elegido no tiene credenciales de Moodle configuradas "
                        "para la universidad elegida"
                    ),
                )

        config.usuario_id = data.usuario_id
        config.universidad_id = data.universidad_id
        config.dia_semana = data.dia_semana
        config.hora = data.hora
        config.minuto = data.minuto
        config.activo = data.activo
        config.remitente = data.remitente
        await self.config_repo.save(config)
        return await self._to_response(config)
