"""
CRUD-011: cuando un Create choca con un registro SOFT-DELETED, el 409 debe decir
explicitamente que el conflicto es contra un registro eliminado y ofrecer
restaurarlo, en vez del generico "ya existe" (que confunde: el registro no aparece
en el listado, asi que para el usuario el codigo/nombre esta "libre").
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.comision_service import ComisionService
from app.services.materia_service import MateriaService
from app.services.rubrica_service import RubricaService


# ===================== materia (codigo) =====================


def _materia_svc(conflicto):
    svc = MateriaService.__new__(MateriaService)
    svc.materia_repo = SimpleNamespace(get_by_codigo=AsyncMock(return_value=conflicto))
    return svc


@pytest.mark.asyncio
async def test_materia_conflicto_con_eliminada_menciona_borrado_y_id():
    borrada = SimpleNamespace(id=7, activa=False)
    svc = _materia_svc(borrada)
    with pytest.raises(HTTPException) as exc:
        await svc.crear_materia(SimpleNamespace(codigo="prog1", coordinador_ids=None), universidad_id=1)
    assert exc.value.status_code == 409
    assert "eliminada" in exc.value.detail.lower()
    assert "7" in exc.value.detail


@pytest.mark.asyncio
async def test_materia_conflicto_con_activa_mensaje_normal():
    activa = SimpleNamespace(id=3, activa=True)
    svc = _materia_svc(activa)
    with pytest.raises(HTTPException) as exc:
        await svc.crear_materia(SimpleNamespace(codigo="prog1", coordinador_ids=None), universidad_id=1)
    assert exc.value.status_code == 409
    assert "eliminada" not in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_materia_sin_conflicto_no_lanza_409():
    svc = _materia_svc(None)
    svc.usuario_repo = SimpleNamespace()
    svc.materia_repo.create = AsyncMock(side_effect=RuntimeError("llego a create"))
    # Sin conflicto, avanza mas alla del chequeo (y explota en create, que no mockeamos
    # del todo): lo que importa es que NO fue un 409 de conflicto.
    with pytest.raises(Exception) as exc:
        await svc.crear_materia(SimpleNamespace(codigo="nueva", coordinador_ids=None), universidad_id=1)
    assert not (isinstance(exc.value, HTTPException) and exc.value.status_code == 409)


# ===================== comision (materia+nombre+anio) =====================


@pytest.mark.asyncio
async def test_comision_conflicto_con_eliminada_menciona_borrado():
    borrada = SimpleNamespace(id=12, activa=False)
    svc = ComisionService.__new__(ComisionService)
    svc.materia_repo = SimpleNamespace(get_active_by_id=AsyncMock(return_value=SimpleNamespace(id=1, universidad_id=1)))
    svc.comision_repo = SimpleNamespace(
        get_by_materia_nombre_anio=AsyncMock(return_value=borrada)
    )
    data = SimpleNamespace(materia_id=1, nombre="C1", anio=2026)
    with pytest.raises(HTTPException) as exc:
        await svc.crear_comision(data)
    assert exc.value.status_code == 409
    assert "eliminada" in exc.value.detail.lower()
    assert "12" in exc.value.detail


@pytest.mark.asyncio
async def test_comision_conflicto_con_activa_mensaje_normal():
    activa = SimpleNamespace(id=4, activa=True)
    svc = ComisionService.__new__(ComisionService)
    svc.materia_repo = SimpleNamespace(get_active_by_id=AsyncMock(return_value=SimpleNamespace(id=1, universidad_id=1)))
    svc.comision_repo = SimpleNamespace(
        get_by_materia_nombre_anio=AsyncMock(return_value=activa)
    )
    data = SimpleNamespace(materia_id=1, nombre="C1", anio=2026)
    with pytest.raises(HTTPException) as exc:
        await svc.crear_comision(data)
    assert exc.value.status_code == 409
    assert "eliminada" not in exc.value.detail.lower()


# ===================== rubrica (materia+tipo+numero+anio) =====================


@pytest.mark.asyncio
async def test_rubrica_conflicto_con_eliminada_menciona_borrado():
    borrada = SimpleNamespace(id=20, activa=False)
    svc = RubricaService.__new__(RubricaService)
    svc._validar_acceso_materia = AsyncMock()
    svc.materia_repo = SimpleNamespace(get_active_by_id=AsyncMock(return_value=SimpleNamespace(id=1, universidad_id=1)))
    svc.rubrica_repo = SimpleNamespace(
        get_by_materia_tipo_numero=AsyncMock(return_value=borrada)
    )
    data = SimpleNamespace(
        materia_id=1, tipo=SimpleNamespace(value="TP"), numero=1, anio=2026
    )
    with pytest.raises(HTTPException) as exc:
        await svc.crear_rubrica(data, current_user=object())
    assert exc.value.status_code == 409
    assert "eliminada" in exc.value.detail.lower()
    assert "20" in exc.value.detail


@pytest.mark.asyncio
async def test_rubrica_conflicto_con_activa_mensaje_normal():
    activa = SimpleNamespace(id=5, activa=True)
    svc = RubricaService.__new__(RubricaService)
    svc._validar_acceso_materia = AsyncMock()
    svc.materia_repo = SimpleNamespace(get_active_by_id=AsyncMock(return_value=SimpleNamespace(id=1, universidad_id=1)))
    svc.rubrica_repo = SimpleNamespace(
        get_by_materia_tipo_numero=AsyncMock(return_value=activa)
    )
    data = SimpleNamespace(
        materia_id=1, tipo=SimpleNamespace(value="TP"), numero=1, anio=2026
    )
    with pytest.raises(HTTPException) as exc:
        await svc.crear_rubrica(data, current_user=object())
    assert exc.value.status_code == 409
    assert "eliminada" not in exc.value.detail.lower()
