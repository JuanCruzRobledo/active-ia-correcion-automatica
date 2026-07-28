# app/services/historial_service.py
"""
Historial service for Active-IA.

Business logic for managing entrega history when submissions are overwritten.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
Ref: docs/specs/06-MODELO-DATOS.md seccion 3.9
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entrega import Entrega, EntregaHistorial
from app.repositories.entrega_historial_repository import (
    EntregaHistorialRepository,
)
from app.schemas.entrega import HistorialItem, HistorialResponse


class HistorialService:
    """Service for entrega history management operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize historial service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.historial_repo = EntregaHistorialRepository(db)

    async def guardar_version_anterior(
        self,
        entrega: Entrega,
        sobrescrito_por_id: int,
    ) -> EntregaHistorial:
        """
        Save current entrega to history before overwriting.

        When an entrega is overwritten (same student + rubrica),
        this method preserves the previous version including its
        correction if it existed.

        Args:
            entrega: Current entrega to save to history.
            sobrescrito_por_id: ID of user overwriting the entrega.

        Returns:
            Created EntregaHistorial object.
        """
        # Extract current correction data if exists
        nota_anterior = None
        correccion_json = None

        if entrega.correccion:
            nota_anterior = entrega.correccion.nota
            correccion_json = {
                "nota_final": float(entrega.correccion.nota),
                "criterios_json": entrega.correccion.criterios_json,
            }

        # Create historial entry
        historial = EntregaHistorial(
            entrega_actual_id=entrega.id,
            alumno_nombre=entrega.alumno_nombre,
            archivo_nombre=entrega.archivo_nombre,
            archivo_tamanio=entrega.archivo_tamanio,
            contenido_preview=entrega.contenido_preview,
            # CRUD-005: preservar el contenido REAL, no solo el preview.
            contenido_consolidado=entrega.contenido_consolidado,
            pdf_contenido_b64=entrega.pdf_contenido_b64,
            hash_sha256=entrega.hash_sha256,
            nota_anterior=nota_anterior,
            correccion_json=correccion_json,
            sobrescrito_en=datetime.utcnow(),
            sobrescrito_por_id=sobrescrito_por_id,
        )

        return await self.historial_repo.create(historial)

    async def obtener_historial(self, entrega_id: int) -> HistorialResponse:
        """
        Get all historical versions for an entrega.

        Args:
            entrega_id: ID of the current entrega.

        Returns:
            HistorialResponse with list of historical versions.
        """
        historial_list = await self.historial_repo.get_by_entrega(entrega_id)

        items = [
            HistorialItem(
                id=h.id,
                archivo_nombre=h.archivo_nombre,
                archivo_tamanio=h.archivo_tamanio,
                hash_sha256=h.hash_sha256,
                nota_anterior=h.nota_anterior,
                sobrescrito_en=h.sobrescrito_en,
                sobrescrito_por_nombre=h.sobrescrito_por.nombre,
            )
            for h in historial_list
        ]

        return HistorialResponse(
            entrega_actual_id=entrega_id,
            total_versiones=len(items),
            versiones_anteriores=items,
        )

    async def obtener_version_especifica(
        self, historial_id: int
    ) -> EntregaHistorial | None:
        """
        Get a specific historical version by ID.

        Args:
            historial_id: ID of the historial entry.

        Returns:
            EntregaHistorial object if found, None otherwise.
        """
        return await self.historial_repo.get_by_id(historial_id)
