"""Guardar, recargar y devolver el desglose con repositorios y SQLite reales."""

import json
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from reportlab.platypus import Paragraph

from app.models.correccion import Correccion
from app.schemas.correccion import CorreccionResponse, CorreccionUpdate
from app.services.correccion_service import CorreccionService
from app.services.pdf_service import PDFService
from app.services.politica_entrega import VERSION_POLITICA
from tests.unit.repositories.test_ia003_reclamar_atomico import _entrega
from tests.unit.services.test_edicion_subcriterios import criterio


@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["desglose", "omitido", "v1"])
async def test_guardar_recargar_y_pdf_conservan_detalle_y_tope(db_session, modo):
    entrega = await _entrega(db_session)
    entrega.analisis_archivos = {"version": VERSION_POLITICA, "rutas_penalizables": ["tp/dist/"]}
    original = criterio()
    if modo == "v1":
        original.pop("subcriterios_evaluados")
    correction = Correccion(
        universidad_id=1, entrega_id=entrega.id, nota=Decimal(50),
        criterios_json={"criterios": [original], "politica_entrega": {"nota_academica": 82}, "origen": "conservar"},
        fortalezas=[], recomendaciones=[], comentario_general="General",
        penalizaciones_aplicadas=[], corregido_por_id=1,
    )
    db_session.add(correction)
    await db_session.commit()
    correction_id = correction.id
    edited = deepcopy(original)
    if modo == "desglose":
        edited["subcriterios_evaluados"][0].update(puntaje_obtenido=16, feedback="Comentario revisado")
    elif modo == "omitido":
        edited.pop("subcriterios_evaluados")
        edited["feedback"] = "Padre revisado"
    else:
        edited["puntaje_obtenido"] = 16
    service = CorreccionService(db_session)
    async def response_sqlite(model):
        # ARRAY de Postgres se compila a JSON en este harness; SQLite devuelve
        # texto crudo. Adaptar SOLO esos campos para ejercer el contrato normal.
        fields = ("id", "entrega_id", "nota", "nota_antes_penalizaciones",
                  "condicion_desaprobacion_aplicada", "criterios_json", "comentario_general",
                  "editado_manualmente", "corregido_por_id", "created_at", "updated_at")
        data = {field: getattr(model, field) for field in fields}
        for field in ("fortalezas", "recomendaciones", "penalizaciones_aplicadas"):
            value = getattr(model, field)
            data[field] = json.loads(value) if isinstance(value, str) else value
        return CorreccionResponse.model_validate(SimpleNamespace(**data))
    service._build_correccion_response = AsyncMock(side_effect=response_sqlite)
    await service.editar_correccion(correction_id, CorreccionUpdate(criterios=[edited]), 7)
    db_session.expire_all()
    response = await service.obtener_correccion(correction_id, universidad_id=1)
    assert response.nota_academica == 82 and response.nota == 50
    assert response.editado_manualmente and response.corregido_por_id == 7
    persisted = await service.correccion_repo.get_by_id(correction_id)
    assert persisted.criterios_json["origen"] == "conservar"
    expected_score = 12 if modo == "omitido" else 16
    assert response.criterios[0].puntaje_obtenido == expected_score
    table = PDFService(None)._format_criterio(persisted.criterios_json["criterios"][0], 1)
    text = " ".join(cell.text for row in table._cellvalues for cell in row if isinstance(cell, Paragraph))
    if modo == "desglose":
        assert "16/20" in text and "Comentario revisado" in text
        assert response.criterios[0].subcriterios_evaluados[0].puntaje_obtenido == 16
    elif modo == "omitido":
        assert "12/20" in text and "Original" in text
        assert response.criterios[0].subcriterios_evaluados[0].feedback == "Original"
    else:
        assert response.criterios[0].subcriterios_evaluados is None
        assert "C1.1" not in text
