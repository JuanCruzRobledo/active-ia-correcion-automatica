"""
ARCH-001 (rebanada Datos): las queries de Moodle que vivían crudas en
moodle_service / moodle_import_service se extrajeron a métodos de repo. Estos
tests ejercitan esos métodos contra SQLite real, fijando los filtros:
- comisiones: activas + moodle_group_id + del tutor (+ scope opcional)
- rúbricas: activas + moodle_assign_id de las materias dadas (+ rubrica_id opcional)
- materias: por lista de ids
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
from app.models.comision import Comision, ComisionTutor
from app.models.enums import TipoRubricaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.repositories.comision_repository import ComisionRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.rubrica_repository import RubricaRepository

sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)


@compiles(JSONB, "sqlite")
def _j(e, c, **k):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _a(e, c, **k):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        # Con el shim de JSONB/ARRAY registrado arriba, todas las tablas compilan
        # en SQLite. Creamos todas para cubrir las relaciones lazy="selectin"
        # (Materia -> unidades/examenes/coordinadores/comisiones, etc.).
        await conn.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _materia(db, id_, nombre="M"):
    m = Materia(id=id_, nombre=nombre, codigo=f"C{id_}")
    db.add(m)
    await db.flush()
    return m


async def _comision(db, id_, materia_id, *, activa=True, moodle_group_id=10, tutor_id=5):
    c = Comision(id=id_, materia_id=materia_id, nombre=f"Com{id_}", anio=2026,
                 activa=activa, moodle_group_id=moodle_group_id)
    db.add(c)
    await db.flush()
    if tutor_id is not None:
        db.add(ComisionTutor(comision_id=id_, tutor_id=tutor_id))
    await db.flush()
    return c


async def _rubrica(db, id_, materia_id, *, activa=True, moodle_assign_id=99):
    r = Rubrica(
        id=id_, materia_id=materia_id, tipo=TipoRubricaEnum.TP, numero=id_, anio=2026,
        titulo=f"R{id_}", descripcion="d", puntaje_maximo=100, metadata_json={},
        criterios_json=[], penalizaciones_json=[], condiciones_desaprobacion_json=[],
        activa=activa, moodle_assign_id=moodle_assign_id,
    )
    db.add(r)
    await db.flush()
    return r


# ------------------------------------------------- Comision

@pytest.mark.asyncio
async def test_comision_moodle_filtra_activa_group_y_tutor(db):
    await _materia(db, 1)
    await _comision(db, 1, 1, activa=True, moodle_group_id=10, tutor_id=5)   # OK
    await _comision(db, 2, 1, activa=False, moodle_group_id=10, tutor_id=5)  # inactiva
    await _comision(db, 3, 1, activa=True, moodle_group_id=None, tutor_id=5)  # sin group
    await _comision(db, 4, 1, activa=True, moodle_group_id=10, tutor_id=99)  # otro tutor
    await db.commit()

    res = await ComisionRepository(db).get_moodle_habilitadas_de_tutor(5)
    assert {c.id for c in res} == {1}


@pytest.mark.asyncio
async def test_comision_moodle_scope_por_comision_y_materia(db):
    await _materia(db, 1)
    await _materia(db, 2)
    await _comision(db, 1, 1, tutor_id=5)
    await _comision(db, 2, 2, tutor_id=5)
    await db.commit()
    repo = ComisionRepository(db)

    solo1 = await repo.get_moodle_habilitadas_de_tutor(5, comision_id=1)
    assert {c.id for c in solo1} == {1}
    mat2 = await repo.get_moodle_habilitadas_de_tutor(5, materia_id=2)
    assert {c.id for c in mat2} == {2}


# ------------------------------------------------- Rubrica

@pytest.mark.asyncio
async def test_rubrica_moodle_filtra_activa_assign_y_materia(db):
    await _materia(db, 1)
    await _materia(db, 2)
    await _rubrica(db, 1, 1, activa=True, moodle_assign_id=99)   # OK
    await _rubrica(db, 2, 1, activa=False, moodle_assign_id=99)  # inactiva
    await _rubrica(db, 3, 1, activa=True, moodle_assign_id=None)  # sin assign
    await _rubrica(db, 4, 2, activa=True, moodle_assign_id=99)   # otra materia
    await db.commit()

    res = await RubricaRepository(db).get_moodle_habilitadas_por_materias([1])
    assert {r.id for r in res} == {1}


@pytest.mark.asyncio
async def test_rubrica_moodle_scope_por_rubrica(db):
    await _materia(db, 1)
    await _rubrica(db, 1, 1)
    await _rubrica(db, 2, 1)
    await db.commit()

    res = await RubricaRepository(db).get_moodle_habilitadas_por_materias([1], rubrica_id=2)
    assert {r.id for r in res} == {2}


# ------------------------------------------------- Materia

@pytest.mark.asyncio
async def test_materia_get_by_ids(db):
    await _materia(db, 1)
    await _materia(db, 2)
    await _materia(db, 3)
    await db.commit()
    repo = MateriaRepository(db)

    assert {m.id for m in await repo.get_by_ids([1, 3])} == {1, 3}
    assert await repo.get_by_ids([]) == []
