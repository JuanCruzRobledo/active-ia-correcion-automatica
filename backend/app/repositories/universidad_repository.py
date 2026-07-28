# app/repositories/universidad_repository.py
"""
Universidad repository for Active-IA — Fase 1 multi-tenant (multi-tenant-auth-jwt),
extendido en Fase 5 (multi-tenant-frontend-workspace) con el listado paginado
y el CRUD del ABM de superadmin.

Consumido por `get_universidad_activa` (app/core/dependencies.py) para validar,
en el bypass de superadmin, que la universidad elegida exista y esté activa —
sin ejecutar SQL crudo fuera de la capa Repository (ARCH-001).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario_universidad import UsuarioUniversidad


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

    async def get_by_id(self, universidad_id: int) -> Universidad | None:
        """Get a Universidad by ID sin filtrar por `activa` (para el ABM)."""
        result = await self.db.execute(
            select(Universidad).where(Universidad.id == universidad_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        include_inactive: bool = False,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Universidad], int]:
        """
        Listado paginado de universidades (ABM de superadmin).

        Args:
            include_inactive: si es False (default), sólo `activa=True`.
            search: filtra por `nombre` (ilike).
            page, per_page: paginación 1-indexed.

        Returns:
            Tupla (universidades, total).
        """
        query = select(Universidad)

        if not include_inactive:
            query = query.where(Universidad.activa == True)  # noqa: E712

        if search:
            query = query.where(Universidad.nombre.ilike(f"%{search}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Universidad.nombre.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_activas(self) -> list[Universidad]:
        """Todas las universidades `activa=True` (superadmin en `/universidades/mias`)."""
        result = await self.db.execute(
            select(Universidad)
            .where(Universidad.activa == True)  # noqa: E712
            .order_by(Universidad.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_propias(self, usuario_id: int) -> list[tuple[Universidad, RolEnum]]:
        """
        Universidades donde `usuario_id` tiene membresía ACTIVA, con su rol.

        Mismo criterio que `UsuarioRepository.get_membresias_activas`: exige
        `usuario_universidad.activo=true` Y `universidades.activa=true`.
        """
        result = await self.db.execute(
            select(Universidad, UsuarioUniversidad.rol)
            .join(
                UsuarioUniversidad,
                UsuarioUniversidad.universidad_id == Universidad.id,
            )
            .where(
                UsuarioUniversidad.usuario_id == usuario_id,
                UsuarioUniversidad.activo == True,  # noqa: E712
                Universidad.activa == True,  # noqa: E712
            )
            .order_by(Universidad.nombre.asc())
        )
        return [(u, rol) for u, rol in result.all()]

    async def existe_con_nombre(self, nombre: str, *, excluir_id: int | None = None) -> bool:
        """True si ya existe una universidad con ese `nombre` (chequeo de duplicado)."""
        query = select(func.count()).select_from(Universidad).where(
            Universidad.nombre == nombre
        )
        if excluir_id is not None:
            query = query.where(Universidad.id != excluir_id)
        result = await self.db.execute(query)
        return (result.scalar() or 0) > 0

    async def create(self, universidad: Universidad) -> Universidad:
        """Persiste una nueva Universidad."""
        self.db.add(universidad)
        await self.db.commit()
        await self.db.refresh(universidad)
        return universidad

    async def update(self, universidad: Universidad) -> Universidad:
        """Persiste cambios sobre una Universidad ya cargada."""
        await self.db.commit()
        await self.db.refresh(universidad)
        return universidad

    async def soft_delete(self, universidad: Universidad) -> Universidad:
        """
        Baja lógica (CRUD-002: nunca borrado físico): `activa = False`.

        Las materias/comisiones asociadas NO se tocan.
        """
        universidad.activa = False
        await self.db.commit()
        await self.db.refresh(universidad)
        return universidad
