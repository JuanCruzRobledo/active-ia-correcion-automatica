# app/services/comision_service.py
"""
Comision service for Active-IA.

Business logic for commission (comision) management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 5
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comision import Comision
from app.models.enums import RolEnum, TipoActividadEnum
from app.repositories.comision_repository import (
    ComisionRepository,
    ComisionTutorRepository,
)
from app.repositories.materia_repository import MateriaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.comision import (
    ComisionCreate,
    ComisionDetailResponse,
    ComisionList,
    ComisionListItem,
    ComisionResponse,
    ComisionUpdate,
    MateriaInfo,
    TutorInfo,
    TutoresAssign,
    TutoresResponse,
)
from app.schemas.usuario import UsuarioListItem
from app.services.actividad_service import ActividadService


class ComisionService:
    """Service for comision management operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize comision service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.comision_repo = ComisionRepository(db)
        self.comision_tutor_repo = ComisionTutorRepository(db)
        self.materia_repo = MateriaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    async def crear_comision(
        self, data: ComisionCreate, current_user_id: int | None = None
    ) -> ComisionDetailResponse:
        """
        Create a new comision.

        Args:
            data: Comision creation data (materia_id, nombre, anio, tutor_ids).
            current_user_id: ID of the user creating this comision (for audit log).

        Returns:
            ComisionDetailResponse with comision data and tutors.

        Raises:
            HTTPException 404: Materia not found.
            HTTPException 409: Comision with same materia+nombre+anio exists.
            HTTPException 400: Invalid tutor.
        """
        # Validate materia exists
        materia = await self.materia_repo.get_active_by_id(data.materia_id)
        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada o inactiva",
            )

        # Check if comision already exists (materia + nombre + anio)
        if await self.comision_repo.exists(
            materia_id=data.materia_id,
            nombre=data.nombre,
            anio=data.anio,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una comisión con ese nombre para esta materia y año",
            )

        # Validate tutors if provided
        valid_tutores = []
        if data.tutor_ids:
            for tutor_id in data.tutor_ids:
                usuario = await self.usuario_repo.get_active_by_id(tutor_id)

                if not usuario:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Usuario con ID {tutor_id} no encontrado o inactivo",
                    )

                if usuario.rol != RolEnum.TUTOR:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El usuario {usuario.username} no tiene rol de TUTOR",
                    )

                valid_tutores.append(usuario)

        # Create comision
        comision = Comision(
            materia_id=data.materia_id,
            nombre=data.nombre,
            anio=data.anio,
            activa=True,
        )

        created_comision = await self.comision_repo.create(comision)

        # Assign tutors
        for usuario in valid_tutores:
            await self.comision_tutor_repo.create(
                tutor_id=usuario.id,
                comision_id=created_comision.id,
            )

        # Registrar actividad
        actividad_service = ActividadService(self.db)
        await actividad_service.registrar_actividad(
            tipo=TipoActividadEnum.COMISION_CREADA,
            descripcion=f"Comisión '{created_comision.nombre}' creada",
            entidad_id=created_comision.id,
            entidad_nombre=created_comision.nombre,
            usuario_id=current_user_id,
        )

        # Return detailed response with tutors
        return await self.obtener_comision(created_comision.id)

    async def listar_comisiones(
        self,
        *,
        materia_id: int | None = None,
        tutor_id: int | None = None,
        coordinador_id: int | None = None,
        anio: int | None = None,
        include_inactive: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> ComisionList:
        """
        List comisiones with optional filters and pagination.

        Args:
            materia_id: Filter by materia ID.
            tutor_id: If provided, return only comisiones assigned to this tutor.
            coordinador_id: If provided, return only comisiones of materias assigned to this coordinator.
            anio: Filter by academic year.
            include_inactive: Include soft-deleted comisiones.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            ComisionList with paginated results.
        """
        comisiones, total = await self.comision_repo.get_all(
            materia_id=materia_id,
            tutor_id=tutor_id,
            coordinador_id=coordinador_id,
            anio=anio,
            include_inactive=include_inactive,
            page=page,
            per_page=per_page,
        )

        # Build list items with counts
        items = []
        for comision in comisiones:
            # Count tutores
            tutores = await self.comision_tutor_repo.get_tutores_for_comision(
                comision.id
            )
            num_tutores = len(tutores)

            # Count entregas
            num_entregas = (
                len(comision.entregas)
                if comision.entregas
                else 0
            )

            items.append(
                ComisionListItem(
                    id=comision.id,
                    materia_id=comision.materia_id,
                    materia_nombre=comision.materia.nombre,
                    materia_codigo=comision.materia.codigo,
                    nombre=comision.nombre,
                    anio=comision.anio,
                    activa=comision.activa,
                    created_at=comision.created_at,
                    num_tutores=num_tutores,
                    num_entregas=num_entregas,
                )
            )

        return ComisionList(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )

    async def obtener_comision(self, comision_id: int) -> ComisionDetailResponse:
        """
        Get a comision by ID with materia and tutores info.

        Args:
            comision_id: Comision's database ID.

        Returns:
            ComisionDetailResponse with full comision data.

        Raises:
            HTTPException 404: Comision not found.
        """
        comision = await self.comision_repo.get_by_id_with_relations(comision_id)

        if not comision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comisión no encontrada",
            )

        # Build materia info
        materia_info = MateriaInfo(
            id=comision.materia.id,
            codigo=comision.materia.codigo,
            nombre=comision.materia.nombre,
        )

        # Build tutores info
        tutores_info = []
        for ct in comision.tutores:
            tutor = await self.usuario_repo.get_by_id(ct.tutor_id)
            if tutor:
                tutores_info.append(
                    TutorInfo(
                        id=tutor.id,
                        username=tutor.username,
                        nombre=tutor.nombre,
                        asignado_en=ct.asignado_en,
                    )
                )

        return ComisionDetailResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            nombre=comision.nombre,
            anio=comision.anio,
            activa=comision.activa,
            moodle_group_id=comision.moodle_group_id,
            moodle_group_code=comision.moodle_group_code,
            created_at=comision.created_at,
            updated_at=comision.updated_at,
            materia=materia_info,
            tutores=tutores_info,
        )

    async def actualizar_comision(
        self,
        comision_id: int,
        data: ComisionUpdate,
    ) -> ComisionDetailResponse:
        """
        Update an existing comision.

        Args:
            comision_id: Comision's database ID.
            data: Comision update data (nombre, tutor_ids).

        Returns:
            ComisionDetailResponse with updated comision data and tutors.

        Raises:
            HTTPException 404: Comision not found.
            HTTPException 409: Updated nombre conflicts with existing comision.
            HTTPException 400: Invalid tutor.
        """
        comision = await self.comision_repo.get_by_id(comision_id)

        if not comision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comisión no encontrada",
            )

        # Update only provided fields
        if data.nombre is not None:
            # Check if new nombre conflicts with existing comision
            if data.nombre != comision.nombre:
                if await self.comision_repo.exists(
                    materia_id=comision.materia_id,
                    nombre=data.nombre,
                    anio=comision.anio,
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya existe una comisión con ese nombre para esta materia y año",
                    )
            comision.nombre = data.nombre

        if data.moodle_group_id is not None:
            comision.moodle_group_id = data.moodle_group_id
        if data.moodle_group_code is not None:
            comision.moodle_group_code = data.moodle_group_code

        await self.comision_repo.update(comision)

        # Update tutors if provided
        if data.tutor_ids is not None:
            # Validate tutors
            valid_tutores = []
            for tutor_id in data.tutor_ids:
                usuario = await self.usuario_repo.get_active_by_id(tutor_id)

                if not usuario:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Usuario con ID {tutor_id} no encontrado o inactivo",
                    )

                if usuario.rol != RolEnum.TUTOR:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El usuario {usuario.username} no tiene rol de TUTOR",
                    )

                valid_tutores.append(usuario)

            # Remove all existing assignments
            await self.comision_tutor_repo.delete_all_for_comision(comision_id)

            # Create new assignments
            for usuario in valid_tutores:
                await self.comision_tutor_repo.create(
                    tutor_id=usuario.id,
                    comision_id=comision_id,
                )

        # Return detailed response with tutors
        return await self.obtener_comision(comision_id)

    async def eliminar_comision(self, comision_id: int) -> None:
        """
        Delete a comision — soft or hard depending on ALLOW_HARD_DELETE setting.

        When ALLOW_HARD_DELETE=false (default):
            Soft delete: sets activa=False. Reversible via restaurar_comision.
        When ALLOW_HARD_DELETE=true:
            Hard delete: physically removes comision and ALL related data:
            - Entregas → Correcciones / EntregaHistorial / archivos físicos
            - ComisionTutor assignments
            - DELETE Comision — IRREVERSIBLE.

        Args:
            comision_id: Comision's database ID.

        Raises:
            HTTPException 404: Comision not found.
        """
        from app.core.config import settings

        if settings.ALLOW_HARD_DELETE:
            # Hard delete: buscar sin filtro activa para poder borrar cualquiera
            comision = await self.comision_repo.get_by_id(comision_id)
            if not comision:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Comisión no encontrada",
                )
            # Hard delete con cascada completa
            await self.comision_repo.hard_delete_with_cascade(comision)
        else:
            # Soft delete: baja lógica (comportamiento original)
            comision = await self.comision_repo.get_active_by_id(comision_id)
            if not comision:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Comisión no encontrada o ya eliminada",
                )
            await self.comision_repo.soft_delete(comision)

    async def restaurar_comision(self, comision_id: int) -> ComisionResponse:
        """
        Restore a soft-deleted comision.

        Args:
            comision_id: Comision's database ID.

        Returns:
            ComisionResponse with restored comision data.

        Raises:
            HTTPException 404: Comision not found.
            HTTPException 400: Comision is not deleted.
        """
        comision = await self.comision_repo.get_by_id(comision_id)

        if not comision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comisión no encontrada",
            )

        if comision.activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La comisión no está eliminada",
            )

        restored_comision = await self.comision_repo.restore(comision)

        return ComisionResponse.model_validate(restored_comision)

    async def asignar_tutores(
        self,
        comision_id: int,
        data: TutoresAssign,
    ) -> TutoresResponse:
        """
        Assign tutors to a comision (replaces existing assignments).

        Args:
            comision_id: Comision's database ID.
            data: TutoresAssign with list of tutor IDs.

        Returns:
            TutoresResponse with assigned tutors.

        Raises:
            HTTPException 404: Comision not found or tutor not found.
            HTTPException 400: User is not a tutor or is inactive.
        """
        # Validate comision exists
        comision = await self.comision_repo.get_active_by_id(comision_id)
        if not comision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comisión no encontrada o inactiva",
            )

        # Validate all tutors exist and have TUTOR role
        valid_tutores = []
        for tutor_id in data.tutor_ids:
            usuario = await self.usuario_repo.get_active_by_id(tutor_id)

            if not usuario:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Usuario con ID {tutor_id} no encontrado o inactivo",
                )

            if usuario.rol != RolEnum.TUTOR:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El usuario {usuario.username} no tiene rol de TUTOR",
                )

            valid_tutores.append(usuario)

        # Remove all previous assignments
        await self.comision_tutor_repo.delete_all_for_comision(comision_id)

        # Create new assignments
        for usuario in valid_tutores:
            await self.comision_tutor_repo.create(
                tutor_id=usuario.id,
                comision_id=comision_id,
            )

        # Build response
        tutores_list = [
            UsuarioListItem(
                id=u.id,
                username=u.username,
                nombre=u.nombre,
                email=u.email,
                rol=u.rol,
                activo=u.activo,
                created_at=u.created_at,
            )
            for u in valid_tutores
        ]

        return TutoresResponse(
            comision_id=comision_id,
            tutores=tutores_list,
            message=f"{len(tutores_list)} tutor(es) asignado(s) exitosamente",
        )
