"""
CRUD-006: el soft delete de una materia propaga a sus comisiones y rúbricas.

Antes, eliminar_materia solo ponía Materia.activa=False; las comisiones seguían
activas y operables (subir entregas, corregir) porque las queries de hijos nunca
miraban Materia.activa. Ahora el soft delete desactiva los hijos en la misma
transacción, y el restore los reactiva.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.materia_service import MateriaService


def _svc(materia):
    svc = MateriaService.__new__(MateriaService)
    svc.materia_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=materia),
        soft_delete=AsyncMock(),
        restore=AsyncMock(return_value=materia),
    )
    svc.comision_repo = SimpleNamespace(
        desactivar_por_materia=AsyncMock(return_value=2),
        reactivar_por_materia=AsyncMock(return_value=2),
    )
    svc.rubrica_repo = SimpleNamespace(
        desactivar_por_materia=AsyncMock(return_value=1),
        reactivar_por_materia=AsyncMock(return_value=1),
    )
    return svc


@pytest.mark.asyncio
async def test_eliminar_materia_propaga_a_comisiones_y_rubricas():
    materia = SimpleNamespace(id=7, activa=True)
    svc = _svc(materia)
    with patch("app.core.config.settings") as st:
        st.ALLOW_HARD_DELETE = False
        await svc.eliminar_materia(7)
        svc.materia_repo.soft_delete.assert_awaited_once()
        svc.comision_repo.desactivar_por_materia.assert_awaited_once_with(7)
        svc.rubrica_repo.desactivar_por_materia.assert_awaited_once_with(7)



@pytest.mark.asyncio
async def test_restaurar_materia_reactiva_hijos():
    materia = SimpleNamespace(id=7, activa=False)
    svc = _svc(materia)
    with patch("app.services.materia_service.MateriaResponse") as MockResp:
        MockResp.model_validate.return_value = "OK"
        await svc.restaurar_materia(7)
        svc.comision_repo.reactivar_por_materia.assert_awaited_once_with(7)
        svc.rubrica_repo.reactivar_por_materia.assert_awaited_once_with(7)
