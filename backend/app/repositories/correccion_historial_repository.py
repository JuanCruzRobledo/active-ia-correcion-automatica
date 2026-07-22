# app/repositories/correccion_historial_repository.py
"""
CorreccionHistorial repository for Active-IA.

CRUD-003: guarda y lista los snapshots de correcciones reemplazadas al recorregir.
Solo operaciones de base de datos, sin lógica de negocio.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.correccion import CorreccionHistorial


class CorreccionHistorialRepository:
    """Repository para las versiones históricas de correcciones."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, historial: CorreccionHistorial) -> CorreccionHistorial:
        """Persiste un snapshot de corrección."""
        self.db.add(historial)
        await self.db.commit()
        await self.db.refresh(historial)
        return historial

    async def list_by_entrega(self, entrega_id: int) -> list[CorreccionHistorial]:
        """
        Versiones históricas de las correcciones de una entrega, de la más reciente
        a la más vieja. NO carga `raw_response` (deferred): el listado no lo necesita.
        """
        result = await self.db.execute(
            select(CorreccionHistorial)
            .options(
                selectinload(CorreccionHistorial.corregido_por),
                selectinload(CorreccionHistorial.reemplazada_por),
            )
            .where(CorreccionHistorial.entrega_id == entrega_id)
            .order_by(CorreccionHistorial.reemplazada_en.desc())
        )
        return list(result.scalars().all())
