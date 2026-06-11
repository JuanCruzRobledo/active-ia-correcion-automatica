# app/services/cohorte_service.py
"""
Cohorte/Cuatrimestre service for Active-IA (Dashboard de Gestores).

Lógica de negocio del ABM de cohortes y cuatrimestres (solo admin).
Ref: PLAN_DASHBOARD_GESTORES.md §5, §8 (T2)
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohorte import Cohorte, Cuatrimestre
from app.models.enums import TipoActividadEnum
from app.repositories.cohorte_repository import (
    CohorteRepository,
    CuatrimestreRepository,
)
from app.services.actividad_service import ActividadService
from app.schemas.cohorte import (
    CohorteCreate,
    CohorteDetailResponse,
    CohorteUpdate,
    CuatrimestreCreate,
    CuatrimestreResponse,
    CuatrimestreUpdate,
)


class CohorteService:
    """Service for Cohorte and Cuatrimestre management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cohorte_repo = CohorteRepository(db)
        self.cuatrimestre_repo = CuatrimestreRepository(db)

    # ===================== Cohorte =====================

    async def listar_cohortes(
        self, *, include_inactive: bool = False
    ) -> list[CohorteDetailResponse]:
        cohortes = await self.cohorte_repo.get_all(include_inactive=include_inactive)
        return [CohorteDetailResponse.model_validate(c) for c in cohortes]

    async def _get_cohorte_or_404(self, cohorte_id: int) -> Cohorte:
        cohorte = await self.cohorte_repo.get_by_id(cohorte_id)
        if cohorte is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cohorte no encontrada",
            )
        return cohorte

    async def obtener_cohorte(self, cohorte_id: int) -> CohorteDetailResponse:
        cohorte = await self._get_cohorte_or_404(cohorte_id)
        return CohorteDetailResponse.model_validate(cohorte)

    async def crear_cohorte(
        self, data: CohorteCreate, usuario_id: int | None = None
    ) -> CohorteDetailResponse:
        if await self.cohorte_repo.exists_codigo(data.codigo):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una cohorte con código '{data.codigo}'",
            )
        cohorte = Cohorte(codigo=data.codigo, nombre=data.nombre, activa=True)
        created = await self.cohorte_repo.create(cohorte)
        await ActividadService(self.db).registrar_actividad(
            tipo=TipoActividadEnum.COHORTE_CREADA,
            descripcion=f"Cohorte '{created.codigo}' creada",
            entidad_id=created.id,
            entidad_nombre=created.codigo,
            usuario_id=usuario_id,
        )
        # Recargar con cuatrimestres (vacíos al crear) para un response consistente
        created = await self.cohorte_repo.get_by_id(created.id)
        return CohorteDetailResponse.model_validate(created)

    async def actualizar_cohorte(
        self, cohorte_id: int, data: CohorteUpdate
    ) -> CohorteDetailResponse:
        cohorte = await self._get_cohorte_or_404(cohorte_id)
        if data.nombre is not None:
            cohorte.nombre = data.nombre
        if data.activa is not None:
            cohorte.activa = data.activa
        await self.cohorte_repo.update(cohorte)
        refreshed = await self.cohorte_repo.get_by_id(cohorte_id)
        return CohorteDetailResponse.model_validate(refreshed)

    async def eliminar_cohorte(self, cohorte_id: int) -> None:
        cohorte = await self._get_cohorte_or_404(cohorte_id)
        materias = await self.cohorte_repo.count_materias(cohorte_id)
        if materias > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"No se puede eliminar: hay {materias} materia(s) vinculada(s) "
                    "a cuatrimestres de esta cohorte"
                ),
            )
        await self.cohorte_repo.delete(cohorte)

    # ===================== Cuatrimestre =====================

    async def crear_cuatrimestre(
        self, cohorte_id: int, data: CuatrimestreCreate
    ) -> CuatrimestreResponse:
        await self._get_cohorte_or_404(cohorte_id)
        if await self.cuatrimestre_repo.exists_numero(cohorte_id, data.numero):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La cohorte ya tiene el cuatrimestre {data.numero}",
            )
        cuatrimestre = Cuatrimestre(
            cohorte_id=cohorte_id, numero=data.numero, nombre=data.nombre
        )
        created = await self.cuatrimestre_repo.create(cuatrimestre)
        return CuatrimestreResponse.model_validate(created)

    async def _get_cuatrimestre_or_404(self, cuatrimestre_id: int) -> Cuatrimestre:
        cuatrimestre = await self.cuatrimestre_repo.get_by_id(cuatrimestre_id)
        if cuatrimestre is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cuatrimestre no encontrado",
            )
        return cuatrimestre

    async def actualizar_cuatrimestre(
        self, cuatrimestre_id: int, data: CuatrimestreUpdate
    ) -> CuatrimestreResponse:
        cuatrimestre = await self._get_cuatrimestre_or_404(cuatrimestre_id)
        if data.numero is not None and data.numero != cuatrimestre.numero:
            if await self.cuatrimestre_repo.exists_numero(
                cuatrimestre.cohorte_id, data.numero
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La cohorte ya tiene el cuatrimestre {data.numero}",
                )
            cuatrimestre.numero = data.numero
        if data.nombre is not None:
            cuatrimestre.nombre = data.nombre
        updated = await self.cuatrimestre_repo.update(cuatrimestre)
        return CuatrimestreResponse.model_validate(updated)

    async def eliminar_cuatrimestre(self, cuatrimestre_id: int) -> None:
        cuatrimestre = await self._get_cuatrimestre_or_404(cuatrimestre_id)
        materias = await self.cuatrimestre_repo.count_materias(cuatrimestre_id)
        if materias > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede eliminar: hay {materias} materia(s) en este cuatrimestre",
            )
        await self.cuatrimestre_repo.delete(cuatrimestre)
