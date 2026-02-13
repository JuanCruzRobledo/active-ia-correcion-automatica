# app/routers/documentos.py
"""
Documentos router for Active-IA.

REST API endpoints for document generation (PDFs and Excel exports).
Endpoints require authentication and tutor/admin authorization.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 10
"""

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_tutor
from app.models.usuario import Usuario
from app.services.excel_service import ExcelService
from app.services.pdf_service import PDFService

router = APIRouter(
    prefix="/documentos",
    tags=["documentos"],
)


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

    **Process:**
    1. Validates correction exists
    2. Generates professional PDF with:
       - Student and assignment info
       - Grade with color coding
       - Detailed criteria evaluation
       - Strengths and recommendations
       - Evaluator comments

    **Returns:**
    - PDF file as download
    - Filename: `{alumno}_devolucion_{fecha}.pdf`

    **Authorization:** Tutor or Admin

    **Ref:** docs/specs/03-REQUISITOS-FUNCIONALES.md HU-DOC-01
    """
    require_tutor(current_user)

    # Generate PDF
    pdf_service = PDFService(db)
    pdf_bytes = await pdf_service.generar_pdf_devolucion(correccion_id)

    # Get correction info for filename
    from app.repositories.correccion_repository import CorreccionRepository

    correccion_repo = CorreccionRepository(db)
    correccion = await correccion_repo.get_by_id_with_relations(correccion_id)

    if correccion:
        alumno_nombre = correccion.entrega.alumno_nombre
        # Sanitize filename - only remove truly problematic characters, keep spaces
        import re

        alumno_safe = re.sub(r'[<>:"/\\|?*]', "", alumno_nombre)
        # Normalize multiple spaces to single space
        alumno_safe = re.sub(r"\s+", " ", alumno_safe).strip()
        filename = f"{alumno_safe} - Devolucion.pdf"
    else:
        filename = f"devolucion_{correccion_id}.pdf"

    # Return as streaming response
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

    **Process:**
    1. Gets all corrected entregas for comision and rubrica
    2. Generates PDF for each entrega
    3. Packages all PDFs in a ZIP file

    **Returns:**
    - ZIP file as download
    - Filename: `devoluciones_{materia}_{tp}_{fecha}.zip`
    - Each PDF named: `{alumno}_devolucion.pdf`

    **Validation:**
    - At least one corrected entrega must exist

    **Authorization:** Tutor or Admin

    **Ref:** docs/specs/03-REQUISITOS-FUNCIONALES.md HU-DOC-02
    """
    require_tutor(current_user)

    # Generate ZIP with PDFs
    pdf_service = PDFService(db)
    zip_bytes, zip_filename = await pdf_service.generar_zip_pdfs(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
    )

    # Return as streaming response
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
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

    **Process:**
    1. Gets all entregas for comision and rubrica
    2. Generates Excel file with formatted data
    3. Includes both corrected and pending entregas

    **Excel columns:**
    - Alumno: Student name
    - Nota: Grade (0-100) with color coding
    - Estado: CORREGIDA, PENDIENTE, ERROR
    - Fecha: Correction date
    - Editado: Yes/No (if manually edited)

    **Returns:**
    - Excel file (.xlsx) as download
    - Filename: `notas_{materia}_{tp}_{fecha}.xlsx`

    **Features:**
    - Color-coded grades (green ≥80, yellow ≥60, red <60)
    - Formatted headers with freeze panes
    - Summary statistics

    **Authorization:** Tutor or Admin

    **Ref:** docs/specs/03-REQUISITOS-FUNCIONALES.md HU-DOC-03
    """
    require_tutor(current_user)

    # Generate Excel
    excel_service = ExcelService(db)
    excel_bytes, excel_filename = await excel_service.exportar_notas_excel(
        comision_id=comision_id,
        rubrica_id=rubrica_id,
    )

    # Return as streaming response
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{excel_filename}"',
        },
    )
