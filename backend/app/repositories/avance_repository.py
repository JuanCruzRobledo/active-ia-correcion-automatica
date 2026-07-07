# app/repositories/avance_repository.py
"""
Avance snapshot repository for Active-IA (Dashboard de Gestores).

Persistencia de snapshots de avance (histórico). Las LECTURAS (pie, detalle,
tendencia) se agregan en T7. Ref: PLAN_DASHBOARD_GESTORES.md §7 (T5).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.avance import AvanceAlumno, AvanceSnapshot
from app.models.enums import EstadoAvanceEnum
from app.utils.orden_natural import orden_natural_sql


class AvanceRepository:
    """Repository for AvanceSnapshot / AvanceAlumno."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def crear(self, snapshot: AvanceSnapshot) -> AvanceSnapshot:
        """Persiste un snapshot con sus alumnos (cascade all)."""
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    # ----- Lectura (Dashboard) -----

    async def get_ultimo_snapshot(self, materia_id: int) -> AvanceSnapshot | None:
        """El snapshot más reciente de una materia (o None si no hay)."""
        result = await self.db.execute(
            select(AvanceSnapshot)
            .where(AvanceSnapshot.materia_id == materia_id)
            .order_by(AvanceSnapshot.generado_en.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def contar_por_estado(
        self, snapshot_ids: list[int]
    ) -> dict[EstadoAvanceEnum, int]:
        """Cantidad de alumnos por estado en los snapshots dados."""
        if not snapshot_ids:
            return {}
        result = await self.db.execute(
            select(AvanceAlumno.estado, func.count())
            .where(AvanceAlumno.snapshot_id.in_(snapshot_ids))
            .group_by(AvanceAlumno.estado)
        )
        return {estado: total for estado, total in result.all()}

    async def get_alumnos_de_snapshot(self, snapshot_id: int) -> list[AvanceAlumno]:
        """Todos los AvanceAlumno de un snapshot (para las notificaciones por email)."""
        result = await self.db.execute(
            select(AvanceAlumno)
            .where(AvanceAlumno.snapshot_id == snapshot_id)
            .order_by(
                *orden_natural_sql(AvanceAlumno.comision),
                AvanceAlumno.apellido.asc(),
                AvanceAlumno.nombre.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_alumnos_por_estado(
        self, snapshot_ids: list[int], estado: EstadoAvanceEnum
    ) -> list[AvanceAlumno]:
        """Alumnos en un estado dado dentro de los snapshots indicados."""
        if not snapshot_ids:
            return []
        result = await self.db.execute(
            select(AvanceAlumno)
            .where(
                AvanceAlumno.snapshot_id.in_(snapshot_ids),
                AvanceAlumno.estado == estado,
            )
            .order_by(
                *orden_natural_sql(AvanceAlumno.comision),
                AvanceAlumno.apellido.asc(),
                AvanceAlumno.nombre.asc(),
            )
        )
        return list(result.scalars().all())
