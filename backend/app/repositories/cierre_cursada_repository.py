# app/repositories/cierre_cursada_repository.py
"""
Repository de cierre de cursada: mapeo de ítems del calificador
(CierreCursadaItem) y corridas (CierreCursadaRun/CierreCursadaAlumno).
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cierre_cursada import (
    CierreCursadaAlumno,
    CierreCursadaItem,
    CierreCursadaRun,
)


class CierreCursadaRepository:
    """Repository para CierreCursadaItem / CierreCursadaRun / CierreCursadaAlumno."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----- Mapeo de ítems (CierreCursadaItem) -----

    async def get_mapping(
        self, materia_id: int, cuatrimestre_id: int
    ) -> list[CierreCursadaItem]:
        """Mapeo ya confirmado para esa materia+cuatrimestre, indexado por cmid."""
        result = await self.db.execute(
            select(CierreCursadaItem).where(
                CierreCursadaItem.materia_id == materia_id,
                CierreCursadaItem.cuatrimestre_id == cuatrimestre_id,
            )
        )
        return list(result.scalars().all())

    async def upsert_mapping(
        self, materia_id: int, cuatrimestre_id: int, items: list[dict]
    ) -> list[CierreCursadaItem]:
        """Reemplaza el mapeo confirmado de (materia, cuatrimestre) por `items`.

        items: [{"moodle_cmid", "nombre_moodle", "categoria", "unidad", "opcional",
        "orden"}]. Delete-then-insert: más simple que un ON CONFLICT DO UPDATE
        y el volumen (decenas de ítems por materia) no lo justifica.
        """
        await self.db.execute(
            delete(CierreCursadaItem).where(
                CierreCursadaItem.materia_id == materia_id,
                CierreCursadaItem.cuatrimestre_id == cuatrimestre_id,
            )
        )
        filas = [
            CierreCursadaItem(
                materia_id=materia_id,
                cuatrimestre_id=cuatrimestre_id,
                moodle_cmid=item["moodle_cmid"],
                nombre_moodle=item["nombre_moodle"],
                categoria=item["categoria"],
                unidad=item.get("unidad"),
                opcional=item.get("opcional", False),
                orden=item.get("orden"),
            )
            for item in items
        ]
        self.db.add_all(filas)
        await self.db.commit()
        return filas

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

    async def listar_runs(self, materia_id: int) -> list[CierreCursadaRun]:
        """Corridas pasadas de una materia, más reciente primero."""
        result = await self.db.execute(
            select(CierreCursadaRun)
            .where(CierreCursadaRun.materia_id == materia_id)
            .order_by(CierreCursadaRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_alumnos_de_run(self, run_id: int) -> list[CierreCursadaAlumno]:
        result = await self.db.execute(
            select(CierreCursadaAlumno)
            .where(CierreCursadaAlumno.run_id == run_id)
            .order_by(
                CierreCursadaAlumno.comision_nombre.asc().nullslast(),
                CierreCursadaAlumno.apellido.asc(),
                CierreCursadaAlumno.nombre.asc(),
            )
        )
        return list(result.scalars().all())
