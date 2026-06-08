# app/services/tutor_nexo_service.py
"""
Service del ABM de TutorNexo (solo admin). Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.3-5.4 (T7).
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tutor_nexo import TutorNexo
from app.repositories.tutor_nexo_repository import TutorNexoRepository
from app.schemas.tutor_nexo import (
    TutorNexoCreate,
    TutorNexoResponse,
    TutorNexoUpdate,
)


class TutorNexoService:
    """Lógica de negocio del ABM de tutores nexo."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TutorNexoRepository(db)

    async def listar(self) -> list[TutorNexoResponse]:
        return [TutorNexoResponse.model_validate(t) for t in await self.repo.listar()]

    async def _get_or_404(self, tutor_nexo_id: int) -> TutorNexo:
        tn = await self.repo.get_by_id(tutor_nexo_id)
        if tn is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tutor nexo no encontrado"
            )
        return tn

    async def obtener(self, tutor_nexo_id: int) -> TutorNexoResponse:
        return TutorNexoResponse.model_validate(await self._get_or_404(tutor_nexo_id))

    async def crear(self, data: TutorNexoCreate) -> TutorNexoResponse:
        tn = TutorNexo(
            nombre=data.nombre, email=data.email, regional=data.regional, activo=True
        )
        return TutorNexoResponse.model_validate(await self.repo.crear(tn))

    async def actualizar(
        self, tutor_nexo_id: int, data: TutorNexoUpdate
    ) -> TutorNexoResponse:
        tn = await self._get_or_404(tutor_nexo_id)
        if data.nombre is not None:
            tn.nombre = data.nombre
        if data.email is not None:
            tn.email = data.email
        if data.regional is not None:
            tn.regional = data.regional
        if data.activo is not None:
            tn.activo = data.activo
        return TutorNexoResponse.model_validate(await self.repo.actualizar(tn))

    async def eliminar(self, tutor_nexo_id: int) -> None:
        tn = await self._get_or_404(tutor_nexo_id)
        await self.repo.eliminar(tn)
