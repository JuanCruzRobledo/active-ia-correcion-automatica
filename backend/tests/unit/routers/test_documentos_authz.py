"""
Tests de autorizacion por pertenencia en el router de documentos (SEC-004).

Los 4 endpoints usaban SOLO `require_any_authenticated`: cualquiera exfiltraba
el PDF de devolucion de cualquier alumno o el Excel de notas COMPLETO de una
comision ajena. Misma clase que SEC-001/002 pero sobre documentos exportables.

`descargar_pdfs_seleccionados` devuelve un ZIP binario, no JSON: los IDs
omitidos por permisos viajan en el header `X-Entregas-Omitidas`.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.routers.documentos import (
    descargar_pdf_correccion,
    descargar_pdfs_lote,
    descargar_pdfs_seleccionados,
    exportar_notas_excel,
)

ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)
TUTOR = SimpleNamespace(id=5, rol=RolEnum.TUTOR)
COORD = SimpleNamespace(id=7, rol=RolEnum.COORDINADOR)
GESTOR = SimpleNamespace(id=9, rol=RolEnum.GESTOR)

_ES_TUTOR = (10, 555, None)
_ES_COORDINADOR = (10, None, 777)
_SIN_PERTENENCIA = (10, None, None)
_CORRECCION_99 = (99, 10)


def _db(*rows):
    db = AsyncMock()
    resultados = []
    for r in rows:
        res = MagicMock()
        res.first.return_value = r
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


# ===================== GET /correcciones/{id}/pdf =====================


@pytest.mark.asyncio
async def test_pdf_correccion_propia_ok():
    db = _db(_CORRECCION_99, _ES_TUTOR)
    with patch("app.routers.documentos.PDFService") as MockPDF, patch(
        "app.repositories.correccion_repository.CorreccionRepository"
    ) as MockRepo:
        MockPDF.return_value.generar_pdf_devolucion = AsyncMock(return_value=b"%PDF")
        MockRepo.return_value.get_by_id_with_relations = AsyncMock(return_value=None)
        resp = await descargar_pdf_correccion(99, current_user=TUTOR, db=db)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pdf_correccion_ajena_403_sin_generar_el_pdf():
    db = _db(_CORRECCION_99, _SIN_PERTENENCIA)
    with patch("app.routers.documentos.PDFService") as MockPDF:
        with pytest.raises(HTTPException) as exc:
            await descargar_pdf_correccion(99, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockPDF.return_value.generar_pdf_devolucion.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_correccion_coordinador_de_la_materia_ok():
    db = _db(_CORRECCION_99, _ES_COORDINADOR)
    with patch("app.routers.documentos.PDFService") as MockPDF, patch(
        "app.repositories.correccion_repository.CorreccionRepository"
    ) as MockRepo:
        MockPDF.return_value.generar_pdf_devolucion = AsyncMock(return_value=b"%PDF")
        MockRepo.return_value.get_by_id_with_relations = AsyncMock(return_value=None)
        resp = await descargar_pdf_correccion(99, current_user=COORD, db=db)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pdf_correccion_inexistente_404():
    db = _db(None)
    with pytest.raises(HTTPException) as exc:
        await descargar_pdf_correccion(404404, current_user=TUTOR, db=db)
    assert exc.value.status_code == 404


# ===================== GET /comisiones/{c}/rubricas/{r}/pdfs =====================


@pytest.mark.asyncio
async def test_pdfs_lote_comision_propia_ok():
    db = _db(_ES_TUTOR)
    with patch("app.routers.documentos.PDFService") as MockPDF:
        MockPDF.return_value.generar_zip_pdfs = AsyncMock(return_value=(b"ZIP", "x.zip"))
        resp = await descargar_pdfs_lote(10, 3, current_user=TUTOR, db=db)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pdfs_lote_comision_ajena_403():
    db = _db(_SIN_PERTENENCIA)
    with patch("app.routers.documentos.PDFService") as MockPDF:
        with pytest.raises(HTTPException) as exc:
            await descargar_pdfs_lote(10, 3, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockPDF.return_value.generar_zip_pdfs.assert_not_called()


@pytest.mark.asyncio
async def test_pdfs_lote_gestor_403():
    db = _db(_SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await descargar_pdfs_lote(10, 3, current_user=GESTOR, db=db)
    assert exc.value.status_code == 403


# ===================== GET /comisiones/{c}/rubricas/{r}/excel =====================


@pytest.mark.asyncio
async def test_excel_comision_propia_ok():
    db = _db(_ES_COORDINADOR)
    with patch("app.routers.documentos.ExcelService") as MockXls:
        MockXls.return_value.exportar_notas_excel = AsyncMock(return_value=(b"XLS", "n.xlsx"))
        resp = await exportar_notas_excel(10, 3, current_user=COORD, db=db)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_excel_comision_ajena_403_sin_generar_el_acta():
    """El Excel es el acta OFICIAL de notas completa: no puede exfiltrarse."""
    db = _db(_SIN_PERTENENCIA)
    with patch("app.routers.documentos.ExcelService") as MockXls:
        with pytest.raises(HTTPException) as exc:
            await exportar_notas_excel(10, 3, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockXls.return_value.exportar_notas_excel.assert_not_called()


@pytest.mark.asyncio
async def test_excel_admin_ok_sin_consultar_permisos():
    db = AsyncMock()
    with patch("app.routers.documentos.ExcelService") as MockXls:
        MockXls.return_value.exportar_notas_excel = AsyncMock(return_value=(b"XLS", "n.xlsx"))
        resp = await exportar_notas_excel(10, 3, current_user=ADMIN, db=db)
    assert resp.status_code == 200
    db.execute.assert_not_called()


# ===================== POST /pdfs-seleccionados (ZIP + header) =====================


@pytest.mark.asyncio
async def test_pdfs_seleccionados_mixto_zip_solo_permitidos_y_header_omitidos():
    db = AsyncMock()
    data = SimpleNamespace(entrega_ids=[1, 2, 99])
    with patch("app.routers.documentos.PDFService") as MockPDF, patch(
        "app.routers.documentos.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, {99})),
    ):
        MockPDF.return_value.generar_zip_pdfs_seleccionados = AsyncMock(
            return_value=(b"ZIP", "sel.zip")
        )
        resp = await descargar_pdfs_seleccionados(data, current_user=TUTOR, db=db)
        # El ZIP se genera SOLO con los permitidos.
        kwargs = MockPDF.return_value.generar_zip_pdfs_seleccionados.await_args.kwargs
    assert kwargs["entrega_ids"] == [1, 2]
    assert resp.headers["X-Entregas-Omitidas"] == "99"


@pytest.mark.asyncio
async def test_pdfs_seleccionados_todo_denegado_403_sin_generar_zip():
    db = AsyncMock()
    data = SimpleNamespace(entrega_ids=[98, 99])
    with patch("app.routers.documentos.PDFService") as MockPDF, patch(
        "app.routers.documentos.filtrar_entregas_accesibles",
        AsyncMock(return_value=(set(), {98, 99})),
    ):
        with pytest.raises(HTTPException) as exc:
            await descargar_pdfs_seleccionados(data, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockPDF.return_value.generar_zip_pdfs_seleccionados.assert_not_called()


@pytest.mark.asyncio
async def test_pdfs_seleccionados_todo_propio_header_vacio():
    db = AsyncMock()
    data = SimpleNamespace(entrega_ids=[1, 2])
    with patch("app.routers.documentos.PDFService") as MockPDF, patch(
        "app.routers.documentos.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, set())),
    ):
        MockPDF.return_value.generar_zip_pdfs_seleccionados = AsyncMock(
            return_value=(b"ZIP", "sel.zip")
        )
        resp = await descargar_pdfs_seleccionados(data, current_user=TUTOR, db=db)
    assert resp.headers["X-Entregas-Omitidas"] == ""


@pytest.mark.asyncio
async def test_pdfs_seleccionados_el_zip_no_incluye_entregas_ajenas():
    """SEC-004: el ZIP jamas debe contener el PDF de una entrega ajena."""
    db = AsyncMock()
    data = SimpleNamespace(entrega_ids=[1, 2, 3, 4, 5])
    with patch("app.routers.documentos.PDFService") as MockPDF, patch(
        "app.routers.documentos.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 3}, {2, 4, 5})),
    ):
        MockPDF.return_value.generar_zip_pdfs_seleccionados = AsyncMock(
            return_value=(b"ZIP", "sel.zip")
        )
        await descargar_pdfs_seleccionados(data, current_user=TUTOR, db=db)
        ids = MockPDF.return_value.generar_zip_pdfs_seleccionados.await_args.kwargs["entrega_ids"]
    assert set(ids) == {1, 3}
    assert not ({2, 4, 5} & set(ids))
