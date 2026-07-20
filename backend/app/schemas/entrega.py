# app/schemas/entrega.py
"""
Entrega schemas for Active-IA.

Pydantic schemas for student submission (entrega) management.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
Ref: docs/specs/06-MODELO-DATOS.md seccion 4.2
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EstadoEntregaEnum


# ============================================================================
# Schemas Base de Entrega
# ============================================================================


class EntregaBase(BaseModel):
    """Base schema for Entrega with common fields."""

    alumno_nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre completo del alumno",
        examples=["Juan Pérez", "María García"],
    )


class EntregaCreate(EntregaBase):
    """Schema for creating a new Entrega (individual upload)."""

    comision_id: int = Field(
        ...,
        gt=0,
        description="ID de la comisión a la que pertenece el alumno",
    )
    rubrica_id: int = Field(
        ...,
        gt=0,
        description="ID de la rúbrica para evaluar esta entrega",
    )
    # Nota: El archivo se maneja por separado en el endpoint con UploadFile


class EntregaUpdate(BaseModel):
    """Schema for updating an existing Entrega."""

    alumno_nombre: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Nuevo nombre del alumno",
    )


# ============================================================================
# Schemas de Respuesta
# ============================================================================


class ComisionInfo(BaseModel):
    """Información reducida de una comisión."""

    id: int
    nombre: str
    materia_nombre: str
    materia_codigo: str

    model_config = {"from_attributes": True}


class RubricaInfo(BaseModel):
    """Información reducida de una rúbrica."""

    id: int
    nombre: str
    tipo: str
    numero: int

    model_config = {"from_attributes": True}


class UsuarioInfo(BaseModel):
    """Información reducida de un usuario."""

    id: int
    nombre: str
    email: str

    model_config = {"from_attributes": True}


class EntregaResponse(BaseModel):
    """Schema for Entrega response with all fields."""

    id: int
    comision_id: int
    rubrica_id: int
    alumno_nombre: str
    archivo_nombre: str
    archivo_ruta: str
    archivo_tamanio: int
    archivo_tipo: str  # 'zip' o 'txt'
    contenido_preview: str | None
    estado: EstadoEntregaEnum
    archivado: bool
    hash_sha256: str | None
    subido_por_id: int
    # Detalle del último error de corrección (item #1). NULL si nunca falló o tras éxito.
    error_code: str | None = None
    error_mensaje: str | None = None
    error_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntregaDetailResponse(EntregaResponse):
    """Schema for detailed Entrega response with relations."""

    comision: ComisionInfo = Field(
        description="Información de la comisión",
    )
    rubrica: RubricaInfo = Field(
        description="Información de la rúbrica",
    )
    subido_por: UsuarioInfo = Field(
        description="Usuario que subió la entrega",
    )
    tiene_correccion: bool = Field(
        default=False,
        description="Indica si la entrega tiene una corrección asociada",
    )
    num_versiones_anteriores: int = Field(
        default=0,
        description="Cantidad de versiones anteriores en el historial",
    )


class EntregaListItem(BaseModel):
    """Schema for Entrega list item with denormalized data."""

    id: int
    comision_id: int
    comision_nombre: str
    rubrica_id: int
    rubrica_nombre: str
    rubrica_tipo: str
    alumno_nombre: str
    archivo_nombre: str
    archivo_tamanio: int
    archivo_tipo: str
    estado: EstadoEntregaEnum
    archivado: bool
    nota: float | None = Field(
        default=None,
        description="Nota de la corrección (si existe)",
    )
    tiene_correccion: bool
    # Detalle del último error de corrección (item #1), para mostrar el motivo en la tabla.
    error_code: str | None = None
    error_mensaje: str | None = None
    subido_por_nombre: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EntregaList(BaseModel):
    """Schema for paginated Entrega list."""

    items: list[EntregaListItem]
    total: int = Field(description="Total de entregas")
    page: int = Field(description="Página actual")
    per_page: int = Field(description="Items por página")


# ============================================================================
# Schemas de Carga Masiva
# ============================================================================


class CargaMasivaCreate(BaseModel):
    """Schema for creating multiple Entregas (bulk upload)."""

    comision_id: int = Field(
        ...,
        gt=0,
        description="ID de la comisión",
    )
    rubrica_id: int = Field(
        ...,
        gt=0,
        description="ID de la rúbrica",
    )
    sobrescribir: bool = Field(
        default=False,
        description="Si es True, sobrescribe entregas existentes del mismo alumno",
    )
    # Nota: El archivo ZIP se maneja por separado en el endpoint con UploadFile


class EntregaCreada(BaseModel):
    """Información de una entrega creada en carga masiva."""

    alumno_nombre: str
    archivo_nombre: str
    entrega_id: int
    sobrescrito: bool = Field(
        default=False,
        description="Indica si se sobrescribió una entrega anterior",
    )


class EntregaError(BaseModel):
    """Información de un error al procesar una entrega en carga masiva."""

    alumno_nombre: str
    archivo_nombre: str
    error: str


class CargaMasivaResponse(BaseModel):
    """Schema for bulk upload response."""

    total_procesadas: int = Field(
        description="Total de entregas procesadas (exitosas + errores)",
    )
    total_exitosas: int = Field(
        description="Cantidad de entregas exitosas",
    )
    total_errores: int = Field(
        description="Cantidad de errores",
    )
    exitosas: list[EntregaCreada] = Field(
        description="Entregas creadas exitosamente",
    )
    errores: list[EntregaError] = Field(
        description="Errores al procesar entregas",
    )


# ============================================================================
# Schemas de Contenido
# ============================================================================


class ContenidoEntrega(BaseModel):
    """Schema for consolidated content of an Entrega.

    For code submissions (zip, txt, individual): contenido_consolidado is populated.
    For PDF submissions: pdf_contenido_b64 is populated and contenido_consolidado is None.
    """

    entrega_id: int
    alumno_nombre: str
    es_pdf: bool = Field(
        default=False,
        description="Indica si la entrega es un PDF (sin consolidación de texto)",
    )
    contenido_consolidado: str | None = Field(
        default=None,
        description="Código consolidado de todos los archivos (None para entregas PDF)",
    )
    pdf_contenido_b64: str | None = Field(
        default=None,
        description="Contenido del PDF en Base64 (solo para entregas PDF)",
    )
    archivos_incluidos: list[str] = Field(
        description="Lista de nombres de archivos incluidos en la consolidación",
    )
    total_lineas: int = Field(
        description="Total de líneas de código consolidado (0 para entregas PDF)",
    )
    total_caracteres: int = Field(
        description="Total de caracteres del contenido consolidado (0 para entregas PDF)",
    )


# ============================================================================
# Schemas de Historial
# ============================================================================


class HistorialItem(BaseModel):
    """Schema for a single history entry."""

    id: int
    alumno_nombre: str
    archivo_nombre: str
    archivo_tamanio: int
    contenido_preview: str | None
    hash_sha256: str | None
    nota_anterior: float | None
    sobrescrito_en: datetime
    sobrescrito_por_nombre: str

    model_config = {"from_attributes": True}


class HistorialResponse(BaseModel):
    """Schema for history response."""

    entrega_actual_id: int
    versiones_anteriores: list[HistorialItem]
    total_versiones: int


# ============================================================================
# Schemas de Acciones Masivas
# ============================================================================


class EntregaArchivarRequest(BaseModel):
    """Schema for bulk archive/unarchive request."""

    ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="IDs de las entregas a archivar/desarchivar",
    )
    archivado: bool = Field(
        default=True,
        description="True para archivar, False para desarchivar",
    )


class EntregaDeleteMasivoRequest(BaseModel):
    """Schema for bulk delete request."""

    ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="IDs de las entregas a eliminar",
    )


class EntregaDescargarPDFsRequest(BaseModel):
    """Schema for selective PDF download request."""

    entrega_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="IDs de entregas a descargar (solo se incluyen las CORREGIDA)",
    )


class EntregaAccionMasivaResponse(BaseModel):
    """Schema for bulk action response."""

    procesadas: int = Field(description="Cantidad de entregas procesadas")
    ids: list[int] = Field(description="IDs de las entregas procesadas")
    # SEC-002: el lote se ejecuta SOLO sobre las entregas accesibles. Lo omitido se
    # informa explícitamente: un borrado que borra menos de lo pedido en silencio es
    # indistinguible de un bug. Campos con default → contrato aditivo (backend se
    # despliega antes que el frontend sin romperlo).
    omitidas: int = Field(
        default=0, description="Entregas omitidas por falta de permisos"
    )
    ids_omitidos: list[int] = Field(
        default_factory=list, description="IDs omitidos por falta de permisos"
    )
