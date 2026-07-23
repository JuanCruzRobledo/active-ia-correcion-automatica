# app/services/universidad_service.py
"""
Universidad service for Active-IA — Fase 5 multi-tenant (multi-tenant-frontend-workspace).

Business logic para el listado propio del selector (`listar_mias`, D5) y el
ABM de superadmin (`listar`, `crear`, `actualizar`, `eliminar`, D7). ARCH-001:
nunca ejecuta SQLAlchemy directo, todo pasa por `UniversidadRepository`.

Ref: openspec/changes/multi-tenant-frontend-workspace/specs/universidades-abm/spec.md
Ref: openspec/changes/multi-tenant-frontend-workspace/design.md (D5, D7)
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.repositories.universidad_repository import UniversidadRepository
from app.schemas.universidad import (
    UniversidadCreate,
    UniversidadList,
    UniversidadListItem,
    UniversidadPropia,
    UniversidadResponse,
    UniversidadUpdate,
)


class UniversidadService:
    """Service for universidad management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UniversidadRepository(db)

    async def listar_mias(self, usuario) -> list[UniversidadPropia]:
        """
        Universidades del selector para el usuario autenticado (D5).

        Un superadmin ve TODAS las universidades activas con un rol `ADMIN`
        sintético (coherente con la decisión de Fase 1); el resto ve sus
        membresías activas, cada una con su rol real.
        """
        if usuario.es_superadmin:
            universidades = await self.repo.get_activas()
            return [
                UniversidadPropia(id=u.id, nombre=u.nombre, rol=RolEnum.ADMIN)
                for u in universidades
            ]

        propias = await self.repo.get_propias(usuario.id)
        return [
            UniversidadPropia(id=u.id, nombre=u.nombre, rol=rol) for u, rol in propias
        ]

    async def listar(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        include_inactive: bool = False,
        search: str | None = None,
    ) -> UniversidadList:
        """Listado paginado de universidades (ABM de superadmin)."""
        universidades, total = await self.repo.get_all(
            include_inactive=include_inactive, search=search, page=page, per_page=per_page
        )
        return UniversidadList(
            items=[UniversidadListItem.model_validate(u) for u in universidades],
            total=total,
            page=page,
            per_page=per_page,
        )

    async def crear(self, data: UniversidadCreate) -> UniversidadResponse:
        """Alta de universidad. 409 si ya existe una con ese `nombre`."""
        if await self.repo.existe_con_nombre(data.nombre):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una universidad con el nombre '{data.nombre}'",
            )

        universidad = Universidad(
            nombre=data.nombre, moodle_host=data.moodle_host, activa=True
        )
        universidad = await self.repo.create(universidad)
        return UniversidadResponse.model_validate(universidad)

    async def actualizar(
        self, universidad_id: int, data: UniversidadUpdate
    ) -> UniversidadResponse:
        """Edición de universidad. 404 si no existe."""
        universidad = await self.repo.get_by_id(universidad_id)
        if universidad is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Universidad no encontrada",
            )

        if data.nombre is not None:
            if await self.repo.existe_con_nombre(data.nombre, excluir_id=universidad_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una universidad con el nombre '{data.nombre}'",
                )
            universidad.nombre = data.nombre
        if data.moodle_host is not None:
            universidad.moodle_host = data.moodle_host
        if data.activa is not None:
            universidad.activa = data.activa

        universidad = await self.repo.update(universidad)
        return UniversidadResponse.model_validate(universidad)

    async def eliminar(self, universidad_id: int) -> None:
        """
        Baja lógica (CRUD-002: nunca borrado físico). 404 si no existe.

        Las materias/comisiones asociadas NO se tocan (viven en su propia
        tabla, sin cascada de borrado).
        """
        universidad = await self.repo.get_by_id(universidad_id)
        if universidad is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Universidad no encontrada",
            )
        await self.repo.soft_delete(universidad)
