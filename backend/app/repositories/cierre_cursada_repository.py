# app/repositories/cierre_cursada_repository.py
"""
Repository de cierre de cursada: corridas (CierreCursadaRun/CierreCursadaAlumno).

El mapeo manual de ítems (CierreCursadaItem) se eliminó: el cierre ahora se
dirige exclusivamente por la configuración de exámenes (`ExamenMateria`).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.utils.orden_natural import orden_natural_sql


class CierreCursadaRepository:
    """Repository para CierreCursadaRun / CierreCursadaAlumno."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----- Corridas (CierreCursadaRun) -----

    async def crear_run(self, run: CierreCursadaRun) -> CierreCursadaRun:
        """Persiste una corrida con sus alumnos (cascade all)."""
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def get_run(self, run_id: int) -> CierreCursadaRun | None:
        result = await self.db.execute(
            select(CierreCursadaRun)
            .where(CierreCursadaRun.id == run_id)
            .options(selectinload(CierreCursadaRun.alumnos))
        )
        return result.scalar_one_or_none()

    async def listar_runs(
        self, materia_id: int, *, universidad_id: int | None = None
    ) -> list[CierreCursadaRun]:
        """Corridas pasadas de una materia, más reciente primero."""
        query = select(CierreCursadaRun).where(CierreCursadaRun.materia_id == materia_id)
        if universidad_id is not None:
            query = query.where(CierreCursadaRun.universidad_id == universidad_id)
        result = await self.db.execute(query.order_by(CierreCursadaRun.created_at.desc()))
        return list(result.scalars().all())

    async def get_alumnos_de_run(self, run_id: int) -> list[CierreCursadaAlumno]:
        result = await self.db.execute(
            select(CierreCursadaAlumno)
            .where(CierreCursadaAlumno.run_id == run_id)
            .order_by(
                *orden_natural_sql(CierreCursadaAlumno.comision_nombre),
                CierreCursadaAlumno.apellido.asc(),
                CierreCursadaAlumno.nombre.asc(),
            )
        )
        return list(result.scalars().all())
