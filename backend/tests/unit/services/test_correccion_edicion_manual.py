from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from reportlab.platypus import Paragraph

from app.schemas.correccion import CorreccionUpdate
from app.services.correccion_service import CorreccionService
from app.services.pdf_service import PDFService


def make_service():
    subs = [{"id": "C1.1", "puntaje_obtenido": 12, "puntaje_maximo": 20,
             "estado": "WARNING", "feedback": "Original"}]
    criterio = {"id": "C1", "nombre": "Criterio", "puntaje_obtenido": 12,
                "puntaje_maximo": 20, "estado": "WARNING", "feedback": "Padre",
                "subcriterios_evaluados": subs}
    entrega = SimpleNamespace(id=1, analisis_archivos=None,
                              rubrica=SimpleNamespace(condiciones_desaprobacion_json=[], penalizaciones_json=[]))
    correccion = SimpleNamespace(
        id=1, entrega_id=1, nota=Decimal(12), nota_antes_penalizaciones=None,
        condicion_desaprobacion_aplicada=None, penalizaciones_aplicadas=[],
        criterios_json={"criterios": [criterio], "otra_clave": {"conservar": True}},
        fortalezas=[], recomendaciones=[], comentario_general="General",
        editado_manualmente=False, corregido_por_id=1,
        created_at=datetime(2026, 11, 6, tzinfo=timezone.utc),
        updated_at=datetime(2026, 11, 6, tzinfo=timezone.utc), entrega=entrega,
    )
    service = CorreccionService(MagicMock())
    service.correccion_repo = MagicMock()
    service.correccion_repo.get_by_id = AsyncMock(return_value=correccion)
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=correccion)
    service.correccion_repo.update = AsyncMock(side_effect=lambda c: c)
    service.entrega_repo.get_by_id = AsyncMock(return_value=entrega)
    return service, correccion


@pytest.mark.asyncio
async def test_actualiza_subcriterio_deriva_padre_preserva_metadatos_nota_y_lectura_pdf():
    service, correction = make_service()
    edited = deepcopy(correction.criterios_json["criterios"])
    edited[0]["subcriterios_evaluados"][0].update(puntaje_obtenido=16, feedback="Revisado")
    response = await service.editar_correccion(1, CorreccionUpdate(criterios=edited), 7)
    assert response.criterios[0].puntaje_obtenido == 16
    assert response.nota == 12
    assert response.editado_manualmente and response.corregido_por_id == 7
    assert correction.criterios_json["otra_clave"] == {"conservar": True}
    reread = await service.obtener_correccion(1)
    assert reread.criterios[0].subcriterios_evaluados[0].feedback == "Revisado"
    table = PDFService(None)._format_criterio(correction.criterios_json["criterios"][0], 1)
    text = " ".join(cell.text for row in table._cellvalues for cell in row if isinstance(cell, Paragraph))
    assert "16/20" in text and "Revisado" in text


@pytest.mark.asyncio
async def test_omitir_subcriterios_preserva_desglose_y_comentario_sin_reparar_total():
    service, correction = make_service()
    correction.criterios_json["criterios"][0]["puntaje_obtenido"] = 19
    edited = deepcopy(correction.criterios_json["criterios"])
    edited[0].pop("subcriterios_evaluados")
    edited[0]["feedback"] = "Revisado padre"
    response = await service.editar_correccion(1, CorreccionUpdate(criterios=edited), 7)
    assert response.criterios[0].puntaje_obtenido == 19
    assert response.criterios[0].subcriterios_evaluados[0].puntaje_obtenido == 12


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["maximo", "estado", "delete", "score", "feedback"])
async def test_edicion_invalida_no_persiste_ni_muta_modelo(change):
    service, correction = make_service()
    before = deepcopy(correction.criterios_json)
    edited = deepcopy(before["criterios"])
    sub = edited[0]["subcriterios_evaluados"][0]
    if change == "maximo":
        sub["puntaje_maximo"] = 30
    elif change == "estado":
        sub["estado"] = "OK"
    elif change == "delete":
        edited[0]["subcriterios_evaluados"] = []
    elif change == "score":
        sub["puntaje_obtenido"] = 21
    else:
        sub["feedback"] = "   "
    with pytest.raises(HTTPException) as error:
        await service.editar_correccion(1, CorreccionUpdate(nota=19, criterios=edited), 7)
    assert error.value.status_code == 400
    service.correccion_repo.update.assert_not_awaited()
    assert correction.criterios_json == before and correction.nota == 12
