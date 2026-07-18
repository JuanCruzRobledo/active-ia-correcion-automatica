"""Tests de los fixes de auditoría sobre EntregaService.

Cubre:
  - BUG-011: la carga masiva con varios archivos sueltos arma el ZIP del alumno
    EN MEMORIA (io.BytesIO), sin crear un archivo temporal en disco.
  - BUG-013: al SOBRESCRIBIR una entrega se limpian los campos de error de la
    corrida anterior (error_code/error_mensaje/error_at).
  - ERR-013: los caminos de carga masiva/importación NO devuelven el str(e) crudo
    al cliente ante un error inesperado; devuelven un mensaje genérico y loguean.

Patrón de mocking (sin DB) tomado de test_entrega_import.py.
"""

import io
import logging
import tempfile
import zipfile

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.enums import EstadoEntregaEnum
from app.schemas.entrega import EntregaCreate
from app.services.entrega_service import EntregaService


@pytest.fixture
def service():
    svc = EntregaService(AsyncMock())
    svc.entrega_repo = AsyncMock()
    svc.comision_repo = AsyncMock()
    svc.rubrica_repo = AsyncMock()
    svc.historial_service = AsyncMock()
    svc.consolidacion_service = MagicMock()
    svc.consolidacion_service.consolidar_zip = MagicMock(return_value=("codigo", ["main.py"]))
    svc.consolidacion_service.consolidar_archivo_individual = MagicMock(return_value=("codigo", ["a.py"]))
    svc.consolidacion_service.consolidar_txt = MagicMock(return_value=("texto", ["a.txt"]))
    svc.consolidacion_service.generar_preview = MagicMock(return_value="preview")
    svc.consolidacion_service.BINARY_EXTENSIONS = {".png", ".jpg", ".exe", ".class", ".jar"}
    # get_active_by_id (comision/rubrica) → objeto truthy por defecto
    svc.comision_repo.get_active_by_id = AsyncMock(return_value=MagicMock())
    svc.rubrica_repo.get_active_by_id = AsyncMock(return_value=MagicMock())
    return svc


def _outer_zip(files: dict[str, bytes]) -> bytes:
    """Arma un ZIP contenedor (el que sube el tutor) con las rutas dadas."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, data in files.items():
            zf.writestr(path, data)
    return buf.getvalue()


def _upload(zip_bytes: bytes):
    archivo = MagicMock()
    archivo.filename = "entregas.zip"
    archivo.size = len(zip_bytes)
    archivo.read = AsyncMock(return_value=zip_bytes)
    return archivo


def _capture_create(svc):
    async def _create(entrega):
        entrega.id = 1
        return entrega
    svc.entrega_repo.create = AsyncMock(side_effect=_create)


# ---------------------------------------------------------------------------
# BUG-011: sin archivo temporal en disco
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_masiva_archivos_sueltos_no_usa_archivo_temporal(service, monkeypatch):
    """Con varios archivos sueltos, el ZIP del alumno se arma en memoria: NO se
    debe invocar tempfile.NamedTemporaryFile (que antes dejaba el .zip huérfano)."""
    def _boom(*args, **kwargs):
        raise AssertionError("No debe crearse un archivo temporal en disco (BUG-011)")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", _boom)

    zip_bytes = _outer_zip({"Juan Perez/a.py": b"print(1)\n", "Juan Perez/b.py": b"print(2)\n"})
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    _capture_create(service)

    res = await service.crear_entrega_masiva(
        comision_id=1, rubrica_id=2, archivo_zip=_upload(zip_bytes), subido_por_id=5,
    )

    assert res.total_exitosas == 1
    assert res.total_errores == 0
    creada = service.entrega_repo.create.call_args[0][0]
    assert creada.archivo_tipo == "zip"
    assert creada.archivo_nombre.endswith("_consolidado.zip")


# ---------------------------------------------------------------------------
# BUG-013: sobrescribir limpia los campos de error
# ---------------------------------------------------------------------------
def _entrega_existente_con_error():
    existente = MagicMock()
    existente.id = 9
    existente.correccion = None
    existente.error_code = "N8N_ERROR"
    existente.error_mensaje = "algo viejo"
    existente.error_at = "2026-06-01"
    return existente


@pytest.mark.asyncio
async def test_masiva_sobrescribir_limpia_error(service):
    existente = _entrega_existente_con_error()
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=existente)
    service.entrega_repo.update = AsyncMock(side_effect=lambda e: e)

    zip_bytes = _outer_zip({"Juan Perez/a.py": b"print(1)\n"})

    res = await service.crear_entrega_masiva(
        comision_id=1, rubrica_id=2, archivo_zip=_upload(zip_bytes),
        subido_por_id=5, sobrescribir=True,
    )

    assert res.total_exitosas == 1
    assert existente.estado == EstadoEntregaEnum.SUBIDA
    assert existente.error_code is None
    assert existente.error_mensaje is None
    assert existente.error_at is None


@pytest.mark.asyncio
async def test_individual_sobrescribir_limpia_error(service):
    from datetime import datetime
    from types import SimpleNamespace

    existente = _entrega_existente_con_error()
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=existente)

    # `crear_entrega_individual` devuelve EntregaResponse.model_validate(update(...)):
    # el update recibe `existente` (ya limpiado por _limpiar_entrega_error) y devolvemos
    # un objeto válido para la validación Pydantic. Asertamos sobre `existente`.
    def _update(e):
        return SimpleNamespace(
            id=9, comision_id=1, rubrica_id=2, alumno_nombre="Juan Perez",
            archivo_nombre="tp.py", archivo_ruta="/x", archivo_tamanio=10,
            archivo_tipo="individual", contenido_preview="preview",
            estado=EstadoEntregaEnum.SUBIDA, archivado=False, hash_sha256="abc",
            subido_por_id=5, error_code=e.error_code, error_mensaje=e.error_mensaje,
            error_at=e.error_at, created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
        )
    service.entrega_repo.update = AsyncMock(side_effect=_update)

    archivo = MagicMock()
    archivo.filename = "tp.py"
    archivo.size = 10
    archivo.read = AsyncMock(return_value=b"print('hola')\n")

    data = EntregaCreate(alumno_nombre="Juan Perez", comision_id=1, rubrica_id=2)

    await service.crear_entrega_individual(
        data=data, archivo=archivo, subido_por_id=5, sobrescribir=True,
    )

    assert existente.estado == EstadoEntregaEnum.SUBIDA
    assert existente.error_code is None
    assert existente.error_mensaje is None
    assert existente.error_at is None


# ---------------------------------------------------------------------------
# ERR-013: no se filtra str(e) crudo; se loguea y se devuelve un mensaje genérico
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_desde_bytes_error_inesperado_no_filtra_str_e(service, caplog):
    """Un error inesperado en la consolidación no debe viajar crudo al cliente."""
    secreto = "psycopg2_NULL_BYTE_INTERNAL_LEAK"
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    service.consolidacion_service.consolidar_zip = MagicMock(
        side_effect=RuntimeError(secreto)
    )

    with caplog.at_level(logging.ERROR):
        res = await service.crear_o_actualizar_desde_bytes(
            comision_id=1, rubrica_id=2, alumno_nombre="Juan Perez",
            archivo_nombre="tp.zip", contenido_bytes=b"PK\x03\x04",
            subido_por_id=5,
        )

    assert res.status == "error"
    assert secreto not in (res.detalle or "")
    assert "No se pudo procesar" in (res.detalle or "")
    # El detalle real (str(e)) sí debe quedar en el log del servidor.
    assert secreto in caplog.text


@pytest.mark.asyncio
async def test_masiva_error_por_alumno_no_filtra_str_e(service, caplog):
    """Si un alumno rompe por un error de DB, el resumen NO expone el str(e) crudo."""
    secreto = "psycopg2_NULL_BYTE_INTERNAL_LEAK"
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    service.entrega_repo.create = AsyncMock(side_effect=RuntimeError(secreto))

    zip_bytes = _outer_zip({"Juan Perez/a.py": b"print(1)\n"})

    with caplog.at_level(logging.ERROR):
        res = await service.crear_entrega_masiva(
            comision_id=1, rubrica_id=2, archivo_zip=_upload(zip_bytes), subido_por_id=5,
        )

    assert res.total_errores == 1
    assert secreto not in res.errores[0].error
    assert "No se pudo procesar" in res.errores[0].error
    assert secreto in caplog.text
