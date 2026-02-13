# app/repositories/actividad_repository.py
"""
Repository for Actividad (Activity/Audit) model.

Handles database operations for activity logging.

Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
Ref: docs/specs/09-PATRONES-CODIGO.md - Repository pattern
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.actividad import Actividad, TipoActividadEnum
from app.schemas.actividad import ActividadCreate


class ActividadRepository:
    """Repository para gestionar actividades/auditoría."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, actividad: ActividadCreate) -> Actividad:
        """Crea un nuevo registro de actividad."""
        db_actividad = Actividad(**actividad.model_dump())
        self.db.add(db_actividad)
        await self.db.commit()
        await self.db.refresh(db_actividad)
        return db_actividad

    async def get_recent(
        self,
        limit: int = 10,
        offset: int = 0,
        tipo: TipoActividadEnum | None = None,
    ) -> tuple[list[Actividad], int]:
        """
        Obtiene las actividades más recientes.

        Args:
            limit: Número máximo de resultados
            offset: Offset para paginación
            tipo: Filtrar por tipo de actividad (opcional)

        Returns:
            Tupla con (lista de actividades, total)
        """
        # Query base
        query = select(Actividad).options(joinedload(Actividad.usuario))

        # Filtrar por tipo si se especifica
        if tipo:
            query = query.where(Actividad.tipo == tipo)

        # Ordenar por fecha de creación descendente
        query = query.order_by(Actividad.created_at.desc())

        # Contar total
        count_query = select(func.count()).select_from(Actividad)
        if tipo:
            count_query = count_query.where(Actividad.tipo == tipo)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Aplicar paginación
        query = query.limit(limit).offset(offset)

        # Ejecutar query
        result = await self.db.execute(query)
        actividades = result.scalars().all()

        return list(actividades), total
