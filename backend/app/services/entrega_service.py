# app/services/entrega_service.py
"""
Entrega service for Active-IA.

Business logic for student submission (entrega) management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
"""

import hashlib
import os
from datetime import datetime
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum
from app.repositories.comision_repository import ComisionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.schemas.entrega import (
    CargaMasivaResponse,
    ContenidoEntrega,
    EntregaCreada,
    EntregaCreate,
    EntregaDetailResponse,
    EntregaError,
    EntregaList,
    EntregaListItem,
    EntregaResponse,
    HistorialItem,
    HistorialResponse,
)
from app.services.consolidacion_service import ConsolidacionService
from app.services.historial_service import HistorialService


class EntregaService:
    """Service for entrega management operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize entrega service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.entrega_repo = EntregaRepository(db)
        self.comision_repo = ComisionRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.consolidacion_service = ConsolidacionService()
        self.historial_service = HistorialService(db)

    async def crear_entrega_individual(
        self,
        data: EntregaCreate,
        archivo: UploadFile,
        subido_por_id: int,
        sobrescribir: bool = False,
        modo_consolidacion: str = "solo_codigo",
    ) -> EntregaResponse:
        """
        Create a new entrega from individual upload.

        Args:
            data: Entrega creation data.
            archivo: Uploaded file (ZIP or TXT).
            subido_por_id: ID of user uploading.
            sobrescribir: If True, overwrites existing entrega.

        Returns:
            EntregaResponse with entrega data.

        Raises:
            HTTPException 404: Comision or Rubrica not found.
            HTTPException 409: Entrega already exists and sobrescribir=False.
            HTTPException 400: Invalid file type.
        """
        # Validate comision exists
        comision = await self.comision_repo.get_active_by_id(data.comision_id)
        if not comision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comisión no encontrada o inactiva",
            )

        # Validate rubrica exists
        rubrica = await self.rubrica_repo.get_active_by_id(data.rubrica_id)
        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada o inactiva",
            )

        # Validate file type
        archivo_tipo = self._get_file_type(archivo.filename)
        if archivo_tipo not in ["zip", "txt"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permiten archivos ZIP o TXT",
            )

        # Read file content
        contenido_bytes = await archivo.read()
        archivo_tamanio = len(contenido_bytes)

        # Calculate hash
        hash_sha256 = hashlib.sha256(contenido_bytes).hexdigest()

        # Consolidate content
        contenido_consolidado, archivos_incluidos = await self._consolidar_archivo(
            contenido_bytes, archivo_tipo, modo_consolidacion
        )

        # Generate preview
        contenido_preview = self.consolidacion_service.generar_preview(
            contenido_consolidado, max_chars=500
        )

        # Check if entrega already exists
        entrega_existente = await self.entrega_repo.get_by_rubrica_alumno(
            rubrica_id=data.rubrica_id,
            alumno_nombre=data.alumno_nombre,
        )

        if entrega_existente:
            if not sobrescribir:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una entrega para el alumno '{data.alumno_nombre}' en esta rúbrica",
                )

            # Save to history before overwriting
            await self.historial_service.guardar_version_anterior(
                entrega_existente, subido_por_id
            )

            # Update existing entrega
            entrega_existente.archivo_nombre = archivo.filename
            entrega_existente.archivo_tamanio = archivo_tamanio
            entrega_existente.archivo_tipo = archivo_tipo
            entrega_existente.contenido_preview = contenido_preview
            entrega_existente.contenido_consolidado = contenido_consolidado
            entrega_existente.archivos_incluidos = archivos_incluidos
            entrega_existente.hash_sha256 = hash_sha256
            entrega_existente.estado = EstadoEntregaEnum.SUBIDA
            entrega_existente.subido_por_id = subido_por_id

            # Note: archivo_ruta would be updated by file storage service
            # For now, we keep the same path or generate a new one
            entrega_existente.archivo_ruta = f"/uploads/entregas/{hash_sha256[:8]}_{archivo.filename}"

            updated_entrega = await self.entrega_repo.update(entrega_existente)
            return EntregaResponse.model_validate(updated_entrega)

        # Create new entrega
        archivo_ruta = f"/uploads/entregas/{hash_sha256[:8]}_{archivo.filename}"

        entrega = Entrega(
            comision_id=data.comision_id,
            rubrica_id=data.rubrica_id,
            alumno_nombre=data.alumno_nombre,
            archivo_nombre=archivo.filename,
            archivo_ruta=archivo_ruta,
            archivo_tamanio=archivo_tamanio,
            archivo_tipo=archivo_tipo,
            contenido_preview=contenido_preview,
            contenido_consolidado=contenido_consolidado,
            archivos_incluidos=archivos_incluidos,
            estado=EstadoEntregaEnum.SUBIDA,
            hash_sha256=hash_sha256,
            subido_por_id=subido_por_id,
        )

        created_entrega = await self.entrega_repo.create(entrega)
        return EntregaResponse.model_validate(created_entrega)

    async def listar_entregas(
        self,
        *,
        comision_id: int | None = None,
        rubrica_id: int | None = None,
        estado: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> EntregaList:
        """
        List entregas with optional filters and pagination.

        Args:
            comision_id: Filter by comision ID.
            rubrica_id: Filter by rubrica ID.
            estado: Filter by estado.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            EntregaList with paginated results.
        """
        entregas, total = await self.entrega_repo.get_all(
            comision_id=comision_id,
            rubrica_id=rubrica_id,
            estado=estado,
            page=page,
            per_page=per_page,
        )

        # Build list items
        items = []
        for entrega in entregas:
            items.append(
                EntregaListItem(
                    id=entrega.id,
                    comision_id=entrega.comision_id,
                    comision_nombre=entrega.comision.nombre,
                    rubrica_id=entrega.rubrica_id,
                    rubrica_nombre=entrega.rubrica.titulo,
                    rubrica_tipo=entrega.rubrica.tipo.value,
                    alumno_nombre=entrega.alumno_nombre,
                    archivo_nombre=entrega.archivo_nombre,
                    archivo_tamanio=entrega.archivo_tamanio,
                    archivo_tipo=entrega.archivo_tipo,
                    estado=entrega.estado,
                    tiene_correccion=entrega.correccion is not None,
                    subido_por_nombre=entrega.subido_por.nombre,
                    created_at=entrega.created_at,
                )
            )

        return EntregaList(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )

    async def obtener_entrega(self, entrega_id: int) -> EntregaDetailResponse:
        """
        Get an entrega by ID with full details.

        Args:
            entrega_id: Entrega's database ID.

        Returns:
            EntregaDetailResponse with full entrega data.

        Raises:
            HTTPException 404: Entrega not found.
        """
        entrega = await self.entrega_repo.get_by_id_with_relations(entrega_id)

        if not entrega:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrega no encontrada",
            )

        # Count historical versions
        historial_response = await self.historial_service.obtener_historial(
            entrega_id
        )
        num_versiones = historial_response.total_versiones

        # Build response (schemas will handle nested objects)
        return EntregaDetailResponse(
            id=entrega.id,
            comision_id=entrega.comision_id,
            rubrica_id=entrega.rubrica_id,
            alumno_nombre=entrega.alumno_nombre,
            archivo_nombre=entrega.archivo_nombre,
            archivo_ruta=entrega.archivo_ruta,
            archivo_tamanio=entrega.archivo_tamanio,
            archivo_tipo=entrega.archivo_tipo,
            contenido_preview=entrega.contenido_preview,
            estado=entrega.estado,
            hash_sha256=entrega.hash_sha256,
            subido_por_id=entrega.subido_por_id,
            created_at=entrega.created_at,
            updated_at=entrega.updated_at,
            comision={
                "id": entrega.comision.id,
                "nombre": entrega.comision.nombre,
                "materia_nombre": entrega.comision.materia.nombre,
                "materia_codigo": entrega.comision.materia.codigo,
            },
            rubrica={
                "id": entrega.rubrica.id,
                "nombre": entrega.rubrica.titulo,
                "tipo": entrega.rubrica.tipo.value,
                "numero": entrega.rubrica.numero,
            },
            subido_por={
                "id": entrega.subido_por.id,
                "nombre": entrega.subido_por.nombre,
                "email": entrega.subido_por.email,
            },
            tiene_correccion=entrega.correccion is not None,
            num_versiones_anteriores=num_versiones,
        )

    async def eliminar_entrega(self, entrega_id: int) -> None:
        """
        Physically delete an entrega (hard delete).

        Args:
            entrega_id: Entrega's database ID.

        Raises:
            HTTPException 404: Entrega not found.
        """
        entrega = await self.entrega_repo.get_by_id(entrega_id)

        if not entrega:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrega no encontrada",
            )

        await self.entrega_repo.delete(entrega)

    async def obtener_contenido(self, entrega_id: int) -> ContenidoEntrega:
        """
        Get the full consolidated content of an entrega.

        Args:
            entrega_id: ID of the entrega.

        Returns:
            ContenidoEntrega with full content and metadata.

        Raises:
            HTTPException 404: Entrega not found.
            HTTPException 400: Content not available.
        """
        # Get entrega
        entrega = await self.entrega_repo.get_by_id(entrega_id)
        if not entrega:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrega no encontrada",
            )

        # Use contenido_consolidado if available, fallback to preview for old entregas
        contenido = entrega.contenido_consolidado or entrega.contenido_preview

        if not contenido:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El contenido no está disponible para esta entrega",
            )

        return ContenidoEntrega(
            entrega_id=entrega.id,
            alumno_nombre=entrega.alumno_nombre,
            contenido_consolidado=contenido,
            archivos_incluidos=entrega.archivos_incluidos or [],
            total_lineas=len(contenido.splitlines()),
            total_caracteres=len(contenido),
        )

    async def _consolidar_archivo(
        self,
        contenido_bytes: bytes,
        archivo_tipo: str,
        modo: str = "solo_codigo",
    ) -> tuple[str, list[str]]:
        """
        Consolidate file content.

        Args:
            contenido_bytes: File content as bytes.
            archivo_tipo: File type ('zip' or 'txt').
            modo: Consolidation mode for ZIP files.

        Returns:
            Tuple of (consolidated_content, list_of_files).
        """
        import io

        file_obj = io.BytesIO(contenido_bytes)

        if archivo_tipo == "zip":
            return self.consolidacion_service.consolidar_zip(
                file_obj, modo=modo
            )
        else:  # txt
            return self.consolidacion_service.consolidar_txt(file_obj)



    def _get_file_type(self, filename: str) -> str:
        """
        Get file type from filename.

        Args:
            filename: Name of the file.

        Returns:
            'zip' or 'txt' or 'unknown'.
        """
        if not filename:
            return "unknown"

        extension = filename.rsplit(".", 1)[-1].lower()

        if extension == "zip":
            return "zip"
        elif extension == "txt":
            return "txt"
        else:
            return "unknown"
