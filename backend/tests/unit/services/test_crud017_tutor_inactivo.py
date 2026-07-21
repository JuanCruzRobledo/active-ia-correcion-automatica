"""
CRUD-017 (#3): obtener_comision oculta los tutores inactivos, alineado con
obtener_materia (que ya oculta coordinadores inactivos). Antes un usuario
deshabilitado desaparecía de una pantalla y seguía en la otra.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.comision_service import ComisionService


@pytest.mark.asyncio
async def test_obtener_comision_oculta_tutores_inactivos():
    svc = ComisionService.__new__(ComisionService)
    activo = SimpleNamespace(id=1, username="act", nombre="Activo", activo=True)
    inactivo = SimpleNamespace(id=2, username="ina", nombre="Inactivo", activo=False)
    comision = SimpleNamespace(
        id=10, materia_id=1, nombre="C1", anio=2026, activa=True,
        moodle_group_id=None, moodle_group_code=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
        materia=SimpleNamespace(id=1, codigo="P1", nombre="Prog"),
        tutores=[
            SimpleNamespace(tutor=activo, asignado_en=datetime(2026, 1, 1)),
            SimpleNamespace(tutor=inactivo, asignado_en=datetime(2026, 1, 1)),
        ],
    )
    svc.comision_repo = SimpleNamespace(
        get_by_id_with_relations=AsyncMock(return_value=comision)
    )

    resp = await svc.obtener_comision(10)
    ids = [t.id for t in resp.tutores]
    assert 1 in ids          # activo aparece
    assert 2 not in ids      # inactivo oculto (alineado con materia)
