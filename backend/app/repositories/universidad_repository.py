# app/repositories/universidad_repository.py
"""
Universidad repository for Active-IA — Fase 1 multi-tenant (multi-tenant-auth-jwt).

Consumido por `get_universidad_activa` (app/core/dependencies.py) para validar,
en el bypass de superadmin, que la universidad elegida exista y esté activa —
sin ejecutar SQL crudo fuera de la capa Repository (ARCH-001).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.universidad import Universidad


class UniversidadRepository:
    """Repository for Universidad model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_activa_by_id(self, universidad_id: int) -> Universidad | None:
        """
        Get an active Universidad by ID.

        Args:
            universidad_id: Universidad's database ID.

        Returns:
            Universidad if it exists and `activa=True`, None otherwise.
        """
        result = await self.db.execute(
            select(Universidad).where(
                Universidad.id == universidad_id,
                Universidad.activa == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()
