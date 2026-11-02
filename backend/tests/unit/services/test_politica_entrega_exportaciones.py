"""La devolución conserva la nota final y explica el tope en cada canal."""

import io
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from openpyxl import load_workbook
from reportlab.platypus import Paragraph, Table

from app.services.excel_service import ExcelService
from app.services.pdf_service import PDFService
from app.services.politica_entrega import aplicar_politica_correccion
from app.services.moodle_service import AssignmentGradeConfig
from tests.unit.services.test_pdf_devolucion_paginacion import _snapshot
from tests.unit.services.test_moodle_grade_subir import (
    _correccion, _usuario, service as moodle_service_fixture,
)

service = moodle_service_fixture


def correction(score, restricted):
    obj = _snapshot([])
    obj.nota = Decimal(score)
    obj.created_at = datetime(2026, 10, 30)
    analysis = {"version": 1, "rutas_penalizables": ["tp/dist/"] if restricted else []}
    aplicar_politica_correccion(obj, analysis)
    return obj


def assert_explanation(text, score):
    text = " ".join(text.split())
    assert f"Nota académica: {score}/100" in text
    assert "máximo 50/100" in text
    assert "tp/dist/" in text
    assert "dependencias o compilados" in text
    assert "nuevamente" in text
    assert "evaluarse otra vez" in text


def flowable_text(items):
    for item in items:
        if isinstance(item, Paragraph):
            yield item.getPlainText()
        elif isinstance(item, Table):
            for row in item._cellvalues:
                yield from flowable_text(row)
        elif isinstance(item, (list, tuple)):
            yield from flowable_text(item)
        elif isinstance(item, str):
            yield item
        elif hasattr(item, "_content"):
            yield from flowable_text(item._content)


@pytest.mark.parametrize("score,restricted,expected", [(90, True, 50), (35, True, 35), (90, False, 90)])
def test_pdf_renderiza_final_y_explicacion(score, restricted, expected):
    obj = correction(score, restricted)
    svc = PDFService(None)
    text = " ".join(flowable_text(svc._build_pdf_content(obj)))
    assert f"Calificación Final: {expected}/100" in text
    if restricted:
        assert_explanation(text, score)
    else:
        assert "máximo 50/100" not in text
    assert svc._render_pdf_bytes(obj).startswith(b"%PDF")


@pytest.mark.asyncio
@pytest.mark.parametrize("score,restricted,expected", [(90, True, 50), (35, True, 35), (90, False, 90)])
async def test_excel_exporta_final_y_explicacion(score, restricted, expected):
    obj = correction(score, restricted)
    entrega = obj.entrega
    entrega.id = 1
    entrega.estado = "CORREGIDA"
    entrega.correccion = obj
    svc = ExcelService(None)
    svc.entrega_repo.get_all_for_export = AsyncMock(return_value=[entrega])
    svc.entrega_repo.get_by_id_with_relations = AsyncMock(return_value=entrega)
    data, _ = await svc.exportar_notas_excel(1, 1)
    sheet = load_workbook(io.BytesIO(data)).active
    assert sheet["B5"].value == expected
    if restricted:
        assert_explanation(sheet["F5"].value, score)
    else:
        assert "máximo 50/100" not in sheet["F5"].value


@pytest.mark.asyncio
@pytest.mark.parametrize("score,restricted,expected", [(90, True, 50), (35, True, 35), (90, False, 90)])
async def test_moodle_envia_final_y_explicacion_aunque_tutor_edite_comentario(service, score, restricted, expected):
    obj = _correccion(nota=score, tipo="PARCIAL_1")
    obj.criterios_json = {"criterios": []}
    obj.comentario_general = "Evaluación académica."
    aplicar_politica_correccion(obj, {"version": 1, "rutas_penalizables": ["tp/dist/"] if restricted else []})
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=obj)
    service.moodle.get_assignment_grade_config = AsyncMock(return_value=AssignmentGradeConfig(
        instance_id=487, tipo="numerica", grade_max=100))
    await service.subir_correccion(correccion_id=9, comentario_final="Revisá la devolución.",
        usuario=_usuario(), ctx=MagicMock(), base_url="http://test")
    sent = service.moodle.save_grade.call_args.kwargs
    assert sent["grade"] == expected
    assert "Revisá la devolución." in sent["feedback_comment"]
    if restricted:
        assert_explanation(sent["feedback_comment"], score)
        assert_explanation(service.moodle_sync_repo.create.call_args.args[0].comentario_enviado, score)
    else:
        assert "máximo 50/100" not in sent["feedback_comment"]
