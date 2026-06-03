"""
Tests del CohorteService (ABM Cohortes/Cuatrimestres — Dashboard de Gestores, T2).

Se mockean los repositorios (no se toca la DB): el valor a cubrir es la LÓGICA
de validación del service (duplicados, not-found, protección por materias vinculadas).
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.cohorte import Cohorte, Cuatrimestre
from app.schemas.cohorte import (
    CohorteCreate,
    CuatrimestreCreate,
    CuatrimestreUpdate,
)
from app.services.cohorte_service import CohorteService


def _make_service() -> CohorteService:
    service = CohorteService(db=MagicMock())
    service.cohorte_repo = AsyncMock()
    service.cuatrimestre_repo = AsyncMock()
    return service


def _cohorte(id_: int = 1, codigo: str = "M27") -> Cohorte:
    c = Cohorte(codigo=codigo, nombre=None, activa=True)
    c.id = id_
    c.created_at = datetime.utcnow()
    c.cuatrimestres = []
    return c


def _cuatrimestre(id_: int = 1, cohorte_id: int = 1, numero: int = 1) -> Cuatrimestre:
    q = Cuatrimestre(cohorte_id=cohorte_id, numero=numero, nombre=None)
    q.id = id_
    return q


# ===================== Cohorte =====================


@pytest.mark.asyncio
async def test_crear_cohorte_codigo_duplicado_lanza_409():
    service = _make_service()
    service.cohorte_repo.exists_codigo.return_value = True

    with pytest.raises(HTTPException) as exc:
        await service.crear_cohorte(CohorteCreate(codigo="m27"))

    assert exc.value.status_code == 409
    service.cohorte_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_crear_cohorte_happy_path_crea_y_normaliza_codigo():
    service = _make_service()
    service.cohorte_repo.exists_codigo.return_value = False
    service.cohorte_repo.create.return_value = _cohorte(id_=5, codigo="M27")
    service.cohorte_repo.get_by_id.return_value = _cohorte(id_=5, codigo="M27")

    result = await service.crear_cohorte(CohorteCreate(codigo="m27"))

    assert result.codigo == "M27"  # el schema normaliza a mayúsculas
    service.cohorte_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_obtener_cohorte_inexistente_lanza_404():
    service = _make_service()
    service.cohorte_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.obtener_cohorte(999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_eliminar_cohorte_con_materias_lanza_409():
    service = _make_service()
    service.cohorte_repo.get_by_id.return_value = _cohorte()
    service.cohorte_repo.count_materias.return_value = 3

    with pytest.raises(HTTPException) as exc:
        await service.eliminar_cohorte(1)

    assert exc.value.status_code == 409
    service.cohorte_repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_eliminar_cohorte_sin_materias_borra():
    service = _make_service()
    cohorte = _cohorte()
    service.cohorte_repo.get_by_id.return_value = cohorte
    service.cohorte_repo.count_materias.return_value = 0

    await service.eliminar_cohorte(1)

    service.cohorte_repo.delete.assert_awaited_once_with(cohorte)


# ===================== Cuatrimestre =====================


@pytest.mark.asyncio
async def test_crear_cuatrimestre_cohorte_inexistente_lanza_404():
    service = _make_service()
    service.cohorte_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.crear_cuatrimestre(999, CuatrimestreCreate(numero=1))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_crear_cuatrimestre_numero_duplicado_lanza_409():
    service = _make_service()
    service.cohorte_repo.get_by_id.return_value = _cohorte()
    service.cuatrimestre_repo.exists_numero.return_value = True

    with pytest.raises(HTTPException) as exc:
        await service.crear_cuatrimestre(1, CuatrimestreCreate(numero=2))

    assert exc.value.status_code == 409
    service.cuatrimestre_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_crear_cuatrimestre_happy_path():
    service = _make_service()
    service.cohorte_repo.get_by_id.return_value = _cohorte()
    service.cuatrimestre_repo.exists_numero.return_value = False
    service.cuatrimestre_repo.create.return_value = _cuatrimestre(numero=3)

    result = await service.crear_cuatrimestre(1, CuatrimestreCreate(numero=3))

    assert result.numero == 3
    service.cuatrimestre_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_actualizar_cuatrimestre_numero_duplicado_lanza_409():
    service = _make_service()
    service.cuatrimestre_repo.get_by_id.return_value = _cuatrimestre(numero=1)
    service.cuatrimestre_repo.exists_numero.return_value = True

    with pytest.raises(HTTPException) as exc:
        await service.actualizar_cuatrimestre(1, CuatrimestreUpdate(numero=2))

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_eliminar_cuatrimestre_con_materias_lanza_409():
    service = _make_service()
    service.cuatrimestre_repo.get_by_id.return_value = _cuatrimestre()
    service.cuatrimestre_repo.count_materias.return_value = 2

    with pytest.raises(HTTPException) as exc:
        await service.eliminar_cuatrimestre(1)

    assert exc.value.status_code == 409
    service.cuatrimestre_repo.delete.assert_not_called()
