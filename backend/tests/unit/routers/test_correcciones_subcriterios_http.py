"""Contrato HTTP real de edición anidada con los guards existentes."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db, get_universidad_activa
from app.routers.correcciones import router
from tests.unit.routers.test_correcciones_authz import (
    _CORRECCION_99,
    _ES_TUTOR,
    _SIN_PERTENENCIA,
    CTX_TUTOR,
    TUTOR,
    _db,
)
from tests.unit.services.test_correccion_edicion_manual import make_service


async def request_edit(service, db, payload):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: TUTOR
    app.dependency_overrides[get_universidad_activa] = lambda: CTX_TUTOR
    app.dependency_overrides[get_db] = lambda: db
    with patch("app.routers.correcciones.CorreccionService", return_value=service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.put("/correcciones/1", json=payload)


@pytest.mark.asyncio
async def test_put_anidado_valido_guarda_y_devuelve_desglose():
    service, correction = make_service()
    criterios = deepcopy(correction.criterios_json["criterios"])
    criterios[0]["subcriterios_evaluados"][0].update(puntaje_obtenido=16, feedback="HTTP revisado")
    response = await request_edit(service, _db(_CORRECCION_99, _ES_TUTOR), {"criterios": criterios})
    assert response.status_code == 200
    data = response.json()
    assert float(data["criterios"][0]["puntaje_obtenido"]) == 16
    assert data["criterios"][0]["subcriterios_evaluados"][0]["feedback"] == "HTTP revisado"
    assert data["corregido_por_id"] == TUTOR.id and data["editado_manualmente"]
    service.correccion_repo.update.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("puntaje_obtenido", 21), ("feedback", "   "), ("puntaje_maximo", 30)])
async def test_put_invalido_400_sin_persistencia_parcial(field, value):
    service, correction = make_service()
    before = deepcopy(correction.criterios_json)
    criterios = deepcopy(before["criterios"])
    criterios[0]["subcriterios_evaluados"][0][field] = value
    response = await request_edit(service, _db(_CORRECCION_99, _ES_TUTOR), {"nota": 19, "criterios": criterios})
    assert response.status_code == 400
    service.correccion_repo.update.assert_not_awaited()
    assert correction.criterios_json == before and correction.nota == 12


@pytest.mark.asyncio
@pytest.mark.parametrize("access,expected", [(_SIN_PERTENENCIA, 403), (None, 404)])
async def test_put_ajeno_o_fuera_universidad_no_consulta_servicio(access, expected):
    service, correction = make_service()
    response = await request_edit(service, _db(_CORRECCION_99, access), {"criterios": correction.criterios_json["criterios"]})
    assert response.status_code == expected
    service.correccion_repo.get_by_id.assert_not_awaited()
    service.correccion_repo.update.assert_not_awaited()
