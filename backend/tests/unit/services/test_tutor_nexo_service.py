"""
Tests del TutorNexoService (T7 — ABM admin). Repo mockeado.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.tutor_nexo import TutorNexoCreate, TutorNexoUpdate
from app.services.tutor_nexo_service import TutorNexoService


def _tn(**kw):
    base = dict(
        id=1, nombre="Nexo Mza", email="nexo@x.com", regional="Mendoza",
        activo=True, created_at=datetime(2026, 6, 7),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _service():
    service = TutorNexoService(db=MagicMock())
    service.repo = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_crear_arma_y_devuelve_response():
    service = _service()

    def _crear(tn):
        tn.id = 5
        tn.created_at = datetime(2026, 6, 7)
        return tn

    service.repo.crear.side_effect = _crear

    data = TutorNexoCreate(nombre="Nexo Mza", email="nexo@x.com", regional="Mendoza")
    resp = await service.crear(data)

    assert resp.id == 5
    assert resp.email == "nexo@x.com"
    assert resp.regional == "Mendoza"
    assert resp.activo is True


@pytest.mark.asyncio
async def test_obtener_inexistente_lanza_404():
    service = _service()
    service.repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.obtener(999)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_actualizar_setea_campos_provistos():
    service = _service()
    existente = _tn()
    service.repo.get_by_id.return_value = existente
    service.repo.actualizar.side_effect = lambda tn: tn

    resp = await service.actualizar(1, TutorNexoUpdate(email="nuevo@x.com", activo=False))

    assert resp.email == "nuevo@x.com"
    assert resp.activo is False
    assert resp.regional == "Mendoza"  # no tocado


@pytest.mark.asyncio
async def test_eliminar_llama_repo():
    service = _service()
    existente = _tn()
    service.repo.get_by_id.return_value = existente

    await service.eliminar(1)

    service.repo.eliminar.assert_awaited_once_with(existente)


def test_schema_rechaza_email_invalido():
    with pytest.raises(ValueError):
        TutorNexoCreate(nombre="X", email="no-es-email", regional="Mendoza")
