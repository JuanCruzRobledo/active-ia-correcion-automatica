# app/services/rubrica_service.py
"""
Rubrica service for Active-IA.

Business logic for rubric (rubrica) management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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

    def _validar_criterios_json(self, criterios: dict) -> None:
        """
        Valida la estructura de criterios_json.

        Verifica:
        - puntaje_maximo == 100
        - suma de puntajes de criterios == puntaje_maximo
        - IDs de criterios únicos
        - niveles con puntajes válidos

        Args:
            criterios: Diccionario con estructura de criterios.

        Raises:
            HTTPException 400: Si la validación falla.
        """
        # Validar puntaje máximo
        puntaje_maximo = criterios.get("puntaje_maximo")
        if puntaje_maximo != 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El puntaje máximo de la rúbrica debe ser exactamente 100",
            )

        # Validar que existan criterios
        criterios_list = criterios.get("criterios", [])
        if not criterios_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La rúbrica debe tener al menos un criterio",
            )

        # Validar suma de puntajes
        suma = sum(c.get("puntaje_maximo", 0) for c in criterios_list)
        if suma != puntaje_maximo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La suma de puntajes de criterios ({suma}) debe ser igual al puntaje máximo ({puntaje_maximo})",
            )

        # Validar IDs únicos
        ids = [c.get("id") for c in criterios_list]
        if len(ids) != len(set(ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los IDs de criterios deben ser únicos",
            )

        # Validar niveles de desempeño
        for criterio in criterios_list:
            niveles = criterio.get("niveles") or []
            criterio_puntaje_max = criterio.get("puntaje_maximo", 0)

            for nivel in niveles:
                nivel_puntaje = nivel.get("puntaje", 0)
                if nivel_puntaje > criterio_puntaje_max:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El puntaje del nivel ({nivel_puntaje}) no puede exceder el puntaje máximo del criterio ({criterio_puntaje_max})",
                    )

    async def crear_rubrica(self, data: RubricaCreate) -> RubricaResponse:
        """
        Create a new rubrica.

        Args:
            data: Rubrica creation data.

        Returns:
            RubricaResponse with rubrica data.

        Raises:
            HTTPException 404: Materia not found.
            HTTPException 409: Rubrica with same materia+tipo+numero+anio exists.
            HTTPException 400: Invalid criterios_json structure.
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

        # Validate criterios_json structure
        # Note: Pydantic already validates via CriteriosStructure,
        # but we double-check for safety
        criterios_dict = data.criterios_json.model_dump()
        self._validar_criterios_json(criterios_dict)

        # Create rubrica
        rubrica = Rubrica(
            materia_id=data.materia_id,
            tipo=data.tipo,
            nombre=data.nombre,
            numero=data.numero,
            anio=data.anio,
            criterios_json=criterios_dict,
            fuente=data.fuente,
            archivo_original=data.archivo_original,
            activa=True,
        )

        created_rubrica = await self.rubrica_repo.create(rubrica)

        return RubricaResponse.model_validate(created_rubrica)

    async def listar_rubricas(
        self,
        *,
        materia_id: int | None = None,
        tipo: str | None = None,
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
            anio=anio,
            include_inactive=include_inactive,
            page=page,
            per_page=per_page,
        )

        # Build list items with counts
        items = []
        for rubrica in rubricas:
            criterios_data = rubrica.criterios_json or {}

            # Extract puntaje_maximo from criterios_json
            puntaje_maximo = criterios_data.get("puntaje_maximo", 100)

            # Count criterios
            criterios = criterios_data.get("criterios", [])
            num_criterios = len(criterios)

            # Count entregas
            num_entregas = (
                len([e for e in rubrica.entregas if e.activa])
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
                    nombre=rubrica.nombre,
                    numero=rubrica.numero,
                    anio=rubrica.anio,
                    puntaje_maximo=puntaje_maximo,
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
            nombre=rubrica.nombre,
            numero=rubrica.numero,
            anio=rubrica.anio,
            criterios_json=rubrica.criterios_json,
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
        Update an existing rubrica.

        Args:
            rubrica_id: Rubrica's database ID.
            data: Rubrica update data.

        Returns:
            RubricaResponse with updated rubrica data.

        Raises:
            HTTPException 404: Rubrica not found.
            HTTPException 400: Invalid criterios_json structure.
        """
        rubrica = await self.rubrica_repo.get_by_id(rubrica_id)

        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada",
            )

        # Update fields
        if data.nombre is not None:
            rubrica.nombre = data.nombre

        if data.criterios_json is not None:
            # Validate new criterios_json
            criterios_dict = data.criterios_json.model_dump()
            self._validar_criterios_json(criterios_dict)
            rubrica.criterios_json = criterios_dict

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

        # Create new rubrica (duplicate)
        nuevo_nombre = data.nuevo_nombre if data.nuevo_nombre else rubrica_original.nombre

        rubrica_nueva = Rubrica(
            materia_id=rubrica_original.materia_id,
            tipo=rubrica_original.tipo,
            nombre=nuevo_nombre,
            numero=rubrica_original.numero,
            anio=data.nuevo_anio,
            criterios_json=rubrica_original.criterios_json.copy(),  # Deep copy
            fuente=rubrica_original.fuente,
            archivo_original=rubrica_original.archivo_original,
            activa=True,
        )

        created_rubrica = await self.rubrica_repo.create(rubrica_nueva)

        return RubricaResponse.model_validate(created_rubrica)
