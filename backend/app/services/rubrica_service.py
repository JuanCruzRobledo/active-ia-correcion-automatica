# app/services/rubrica_service.py
"""
Rubrica service for Active-IA.

Business logic for rubric (rubrica) management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TipoActividadEnum
from app.models.rubrica import Rubrica
from app.repositories.materia_repository import MateriaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.schemas.rubrica import (
    MateriaInfo,
    RubricaCreate,
    RubricaDetailResponse,
    RubricaDuplicar,
    RubricaList,
    RubricaListItem,
    RubricaResponse,
    RubricaUpdate,
)
from app.services.actividad_service import ActividadService


class RubricaService:
    """Service for rubrica management operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize rubrica service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.rubrica_repo = RubricaRepository(db)
        self.materia_repo = MateriaRepository(db)

    def _validar_criterios_v2(self, criterios_list: list) -> None:
        """
        Valida la estructura de criterios V2.

        Verifica:
        - Existe al menos un criterio
        - Suma de pesos == 100
        - IDs de criterios únicos
        - Cada criterio tiene subcriterios
        - Cada subcriterio tiene evidencias

        Args:
            criterios_list: Lista de criterios V2.

        Raises:
            HTTPException 400: Si la validación falla.
        """
        # Validar que existan criterios
        if not criterios_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La rúbrica debe tener al menos un criterio",
            )

        # Validar suma de pesos
        suma = sum(c.get("peso", 0) for c in criterios_list)
        if suma != 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La suma de pesos de criterios ({suma}) debe ser exactamente 100",
            )

        # Validar IDs únicos
        ids = [c.get("id") for c in criterios_list]
        if len(ids) != len(set(ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los IDs de criterios deben ser únicos",
            )

        # Validar que cada criterio tenga subcriterios con evidencias
        for criterio in criterios_list:
            subcriterios = criterio.get("subcriterios", [])
            if not subcriterios:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El criterio {criterio.get('id')} debe tener al menos un subcriterio",
                )

            for subcriterio in subcriterios:
                evidencias = subcriterio.get("evidencias", [])
                if not evidencias:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El subcriterio {subcriterio.get('id')} debe tener al menos una evidencia",
                    )

    async def crear_rubrica(
        self, data: RubricaCreate, current_user_id: int | None = None
    ) -> RubricaResponse:
        """
        Create a new rubrica V2.

        Args:
            data: Rubrica creation data.
            current_user_id: ID of the user creating this rubrica (for audit log).

        Returns:
            RubricaResponse with rubrica data.

        Raises:
            HTTPException 404: Materia not found.
            HTTPException 409: Rubrica with same materia+tipo+numero+anio exists.
            HTTPException 400: Invalid estructura V2.
        """
        # Validate materia exists
        materia = await self.materia_repo.get_active_by_id(data.materia_id)
        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada o inactiva",
            )

        # Check if rubrica already exists
        if await self.rubrica_repo.exists(
            materia_id=data.materia_id,
            tipo=data.tipo.value,
            numero=data.numero,
            anio=data.anio,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una rúbrica con ese tipo y número para esta materia y año",
            )

        # Validate criterios V2 structure
        # Note: Pydantic already validates via RubricaCreate validator,
        # but we double-check for safety
        self._validar_criterios_v2(data.criterios_json)

        # Create rubrica V2
        rubrica = Rubrica(
            materia_id=data.materia_id,
            tipo=data.tipo,
            numero=data.numero,
            anio=data.anio,
            titulo=data.titulo,
            descripcion=data.descripcion,
            puntaje_maximo=data.puntaje_maximo,
            metadata_json=data.metadata_json,
            criterios_json=data.criterios_json,
            penalizaciones_json=data.penalizaciones_json,
            condiciones_desaprobacion_json=data.condiciones_desaprobacion_json,
            fuente=data.fuente,
            archivo_original=data.archivo_original,
            activa=True,
        )

        created_rubrica = await self.rubrica_repo.create(rubrica)

        # Registrar actividad
        actividad_service = ActividadService(self.db)
        await actividad_service.registrar_actividad(
            tipo=TipoActividadEnum.RUBRICA_CREADA,
            descripcion=f"Rúbrica '{created_rubrica.titulo}' (tipo: {created_rubrica.tipo.value}) creada",
            entidad_id=created_rubrica.id,
            entidad_nombre=created_rubrica.titulo,
            usuario_id=current_user_id,
        )

        return RubricaResponse.model_validate(created_rubrica)

    async def listar_rubricas(
        self,
        *,
        materia_id: int | None = None,
        tipo: str | None = None,
        coordinador_id: int | None = None,
        anio: int | None = None,
        include_inactive: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> RubricaList:
        """
        List rubricas with optional filters and pagination.

        Args:
            materia_id: Filter by materia ID.
            tipo: Filter by rubrica type.
            coordinador_id: If provided, return only rubricas of materias assigned to this coordinator.
            anio: Filter by academic year.
            include_inactive: Include soft-deleted rubricas.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            RubricaList with paginated results.
        """
        rubricas, total = await self.rubrica_repo.get_all(
            materia_id=materia_id,
            tipo=tipo,
            coordinador_id=coordinador_id,
            anio=anio,
            include_inactive=include_inactive,
            page=page,
            per_page=per_page,
        )

        # Build list items with counts
        items = []
        for rubrica in rubricas:
            # Count criterios (V2: list of criterios)
            criterios = rubrica.criterios_json or []
            num_criterios = len(criterios)

            # Count entregas
            num_entregas = (
                len(rubrica.entregas)
                if rubrica.entregas
                else 0
            )

            items.append(
                RubricaListItem(
                    id=rubrica.id,
                    materia_id=rubrica.materia_id,
                    materia_nombre=rubrica.materia.nombre,
                    materia_codigo=rubrica.materia.codigo,
                    tipo=rubrica.tipo,
                    titulo=rubrica.titulo,
                    numero=rubrica.numero,
                    anio=rubrica.anio,
                    puntaje_maximo=rubrica.puntaje_maximo,
                    num_criterios=num_criterios,
                    num_entregas=num_entregas,
                    activa=rubrica.activa,
                    created_at=rubrica.created_at,
                )
            )

        return RubricaList(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )

    async def obtener_rubrica(self, rubrica_id: int) -> RubricaDetailResponse:
        """
        Get a rubrica by ID with materia info.

        Args:
            rubrica_id: Rubrica's database ID.

        Returns:
            RubricaDetailResponse with full rubrica data.

        Raises:
            HTTPException 404: Rubrica not found.
        """
        rubrica = await self.rubrica_repo.get_by_id_with_relations(rubrica_id)

        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada",
            )

        # Build materia info
        materia_info = MateriaInfo(
            id=rubrica.materia.id,
            codigo=rubrica.materia.codigo,
            nombre=rubrica.materia.nombre,
        )

        # Count entregas
        num_entregas = await self.rubrica_repo.count_entregas(rubrica_id)

        return RubricaDetailResponse(
            id=rubrica.id,
            materia_id=rubrica.materia_id,
            tipo=rubrica.tipo,
            numero=rubrica.numero,
            anio=rubrica.anio,
            titulo=rubrica.titulo,
            descripcion=rubrica.descripcion,
            puntaje_maximo=rubrica.puntaje_maximo,
            metadata_json=rubrica.metadata_json,
            criterios_json=rubrica.criterios_json,
            penalizaciones_json=rubrica.penalizaciones_json,
            condiciones_desaprobacion_json=rubrica.condiciones_desaprobacion_json,
            fuente=rubrica.fuente,
            archivo_original=rubrica.archivo_original,
            activa=rubrica.activa,
            created_at=rubrica.created_at,
            updated_at=rubrica.updated_at,
            materia=materia_info,
            num_entregas=num_entregas,
        )

    async def actualizar_rubrica(
        self,
        rubrica_id: int,
        data: RubricaUpdate,
    ) -> RubricaResponse:
        """
        Update an existing rubrica V2.

        Args:
            rubrica_id: Rubrica's database ID.
            data: Rubrica update data.

        Returns:
            RubricaResponse with updated rubrica data.

        Raises:
            HTTPException 404: Rubrica not found.
            HTTPException 400: Invalid estructura V2.
        """
        rubrica = await self.rubrica_repo.get_by_id(rubrica_id)

        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada",
            )

        # Update fields
        if data.titulo is not None:
            rubrica.titulo = data.titulo

        if data.descripcion is not None:
            rubrica.descripcion = data.descripcion

        if data.metadata_json is not None:
            rubrica.metadata_json = data.metadata_json

        if data.criterios_json is not None:
            # Validate new criterios V2
            self._validar_criterios_v2(data.criterios_json)
            rubrica.criterios_json = data.criterios_json

        if data.penalizaciones_json is not None:
            rubrica.penalizaciones_json = data.penalizaciones_json

        if data.condiciones_desaprobacion_json is not None:
            rubrica.condiciones_desaprobacion_json = data.condiciones_desaprobacion_json

        updated_rubrica = await self.rubrica_repo.update(rubrica)

        return RubricaResponse.model_validate(updated_rubrica)

    async def eliminar_rubrica(self, rubrica_id: int) -> None:
        """
        Soft delete a rubrica.

        Args:
            rubrica_id: Rubrica's database ID.

        Raises:
            HTTPException 404: Rubrica not found.
        """
        rubrica = await self.rubrica_repo.get_active_by_id(rubrica_id)

        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada o ya eliminada",
            )

        await self.rubrica_repo.soft_delete(rubrica)

    async def restaurar_rubrica(self, rubrica_id: int) -> RubricaResponse:
        """
        Restore a soft-deleted rubrica.

        Args:
            rubrica_id: Rubrica's database ID.

        Returns:
            RubricaResponse with restored rubrica data.

        Raises:
            HTTPException 404: Rubrica not found.
            HTTPException 400: Rubrica is not deleted.
        """
        rubrica = await self.rubrica_repo.get_by_id(rubrica_id)

        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada",
            )

        if rubrica.activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La rúbrica no está eliminada",
            )

        restored_rubrica = await self.rubrica_repo.restore(rubrica)

        return RubricaResponse.model_validate(restored_rubrica)

    async def duplicar_rubrica(
        self,
        rubrica_id: int,
        data: RubricaDuplicar,
    ) -> RubricaResponse:
        """
        Duplicate a rubrica to a new year.

        Args:
            rubrica_id: Rubrica's database ID to duplicate.
            data: RubricaDuplicar with new year and optional new name.

        Returns:
            RubricaResponse with new rubrica data.

        Raises:
            HTTPException 404: Rubrica not found.
            HTTPException 409: Rubrica with same materia+tipo+numero+new_year exists.
        """
        # Get original rubrica
        rubrica_original = await self.rubrica_repo.get_by_id(rubrica_id)

        if not rubrica_original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica original no encontrada",
            )

        # Check if rubrica with new year already exists
        if await self.rubrica_repo.exists(
            materia_id=rubrica_original.materia_id,
            tipo=rubrica_original.tipo.value,
            numero=rubrica_original.numero,
            anio=data.nuevo_anio,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una rúbrica con ese tipo y número para el año {data.nuevo_anio}",
            )

        # Create new rubrica V2 (duplicate)
        nuevo_titulo = data.nuevo_titulo if data.nuevo_titulo else rubrica_original.titulo

        rubrica_nueva = Rubrica(
            materia_id=rubrica_original.materia_id,
            tipo=rubrica_original.tipo,
            numero=rubrica_original.numero,
            anio=data.nuevo_anio,
            titulo=nuevo_titulo,
            descripcion=rubrica_original.descripcion,
            puntaje_maximo=rubrica_original.puntaje_maximo,
            metadata_json=rubrica_original.metadata_json.copy() if rubrica_original.metadata_json else {},
            criterios_json=rubrica_original.criterios_json.copy() if rubrica_original.criterios_json else [],
            penalizaciones_json=rubrica_original.penalizaciones_json.copy() if rubrica_original.penalizaciones_json else [],
            condiciones_desaprobacion_json=rubrica_original.condiciones_desaprobacion_json.copy() if rubrica_original.condiciones_desaprobacion_json else [],
            fuente=rubrica_original.fuente,
            archivo_original=rubrica_original.archivo_original,
            activa=True,
        )

        created_rubrica = await self.rubrica_repo.create(rubrica_nueva)

        return RubricaResponse.model_validate(created_rubrica)
