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

    async def get_ultimo_snapshot(
        self, materia_id: int, *, universidad_id: int | None = None
    ) -> AvanceSnapshot | None:
        """El snapshot más reciente de una materia (o None si no hay)."""
        query = select(AvanceSnapshot).where(AvanceSnapshot.materia_id == materia_id)
        if universidad_id is not None:
            query = query.where(AvanceSnapshot.universidad_id == universidad_id)
        result = await self.db.execute(
            query.order_by(AvanceSnapshot.generado_en.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_ultimos_snapshots(
        self, materia_ids: list[int], *, universidad_id: int | None = None
    ) -> list[AvanceSnapshot]:
        """El snapshot MÁS RECIENTE de cada materia dada, en UNA sola query.

        Reemplaza el N+1 de llamar ``get_ultimo_snapshot(materia_id)`` por cada
        materia (Dashboard de Gestores). Devuelve a lo sumo un snapshot por materia
        —el de ``generado_en`` más alto—, exactamente lo que devolvía
        ``get_ultimo_snapshot`` para cada una; las materias sin snapshot simplemente
        no aparecen en la lista (equivalente al ``if snap is not None`` del loop).

        Implementación con una ventana ``row_number()`` particionada por materia
        (``PostgreSQL`` y ``SQLite >= 3.25``); se prefiere sobre ``DISTINCT ON`` de
        Postgres para que sea portable y testeable en el harness SQLite. En empate de
        ``generado_en`` se devuelve una sola fila (igual que ``ORDER BY ... LIMIT 1``).

        Args:
            materia_ids: IDs de materias.

        Returns:
            Lista de snapshots (uno por materia con datos), orden no garantizado.
        """
        if not materia_ids:
            return []

        rn = (
            func.row_number()
            .over(
                partition_by=AvanceSnapshot.materia_id,
                order_by=AvanceSnapshot.generado_en.desc(),
            )
            .label("rn")
        )
        ranked = (
            select(AvanceSnapshot.id.label("sid"), rn)
            .where(AvanceSnapshot.materia_id.in_(materia_ids))
            .subquery()
        )
        ids_ultimos = select(ranked.c.sid).where(ranked.c.rn == 1)

        query = select(AvanceSnapshot).where(AvanceSnapshot.id.in_(ids_ultimos))
        if universidad_id is not None:
            query = query.where(AvanceSnapshot.universidad_id == universidad_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def contar_por_estado(
        self, snapshot_ids: list[int], *, universidad_id: int | None = None
    ) -> dict[EstadoAvanceEnum, int]:
        """Cantidad de alumnos por estado en los snapshots dados.

        universidad_id: Fase 4 multi-tenant, defensa en profundidad (D2) — si algún
        snapshot_id fuera de otra universidad, el join lo excluye. None = sin filtro.
        """
        if not snapshot_ids:
            return {}
        query = select(AvanceAlumno.estado, func.count()).where(
            AvanceAlumno.snapshot_id.in_(snapshot_ids)
        )
        if universidad_id is not None:
            query = query.join(
                AvanceSnapshot, AvanceSnapshot.id == AvanceAlumno.snapshot_id
            ).where(AvanceSnapshot.universidad_id == universidad_id)
        result = await self.db.execute(query.group_by(AvanceAlumno.estado))
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
