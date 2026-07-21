"""
CRUD-005: al sobrescribir una entrega, el historial preserva el contenido REAL.

Antes, guardar_version_anterior copiaba solo contenido_preview (500 chars): el
contenido_consolidado (único lugar donde vive el código del alumno) se perdía al
pisarse en el update siguiente. Ahora el snapshot copia contenido_consolidado y
pdf_contenido_b64 a EntregaHistorial.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.historial_service import HistorialService


@pytest.mark.asyncio
async def test_guardar_version_preserva_contenido_consolidado_y_pdf():
    svc = HistorialService.__new__(HistorialService)
    creado = {}

    async def _create(h):
        creado["h"] = h
        h.id = 1
        return h

    svc.historial_repo = SimpleNamespace(create=AsyncMock(side_effect=_create))

    entrega = SimpleNamespace(
        id=10, alumno_nombre="Juan", archivo_nombre="tp.zip", archivo_ruta="/x",
        archivo_tamanio=100, contenido_preview="print(1)"[:500],
        contenido_consolidado="print('todo el codigo del alumno')",
        pdf_contenido_b64="JVBERi0x", hash_sha256="abc", correccion=None,
    )
    await svc.guardar_version_anterior(entrega, sobrescrito_por_id=5)

    h = creado["h"]
    assert h.contenido_consolidado == "print('todo el codigo del alumno')"
    assert h.pdf_contenido_b64 == "JVBERi0x"
    # el preview se sigue guardando
    assert h.contenido_preview == "print(1)"
