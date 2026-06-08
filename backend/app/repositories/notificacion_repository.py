# app/repositories/notificacion_repository.py
"""
Repositorio de EnvioEmailLog (cola + auditoría de notificaciones).

Soporta la idempotencia de la corrida semanal (refs ya ENVIADOS por tanda) y el
historial para el panel admin. Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.3, §7.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EstadoEnvioEnum, TipoNotificacionEnum
from app.models.notificacion import EnvioEmailLog


class NotificacionRepository:
    """Repository para EnvioEmailLog."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def agregar_todos(self, logs: list[EnvioEmailLog]) -> None:
        """Persiste una tanda de logs (ya con su estado final tras el envío)."""
        if not logs:
            return
        self.db.add_all(logs)
        await self.db.commit()

    async def refs_enviados(
        self, tanda_id: str, tipo: TipoNotificacionEnum
    ) -> set[str]:
        """destinatario_ref ya ENVIADOS en esta tanda+tipo (para no reenviar al reanudar)."""
        result = await self.db.execute(
            select(EnvioEmailLog.destinatario_ref).where(
                EnvioEmailLog.tanda_id == tanda_id,
                EnvioEmailLog.tipo == tipo,
                EnvioEmailLog.estado == EstadoEnvioEnum.ENVIADO,
            )
        )
        return {ref for (ref,) in result.all() if ref}

    async def listar(
        self, *, tanda_id: str | None = None, limit: int = 200
    ) -> list[EnvioEmailLog]:
        """Historial de envíos (panel admin), más recientes primero."""
        stmt = select(EnvioEmailLog).order_by(EnvioEmailLog.created_at.desc()).limit(limit)
        if tanda_id:
            stmt = stmt.where(EnvioEmailLog.tanda_id == tanda_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
