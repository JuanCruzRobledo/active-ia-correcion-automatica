# app/services/materia_service.py
"""
Materia service for Active-IA.

Business logic for subject (materia) management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 4
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import verificar_pertenencia_universidad
from app.models.enums import RolEnum, TipoActividadEnum
from app.models.materia import Materia
from app.repositories.comision_repository import ComisionRepository
from app.repositories.materia_repository import (
    CoordinadorMateriaRepository,
    MateriaRepository,
)
from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.materia import (
    CoordinadoresAssign,
    CoordinadoresResponse,
    MateriaCreate,
    MateriaDetailResponse,
    MateriaList,
    MateriaListItem,
    MateriaResponse,
    MateriaUpdate,
)
from app.schemas.usuario import UsuarioListItem
from app.services.actividad_service import ActividadService


class MateriaService:
    """Service for materia management operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize materia service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.materia_repo = MateriaRepository(db)
        self.coord_materia_repo = CoordinadorMateriaRepository(db)
        self.comision_repo = ComisionRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    async def crear_materia(
        self,
        data: MateriaCreate,
        current_user_id: int | None = None,
        *,
        universidad_id: int | None = None,
    ) -> MateriaDetailResponse:
        """
        Create a new materia.

        Args:
            data: Materia creation data (codigo, nombre, descripcion, coordinador_ids).
            current_user_id: ID of the user creating this materia (for audit log).
            universidad_id: Fase 4 multi-tenant — `ctx.universidad_id` de quien crea.
                Materia es la RAÍZ del árbol (no tiene padre del que heredarlo), así
                que debe venir explícito. Un superadmin SIN universidad activa no
                puede crear materias "flotantes" — 400 si es None.

        Returns:
            MateriaDetailResponse with materia data and coordinators.

        Raises:
            HTTPException 409: Codigo already exists.
            HTTPException 400: Invalid coordinator, o falta universidad activa.
        """
        if universidad_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Se requiere una universidad activa para crear una materia "
                    "(seleccioná una universidad)"
                ),
            )
        # Normalize codigo to uppercase
        codigo_upper = data.codigo.upper()

        # Check if codigo already exists. CRUD-011: si el conflicto es contra una
        # materia ELIMINADA (soft delete), decirlo y ofrecer restaurar — si no, el
        # 409 confunde porque la materia borrada no aparece en el listado.
        conflicto = await self.materia_repo.get_by_codigo(
            codigo_upper, universidad_id=universidad_id
        )
        if conflicto is not None:
            if not conflicto.activa:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Ya existe una materia con código {codigo_upper}, pero está "
                        f"eliminada (id {conflicto.id}). Restaurala o elegí otro código."
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El código de materia ya existe",
            )

        # Validate coordinators if provided
        valid_coordinadores = []
        if data.coordinador_ids:
            for coord_id in data.coordinador_ids:
                usuario = await self.usuario_repo.get_by_id(coord_id)

                if not usuario:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Usuario con ID {coord_id} no encontrado",
                    )

                if not usuario.activo:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Usuario {usuario.username} está deshabilitado",
                    )

                if usuario.rol != RolEnum.COORDINADOR:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Usuario {usuario.username} no tiene rol de coordinador",
                    )

                valid_coordinadores.append(usuario)

        # Create materia
        materia = Materia(
            universidad_id=universidad_id,
            codigo=codigo_upper,
            nombre=data.nombre,
            descripcion=data.descripcion,
            activa=True,
        )

        created_materia = await self.materia_repo.create(materia)

        # Assign coordinators
        for usuario in valid_coordinadores:
            await self.coord_materia_repo.create(
                coordinador_id=usuario.id,
                materia_id=created_materia.id,
            )

        # Registrar actividad
        actividad_service = ActividadService(self.db)
        await actividad_service.registrar_actividad(
            tipo=TipoActividadEnum.MATERIA_CREADA,
            descripcion=f"Materia '{created_materia.nombre}' creada",
            entidad_id=created_materia.id,
            entidad_nombre=created_materia.nombre,
            usuario_id=current_user_id,
        )

        # Return detailed response with coordinators
        return await self.obtener_materia(created_materia.id)

    async def listar_materias(
        self,
        *,
        include_inactive: bool = False,
        activa: bool | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        coordinador_id: int | None = None,
        universidad_id: int | None = None,
    ) -> MateriaList:
        """
        List materias with optional filters and pagination.

        Args:
            include_inactive: Include soft-deleted materias.
            activa: If provided, filter by active status (only meaningful when include_inactive=True).
            search: Search term for codigo or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.
            coordinador_id: If set, filter to materias assigned to this coordinator.
            universidad_id: Fase 4 multi-tenant. `ctx.universidad_id`; None = sin
                filtro (bypass superadmin sin universidad activa).

        Returns:
            MateriaList with paginated results.
        """
        materias, total = await self.materia_repo.get_all(
            include_inactive=include_inactive,
            activa=activa,
            search=search,
            page=page,
            per_page=per_page,
            coordinador_id=coordinador_id,
            universidad_id=universidad_id,
        )

        materia_ids = [materia.id for materia in materias]
        # PERF-012: conteo de coordinadores de TODAS las materias de la página en UNA
        # query agregada (antes: get_coordinadores_for_materia por materia en loop).
        coord_counts = await self.coord_materia_repo.contar_por_materias(materia_ids)
        # CRUD-016: idem para las comisiones activas, en vez de materializar la
        # colección materia.comisiones (lazy=selectin) de cada materia solo para contar.
        comi_counts = await self.comision_repo.contar_comisiones_activas_por_materia(
            materia_ids
        )

        # Build list items with counts
        items = []
        for materia in materias:
            num_coordinadores = coord_counts.get(materia.id, 0)
            num_comisiones = comi_counts.get(materia.id, 0)

            items.append(
                MateriaListItem(
                    id=materia.id,
                    codigo=materia.codigo,
                    nombre=materia.nombre,
                    activa=materia.activa,
                    created_at=materia.created_at,
                    num_coordinadores=num_coordinadores,
                    num_comisiones=num_comisiones,
                )
            )

        return MateriaList(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )

    async def obtener_materia(
        self, materia_id: int, *, universidad_id: int | None = None
    ) -> MateriaDetailResponse:
        """
        Get a materia by ID with coordinators info.

        Args:
            materia_id: Materia's database ID.
            universidad_id: Fase 4 multi-tenant. `ctx.universidad_id`; si la
                materia pertenece a otra universidad, 404 (D3).

        Returns:
            MateriaDetailResponse with materia data and coordinators.

        Raises:
            HTTPException 404: Materia not found (o de otra universidad).
        """
        materia = await self.materia_repo.get_by_id_with_coordinadores(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )
        # Fase 4 multi-tenant (D3): mismo mensaje que el "no encontrada" de arriba,
        # para que el caso cross-tenant sea indistinguible de "no existe".
        verificar_pertenencia_universidad(
            materia, universidad_id, detail="Materia no encontrada"
        )

        # Build coordinadores info
        coordinadores_info = []
        for coord_materia in materia.coordinadores:
            coordinador = await self.usuario_repo.get_by_id(
                coord_materia.coordinador_id
            )
            if coordinador and coordinador.activo:
                coordinadores_info.append({
                    "id": coordinador.id,
                    "username": coordinador.username,
                    "nombre": coordinador.nombre,
                    "asignado_en": coord_materia.asignado_en,
                })

        return MateriaDetailResponse(
            id=materia.id,
            codigo=materia.codigo,
            nombre=materia.nombre,
            descripcion=materia.descripcion,
            activa=materia.activa,
            moodle_course_id=materia.moodle_course_id,
            created_at=materia.created_at,
            updated_at=materia.updated_at,
            coordinadores=coordinadores_info,
        )

    async def actualizar_materia(
        self,
        materia_id: int,
        data: MateriaUpdate,
        *,
        universidad_id: int | None = None,
    ) -> MateriaDetailResponse:
        """
        Update a materia's information.

        Args:
            materia_id: Materia's database ID.
            data: Update data (nombre, descripcion, coordinador_ids).
            universidad_id: Fase 4 multi-tenant. `ctx.universidad_id`.

        Returns:
            MateriaDetailResponse with updated materia data and coordinators.

        Raises:
            HTTPException 404: Materia not found (o de otra universidad).
            HTTPException 400: Invalid coordinator.
        """
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )
        verificar_pertenencia_universidad(
            materia, universidad_id, detail="Materia no encontrada"
        )

        # Update only provided fields. CRUD-010: los nullable usan model_fields_set
        # para distinguir "ausente" (preservar) de "null explícito" (limpiar).
        if data.nombre is not None:
            materia.nombre = data.nombre
        if "descripcion" in data.model_fields_set:
            materia.descripcion = data.descripcion
        if "moodle_course_id" in data.model_fields_set:
            materia.moodle_course_id = data.moodle_course_id

        await self.materia_repo.update(materia)

        # Update coordinators if provided
        if data.coordinador_ids is not None:
            # Validate coordinators
            valid_coordinadores = []
            for coord_id in data.coordinador_ids:
                usuario = await self.usuario_repo.get_by_id(coord_id)

                if not usuario:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Usuario con ID {coord_id} no encontrado",
                    )

                if not usuario.activo:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Usuario {usuario.username} está deshabilitado",
                    )

                if usuario.rol != RolEnum.COORDINADOR:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Usuario {usuario.username} no tiene rol de coordinador",
                    )

                valid_coordinadores.append(usuario)

            # Remove all existing assignments
            await self.coord_materia_repo.delete_all_for_materia(materia_id)

            # Create new assignments
            for usuario in valid_coordinadores:
                await self.coord_materia_repo.create(
                    coordinador_id=usuario.id,
                    materia_id=materia_id,
                )

        # Return detailed response with coordinators
        return await self.obtener_materia(materia_id)

    async def eliminar_materia(
        self, materia_id: int, *, universidad_id: int | None = None
    ) -> None:
        """
        Delete a materia — soft or hard depending on ALLOW_HARD_DELETE setting.

        When ALLOW_HARD_DELETE=false (default):
            Soft delete: sets activa=False. Reversible via restaurar_materia.
        When ALLOW_HARD_DELETE=true:
            Hard delete: physically removes materia and ALL related data:
            - Comisiones → Entregas → Correcciones / EntregaHistorial / archivos físicos
            - Rúbricas (exclusivas de la materia)
            - CoordinadorMateria assignments
            - DELETE Materia — IRREVERSIBLE.

        Args:
            materia_id: Materia's database ID.
            universidad_id: Fase 4 multi-tenant. `ctx.universidad_id`.

        Raises:
            HTTPException 404: Materia not found (o de otra universidad).
            HTTPException 400: (soft delete only) Materia already deleted.
        """
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )
        verificar_pertenencia_universidad(
            materia, universidad_id, detail="Materia no encontrada"
        )

        # CRUD-002: soft delete SIEMPRE (se eliminó el flag ALLOW_HARD_DELETE, que
        # sobrecargaba el mismo verbo DELETE con dos semánticas según config).
        if not materia.activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La materia ya está eliminada",
            )
        await self.materia_repo.soft_delete(materia)
        # CRUD-006: propagar la baja a los hijos, para que las comisiones no
        # queden operables (crear_entrega valida comisión activa) ni visibles.
        await self.comision_repo.desactivar_por_materia(materia_id)
        await self.rubrica_repo.desactivar_por_materia(materia_id)

    async def restaurar_materia(
        self, materia_id: int, *, universidad_id: int | None = None
    ) -> MateriaResponse:
        """
        Restore a soft-deleted materia.

        Args:
            materia_id: Materia's database ID.
            universidad_id: Fase 4 multi-tenant. `ctx.universidad_id`.

        Returns:
            MateriaResponse with restored materia data.

        Raises:
            HTTPException 404: Materia not found (o de otra universidad).
            HTTPException 400: Materia is not deleted.
        """
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )
        verificar_pertenencia_universidad(
            materia, universidad_id, detail="Materia no encontrada"
        )

        if materia.activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La materia no está eliminada",
            )

        restored_materia = await self.materia_repo.restore(materia)
        # CRUD-006: reactivar los hijos que se dieron de baja al eliminar la materia.
        await self.comision_repo.reactivar_por_materia(materia_id)
        await self.rubrica_repo.reactivar_por_materia(materia_id)

        return MateriaResponse.model_validate(restored_materia)

    async def asignar_coordinadores(
        self,
        materia_id: int,
        data: CoordinadoresAssign,
        *,
        universidad_id: int | None = None,
    ) -> CoordinadoresResponse:
        """
        Assign coordinators to a materia.

        This replaces all existing coordinators with the new list.

        Args:
            materia_id: Materia's database ID.
            data: List of coordinator IDs to assign.
            universidad_id: Fase 4 multi-tenant. `ctx.universidad_id`.

        Returns:
            CoordinadoresResponse with assigned coordinators.

        Raises:
            HTTPException 404: Materia not found (o de otra universidad).
            HTTPException 400: Invalid coordinator (not found or wrong role).
        """
        # Verify materia exists
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )
        verificar_pertenencia_universidad(
            materia, universidad_id, detail="Materia no encontrada"
        )

        # Validate all coordinators
        valid_coordinadores = []
        for coord_id in data.coordinador_ids:
            usuario = await self.usuario_repo.get_by_id(coord_id)

            if not usuario:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Usuario con ID {coord_id} no encontrado",
                )

            if not usuario.activo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Usuario {usuario.username} está deshabilitado",
                )

            if usuario.rol != RolEnum.COORDINADOR:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Usuario {usuario.username} no tiene rol de coordinador",
                )

            valid_coordinadores.append(usuario)

        # Remove all existing assignments
        await self.coord_materia_repo.delete_all_for_materia(materia_id)

        # Create new assignments
        for usuario in valid_coordinadores:
            await self.coord_materia_repo.create(
                coordinador_id=usuario.id,
                materia_id=materia_id,
            )

        # Build response
        coordinadores_list = [
            UsuarioListItem(
                id=u.id,
                username=u.username,
                nombre=u.nombre,
                rol=u.rol,
                activo=u.activo,
                created_at=u.created_at,
                last_login=u.last_login,
            )
            for u in valid_coordinadores
        ]

        return CoordinadoresResponse(
            materia_id=materia_id,
            coordinadores=coordinadores_list,
            message=f"{len(valid_coordinadores)} coordinador(es) asignado(s) exitosamente",
        )

    async def obtener_materias_coordinador(
        self,
        coordinador_id: int,
        *,
        universidad_id: int | None = None,
    ) -> list[MateriaResponse]:
        """
        Get all materias assigned to a coordinator.

        Args:
            coordinador_id: Coordinator's user ID.
            universidad_id: Fase 4 multi-tenant. `ctx.universidad_id`.

        Returns:
            List of MateriaResponse for the coordinator.
        """
        materias = await self.materia_repo.get_by_coordinador(
            coordinador_id, universidad_id=universidad_id
        )

        return [MateriaResponse.model_validate(m) for m in materias]
