"""
CRUD-014: sincronizar unidades es un UPSERT por moodle_section_id, no delete+recreate.

Antes, sincronizar BORRABA todas las unidades y las recreaba: los IDs cambiaban en
cada sync, las rúbricas quedaban desvinculadas (unidad_id=NULL) y los componentes
configurados a mano se perdían. Ahora se matchea por moodle_section_id: las que
siguen existiendo conservan su id (y sus vínculos); solo se crean las nuevas y se
borran las ausentes.
"""

import json
import sqlite3

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.componente_unidad import ComponenteUnidad
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.unidad import Unidad
from app.repositories.unidad_repository import UnidadRepository

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
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                Materia.__table__, Unidad.__table__,
                ComponenteUnidad.__table__, Rubrica.__table__,
            ],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _materia(db):
    m = Materia(nombre="M1", codigo="M1")
    db.add(m)
    await db.flush()
    return m.id


@pytest.mark.asyncio
async def test_upsert_preserva_el_id_de_las_que_siguen(db_session):
    mid = await _materia(db_session)
    repo = UnidadRepository(db_session)
    # estado inicial: sections 100 y 200
    iniciales = await repo.sincronizar(mid, [(1, 100, "U1"), (2, 200, "U2")])
    id_100 = next(u.id for u in iniciales if u.moodle_section_id == 100)

    # re-sync: 100 sigue (renombrada), 200 se va, 300 es nueva
    res = await repo.sincronizar(mid, [(1, 100, "U1 nueva"), (2, 300, "U3")])
    por_section = {u.moodle_section_id: u for u in res}

    # la unidad de section 100 CONSERVA su id (no fue recreada)
    assert por_section[100].id == id_100
    assert por_section[100].nombre == "U1 nueva"   # actualizada in place
    assert 300 in por_section                       # nueva creada
    assert 200 not in por_section                   # ausente borrada


@pytest.mark.asyncio
async def test_upsert_renumerar_sin_violar_unique(db_session):
    """Intercambiar números (1<->2) no debe chocar con UNIQUE(materia_id, numero)."""
    mid = await _materia(db_session)
    repo = UnidadRepository(db_session)
    await repo.sincronizar(mid, [(1, 100, "A"), (2, 200, "B")])

    # swap: section 100 pasa a numero 2, section 200 a numero 1
    res = await repo.sincronizar(mid, [(2, 100, "A"), (1, 200, "B")])
    por_section = {u.moodle_section_id: u for u in res}
    assert por_section[100].numero == 2
    assert por_section[200].numero == 1


@pytest.mark.asyncio
async def test_upsert_solo_crea_las_nuevas(db_session):
    mid = await _materia(db_session)
    repo = UnidadRepository(db_session)
    await repo.sincronizar(mid, [(1, 100, "A")])
    res = await repo.sincronizar(mid, [(1, 100, "A"), (2, 200, "B")])
    assert {u.moodle_section_id for u in res} == {100, 200}
