"""Contratos de persistencia, corrección y reentrega con política de archivos."""

import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.correccion import CorreccionUpdate
from app.services.correccion_service import CorreccionService
from app.services.entrega_service import EntregaService
from tests.unit.services.test_correccion_service_persistencia_subcriterios import (
    _fake_entrega, _fake_rubrica, _gemini_result_v1, _service_con,
)
from tests.unit.services.test_politica_entrega import zip_bytes


DIRTY = {"version": 1, "rutas_penalizables": ["tp/node_modules/"], "limite_nota": 50}


@pytest.mark.asyncio
@pytest.mark.parametrize("score,expected", [(90, 50), (35, 35)])
async def test_resultado_ia_se_limita_despues_de_evaluar(monkeypatch, score, expected):
    from app.schemas.correccion import GeminiResponse
    entrega = _fake_entrega(analisis_archivos=DIRTY)
    result = _gemini_result_v1()["correccion"]
    result["criterios"][0]["puntaje_obtenido"] = score
    result["nota"] = score
    service, captured = _service_con(entrega, _fake_rubrica(1), {})
    service._build_correccion_response = AsyncMock(side_effect=lambda c: c)
    saved = await service._persistir_resultado_correccion(
        entrega=entrega, rubrica=_fake_rubrica(1), corregido_por_id=1,
        gemini_response=GeminiResponse(**result), raw_response={}, ia_proveedor="gemini", metricas_extra={})
    assert saved.nota == expected
    assert saved.criterios_json["politica_entrega"]["nota_academica"] == score
    assert saved.criterios_json["criterios"][0]["puntaje_obtenido"] == score
    assert "node_modules" in saved.comentario_general


@pytest.mark.asyncio
@pytest.mark.parametrize("update,expected", [({"comentario_general": "Otro comentario"}, 90), ({"nota": 75}, 75)])
async def test_edicion_reaplica_tope_sin_perder_nota_academica(update, expected):
    correction = SimpleNamespace(id=1, entrega_id=1, nota=Decimal(50),
        criterios_json={"criterios": [], "politica_entrega": {"nota_academica": 90, "limite_nota": 50}},
        comentario_general="Bien", penalizaciones_aplicadas=[])
    service = CorreccionService(MagicMock())
    service.correccion_repo.get_by_id = AsyncMock(return_value=correction)
    service.correccion_repo.update = AsyncMock(side_effect=lambda c: c)
    service.entrega_repo.get_by_id = AsyncMock(return_value=SimpleNamespace(analisis_archivos=DIRTY))
    service._build_correccion_response = AsyncMock(side_effect=lambda c: c)
    saved = await service.editar_correccion(1, CorreccionUpdate(**update), 2)
    assert saved.nota == 50
    assert saved.criterios_json["politica_entrega"]["nota_academica"] == expected
    assert saved.comentario_general.count("[Presentación de la entrega]") == 1


@pytest.mark.asyncio
async def test_exceso_no_llama_proveedor_ni_persiste_nota(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_CODIGO_CORRECCION_CHARS", 100)
    entrega = _fake_entrega(contenido_consolidado="x" * 101)
    service, captured = _service_con(entrega, _fake_rubrica(1), _gemini_result_v1())
    service._call_ia_with_retry = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await service.corregir_individual(1, "irrelevant", 1)
    assert exc.value.status_code == 413
    assert entrega.error_code == "CONTENIDO_EXCESIVO"
    service._call_ia_with_retry.assert_not_awaited()
    service.correccion_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_importacion_persiste_analisis_sin_enviar_dependencias():
    service = EntregaService(MagicMock())
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(metadata_json={}))
    service.comision_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(universidad_id=1))
    async def create(entrega):
        entrega.id = 1
        return entrega
    service.entrega_repo.create = AsyncMock(side_effect=create)
    archive = zip_bytes({"tp/node_modules/lib.js": "DEPENDENCY", "tp/src/main.js": "SOURCE"})
    result = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=1, alumno_nombre="Alumno", archivo_nombre="tp.zip",
        contenido_bytes=archive, subido_por_id=1, modo_consolidacion="solo_codigo")
    assert result.status == "creada"
    saved = service.entrega_repo.create.call_args.args[0]
    assert saved.analisis_archivos["limite_nota"] == 50
    assert "DEPENDENCY" not in saved.contenido_consolidado


@pytest.mark.asyncio
async def test_reentrega_limpia_archiva_version_y_quita_correccion():
    from app.models.entrega import Entrega
    from app.models.correccion import Correccion
    from app.models.enums import EstadoEntregaEnum
    old = Entrega(id=1, analisis_archivos={**DIRTY, "moodle_timemodified": 100},
                  contenido_consolidado="old", hash_sha256="old", estado=EstadoEntregaEnum.CORREGIDA)
    old.correccion = Correccion(nota=Decimal(50), criterios_json={"criterios": []})
    service = EntregaService(MagicMock())
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=old)
    service.entrega_repo.update = AsyncMock(side_effect=lambda e: e)
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(metadata_json={}))
    service.historial_service.guardar_version_anterior = AsyncMock()
    archive = zip_bytes({"tp/src/main.js": "SOURCE"})
    result = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=1, alumno_nombre="Alumno", archivo_nombre="tp.zip",
        contenido_bytes=archive, subido_por_id=1, modo_consolidacion="solo_codigo", moodle_timemodified=200)
    assert result.status == "creada"
    service.historial_service.guardar_version_anterior.assert_awaited_once()
    assert old.correccion is None
    assert old.estado == EstadoEntregaEnum.SUBIDA
    assert old.analisis_archivos["limite_nota"] is None
    assert old.analisis_archivos["moodle_timemodified"] == 200


@pytest.mark.asyncio
async def test_reimportacion_misma_version_no_pisa():
    from app.models.entrega import Entrega
    old = Entrega(id=1, analisis_archivos={"version": 1, "moodle_timemodified": 200})
    service = EntregaService(MagicMock())
    service.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=old)
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(metadata_json={}))
    service.historial_service.guardar_version_anterior = AsyncMock()
    result = await service.crear_o_actualizar_desde_bytes(
        comision_id=1, rubrica_id=1, alumno_nombre="Alumno", archivo_nombre="tp.zip",
        contenido_bytes=b"same", subido_por_id=1, modo_consolidacion="solo_codigo", moodle_timemodified=200)
    assert result.status == "duplicada"
    service.historial_service.guardar_version_anterior.assert_not_awaited()


@pytest.mark.asyncio
async def test_historial_preserva_devolucion_y_restriccion_completas():
    from app.services.historial_service import HistorialService
    correction = SimpleNamespace(nota=Decimal(50), criterios_json={"politica_entrega": {"nota_academica": 90}},
        comentario_general="Devolución con restricción", fortalezas=["Bien"], recomendaciones=["Quitar dependencias"],
        nota_antes_penalizaciones=None, condicion_desaprobacion_aplicada=None,
        penalizaciones_aplicadas=[], editado_manualmente=False, corregido_por_id=1,
        raw_response={"original": "response"}, moodle_syncs=[SimpleNamespace(id=9, estado="ENVIADO", nota_enviada="50", comentario_enviado="Cap", enviado_por_id=2)])
    entrega = SimpleNamespace(id=1, alumno_nombre="Alumno", archivo_nombre="tp.zip", archivo_tamanio=1,
        contenido_preview="source", contenido_consolidado="source", pdf_contenido_b64=None,
        hash_sha256="old", analisis_archivos=DIRTY, correccion=correction)
    service = HistorialService(MagicMock())
    service.historial_repo.create = AsyncMock(side_effect=lambda h: h)
    history = await service.guardar_version_anterior(entrega, 1)
    assert history.correccion_json["raw_response"] == {"original": "response"}
    assert history.correccion_json["moodle_syncs"][0]["nota_enviada"] == "50"
    assert history.analisis_archivos == DIRTY
    assert history.correccion_json["comentario_general"] == "Devolución con restricción"
    assert history.correccion_json["recomendaciones"] == ["Quitar dependencias"]


@pytest.mark.asyncio
async def test_reconsolidacion_invalida_correccion_tras_guardar_historial(monkeypatch):
    from fastapi import UploadFile
    from app.models.entrega import Entrega
    from app.models.correccion import Correccion
    from app.models.enums import EstadoEntregaEnum
    from app.schemas.entrega import EntregaResponse
    old = Entrega(id=1, rubrica_id=1, archivo_nombre="tp.zip", contenido_consolidado="old", analisis_archivos=DIRTY)
    old.correccion = Correccion(nota=Decimal(50), criterios_json={"criterios": []})
    service = EntregaService(MagicMock())
    service.entrega_repo.get_by_id_with_relations = AsyncMock(return_value=old)
    service.entrega_repo.update = AsyncMock(side_effect=lambda e: e)
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=SimpleNamespace(metadata_json={}, modo_consolidacion="solo_codigo"))
    service.historial_service.guardar_version_anterior = AsyncMock()
    monkeypatch.setattr(EntregaResponse, "model_validate", lambda e: e)
    await service.reconsolidar_entrega(entrega_id=1,
        archivo=UploadFile(io.BytesIO(zip_bytes({"src/main.js": "clean"})), filename="tp.zip"), actor_id=1)
    assert old.correccion is None
    assert old.estado == EstadoEntregaEnum.SUBIDA
    assert old.analisis_archivos["limite_nota"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("size,blocked", [(101, True), (100, False)])
async def test_correccion_externa_respeta_integridad_de_contenido(monkeypatch, size, blocked):
    from app.core.config import settings
    from app.schemas.correccion import CorreccionExternaCreate
    monkeypatch.setattr(settings, "MAX_CODIGO_CORRECCION_CHARS", 100)
    entrega = _fake_entrega(contenido_consolidado="x" * size, analisis_archivos=DIRTY)
    service, captured = _service_con(entrega, _fake_rubrica(1), {})
    service._build_correccion_response = AsyncMock(side_effect=lambda c: c)
    data = CorreccionExternaCreate(**_gemini_result_v1()["correccion"], ia_proveedor="externo")
    if blocked:
        with pytest.raises(HTTPException) as error:
            await service.cargar_correccion_externa(1, data, 1)
        assert error.value.status_code == 413
        service.correccion_repo.create.assert_not_awaited()
    else:
        saved = await service.cargar_correccion_externa(1, data, 1)
        assert saved.nota == 50
        assert saved.criterios_json["politica_entrega"]["nota_academica"] == 90
