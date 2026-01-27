# app/services/materia_service.py
"""
Materia service for Active-IA.

Business logic for subject (materia) management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 4
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RolEnum
from app.models.materia import Materia
from app.repositories.materia_repository import (
    CoordinadorMateriaRepository,
    MateriaRepository,
)
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
        self.usuario_repo = UsuarioRepository(db)

    async def crear_materia(self, data: MateriaCreate) -> MateriaResponse:
        """
        Create a new materia.

        Args:
            data: Materia creation data (codigo, nombre, descripcion).

        Returns:
            MateriaResponse with materia data.

        Raises:
            HTTPException 409: Codigo already exists.
        """
        # Normalize codigo to uppercase
        codigo_upper = data.codigo.upper()

        # Check if codigo already exists
        if await self.materia_repo.exists_codigo(codigo_upper):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El código de materia ya existe",
            )

        # Create materia
        materia = Materia(
            codigo=codigo_upper,
            nombre=data.nombre,
            descripcion=data.descripcion,
            activa=True,
        )

        created_materia = await self.materia_repo.create(materia)

        return MateriaResponse.model_validate(created_materia)

    async def listar_materias(
        self,
        *,
        include_inactive: bool = False,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> MateriaList:
        """
        List materias with optional filters and pagination.

        Args:
            include_inactive: Include soft-deleted materias.
            search: Search term for codigo or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            MateriaList with paginated results.
        """
        materias, total = await self.materia_repo.get_all(
            include_inactive=include_inactive,
            search=search,
            page=page,
            per_page=per_page,
        )

        # Build list items with counts
        items = []
        for materia in materias:
            # Count coordinadores
            coordinadores = await self.coord_materia_repo.get_coordinadores_for_materia(
                materia.id
            )
            num_coordinadores = len(coordinadores)

            # Count active comisiones
            num_comisiones = len(
                [c for c in materia.comisiones if c.activa]
            ) if materia.comisiones else 0

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

    async def obtener_materia(self, materia_id: int) -> MateriaDetailResponse:
        """
        Get a materia by ID with coordinators info.

        Args:
            materia_id: Materia's database ID.

        Returns:
            MateriaDetailResponse with materia data and coordinators.

        Raises:
            HTTPException 404: Materia not found.
        """
        materia = await self.materia_repo.get_by_id_with_coordinadores(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
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
            created_at=materia.created_at,
            updated_at=materia.updated_at,
            coordinadores=coordinadores_info,
        )

    async def actualizar_materia(
        self,
        materia_id: int,
        data: MateriaUpdate,
    ) -> MateriaResponse:
        """
        Update a materia's information.

        Args:
            materia_id: Materia's database ID.
            data: Update data (nombre, descripcion).

        Returns:
            MateriaResponse with updated materia data.

        Raises:
            HTTPException 404: Materia not found.
        """
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )

        # Update only provided fields
        if data.nombre is not None:
            materia.nombre = data.nombre
        if data.descripcion is not None:
            materia.descripcion = data.descripcion

        updated_materia = await self.materia_repo.update(materia)

        return MateriaResponse.model_validate(updated_materia)

    async def eliminar_materia(self, materia_id: int) -> None:
        """
        Soft delete a materia.

        Args:
            materia_id: Materia's database ID.

        Raises:
            HTTPException 404: Materia not found.
            HTTPException 400: Materia already deleted.
        """
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )

        if not materia.activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La materia ya está eliminada",
            )

        await self.materia_repo.soft_delete(materia)

    async def restaurar_materia(self, materia_id: int) -> MateriaResponse:
        """
        Restore a soft-deleted materia.

        Args:
            materia_id: Materia's database ID.

        Returns:
            MateriaResponse with restored materia data.

        Raises:
            HTTPException 404: Materia not found.
            HTTPException 400: Materia is not deleted.
        """
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
            )

        if materia.activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La materia no está eliminada",
            )

        restored_materia = await self.materia_repo.restore(materia)

        return MateriaResponse.model_validate(restored_materia)

    async def asignar_coordinadores(
        self,
        materia_id: int,
        data: CoordinadoresAssign,
    ) -> CoordinadoresResponse:
        """
        Assign coordinators to a materia.

        This replaces all existing coordinators with the new list.

        Args:
            materia_id: Materia's database ID.
            data: List of coordinator IDs to assign.

        Returns:
            CoordinadoresResponse with assigned coordinators.

        Raises:
            HTTPException 404: Materia not found.
            HTTPException 400: Invalid coordinator (not found or wrong role).
        """
        # Verify materia exists
        materia = await self.materia_repo.get_by_id(materia_id)

        if not materia:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Materia no encontrada",
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
    ) -> list[MateriaResponse]:
        """
        Get all materias assigned to a coordinator.

        Args:
            coordinador_id: Coordinator's user ID.

        Returns:
            List of MateriaResponse for the coordinator.
        """
        materias = await self.materia_repo.get_by_coordinador(coordinador_id)

        return [MateriaResponse.model_validate(m) for m in materias]
