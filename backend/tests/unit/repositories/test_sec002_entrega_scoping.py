"""
SEC-002: scoping por pertenencia en el listado de entregas.

`GET /entregas/` sin `comision_id` devolvia entregas de TODAS las comisiones.
Aca no aplica un 403 (el endpoint es legitimo): hay que FILTRAR.

El filtro entra en la lista `conditions` que get_all ya comparte entre la query
de datos y la del count, asi el total paginado NO revela la cantidad global.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.entrega_repository import EntregaRepository


def _db_listado(filas=(), total=0):
    """db async para get_all: 1a llamada = count, 2a = data."""
    db = AsyncMock()

    count_res = MagicMock()
    count_res.scalar.return_value = total

    data_res = MagicMock()
    data_res.scalars.return_value.all.return_value = list(filas)

    db.execute.side_effect = [count_res, data_res]
    return db


def _sql(db, i):
    return str(db.execute.call_args_list[i].args[0])


@pytest.mark.asyncio
async def test_scoping_filtra_datos_y_count_con_las_mismas_comisiones():
    db = _db_listado()
    await EntregaRepository(db).get_all(comisiones_visibles=[10, 11])

    count_sql, data_sql = _sql(db, 0), _sql(db, 1)
    # El filtro tiene que estar en LAS DOS queries: si el count no lo tuviera,
    # el total paginado revelaria cuantas entregas hay en todo el sistema.
    assert "comision_id IN" in count_sql
    assert "comision_id IN" in data_sql


@pytest.mark.asyncio
async def test_sin_scoping_no_agrega_filtro_de_comision():
    """None = ADMIN: sin filtro, ve todo."""
    db = _db_listado()
    await EntregaRepository(db).get_all(comisiones_visibles=None)

    assert "comision_id IN" not in _sql(db, 0)
    assert "comision_id IN" not in _sql(db, 1)


@pytest.mark.asyncio
async def test_lista_vacia_de_comisiones_no_devuelve_nada():
    """Un usuario sin asignaciones no ve entregas. No es un bug: es el scoping."""
    db = _db_listado()
    await EntregaRepository(db).get_all(comisiones_visibles=[])

    # SQLAlchemy compila `IN ()` como una condicion siempre falsa.
    assert "comision_id IN" in _sql(db, 0)
    assert "comision_id IN" in _sql(db, 1)


@pytest.mark.asyncio
async def test_scoping_convive_con_los_demas_filtros():
    db = _db_listado()
    await EntregaRepository(db).get_all(
        comisiones_visibles=[10],
        rubrica_id=3,
        search="perez",
    )

    count_sql = _sql(db, 0)
    assert "comision_id IN" in count_sql
    assert "rubrica_id" in count_sql
    assert "lower" in count_sql.lower() or "ilike" in count_sql.lower()


# ===================== get_all_for_export (PERF-009) =====================


@pytest.mark.asyncio
async def test_export_propaga_el_scoping_a_get_all():
    """
    PUERTA TRASERA: get_all_for_export reutiliza get_all internamente y alimenta
    el Excel de notas. Si no propagara el scoping, el export seria un camino
    alternativo para leer entregas ajenas, salteando el filtro del listado.
    """
    repo = EntregaRepository(AsyncMock())
    repo.get_all = AsyncMock(return_value=([], 0))

    await repo.get_all_for_export(comision_id=10, comisiones_visibles=[10, 11])

    assert repo.get_all.await_args.kwargs["comisiones_visibles"] == [10, 11]


@pytest.mark.asyncio
async def test_export_sin_scoping_propaga_none():
    repo = EntregaRepository(AsyncMock())
    repo.get_all = AsyncMock(return_value=([], 0))

    await repo.get_all_for_export(comision_id=10)

    assert repo.get_all.await_args.kwargs["comisiones_visibles"] is None
