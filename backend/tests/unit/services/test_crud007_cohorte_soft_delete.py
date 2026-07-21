"""
CRUD-007: eliminar una cohorte es soft delete (activa=False), no físico.

Antes CohorteRepository.delete era físico pese a que Cohorte tiene `activa`; y
borrar una cohorte con cuatrimestres reventaba con IntegrityError 500 (la FK
cohorte_id es NOT NULL sin ON DELETE). Con soft delete no hay borrado físico, así
que desaparece el 500 y la baja es reversible.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.cohorte_service import CohorteService


def _svc(cohorte, materias=0):
    svc = CohorteService.__new__(CohorteService)
    svc._get_cohorte_or_404 = AsyncMock(return_value=cohorte)
    svc.cohorte_repo = SimpleNamespace(
        count_materias=AsyncMock(return_value=materias),
        soft_delete=AsyncMock(),
        delete=AsyncMock(),
    )
    return svc


@pytest.mark.asyncio
async def test_eliminar_cohorte_es_soft_delete():
    cohorte = SimpleNamespace(id=1, activa=True)
    svc = _svc(cohorte, materias=0)
    await svc.eliminar_cohorte(1)
    svc.cohorte_repo.soft_delete.assert_awaited_once()
    svc.cohorte_repo.delete.assert_not_called()  # nada de borrado físico


@pytest.mark.asyncio
async def test_eliminar_cohorte_con_materias_da_409():
    cohorte = SimpleNamespace(id=1, activa=True)
    svc = _svc(cohorte, materias=3)
    with pytest.raises(HTTPException) as exc:
        await svc.eliminar_cohorte(1)
    assert exc.value.status_code == 409
    svc.cohorte_repo.soft_delete.assert_not_called()


@pytest.mark.asyncio
async def test_eliminar_cohorte_ya_eliminada_da_400():
    cohorte = SimpleNamespace(id=1, activa=False)
    svc = _svc(cohorte, materias=0)
    with pytest.raises(HTTPException) as exc:
        await svc.eliminar_cohorte(1)
    assert exc.value.status_code == 400
    svc.cohorte_repo.soft_delete.assert_not_called()
