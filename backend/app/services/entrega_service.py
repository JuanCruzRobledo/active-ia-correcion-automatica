# app/services/entrega_service.py
"""
Entrega service for Active-IA.

Business logic for student submission (entrega) management operations.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
"""

import base64
import hashlib
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import BinaryIO, Literal

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.upload_limits import validar_tamano_upload, validar_zip_bomb
from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum
from app.repositories.comision_repository import ComisionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.schemas.entrega import (
    CargaMasivaResponse,
    ContenidoEntrega,
    EntregaAccionMasivaResponse,
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


@dataclass
class ResultadoImportEntrega:
    """Resultado clasificado de importar una entrega desde bytes (sin lanzar).

    status:
      - "creada"       : se creó una entrega nueva en estado SUBIDA.
      - "duplicada"    : ya existía (sin corrección) → no se re-importa.
      - "ya_corregida" : ya existía y tiene corrección → no se pisa.
      - "error"        : tipo de archivo no soportado u otro problema.
    """

    status: Literal["creada", "duplicada", "ya_corregida", "error"]
    entrega_id: int | None = None
    detalle: str | None = None
    # En caso "ya_corregida": fecha de la corrección existente, para que el
    # importador pueda detectar re-entregas (timemodified Moodle > esta fecha).
    correccion_actualizada_en: datetime | None = None


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
        extensiones_personalizadas: list[str] | None = None,
        moodle_user_id: int | None = None,
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
            HTTPException 413: File exceeds MAX_UPLOAD_SIZE.
        """
        # Barrera temprana de tamaño (PERF-008): rechazar por el tamaño declarado
        # (UploadFile.size / Content-Length) antes de cualquier trabajo de DB.
        validar_tamano_upload(getattr(archivo, "size", None))

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
        if archivo_tipo == "binary":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se permiten archivos binarios (imágenes, ejecutables, etc.). Para entregar un PDF, selecciona el archivo .pdf directamente.",
            )
        elif archivo_tipo == "unknown":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipo de archivo desconocido",
            )

        # Read file content
        contenido_bytes = await archivo.read()
        archivo_tamanio = len(contenido_bytes)

        # Barrera definitiva de tamaño (PERF-008): el header es falsificable/ausente,
        # así que se valida el largo real antes de consolidar.
        validar_tamano_upload(archivo_tamanio)

        # Calculate hash
        hash_sha256 = hashlib.sha256(contenido_bytes).hexdigest()

        # Consolidate content. Un ZIP que solo trae un PDF se reclasifica como
        # "pdf"; con código, prioriza el código. Lógica única en _procesar_contenido.
        (
            archivo_tipo,
            contenido_consolidado,
            contenido_preview,
            archivos_incluidos,
            pdf_contenido_b64,
        ) = await self._procesar_contenido(
            contenido_bytes, archivo_tipo, modo_consolidacion, archivo.filename,
            extensiones_personalizadas,
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

            # Prevent overwriting if entrega has a correction
            if entrega_existente.correccion:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede sobrescribir la entrega del alumno '{data.alumno_nombre}' porque ya tiene una corrección. Elimina la corrección para poder sobrescribir.",
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
            entrega_existente.pdf_contenido_b64 = pdf_contenido_b64
            entrega_existente.hash_sha256 = hash_sha256
            entrega_existente.estado = EstadoEntregaEnum.SUBIDA
            entrega_existente.subido_por_id = subido_por_id
            # Vínculo a Moodle desde la URL pegada (item #4); solo si vino uno nuevo.
            if moodle_user_id is not None:
                entrega_existente.moodle_user_id = moodle_user_id

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
            pdf_contenido_b64=pdf_contenido_b64,
            estado=EstadoEntregaEnum.SUBIDA,
            hash_sha256=hash_sha256,
            subido_por_id=subido_por_id,
            # Vínculo a Moodle desde la URL pegada (item #4): habilita "Subir a Moodle"
            # en entregas cargadas a mano.
            moodle_user_id=moodle_user_id,
        )

        created_entrega = await self.entrega_repo.create(entrega)
        return EntregaResponse.model_validate(created_entrega)

    async def verificar_entrega_existente(
        self, rubrica_id: int, alumno_nombre: str
    ) -> ResultadoImportEntrega | None:
        """Verifica si ya existe una entrega para (rubrica_id, alumno_nombre) SIN descargar.

        Permite al importador decidir si hace falta descargar el archivo desde Moodle:
          - None          → no existe, hay que importarla.
          - "ya_corregida"→ existe con corrección (incluye fecha para detectar reentregas).
          - "duplicada"   → existe sin corrección.
        """
        existente = await self.entrega_repo.get_by_rubrica_alumno(
            rubrica_id=rubrica_id,
            alumno_nombre=alumno_nombre,
        )
        if not existente:
            return None
        if existente.correccion:
            return ResultadoImportEntrega(
                status="ya_corregida",
                entrega_id=existente.id,
                correccion_actualizada_en=getattr(existente.correccion, "updated_at", None),
            )
        return ResultadoImportEntrega(status="duplicada", entrega_id=existente.id)

    async def crear_o_actualizar_desde_bytes(
        self,
        *,
        comision_id: int,
        rubrica_id: int,
        alumno_nombre: str,
        archivo_nombre: str,
        contenido_bytes: bytes,
        subido_por_id: int,
        moodle_user_id: int | None = None,
        modo_consolidacion: str = "solo_codigo",
        extensiones_personalizadas: list[str] | None = None,
    ) -> ResultadoImportEntrega:
        """Crea una entrega a partir de bytes (descarga de Moodle), de forma idempotente.

        A diferencia de `crear_entrega_individual`, NO recibe UploadFile y NO lanza
        HTTPException por casos de negocio: devuelve un `ResultadoImportEntrega`
        clasificado para que el importador arme el resumen.

        Asume que `comision_id`/`rubrica_id` ya fueron validados aguas arriba
        (el MoodleImportService los resuelve de la DB antes de llamar).

        Reglas de idempotencia (no destructivas):
          - Si ya existe entrega para (rubrica_id, alumno_nombre) CON corrección → "ya_corregida".
          - Si existe SIN corrección → "duplicada" (no se re-descarga ni se pisa).
          - Si no existe → se crea en estado SUBIDA → "creada".
        """
        archivo_tipo = self._get_file_type(archivo_nombre)
        if archivo_tipo in ("binary", "unknown"):
            return ResultadoImportEntrega(
                status="error",
                detalle=f"Tipo de archivo no soportado: {archivo_nombre}",
            )

        # Idempotencia: no re-importar ni pisar entregas existentes
        existente = await self.verificar_entrega_existente(rubrica_id, alumno_nombre)
        if existente is not None:
            return existente

        # Procesar contenido. Un ZIP sin archivos válidos (p. ej. solo .docx/imágenes)
        # es un caso de negocio de UNA entrega: se reporta como error, NO se lanza
        # (así no aborta la importación del resto del lote).
        try:
            (
                archivo_tipo,
                contenido_consolidado,
                contenido_preview,
                archivos_incluidos,
                pdf_contenido_b64,
            ) = await self._procesar_contenido(
                contenido_bytes, archivo_tipo, modo_consolidacion, archivo_nombre,
                extensiones_personalizadas,
            )
        except HTTPException as e:
            detalle = e.detail if isinstance(e.detail, str) else str(e.detail)
            return ResultadoImportEntrega(status="error", detalle=detalle)
        except Exception as e:  # noqa: BLE001 — robustez: una entrega no debe romper el lote
            return ResultadoImportEntrega(status="error", detalle=str(e))

        hash_sha256 = hashlib.sha256(contenido_bytes).hexdigest()
        archivo_ruta = f"/uploads/entregas/{hash_sha256[:8]}_{archivo_nombre}"

        entrega = Entrega(
            comision_id=comision_id,
            rubrica_id=rubrica_id,
            alumno_nombre=alumno_nombre,
            archivo_nombre=archivo_nombre,
            archivo_ruta=archivo_ruta,
            archivo_tamanio=len(contenido_bytes),
            archivo_tipo=archivo_tipo,
            contenido_preview=contenido_preview,
            contenido_consolidado=contenido_consolidado,
            archivos_incluidos=archivos_incluidos,
            pdf_contenido_b64=pdf_contenido_b64,
            estado=EstadoEntregaEnum.SUBIDA,
            hash_sha256=hash_sha256,
            subido_por_id=subido_por_id,
            moodle_user_id=moodle_user_id,
        )
        created_entrega = await self.entrega_repo.create(entrega)
        return ResultadoImportEntrega(status="creada", entrega_id=created_entrega.id)

    def _resultado_pdf(
        self, contenido_bytes: bytes, archivo_nombre: str
    ) -> tuple[str, None, str, list[str], str]:
        """Empaqueta una entrega PDF: base64, sin consolidación de texto."""
        pdf_b64 = base64.b64encode(contenido_bytes).decode("utf-8")
        return "pdf", None, "[Entrega en formato PDF]", [archivo_nombre], pdf_b64

    async def _procesar_contenido(
        self,
        contenido_bytes: bytes,
        archivo_tipo: str,
        modo_consolidacion: str,
        archivo_nombre: str,
        extensiones_personalizadas: list[str] | None,
    ) -> tuple[str, str | None, str, list[str], str | None]:
        """Procesa el contenido de un archivo según su tipo.

        Returns: (archivo_tipo, contenido_consolidado, contenido_preview,
                  archivos_incluidos, pdf_contenido_b64)

        El `archivo_tipo` devuelto puede DIFERIR del recibido: un ZIP que solo
        contiene un PDF se reclasifica como "pdf" para que la corrección lo mande
        como documento. Reglas:
          - PDF directo            → se guarda como Base64.
          - ZIP con código         → se consolida el código (prioridad).
          - ZIP sin código con PDF → se extrae y procesa el PDF.
          - ZIP sin código ni PDF  → se mantiene el error 400 (ZIP vacío/binarios).
        Los PDF no se consolidan: se guardan como Base64.
        """
        if archivo_tipo == "pdf":
            return self._resultado_pdf(contenido_bytes, archivo_nombre)

        if archivo_tipo == "zip":
            try:
                contenido_consolidado, archivos_incluidos = await self._consolidar_archivo(
                    contenido_bytes, "zip", modo_consolidacion, archivo_nombre,
                    extensiones_personalizadas=extensiones_personalizadas,
                )
            except HTTPException as e:
                # No hay código en el ZIP. Si trae un PDF, se procesa como entrega
                # PDF; si no (ZIP vacío o solo binarios), se mantiene el error.
                if e.status_code == status.HTTP_400_BAD_REQUEST:
                    pdf = self.consolidacion_service.extraer_pdf_de_zip(contenido_bytes)
                    if pdf is not None:
                        pdf_bytes, pdf_nombre = pdf
                        return self._resultado_pdf(pdf_bytes, pdf_nombre)
                raise
            contenido_preview = self.consolidacion_service.generar_preview(
                contenido_consolidado, max_chars=500
            )
            return "zip", contenido_consolidado, contenido_preview, archivos_incluidos, None

        # txt / individual
        contenido_consolidado, archivos_incluidos = await self._consolidar_archivo(
            contenido_bytes, archivo_tipo, modo_consolidacion, archivo_nombre,
            extensiones_personalizadas=extensiones_personalizadas,
        )
        contenido_preview = self.consolidacion_service.generar_preview(
            contenido_consolidado, max_chars=500
        )
        return archivo_tipo, contenido_consolidado, contenido_preview, archivos_incluidos, None

    async def listar_entregas(
        self,
        *,
        comision_id: int | None = None,
        rubrica_id: int | None = None,
        estado: str | None = None,
        include_archivadas: bool = False,
        solo_archivadas: bool = False,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> EntregaList:
        """
        List entregas with optional filters and pagination.

        Args:
            comision_id: Filter by comision ID.
            rubrica_id: Filter by rubrica ID.
            estado: Filter by estado.
            include_archivadas: If True, include archived entregas.
            solo_archivadas: If True, show only archived entregas.
            fecha_desde: Filter from this date (inclusive).
            fecha_hasta: Filter to this date (inclusive).
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            EntregaList with paginated results.
        """
        entregas, total = await self.entrega_repo.get_all(
            comision_id=comision_id,
            rubrica_id=rubrica_id,
            estado=estado,
            include_archivadas=include_archivadas,
            solo_archivadas=solo_archivadas,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
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
                    archivado=entrega.archivado,
                    nota=entrega.correccion.nota if entrega.correccion else None,
                    tiene_correccion=entrega.correccion is not None,
                    error_code=entrega.error_code,
                    error_mensaje=entrega.error_mensaje,
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
            archivado=entrega.archivado,
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

    async def archivar_entregas(
        self,
        ids: list[int],
        archivado: bool,
    ) -> EntregaAccionMasivaResponse:
        """
        Archive or unarchive multiple entregas.

        Args:
            ids: List of entrega IDs.
            archivado: True to archive, False to unarchive.

        Returns:
            EntregaAccionMasivaResponse with count of processed entregas.

        Raises:
            HTTPException 404: One or more IDs not found.
        """
        found = await self.entrega_repo.get_by_ids(ids)
        found_ids = {e.id for e in found}
        missing = [i for i in ids if i not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entregas no encontradas: {missing}",
            )

        count = await self.entrega_repo.archive_by_ids(ids, archivado)
        return EntregaAccionMasivaResponse(procesadas=count, ids=ids)

    async def eliminar_entregas_masivo(
        self,
        ids: list[int],
    ) -> EntregaAccionMasivaResponse:
        """
        Bulk hard delete multiple entregas.

        Args:
            ids: List of entrega IDs to delete.

        Returns:
            EntregaAccionMasivaResponse with count of deleted entregas.

        Raises:
            HTTPException 404: One or more IDs not found.
        """
        found = await self.entrega_repo.get_by_ids(ids)
        found_ids = {e.id for e in found}
        missing = [i for i in ids if i not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entregas no encontradas: {missing}",
            )

        count = await self.entrega_repo.delete_by_ids(ids)
        return EntregaAccionMasivaResponse(procesadas=count, ids=ids)

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

        # PDF submissions: return base64 content directly (no text consolidation)
        if entrega.archivo_tipo == "pdf":
            return ContenidoEntrega(
                entrega_id=entrega.id,
                alumno_nombre=entrega.alumno_nombre,
                es_pdf=True,
                contenido_consolidado=None,
                pdf_contenido_b64=entrega.pdf_contenido_b64,
                archivos_incluidos=entrega.archivos_incluidos or [entrega.archivo_nombre],
                total_lineas=0,
                total_caracteres=0,
            )

        # Code submissions: use contenido_consolidado, fallback to preview for old entregas
        contenido = entrega.contenido_consolidado or entrega.contenido_preview

        if not contenido:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El contenido no está disponible para esta entrega",
            )

        return ContenidoEntrega(
            entrega_id=entrega.id,
            alumno_nombre=entrega.alumno_nombre,
            es_pdf=False,
            contenido_consolidado=contenido,
            pdf_contenido_b64=None,
            archivos_incluidos=entrega.archivos_incluidos or [],
            total_lineas=len(contenido.splitlines()),
            total_caracteres=len(contenido),
        )

    async def crear_entrega_masiva(
        self,
        comision_id: int,
        rubrica_id: int,
        archivo_zip: UploadFile,
        subido_por_id: int,
        sobrescribir: bool = False,
        modo_consolidacion: str = "solo_codigo",
        extensiones_personalizadas: list[str] | None = None,
    ) -> CargaMasivaResponse:
        """
        Create multiple entregas from a ZIP file containing student folders.

        Expected structure:
        - entregas.zip
          - alumno1/
            - proyecto.zip (or loose files)
          - alumno2/
            - proyecto.zip (or loose files)

        Args:
            comision_id: ID of the comision.
            rubrica_id: ID of the rubrica.
            archivo_zip: ZIP file with student folders.
            subido_por_id: ID of user uploading.
            sobrescribir: If True, overwrites existing entregas.
            modo_consolidacion: Consolidation mode for ZIP files.

        Returns:
            CargaMasivaResponse with summary of processed entregas.

        Raises:
            HTTPException 404: Comision or Rubrica not found.
            HTTPException 400: Invalid file type or structure.
        """
        import io
        import zipfile
        import tempfile

        # Barrera temprana de tamaño (PERF-008): rechazar el ZIP contenedor por su
        # tamaño declarado antes de cualquier trabajo de DB.
        validar_tamano_upload(getattr(archivo_zip, "size", None))

        # Validate comision exists
        comision = await self.comision_repo.get_active_by_id(comision_id)
        if not comision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comisión no encontrada o inactiva",
            )

        # Validate rubrica exists
        rubrica = await self.rubrica_repo.get_active_by_id(rubrica_id)
        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada o inactiva",
            )

        # Validate file type
        if not archivo_zip.filename or not archivo_zip.filename.lower().endswith(".zip"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permiten archivos ZIP",
            )

        # Read ZIP content
        contenido_bytes = await archivo_zip.read()

        # Barrera definitiva de tamaño del ZIP contenedor (PERF-008), antes de abrirlo.
        validar_tamano_upload(len(contenido_bytes))

        exitosas: list[EntregaCreada] = []
        errores: list[EntregaError] = []

        try:
            with zipfile.ZipFile(io.BytesIO(contenido_bytes), "r") as zip_file:
                # Anti ZIP-bomb (SEC-005): cortar por tamaño descomprimido acumulado
                # y por cantidad de entradas ANTES de leer/descomprimir carpetas.
                validar_zip_bomb(zip_file.filelist)

                # Normalize all paths: Windows ZIPs may use backslashes.
                # Build a mapping so we can read entries using the original name.
                original_names = zip_file.namelist()
                all_names = [n.replace("\\", "/") for n in original_names]
                normalized_to_original = dict(zip(all_names, original_names))

                # Get all directories in root (each directory = one student)
                root_dirs = set()
                for name in all_names:
                    parts = name.split("/")
                    if len(parts) > 1 and parts[0]:  # Has at least one folder
                        root_dirs.add(parts[0])

                if not root_dirs:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El ZIP no contiene carpetas de alumnos. Estructura esperada: carpeta_alumno/archivos",
                    )

                # Process each student folder
                for alumno_folder in sorted(root_dirs):
                    # Extract student name: take only before first "_", normalize spaces, apply title case
                    # Example: "Jose Andres    Sandoval_925405_assignsubmission_file" -> "Jose Andres Sandoval"
                    alumno_nombre = " ".join(alumno_folder.split("_")[0].split()).title()

                    try:
                        # Get all files in this student's folder
                        alumno_files = [
                            f for f in all_names
                            if f.startswith(f"{alumno_folder}/") and not f.endswith("/")
                        ]

                        if not alumno_files:
                            errores.append(
                                EntregaError(
                                    alumno_nombre=alumno_nombre,
                                    archivo_nombre=alumno_folder,
                                    error="La carpeta está vacía",
                                )
                            )
                            continue

                        # Check if there's a ZIP file inside
                        zip_files = [f for f in alumno_files if f.lower().endswith(".zip")]

                        if zip_files:
                            # Use the first ZIP found
                            inner_zip_path = zip_files[0]
                            inner_zip_content = zip_file.read(normalized_to_original[inner_zip_path])
                            archivo_nombre = inner_zip_path.split("/")[-1]
                            archivo_tipo = "zip"
                            contenido_bytes_alumno = inner_zip_content
                        elif len(alumno_files) == 1:
                            # Single file (not ZIP) - treat as individual file
                            single_file_path = alumno_files[0]
                            archivo_nombre = single_file_path.split("/")[-1]
                            contenido_bytes_alumno = zip_file.read(normalized_to_original[single_file_path])

                            # Detect file type
                            archivo_tipo_temp = self._get_file_type(archivo_nombre)
                            if archivo_tipo_temp == "pdf":
                                # PDF submissions: store as base64, skip consolidation
                                archivo_tipo = "pdf"
                            elif archivo_tipo_temp == "binary":
                                errores.append(
                                    EntregaError(
                                        alumno_nombre=alumno_nombre,
                                        archivo_nombre=archivo_nombre,
                                        error="No se permiten archivos binarios (imágenes, ejecutables, etc.)",
                                    )
                                )
                                continue
                            elif archivo_tipo_temp == "txt":
                                archivo_tipo = "txt"
                            else:
                                archivo_tipo = "individual"
                        else:
                            # Multiple loose files - create a ZIP from them
                            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
                                with zipfile.ZipFile(tmp_zip, "w") as new_zip:
                                    for file_path in alumno_files:
                                        # Remove student folder prefix
                                        arcname = "/".join(file_path.split("/")[1:])
                                        if arcname:  # Skip empty paths
                                            new_zip.writestr(arcname, zip_file.read(normalized_to_original[file_path]))

                                tmp_zip.seek(0)
                                contenido_bytes_alumno = tmp_zip.read()
                                archivo_nombre = f"{alumno_folder}_consolidado.zip"
                                archivo_tipo = "zip"

                        # Calculate hash
                        hash_sha256 = hashlib.sha256(contenido_bytes_alumno).hexdigest()
                        archivo_tamanio = len(contenido_bytes_alumno)

                        # Consolidate content. Un ZIP con solo PDF se reclasifica
                        # como "pdf"; con código prioriza el código. Misma lógica
                        # única que la subida individual y la importación Moodle.
                        (
                            archivo_tipo,
                            contenido_consolidado,
                            contenido_preview,
                            archivos_incluidos,
                            pdf_contenido_b64_alumno,
                        ) = await self._procesar_contenido(
                            contenido_bytes_alumno, archivo_tipo, modo_consolidacion,
                            archivo_nombre, extensiones_personalizadas,
                        )

                        # Check if entrega already exists
                        entrega_existente = await self.entrega_repo.get_by_rubrica_alumno(
                            rubrica_id=rubrica_id,
                            alumno_nombre=alumno_nombre,
                        )

                        sobrescrito = False

                        if entrega_existente:
                            if not sobrescribir:
                                errores.append(
                                    EntregaError(
                                        alumno_nombre=alumno_nombre,
                                        archivo_nombre=archivo_nombre,
                                        error=f"Ya existe una entrega para este alumno. Usa 'sobrescribir' para reemplazarla.",
                                    )
                                )
                                continue

                            # Prevent overwriting if entrega has a correction
                            if entrega_existente.correccion:
                                errores.append(
                                    EntregaError(
                                        alumno_nombre=alumno_nombre,
                                        archivo_nombre=archivo_nombre,
                                        error=f"No se puede sobrescribir porque el alumno ya tiene una corrección. Elimina la corrección para poder sobrescribir.",
                                    )
                                )
                                continue

                            # Save to history before overwriting
                            await self.historial_service.guardar_version_anterior(
                                entrega_existente, subido_por_id
                            )

                            # Update existing entrega
                            entrega_existente.archivo_nombre = archivo_nombre
                            entrega_existente.archivo_tamanio = archivo_tamanio
                            entrega_existente.archivo_tipo = archivo_tipo
                            entrega_existente.contenido_preview = contenido_preview
                            entrega_existente.contenido_consolidado = contenido_consolidado
                            entrega_existente.archivos_incluidos = archivos_incluidos
                            entrega_existente.pdf_contenido_b64 = pdf_contenido_b64_alumno
                            entrega_existente.hash_sha256 = hash_sha256
                            entrega_existente.estado = EstadoEntregaEnum.SUBIDA
                            entrega_existente.subido_por_id = subido_por_id
                            entrega_existente.archivo_ruta = f"/uploads/entregas/{hash_sha256[:8]}_{archivo_nombre}"

                            updated_entrega = await self.entrega_repo.update(entrega_existente)
                            sobrescrito = True
                            entrega_id = updated_entrega.id

                        else:
                            # Create new entrega
                            archivo_ruta = f"/uploads/entregas/{hash_sha256[:8]}_{archivo_nombre}"

                            entrega = Entrega(
                                comision_id=comision_id,
                                rubrica_id=rubrica_id,
                                alumno_nombre=alumno_nombre,
                                archivo_nombre=archivo_nombre,
                                archivo_ruta=archivo_ruta,
                                archivo_tamanio=archivo_tamanio,
                                archivo_tipo=archivo_tipo,
                                contenido_preview=contenido_preview,
                                contenido_consolidado=contenido_consolidado,
                                archivos_incluidos=archivos_incluidos,
                                pdf_contenido_b64=pdf_contenido_b64_alumno,
                                estado=EstadoEntregaEnum.SUBIDA,
                                hash_sha256=hash_sha256,
                                subido_por_id=subido_por_id,
                            )

                            created_entrega = await self.entrega_repo.create(entrega)
                            entrega_id = created_entrega.id

                        exitosas.append(
                            EntregaCreada(
                                alumno_nombre=alumno_nombre,
                                archivo_nombre=archivo_nombre,
                                entrega_id=entrega_id,
                                sobrescrito=sobrescrito,
                            )
                        )

                    except Exception as e:
                        # Roll back the session so the next student can still be processed.
                        # Without this, a DB-level error (e.g. null bytes in content)
                        # leaves the SQLAlchemy session in an invalid state and every
                        # subsequent student fails with "This Session's transaction has
                        # been rolled back due to a previous exception during flush".
                        try:
                            await self.db.rollback()
                        except Exception:
                            pass
                        errores.append(
                            EntregaError(
                                alumno_nombre=alumno_nombre,
                                archivo_nombre=alumno_folder,
                                error=str(e),
                            )
                        )

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es un ZIP válido",
            )

        return CargaMasivaResponse(
            total_procesadas=len(exitosas) + len(errores),
            total_exitosas=len(exitosas),
            total_errores=len(errores),
            exitosas=exitosas,
            errores=errores,
        )

    async def _consolidar_archivo(
        self,
        contenido_bytes: bytes,
        archivo_tipo: str,
        modo: str = "solo_codigo",
        filename: str = "archivo",
        extensiones_personalizadas: list[str] | None = None,
    ) -> tuple[str, list[str]]:
        """
        Consolidate file content.

        Args:
            contenido_bytes: File content as bytes.
            archivo_tipo: File type ('zip', 'txt', or 'individual').
            modo: Consolidation mode.
            filename: Original filename (for individual files).
            extensiones_personalizadas: Custom extensions list when modo is 'personalizado'.

        Returns:
            Tuple of (consolidated_content, list_of_files).
        """
        import io

        file_obj = io.BytesIO(contenido_bytes)

        if archivo_tipo == "zip":
            return self.consolidacion_service.consolidar_zip(
                file_obj, modo=modo, extensiones_custom=extensiones_personalizadas
            )
        elif archivo_tipo == "txt":
            return self.consolidacion_service.consolidar_txt(file_obj)
        else:  # individual code file
            return self.consolidacion_service.consolidar_archivo_individual(
                file_obj, filename, modo=modo, extensiones_custom=extensiones_personalizadas
            )



    def _get_file_type(self, filename: str) -> str:
        """
        Get file type from filename.

        Args:
            filename: Name of the file.

        Returns:
            'zip', 'txt', 'pdf', 'individual' (for code files),
            'binary' (for unsupported binaries), or 'unknown'.
        """
        if not filename:
            return "unknown"

        extension = "." + filename.rsplit(".", 1)[-1].lower()

        if extension == ".zip":
            return "zip"
        elif extension == ".txt":
            return "txt"
        elif extension == ".pdf":
            # PDFs have their own correction workflow (N8N /webhook/corregir-pdf)
            return "pdf"
        # Check if it's a binary file that cannot be consolidated
        elif extension in self.consolidacion_service.BINARY_EXTENSIONS:
            return "binary"
        # Any other extension is treated as 'individual' code file
        else:
            return "individual"
