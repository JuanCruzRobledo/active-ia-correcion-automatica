# app/services/examen_service.py
"""
ExamenService — ABM de exámenes de una materia (Dashboard de Gestores). Solo admin.

CRUD incremental por examen. Valida la coherencia del vínculo de rescate
(recupera_examen_id debe ser un PARCIAL o GLOBAL de la misma materia) y deriva el
número/etiqueta visible por tipo reusando examen_mapper.
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TipoActividadEnum, TipoExamenEnum
from app.models.examen_materia import ExamenMateria
from app.repositories.examen_repository import ExamenRepository
from app.repositories.materia_repository import MateriaRepository
from app.services.actividad_service import ActividadService
from app.schemas.examen import (
    TIPOS_RESCATE,
    ExamenMateriaCreate,
    ExamenMateriaResponse,
    ExamenMateriaUpdate,
)
from app.services.examen_mapper import etiqueta_examen, numeros_por_tipo


class ExamenService:
    """Service para el ABM de exámenes de una materia."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.examen_repo = ExamenRepository(db)
        self.materia_repo = MateriaRepository(db)

    async def _get_materia_or_404(self, materia_id: int):
        materia = await self.materia_repo.get_by_id(materia_id)
        if materia is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Materia no encontrada"
            )
        return materia

    async def _get_examen_or_404(self, examen_id: int) -> ExamenMateria:
        examen = await self.examen_repo.get_by_id(examen_id)
        if examen is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado"
            )
        return examen

    # Tipos que pueden SER rescatados (padre de un recuperatorio/extensión/extraordinaria).
    TIPOS_RESCATABLES = (TipoExamenEnum.PARCIAL, TipoExamenEnum.GLOBAL)

    async def _validar_vinculo(
        self, materia_id: int, recupera_examen_id: int | None
    ) -> None:
        """El examen a recuperar debe existir, ser de la misma materia y ser PARCIAL o GLOBAL."""
        if recupera_examen_id is None:
            return
        objetivo = await self.examen_repo.get_by_id(recupera_examen_id)
        if objetivo is None or objetivo.materia_id != materia_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El examen a recuperar no existe en esta materia",
            )
        if objetivo.tipo not in self.TIPOS_RESCATABLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede recuperar un PARCIAL o un GLOBAL",
            )

    def _a_response(
        self, examen: ExamenMateria, numeros: dict[int, int]
    ) -> ExamenMateriaResponse:
        numero = numeros.get(examen.id, 1)
        etiqueta = etiqueta_examen(examen.tipo.value, numero)
        return ExamenMateriaResponse(
            id=examen.id,
            materia_id=examen.materia_id,
            tipo=examen.tipo,
            numero=numero,
            etiqueta=etiqueta,
            moodle_cmid=examen.moodle_cmid,
            tipo_actividad=examen.tipo_actividad,
            modo_aprobacion=examen.modo_aprobacion,
            nota_minima=examen.nota_minima,
            recupera_examen_id=examen.recupera_examen_id,
            orden=examen.orden,
        )

    @staticmethod
    def _config(examenes: list[ExamenMateria]) -> list[dict]:
        return [
            {"id": e.id, "tipo": e.tipo.value, "orden": e.orden} for e in examenes
        ]

    async def listar(self, materia_id: int) -> list[ExamenMateriaResponse]:
        await self._get_materia_or_404(materia_id)
        examenes = await self.examen_repo.get_by_materia(materia_id)
        numeros = numeros_por_tipo(self._config(examenes))
        return [self._a_response(e, numeros) for e in examenes]

    async def crear(
        self, materia_id: int, data: ExamenMateriaCreate, usuario_id: int | None = None
    ) -> ExamenMateriaResponse:
        await self._get_materia_or_404(materia_id)
        await self._validar_vinculo(materia_id, data.recupera_examen_id)
        orden = await self.examen_repo.max_orden(materia_id) + 1
        examen = ExamenMateria(
            materia_id=materia_id,
            tipo=data.tipo,
            moodle_cmid=data.moodle_cmid,
            tipo_actividad=data.tipo_actividad,
            modo_aprobacion=data.modo_aprobacion,
            nota_minima=data.nota_minima,
            recupera_examen_id=data.recupera_examen_id,
            orden=orden,
        )
        creado = await self.examen_repo.create(examen)
        examenes = await self.examen_repo.get_by_materia(materia_id)
        numeros = numeros_por_tipo(self._config(examenes))
        resp = self._a_response(creado, numeros)
        await ActividadService(self.db).registrar_actividad(
            tipo=TipoActividadEnum.EXAMEN_CREADO,
            descripcion=f"Examen '{resp.etiqueta}' creado",
            entidad_id=creado.id,
            entidad_nombre=resp.etiqueta,
            usuario_id=usuario_id,
        )
        return resp

    async def actualizar(
        self, examen_id: int, data: ExamenMateriaUpdate
    ) -> ExamenMateriaResponse:
        examen = await self._get_examen_or_404(examen_id)
        # No puede recuperarse a sí mismo.
        if data.recupera_examen_id == examen_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un examen no puede recuperarse a sí mismo",
            )
        await self._validar_vinculo(examen.materia_id, data.recupera_examen_id)
        examen.tipo = data.tipo
        examen.moodle_cmid = data.moodle_cmid
        examen.tipo_actividad = data.tipo_actividad
        examen.modo_aprobacion = data.modo_aprobacion
        examen.nota_minima = data.nota_minima
        examen.recupera_examen_id = data.recupera_examen_id
        actualizado = await self.examen_repo.update(examen)
        examenes = await self.examen_repo.get_by_materia(examen.materia_id)
        numeros = numeros_por_tipo(self._config(examenes))
        return self._a_response(actualizado, numeros)

    async def eliminar(self, examen_id: int) -> None:
        examen = await self._get_examen_or_404(examen_id)
        await self.examen_repo.delete(examen)
