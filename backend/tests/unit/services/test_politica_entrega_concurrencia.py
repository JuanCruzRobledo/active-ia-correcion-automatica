"""Una nueva versión no puede mezclarse con la corrección que está en curso."""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum
from app.repositories.entrega_repository import EntregaRepository
from app.services.entrega_service import EntregaService
from tests.unit.repositories.test_ia003_reclamar_atomico import _entrega
from tests.unit.services.test_politica_entrega import zip_bytes


@pytest.mark.asyncio
async def test_reconsolidar_no_reemplaza_una_correccion_en_curso(monkeypatch):
    from app.schemas.entrega import EntregaResponse
    entrega = Entrega(id=1, rubrica_id=1, estado=EstadoEntregaEnum.PENDIENTE)
    service = EntregaService(MagicMock())
    service.entrega_repo.get_by_id_with_relations = AsyncMock(return_value=entrega)
    service.entrega_repo.update = AsyncMock(side_effect=lambda e: e)
    monkeypatch.setattr(EntregaResponse, "model_validate", lambda e: e)
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(metadata_json={}, modo_consolidacion="solo_codigo"))
    service.historial_service.guardar_version_anterior = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await service.reconsolidar_entrega(entrega_id=1,
            archivo=UploadFile(io.BytesIO(zip_bytes({"src/main.py": "clean"})), filename="tp.zip"), actor_id=1)
    assert error.value.status_code == 409
    service.historial_service.guardar_version_anterior.assert_not_awaited()


@pytest.mark.asyncio
async def test_moodle_no_pisa_entrega_mientras_se_corrige():
    entrega = Entrega(id=1, rubrica_id=1, estado=EstadoEntregaEnum.PENDIENTE,
                      analisis_archivos={"version": 1, "moodle_timemodified": 100})
    service = EntregaService(MagicMock())
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=entrega)
    service.entrega_repo.update = AsyncMock()
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(metadata_json={}))
    service.historial_service.guardar_version_anterior = AsyncMock()
    result = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=1, alumno_nombre="Alumno", archivo_nombre="tp.zip",
        contenido_bytes=zip_bytes({"src/main.py": "clean"}), subido_por_id=1,
        modo_consolidacion="solo_codigo", moodle_timemodified=200)
    assert result.status == "error"
    assert "corrección" in result.detalle
    service.historial_service.guardar_version_anterior.assert_not_awaited()
    service.entrega_repo.update.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("expected,claimed", [("old", False), ("new", True)])
async def test_reclamo_no_califica_el_contenido_de_una_version_anterior(db_session, expected, claimed):
    entrega = await _entrega(db_session)
    entrega.hash_sha256 = "new"
    await db_session.commit()
    assert await EntregaRepository(db_session).reclamar_para_correccion(entrega.id, hash_esperado=expected) is claimed


@pytest.mark.asyncio
async def test_reemplazo_bloquea_fila_hasta_confirmacion():
    from sqlalchemy.dialects import postgresql
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock())
    await EntregaRepository(db).get_by_rubrica_alumno(1, "Alumno", bloquear=True)
    statement = db.execute.call_args.args[0]
    assert "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_snapshot_y_reemplazo_comparten_transaccion():
    from app.models.entrega import EntregaHistorial
    from app.repositories.entrega_historial_repository import EntregaHistorialRepository
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    await EntregaHistorialRepository(db).create(EntregaHistorial(), confirmar=False)
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mass", [False, True])
async def test_upload_no_sobrescribe_pendiente(mass):
    from app.schemas.entrega import EntregaCreate
    old = Entrega(id=1, estado=EstadoEntregaEnum.PENDIENTE)
    svc = EntregaService(MagicMock())
    svc.comision_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(universidad_id=1))
    svc.rubrica_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(metadata_json={}, modo_consolidacion="solo_codigo"))
    svc.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=old)
    svc.historial_service.guardar_version_anterior = AsyncMock()
    svc.entrega_repo.update = AsyncMock(side_effect=lambda e: e)
    data = zip_bytes({"Alumno/main.py" if mass else "main.py": "clean"})
    upload = UploadFile(io.BytesIO(data), filename="tp.zip")
    if mass:
        result = await svc.crear_entrega_masiva(1, 1, upload, 1, sobrescribir=True)
        assert result.errores and "corrección" in result.errores[0].error
    else:
        with pytest.raises(HTTPException) as error:
            await svc.crear_entrega_individual(EntregaCreate(comision_id=1, rubrica_id=1, alumno_nombre="Alumno"), upload, 1, sobrescribir=True)
        assert error.value.status_code == 409
    svc.historial_service.guardar_version_anterior.assert_not_awaited()
