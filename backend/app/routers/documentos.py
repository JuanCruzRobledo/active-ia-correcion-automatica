# app/routers/documentos.py
"""
Documentos router for Active-IA.

REST API endpoints for document generation (PDFs and Excel exports).
Endpoints require authentication and tutor/admin authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 10
"""

import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import (
    filtrar_entregas_accesibles,
    verificar_acceso_comision_o_materia,
    verificar_acceso_correccion,
)
from app.models.usuario import Usuario
from app.schemas.entrega import EntregaDescargarPDFsRequest
from app.services.excel_service import ExcelService
from app.services.pdf_service import PDFService

router = APIRouter(
    prefix="/documentos",
    tags=["documentos"],
)


def _ascii_filename(filename: str) -> str:
    """
    Convert a filename to latin-1-safe string for use in HTTP headers.

    1. NFKD normalization decomposes accented chars (e.g. á -> a + combining)
    2. Strip combining characters (the accent marks)
    3. Encode to latin-1 ignoring anything that still can't be represented
       (e.g. en-dash –, em-dash —, smart quotes, etc.)
    """
    normalized = unicodedata.normalize("NFKD", filename)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return stripped.encode("latin-1", errors="ignore").decode("latin-1")


@router.get(
    "/correcciones/{correccion_id}/pdf",
    response_class=StreamingResponse,
)
async def descargar_pdf_correccion(
    correccion_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Download PDF feedback document for a correction.

    **Authorization:** Any authenticated user

    **Ref:** docs/specs/03-REQUISITOS-FUNCIONALES.md HU-DOC-01
    """
    # SEC-004: el guard va ANTES de generar el PDF de devolución del alumno.
    await verificar_acceso_correccion(db, current_user, correccion_id)

    # Generate PDF
    pdf_service = PDFService(db)
    pdf_bytes = await pdf_service.generar_pdf_devolucion(correccion_id)

    # Get correction info for filename
    from app.repositories.correccion_repository import CorreccionRepository

    correccion_repo = CorreccionRepository(db)
    correccion = await correccion_repo.get_by_id_with_relations(correccion_id)

    if correccion:
        alumno_nombre = correccion.entrega.alumno_nombre
        alumno_safe = re.sub(r'[<>:"/\\|?*]', "", alumno_nombre)
        alumno_safe = re.sub(r"\s+", " ", alumno_safe).strip()
        filename = _ascii_filename(f"{alumno_safe} - Devolucion.pdf")
    else:
        filename = f"devolucion_{correccion_id}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/comisiones/{comision_id}/rubricas/{rubrica_id}/pdfs",
    response_class=StreamingResponse,
)
async def descargar_pdfs_lote(
    comision_id: int,
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Download ZIP file with PDFs for all corrected entregas.

    **Authorization:** Any authenticated user

    **Ref:** docs/specs/03-REQUISITOS-FUNCIONALES.md HU-DOC-02
    """
    # SEC-004: el ZIP contiene las devoluciones de toda la comisión.
    await verificar_acceso_comision_o_materia(db, current_user, comision_id)

    pdf_service = PDFService(db)
    zip_bytes, zip_filename = await pdf_service.generar_zip_pdfs(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
    )

    # Sanitize filename for HTTP header (latin-1 safe)
    zip_filename = _ascii_filename(zip_filename)

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )


@router.post(
    "/pdfs-seleccionados",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
)
async def descargar_pdfs_seleccionados(
    data: EntregaDescargarPDFsRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Download ZIP with PDFs for a user-selected subset of corrected entregas.

    Only CORREGIDA entregas are included; others are silently skipped.

    **Authorization:** Admin, o tutor/coordinador de las entregas. El ZIP incluye
    solo las accesibles; las omitidas se listan en el header `X-Entregas-Omitidas`.
    """
    # SEC-004: partición. El ZIP se arma solo con las accesibles; los omitidos
    # viajan en un header (la respuesta es binaria, no hay JSON donde ponerlos).
    permitidos, denegados = await filtrar_entregas_accesibles(
        db, current_user, data.entrega_ids
    )
    if not permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a ninguna de las entregas solicitadas",
        )

    pdf_service = PDFService(db)
    zip_bytes, zip_filename = await pdf_service.generar_zip_pdfs_seleccionados(
        entrega_ids=sorted(permitidos),
    )

    zip_filename = _ascii_filename(zip_filename)

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "X-Entregas-Omitidas": ",".join(str(i) for i in sorted(denegados)),
        },
    )


@router.get(
    "/comisiones/{comision_id}/rubricas/{rubrica_id}/excel",
    response_class=StreamingResponse,
)
async def exportar_notas_excel(
    comision_id: int,
    rubrica_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export grades to Excel format.

    **Authorization:** Any authenticated user

    **Ref:** docs/specs/03-REQUISITOS-FUNCIONALES.md HU-DOC-03
    """
    # SEC-004: el Excel es el acta OFICIAL de notas completa de la comisión.
    await verificar_acceso_comision_o_materia(db, current_user, comision_id)

    excel_service = ExcelService(db)
    excel_bytes, excel_filename = await excel_service.exportar_notas_excel(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
    )

    # Sanitize filename for HTTP header (latin-1 safe)
    excel_filename = _ascii_filename(excel_filename)

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{excel_filename}"',
        },
    )
