"""
CRUD-016: el conteo de comisiones activas del listado de materias se hace con una
query agregada (func.count + GROUP BY), no materializando la colección
materia.comisiones (lazy=selectin) de cada materia solo para contarla.
"""

import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

UNIV_ID = 1  # multi-tenant-scoping-queries: universidad_id ahora NOT NULL


sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)


@compiles(JSONB, "sqlite")
def _j(e, c, **k):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _a(e, c, **k):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    from app.models.base import Base
    from app.models.comision import Comision
    from app.models.materia import Materia

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[Materia.__table__, Comision.__table__]
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_contar_comisiones_activas_por_materia(db_session):
    from app.models.comision import Comision
    from app.models.materia import Materia
    from app.repositories.comision_repository import ComisionRepository

    m1 = Materia(universidad_id=UNIV_ID, nombre="M1", codigo="M1")
    m2 = Materia(universidad_id=UNIV_ID, nombre="M2", codigo="M2")
    db_session.add_all([m1, m2])
    await db_session.flush()
    db_session.add_all([
        Comision(universidad_id=UNIV_ID, materia_id=m1.id, nombre="A", anio=2026, activa=True),
        Comision(universidad_id=UNIV_ID, materia_id=m1.id, nombre="B", anio=2026, activa=True),
        Comision(universidad_id=UNIV_ID, materia_id=m1.id, nombre="C", anio=2026, activa=False),  # inactiva no cuenta
        Comision(universidad_id=UNIV_ID, materia_id=m2.id, nombre="D", anio=2026, activa=True),
    ])
    await db_session.commit()

    repo = ComisionRepository(db_session)
    counts = await repo.contar_comisiones_activas_por_materia([m1.id, m2.id])
    assert counts.get(m1.id) == 2   # solo las activas
    assert counts.get(m2.id) == 1


@pytest.mark.asyncio
async def test_lista_vacia_devuelve_dict_vacio(db_session):
    from app.repositories.comision_repository import ComisionRepository

    repo = ComisionRepository(db_session)
    assert await repo.contar_comisiones_activas_por_materia([]) == {}


@pytest.mark.asyncio
async def test_service_usa_el_conteo_agregado():
    """listar_materias no debe contar sobre materia.comisiones."""
    from app.services.materia_service import MateriaService

    svc = MateriaService.__new__(MateriaService)
    # materia.comisiones lanzaría si se accediera (no debe accederse para contar).
    materia = SimpleNamespace(
        id=1, codigo="M1", nombre="M1", activa=True,
        created_at=__import__("datetime").datetime(2026,1,1),
    )
    svc.materia_repo = SimpleNamespace(
        get_all=AsyncMock(return_value=([materia], 1))
    )
    svc.coord_materia_repo = SimpleNamespace(
        contar_por_materias=AsyncMock(return_value={1: 3})
    )
    svc.comision_repo = SimpleNamespace(
        contar_comisiones_activas_por_materia=AsyncMock(return_value={1: 5})
    )
    resp = await svc.listar_materias()
    svc.comision_repo.contar_comisiones_activas_por_materia.assert_awaited_once_with([1])
    assert resp.items[0].num_comisiones == 5
