# app/core/scheduler.py
"""
Scheduler del cron de snapshots (Dashboard de Gestores).

AsyncIOScheduler global que corre el snapshot diario según la config en DB
(SnapshotCronConfig). Se (re)programa al iniciar la app y cada vez que el admin
edita la config. Ref: PLAN_DASHBOARD_GESTORES.md §7 (T6).
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.models.base import async_session_maker
from app.models.enums import OrigenSnapshotEnum

logger = logging.getLogger(__name__)

TIMEZONE = "America/Argentina/Buenos_Aires"
_JOB_ID = "snapshot_diario"
_JOB_ID_NOTIF = "notificacion_semanal"
_scheduler: AsyncIOScheduler | None = None


async def _run_snapshot_job() -> None:
    """Job del cron: genera snapshots de todas las materias con el usuario configurado."""
    from app.services.snapshot_config_service import SnapshotConfigService
    from app.services.snapshot_service import SnapshotService

    async with async_session_maker() as db:
        config = await SnapshotConfigService(db).get_config()
        if not config.activo or not config.usuario_id or not config.universidad_id:
            logger.info("Cron snapshot: inactivo o sin usuario/universidad, se omite.")
            return
        try:
            await SnapshotService(db).generar_todas_para_usuario(
                config.usuario_id, origen=OrigenSnapshotEnum.CRON,
                universidad_id=config.universidad_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Cron snapshot: falló la corrida completa")


def start_scheduler() -> None:
    """Arranca el scheduler (idempotente). No programa nada todavía."""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    _scheduler.start()
    logger.info("Scheduler iniciado.")


async def reprogramar_desde_config() -> None:
    """(Re)programa el job diario según la config en DB. Llamar al inicio y tras cada update."""
    if _scheduler is None:
        return
    from app.services.snapshot_config_service import SnapshotConfigService

    async with async_session_maker() as db:
        config = await SnapshotConfigService(db).get_config()

    if _scheduler.get_job(_JOB_ID):
        _scheduler.remove_job(_JOB_ID)

    if config.activo and config.usuario_id:
        _scheduler.add_job(
            _run_snapshot_job,
            CronTrigger(hour=config.hora, minute=config.minuto, timezone=TIMEZONE),
            id=_JOB_ID,
            replace_existing=True,
        )
        logger.info(
            "Cron snapshot programado %02d:%02d (%s).", config.hora, config.minuto, TIMEZONE
        )
    else:
        logger.info("Cron snapshot no programado (inactivo o sin usuario).")


async def _run_notificacion_job() -> None:
    """Job del cron semanal: corre la cadena de notificaciones con el usuario configurado."""
    from app.services.notificacion_config_service import NotificacionConfigService
    from app.services.notificacion_service import NotificacionService

    async with async_session_maker() as db:
        config = await NotificacionConfigService(db).get_config()
        if not config.activo or not config.usuario_id or not config.universidad_id:
            logger.info("Cron notificaciones: inactivo o sin usuario/universidad, se omite.")
            return
        try:
            # ejecutar_corrida_semanal relee universidad_id de su propia config
            # (NotificacionConfigService, OQ2) — no hace falta pasarlo acá.
            await NotificacionService(db).ejecutar_corrida_semanal(config.usuario_id)
        except Exception:  # noqa: BLE001
            logger.exception("Cron notificaciones: falló la corrida completa")


async def reprogramar_notificaciones_desde_config() -> None:
    """(Re)programa el job semanal de notificaciones según la config en DB."""
    if _scheduler is None:
        return
    from app.services.notificacion_config_service import NotificacionConfigService

    async with async_session_maker() as db:
        config = await NotificacionConfigService(db).get_config()

    if _scheduler.get_job(_JOB_ID_NOTIF):
        _scheduler.remove_job(_JOB_ID_NOTIF)

    if config.activo and config.usuario_id:
        _scheduler.add_job(
            _run_notificacion_job,
            CronTrigger(
                day_of_week=config.dia_semana,
                hour=config.hora,
                minute=config.minuto,
                timezone=TIMEZONE,
            ),
            id=_JOB_ID_NOTIF,
            replace_existing=True,
        )
        logger.info(
            "Cron notificaciones programado dow=%s %02d:%02d (%s).",
            config.dia_semana, config.hora, config.minuto, TIMEZONE,
        )
    else:
        logger.info("Cron notificaciones no programado (inactivo o sin usuario).")


def shutdown_scheduler() -> None:
    """Detiene el scheduler (idempotente)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler detenido.")
