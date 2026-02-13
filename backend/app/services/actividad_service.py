# app/services/actividad_service.py
"""
Service layer for Actividad (Activity/Audit) operations.

Handles business logic for activity logging and retrieval.

Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
Ref: docs/specs/09-PATRONES-CODIGO.md - Service pattern
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TipoActividadEnum
from app.repositories.actividad_repository import ActividadRepository
from app.schemas.actividad import (
    ActividadCreate,
    ActividadListResponse,
    ActividadResponse,
)


class ActividadService:
    """Service para gestionar actividades/auditoría."""

    def __init__(self, db: AsyncSession):
        self.repository = ActividadRepository(db)

    async def registrar_actividad(
        self,
        tipo: TipoActividadEnum,
        descripcion: str,
        entidad_id: int,
        entidad_nombre: str,
        usuario_id: int | None = None,
        metadatos: str | None = None,
    ) -> None:
        """
        Registra una nueva actividad en el sistema.

        Este método se llamará desde otros servicios al crear entidades.

        Args:
            tipo: Tipo de actividad
            descripcion: Descripción de la actividad
            entidad_id: ID de la entidad afectada
            entidad_nombre: Nombre de la entidad afectada
            usuario_id: ID del usuario que realizó la acción (opcional)
            metadatos: Datos adicionales en formato JSON (opcional)
        """
        actividad = ActividadCreate(
            tipo=tipo,
            descripcion=descripcion,
            entidad_id=entidad_id,
            entidad_nombre=entidad_nombre,
            usuario_id=usuario_id,
            metadatos=metadatos,
        )
        await self.repository.create(actividad)

    async def get_actividades_recientes(
        self,
        limit: int = 10,
        offset: int = 0,
        tipo: TipoActividadEnum | None = None,
    ) -> ActividadListResponse:
        """
        Obtiene las actividades más recientes.

        Args:
            limit: Número máximo de resultados
            offset: Offset para paginación
            tipo: Filtrar por tipo de actividad (opcional)

        Returns:
            Lista de actividades con información del usuario
        """
        actividades, total = await self.repository.get_recent(
            limit=limit, offset=offset, tipo=tipo
        )

        # Mapear a response schema
        items = []
        for act in actividades:
            item = ActividadResponse(
                id=act.id,
                tipo=act.tipo,
                descripcion=act.descripcion,
                entidad_id=act.entidad_id,
                entidad_nombre=act.entidad_nombre,
                usuario_id=act.usuario_id,
                created_at=act.created_at,
                usuario_nombre=(
                    f"{act.usuario.nombre}" if act.usuario else None
                ),
                usuario_rol=act.usuario.rol.value if act.usuario else None,
            )
            items.append(item)

        return ActividadListResponse(items=items, total=total)
