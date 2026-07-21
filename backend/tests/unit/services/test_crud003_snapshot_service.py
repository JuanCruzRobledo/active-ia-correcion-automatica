"""
CRUD-003 (Fase 3): snapshot de la corrección saliente en corregir_individual.

- `_snapshot_de_correccion`: función pura que mapea Correccion -> CorreccionHistorial
  preservando editado_manualmente y raw_response, con correccion_creada_en =
  created_at original y reemplazada_por_id = actor.
- corregir_individual sobre una entrega CON corrección existente: versiona antes de
  borrar y registra Actividad CORRECCION_RECORREGIDA.
- corregir_individual sobre la PRIMERA corrección: NO versiona ni audita.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import EstadoEntregaEnum, TipoActividadEnum, TipoRubricaEnum
from app.services.correccion_service import CorreccionService, _snapshot_de_correccion


# ===================== función pura =====================


def _correccion_existente(**over):
    base = dict(
        entrega_id=1,
        nota=Decimal("80.00"),
        criterios_json={"criterios": [{"id": "C1"}]},
        fortalezas=["clara"],
        recomendaciones=["mejorar tests"],
        comentario_general="ok",
        nota_antes_penalizaciones=Decimal("85.00"),
        condicion_desaprobacion_aplicada=None,
        penalizaciones_aplicadas=["tarde"],
        editado_manualmente=True,
        raw_response={"gemini": "crudo"},
        corregido_por_id=3,
        created_at=datetime(2026, 5, 1, 10, 0, 0),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_snapshot_preserva_edicion_manual_y_raw():
    c = _correccion_existente()
    snap = _snapshot_de_correccion(c, reemplazada_por_id=9)
    assert snap.editado_manualmente is True          # lo más importante ante un reclamo
    assert snap.raw_response == {"gemini": "crudo"}
    assert snap.nota == Decimal("80.00")
    assert snap.penalizaciones_aplicadas == ["tarde"]


def test_snapshot_usa_created_at_original_y_actor():
    c = _correccion_existente()
    snap = _snapshot_de_correccion(c, reemplazada_por_id=9)
    assert snap.correccion_creada_en == datetime(2026, 5, 1, 10, 0, 0)  # cuándo se calificó
    assert snap.reemplazada_por_id == 9                                 # quién recorrigió
    assert snap.corregido_por_id == 3                                   # quién había corregido


# ===================== orquestación en corregir_individual =====================

from app.models.enums import EstadoEntregaEnum as _E  # noqa: E402


def _fake_entrega():
    return SimpleNamespace(
        id=1, archivo_tipo="txt", contenido_consolidado="print(1)",
        contenido_preview="print(1)", pdf_contenido_b64=None, rubrica_id=5,
        alumno_nombre="Juan", comision=SimpleNamespace(materia=SimpleNamespace(nombre="P1")),
        estado=EstadoEntregaEnum.SUBIDA, error_code=None, error_mensaje=None, error_at=None,
    )


def _fake_rubrica():
    return SimpleNamespace(
        id=5, titulo="TP1", descripcion="desc", tipo=TipoRubricaEnum.TP,
        puntaje_maximo=100, metadata_json={},
        criterios_json=[{"id": "C1", "peso": 100, "subcriterios": []}],
        penalizaciones_json=[], condiciones_desaprobacion_json=[],
        schema_version=1, condicion_desaprobacion_json=[],
    )


def _gemini_ok():
    return {
        "success": True,
        "correccion": {
            "nota": 90,
            "criterios": [{"id": "C1", "nombre": "C1", "puntaje_obtenido": 90,
                           "puntaje_maximo": 100, "estado": "OK", "feedback": "Bien"}],
            "fortalezas": ["ok"], "recomendaciones": ["mejorar"], "comentario_general": "Bien",
        },
    }


def _service(existing):
    entrega = _fake_entrega()
    entrega.rubrica = _fake_rubrica()  # el builder de respuesta lee entrega.rubrica
    svc = CorreccionService(db=MagicMock())
    svc.entrega_repo = MagicMock()
    svc.entrega_repo.get_by_id_with_relations = AsyncMock(return_value=entrega)
    svc.entrega_repo.update = AsyncMock(return_value=entrega)
    svc.rubrica_repo = MagicMock()
    svc.rubrica_repo.get_active_by_id = AsyncMock(return_value=_fake_rubrica())

    svc.correccion_repo = MagicMock()
    svc.correccion_repo.get_by_entrega_id = AsyncMock(return_value=existing)
    svc.correccion_repo.delete = AsyncMock()

    creada = {}

    async def _create(correccion):
        correccion.id = 100
        correccion.created_at = datetime(2026, 7, 21)
        correccion.updated_at = datetime(2026, 7, 21)
        creada["c"] = correccion
        return correccion

    svc.correccion_repo.create = AsyncMock(side_effect=_create)
    svc.correccion_repo.get_by_id_with_relations = AsyncMock(
        return_value=SimpleNamespace(
            id=100, entrega_id=1, nota=Decimal("90"), nota_antes_penalizaciones=None,
            condicion_desaprobacion_aplicada=None, penalizaciones_aplicadas=[],
            criterios_json={"criterios": []}, fortalezas=["ok"], recomendaciones=["mejorar"],
            comentario_general="Bien", editado_manualmente=False, corregido_por_id=9,
            created_at=datetime(2026, 7, 21), updated_at=datetime(2026, 7, 21), entrega=entrega,
        )
    )
    svc.correccion_historial_repo = MagicMock()
    svc.correccion_historial_repo.create = AsyncMock()
    svc.gemini_client = MagicMock()
    svc.gemini_client.corregir_codigo = AsyncMock(return_value=_gemini_ok())
    svc.usuario_repo = MagicMock()
    return svc


@pytest.fixture(autouse=True)
def _no_decrypt(monkeypatch):
    monkeypatch.setattr("app.services.correccion_service.decrypt_api_key", lambda v: v)


@pytest.mark.asyncio
async def test_recorreccion_versiona_antes_de_borrar_y_audita():
    existing = _correccion_existente(nota=Decimal("70.00"))
    svc = _service(existing)
    with patch("app.services.correccion_service.ActividadService") as MockAct:
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.corregir_individual(entrega_id=1, api_key_encrypted="x", corregido_por_id=9)

        # Se creó el snapshot con la nota vieja.
        svc.correccion_historial_repo.create.assert_awaited_once()
        snap = svc.correccion_historial_repo.create.await_args.args[0]
        assert snap.nota == Decimal("70.00")
        assert snap.reemplazada_por_id == 9
        # Se borró la vieja.
        svc.correccion_repo.delete.assert_awaited_once()
        # Se auditó la recorrección.
        kwargs = MockAct.return_value.registrar_actividad.await_args.kwargs
    assert kwargs["tipo"] == TipoActividadEnum.CORRECCION_RECORREGIDA
    assert kwargs["entidad_id"] == 1
    assert kwargs["usuario_id"] == 9


@pytest.mark.asyncio
async def test_primera_correccion_no_versiona_ni_audita():
    svc = _service(existing=None)  # no hay corrección previa
    with patch("app.services.correccion_service.ActividadService") as MockAct:
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.corregir_individual(entrega_id=1, api_key_encrypted="x", corregido_por_id=9)

        svc.correccion_historial_repo.create.assert_not_called()
        svc.correccion_repo.delete.assert_not_called()
        MockAct.return_value.registrar_actividad.assert_not_called()


@pytest.mark.asyncio
async def test_recorreccion_lee_la_correccion_con_load_raw():
    """Sin load_raw, raw_response quedaría diferido y el snapshot lo perdería."""
    existing = _correccion_existente()
    svc = _service(existing)
    with patch("app.services.correccion_service.ActividadService") as MockAct:
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.corregir_individual(entrega_id=1, api_key_encrypted="x", corregido_por_id=9)
        _, kwargs = svc.correccion_repo.get_by_entrega_id.await_args
    assert kwargs.get("load_raw") is True
