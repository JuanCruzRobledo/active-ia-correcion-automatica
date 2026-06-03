# app/services/unidad_service.py
"""
Unidad / config de dashboard service for Active-IA (Dashboard de Gestores).

Lógica del ABM de unidades de una materia, la config de dashboard de la materia
(cuatrimestre, unidad_actual, tope) y el vínculo rúbrica→unidad. Solo admin.

Ref: PLAN_DASHBOARD_GESTORES.md §5, §6.1, §8 (T3)
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unidad import Unidad
from app.repositories.cohorte_repository import CuatrimestreRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.unidad_repository import UnidadRepository
from app.schemas.unidad import (
    MateriaDashboardConfig,
    MateriaDashboardConfigResponse,
    MoodleSeccionItem,
    MoodleSeccionesSugeridas,
    UnidadCreate,
    UnidadesSyncRequest,
    UnidadResponse,
    UnidadUpdate,
)
from app.services.avance_mapper import detectar_cabeceras
from app.services.moodle_service import MoodleService


class UnidadService:
    """Service for Unidad management and materia dashboard config."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.unidad_repo = UnidadRepository(db)
        self.materia_repo = MateriaRepository(db)
        self.cuatrimestre_repo = CuatrimestreRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.moodle = MoodleService(db)

    async def _get_materia_or_404(self, materia_id: int):
        materia = await self.materia_repo.get_by_id(materia_id)
        if materia is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Materia no encontrada"
            )
        return materia

    async def _get_unidad_or_404(self, unidad_id: int) -> Unidad:
        unidad = await self.unidad_repo.get_by_id(unidad_id)
        if unidad is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unidad no encontrada"
            )
        return unidad

    # ===================== Unidades =====================

    async def listar_unidades(self, materia_id: int) -> list[UnidadResponse]:
        await self._get_materia_or_404(materia_id)
        unidades = await self.unidad_repo.get_by_materia(materia_id)
        return [UnidadResponse.model_validate(u) for u in unidades]

    async def crear_unidad(
        self, materia_id: int, data: UnidadCreate
    ) -> UnidadResponse:
        await self._get_materia_or_404(materia_id)
        if await self.unidad_repo.exists_numero(materia_id, data.numero):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La materia ya tiene la unidad {data.numero}",
            )
        if await self.unidad_repo.exists_section(materia_id, data.moodle_section_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La sección de Moodle {data.moodle_section_id} ya está asignada a otra unidad",
            )
        unidad = Unidad(
            materia_id=materia_id,
            numero=data.numero,
            moodle_section_id=data.moodle_section_id,
            nombre=data.nombre,
        )
        created = await self.unidad_repo.create(unidad)
        return UnidadResponse.model_validate(created)

    async def actualizar_unidad(
        self, unidad_id: int, data: UnidadUpdate
    ) -> UnidadResponse:
        unidad = await self._get_unidad_or_404(unidad_id)
        if data.numero is not None and data.numero != unidad.numero:
            if await self.unidad_repo.exists_numero(
                unidad.materia_id, data.numero, exclude_id=unidad_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La materia ya tiene la unidad {data.numero}",
                )
            unidad.numero = data.numero
        if data.moodle_section_id is not None and data.moodle_section_id != unidad.moodle_section_id:
            if await self.unidad_repo.exists_section(
                unidad.materia_id, data.moodle_section_id, exclude_id=unidad_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La sección de Moodle {data.moodle_section_id} ya está asignada a otra unidad",
                )
            unidad.moodle_section_id = data.moodle_section_id
        if data.nombre is not None:
            unidad.nombre = data.nombre
        updated = await self.unidad_repo.update(unidad)
        return UnidadResponse.model_validate(updated)

    async def eliminar_unidad(self, unidad_id: int) -> None:
        unidad = await self._get_unidad_or_404(unidad_id)
        # delete() desvincula las rúbricas (unidad_id=NULL) antes de borrar
        await self.unidad_repo.delete(unidad)

    async def sincronizar_unidades(
        self, materia_id: int, data: UnidadesSyncRequest
    ) -> list[UnidadResponse]:
        """Reemplaza las unidades de la materia por las secciones tildadas.

        El ORDEN de `data.secciones` define el número de unidad (1..N).
        """
        await self._get_materia_or_404(materia_id)
        section_ids = [s.moodle_section_id for s in data.secciones]
        if len(section_ids) != len(set(section_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hay secciones repetidas en la selección",
            )
        nuevas = [
            (idx, s.moodle_section_id, s.nombre)
            for idx, s in enumerate(data.secciones, start=1)
        ]
        creadas = await self.unidad_repo.sincronizar(materia_id, nuevas)
        return [UnidadResponse.model_validate(u) for u in creadas]

    # ===================== Config dashboard de la Materia =====================

    async def get_config_materia(self, materia_id: int) -> MateriaDashboardConfigResponse:
        materia = await self._get_materia_or_404(materia_id)
        return MateriaDashboardConfigResponse(
            materia_id=materia.id,
            cuatrimestre_id=materia.cuatrimestre_id,
            unidad_actual=materia.unidad_actual,
            moodle_section_fin_id=materia.moodle_section_fin_id,
        )

    async def set_config_materia(
        self, materia_id: int, data: MateriaDashboardConfig
    ) -> MateriaDashboardConfigResponse:
        materia = await self._get_materia_or_404(materia_id)

        if data.cuatrimestre_id is not None:
            cuatrimestre = await self.cuatrimestre_repo.get_by_id(data.cuatrimestre_id)
            if cuatrimestre is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El cuatrimestre indicado no existe",
                )

        materia.cuatrimestre_id = data.cuatrimestre_id
        materia.unidad_actual = data.unidad_actual
        materia.moodle_section_fin_id = data.moodle_section_fin_id
        await self.materia_repo.update(materia)

        return MateriaDashboardConfigResponse(
            materia_id=materia.id,
            cuatrimestre_id=materia.cuatrimestre_id,
            unidad_actual=materia.unidad_actual,
            moodle_section_fin_id=materia.moodle_section_fin_id,
        )

    # ===================== Vínculo Rúbrica → Unidad =====================

    async def vincular_rubrica_unidad(
        self, rubrica_id: int, unidad_id: int | None
    ) -> None:
        rubrica = await self.rubrica_repo.get_by_id(rubrica_id)
        if rubrica is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Rúbrica no encontrada"
            )
        if unidad_id is not None:
            unidad = await self._get_unidad_or_404(unidad_id)
            if unidad.materia_id != rubrica.materia_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La unidad pertenece a otra materia que la rúbrica",
                )
        rubrica.unidad_id = unidad_id
        await self.rubrica_repo.update(rubrica)

    # ===================== Auto-sugerencia de cabeceras (Moodle) =====================

    async def _token_moodle(self, usuario) -> tuple[str, str]:
        """Token + host de Moodle del usuario actual (mismo patrón que Gestión)."""
        if not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail="Configurá tus credenciales Moodle en tu perfil",
            )
        host = usuario.moodle_host or ""
        token = await self.moodle.get_token(
            user_id=usuario.id,
            moodle_host=host,
            username=usuario.moodle_username,
            password_encrypted=usuario.moodle_password_encrypted,
        )
        return token, host

    async def sugerir_secciones_moodle(
        self, materia_id: int, usuario
    ) -> MoodleSeccionesSugeridas:
        """Trae las secciones del curso de Moodle y auto-detecta las cabeceras de unidad.

        Alimenta el ABM: el admin ve todas las secciones y confirma/ajusta las
        cabeceras pre-detectadas (patrón 'N- Tema').
        """
        materia = await self._get_materia_or_404(materia_id)
        if not materia.moodle_course_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La materia no tiene vínculo con un curso de Moodle",
            )

        token, host = await self._token_moodle(usuario)
        secciones = await self.moodle.get_course_contents(
            token, host, materia.moodle_course_id
        )

        cabeceras = detectar_cabeceras(secciones)
        numero_por_section_id = {
            c["moodle_section_id"]: c["numero"] for c in cabeceras
        }

        items = [
            MoodleSeccionItem(
                moodle_section_id=s.get("id"),
                section=s.get("section") or 0,
                nombre=(s.get("name") or "").strip(),
                es_cabecera_sugerida=s.get("id") in numero_por_section_id,
                numero_sugerido=numero_por_section_id.get(s.get("id")),
            )
            for s in secciones
        ]
        sugeridas = [
            UnidadCreate(
                numero=c["numero"],
                moodle_section_id=c["moodle_section_id"],
                nombre=c["nombre"],
            )
            for c in cabeceras
        ]
        return MoodleSeccionesSugeridas(
            materia_id=materia.id,
            moodle_course_id=materia.moodle_course_id,
            secciones=items,
            cabeceras_sugeridas=sugeridas,
        )
