"""
CRUD-003 (Fase 4): endpoint de lectura del historial de correcciones + schema.

Sin read path, preservar datos que nadie puede ver es medio fix. El GET expone las
versiones (nota, edición manual, quién y cuándo) SIN raw_response (forense), con
guard de pertenencia.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum


# ===================== schema =====================


def test_schema_item_no_expone_raw_response():
    from app.schemas.correccion import CorreccionHistorialItem

    campos = set(CorreccionHistorialItem.model_fields.keys())
    assert "raw_response" not in campos
    assert {"id", "nota", "editado_manualmente", "correccion_creada_en",
            "reemplazada_en"} <= campos


def test_schema_response_shape():
    from app.schemas.correccion import (
        CorreccionHistorialItem,
        CorreccionHistorialResponse,
    )

    resp = CorreccionHistorialResponse(
        entrega_id=1, total_versiones=0, versiones=[]
    )
    assert resp.total_versiones == 0
    assert isinstance(resp.versiones, list)
    _ = CorreccionHistorialItem  # referenciado


# ===================== service.obtener_historial_correcciones =====================


@pytest.mark.asyncio
async def test_service_arma_response_desde_el_repo():
    from app.services.correccion_service import CorreccionService

    svc = CorreccionService.__new__(CorreccionService)
    versiones = [
        SimpleNamespace(
            id=2, nota=85, editado_manualmente=True, comentario_general="ok",
            corregido_por=SimpleNamespace(nombre="Tutor A"),
            reemplazada_por=SimpleNamespace(nombre="Tutor B"),
            correccion_creada_en=datetime(2026, 5, 1),
            reemplazada_en=datetime(2026, 6, 1),
        ),
    ]
    svc.correccion_historial_repo = SimpleNamespace(
        list_by_entrega=AsyncMock(return_value=versiones)
    )
    resp = await svc.obtener_historial_correcciones(1)
    assert resp.entrega_id == 1
    assert resp.total_versiones == 1
    assert resp.versiones[0].nota == 85.0
    assert resp.versiones[0].corregido_por_nombre == "Tutor A"
    assert resp.versiones[0].reemplazada_por_nombre == "Tutor B"


@pytest.mark.asyncio
async def test_service_tolera_autor_nulo():
    """corregido_por / reemplazada_por pueden ser None (usuario borrado, SET NULL)."""
    from app.services.correccion_service import CorreccionService

    svc = CorreccionService.__new__(CorreccionService)
    versiones = [
        SimpleNamespace(
            id=2, nota=70, editado_manualmente=False, comentario_general=None,
            corregido_por=None, reemplazada_por=None,
            correccion_creada_en=datetime(2026, 5, 1),
            reemplazada_en=datetime(2026, 6, 1),
        ),
    ]
    svc.correccion_historial_repo = SimpleNamespace(
        list_by_entrega=AsyncMock(return_value=versiones)
    )
    resp = await svc.obtener_historial_correcciones(1)
    assert resp.versiones[0].corregido_por_nombre is None
    assert resp.versiones[0].reemplazada_por_nombre is None


# ===================== router GET =====================

TUTOR = SimpleNamespace(id=5, rol=RolEnum.TUTOR)
_ENTREGA = (42, 10)
_ES_TUTOR = (10, 555, None)
_SIN = (10, None, None)


def _db(*rows):
    db = AsyncMock()
    res = []
    for r in rows:
        m = MagicMock()
        m.first.return_value = r
        res.append(m)
    db.execute.side_effect = res
    return db


@pytest.mark.asyncio
async def test_endpoint_con_pertenencia_devuelve_historial():
    from app.routers.correcciones import obtener_historial_correcciones

    db = _db(_ENTREGA, _ES_TUTOR)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.obtener_historial_correcciones = AsyncMock(return_value="HIST")
        res = await obtener_historial_correcciones(42, current_user=TUTOR, db=db)
        MockSvc.return_value.obtener_historial_correcciones.assert_awaited_once_with(42)
    assert res == "HIST"


@pytest.mark.asyncio
async def test_endpoint_sin_pertenencia_403():
    from app.routers.correcciones import obtener_historial_correcciones

    db = _db(_ENTREGA, _SIN)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await obtener_historial_correcciones(42, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.obtener_historial_correcciones.assert_not_called()
