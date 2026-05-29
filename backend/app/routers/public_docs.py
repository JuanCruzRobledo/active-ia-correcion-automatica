# app/routers/public_docs.py
"""Router PÚBLICO (sin JWT) para que el alumno abra su PDF de devolución desde Moodle.

El acceso se controla por un token firmado (DevolucionLinkService), no por sesión.
Cada token apunta a UNA corrección → no expone datos de otros alumnos.
"""

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.services.devolucion_link_service import (
    DevolucionLinkService,
    TokenDevolucionInvalido,
)
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/devoluciones/{token}", response_class=StreamingResponse)
async def descargar_devolucion_publica(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Sirve el PDF de devolución correspondiente al token firmado. SIN autenticación."""
    try:
        correccion_id = DevolucionLinkService.validar_token(token)
    except TokenDevolucionInvalido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link inválido o expirado",
        )

    pdf_service = PDFService(db)
    try:
        pdf_bytes = await pdf_service.generar_pdf_devolucion(correccion_id)
    except HTTPException:
        # La corrección pudo haber sido eliminada
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La devolución ya no está disponible",
        )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=devolucion.pdf"},
    )
