"""Tests para EntregaService.crear_o_actualizar_desde_bytes (Fase 2 — importación Moodle).

Este método crea entregas a partir de bytes (lo que se descarga de Moodle), reusando
la consolidación/PDF e idempotencia, pero SIN lanzar HTTPException: devuelve un
resultado clasificado para que el importador arme el resumen.

Se mockean los repos/servicios (test unitario, sin DB) siguiendo el patrón de
test_moodle_service.py.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.enums import EstadoEntregaEnum
from app.services.entrega_service import EntregaService


@pytest.fixture
def service():
    svc = EntregaService(AsyncMock())
    svc.entrega_repo = AsyncMock()
    svc.consolidacion_service = MagicMock()
    svc.consolidacion_service.consolidar_zip = MagicMock(return_value=("codigo consolidado", ["main.py"]))
    svc.consolidacion_service.consolidar_archivo_individual = MagicMock(return_value=("codigo", ["main.py"]))
    svc.consolidacion_service.consolidar_txt = MagicMock(return_value=("texto", ["a.txt"]))
    svc.consolidacion_service.generar_preview = MagicMock(return_value="preview")
    # _get_file_type consulta este set para detectar binarios
    svc.consolidacion_service.BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".exe", ".class", ".jar"}
    return svc


def _capture_id_on_create(svc):
    """Hace que entrega_repo.create asigne id=1 y devuelva el objeto creado."""
    async def _create(entrega):
        entrega.id = 1
        return entrega
    svc.entrega_repo.create = AsyncMock(side_effect=_create)


@pytest.mark.asyncio
async def test_crear_desde_bytes_nueva_zip(service):
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    _capture_id_on_create(service)

    res = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=2, alumno_nombre="Juan Perez",
        archivo_nombre="tp.zip", contenido_bytes=b"PK\x03\x04",
        subido_por_id=5, moodle_user_id=101,
    )

    assert res.status == "creada"
    assert res.entrega_id == 1
    creada = service.entrega_repo.create.call_args[0][0]
    assert creada.moodle_user_id == 101
    assert creada.estado == EstadoEntregaEnum.SUBIDA
    assert creada.alumno_nombre == "Juan Perez"
    assert creada.archivo_tipo == "zip"


@pytest.mark.asyncio
async def test_crear_desde_bytes_duplicada_sin_correccion(service):
    existente = MagicMock()
    existente.id = 9
    existente.correccion = None
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=existente)
    service.entrega_repo.create = AsyncMock()

    res = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=2, alumno_nombre="Juan Perez",
        archivo_nombre="tp.zip", contenido_bytes=b"PK\x03\x04",
        subido_por_id=5, moodle_user_id=101,
    )

    assert res.status == "duplicada"
    assert res.entrega_id == 9
    service.entrega_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_crear_desde_bytes_ya_corregida_no_pisa(service):
    existente = MagicMock()
    existente.id = 9
    existente.correccion = MagicMock()  # truthy → tiene corrección
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=existente)
    service.entrega_repo.create = AsyncMock()

    res = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=2, alumno_nombre="Juan Perez",
        archivo_nombre="tp.zip", contenido_bytes=b"PK\x03\x04",
        subido_por_id=5, moodle_user_id=101,
    )

    assert res.status == "ya_corregida"
    assert res.entrega_id == 9
    service.entrega_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_crear_desde_bytes_pdf(service):
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    _capture_id_on_create(service)

    res = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=2, alumno_nombre="Ana Gomez",
        archivo_nombre="entrega.pdf", contenido_bytes=b"%PDF-1.4 mock",
        subido_por_id=5, moodle_user_id=202,
    )

    assert res.status == "creada"
    creada = service.entrega_repo.create.call_args[0][0]
    assert creada.archivo_tipo == "pdf"
    assert creada.pdf_contenido_b64 is not None
    assert creada.contenido_consolidado is None
    # No se debe consolidar un PDF
    service.consolidacion_service.consolidar_zip.assert_not_called()


@pytest.mark.asyncio
async def test_crear_desde_bytes_error_consolidacion_no_lanza(service):
    """Un ZIP sin archivos válidos devuelve status 'error', NO lanza (no aborta el lote)."""
    from fastapi import HTTPException

    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    service.entrega_repo.create = AsyncMock()
    service.consolidacion_service.consolidar_zip = MagicMock(
        side_effect=HTTPException(
            status_code=400,
            detail="No se encontraron archivos válidos en el ZIP con las extensiones especificadas",
        )
    )

    res = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=2, alumno_nombre="Juan Perez",
        archivo_nombre="tp.zip", contenido_bytes=b"PK\x03\x04",
        subido_por_id=5, moodle_user_id=101,
    )

    assert res.status == "error"
    assert "archivos válidos" in (res.detalle or "")
    service.entrega_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_crear_desde_bytes_binario_rechazado(service):
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    service.entrega_repo.create = AsyncMock()

    res = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=2, alumno_nombre="Ana Gomez",
        archivo_nombre="foto.png", contenido_bytes=b"\x89PNG",
        subido_por_id=5, moodle_user_id=202,
    )

    assert res.status == "error"
    assert res.detalle is not None
    service.entrega_repo.create.assert_not_called()
