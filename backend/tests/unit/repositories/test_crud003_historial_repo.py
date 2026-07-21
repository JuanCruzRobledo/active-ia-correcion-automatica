"""
CRUD-003 (Fase 2): repositorio del historial de correcciones.

- CorreccionHistorialRepository.create / list_by_entrega (ordenado desc, sin
  arrastrar raw_response deferred).
- CorreccionRepository.get_by_entrega_id(load_raw=True): trae la corrección vigente
  CON raw_response undeferred, para poder snapshotear el crudo ANTES del delete
  (si se lee despues del delete -> DetachedInstanceError).
"""

import json
import sqlite3
from datetime import datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)


@compiles(JSONB, "sqlite")
def _jsonb(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array(element, compiler, **kw):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    from app.models.base import Base
    from app.models.correccion import Correccion, CorreccionHistorial
    from app.models.entrega import Entrega
    from app.models.usuario import Usuario

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                Usuario.__table__, Entrega.__table__,
                Correccion.__table__, CorreccionHistorial.__table__,
            ],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


def _snapshot(entrega_id, nota, reemplazada_en, *, raw=None):
    from app.models.correccion import CorreccionHistorial

    return CorreccionHistorial(
        entrega_id=entrega_id,
        nota=Decimal(str(nota)),
        criterios_json={"criterios": []},
        editado_manualmente=False,
        raw_response=raw,
        correccion_creada_en=datetime(2026, 5, 1),
        reemplazada_en=reemplazada_en,
    )


# ===================== CorreccionHistorialRepository =====================


@pytest.mark.asyncio
async def test_create_persiste_snapshot(db_session):
    from app.repositories.correccion_historial_repository import (
        CorreccionHistorialRepository,
    )

    repo = CorreccionHistorialRepository(db_session)
    h = await repo.create(_snapshot(1, 80, datetime(2026, 6, 1)))
    assert h.id is not None
    assert h.nota == Decimal("80.00")


@pytest.mark.asyncio
async def test_list_by_entrega_ordena_por_reemplazada_desc(db_session):
    from app.repositories.correccion_historial_repository import (
        CorreccionHistorialRepository,
    )

    repo = CorreccionHistorialRepository(db_session)
    await repo.create(_snapshot(1, 70, datetime(2026, 6, 1)))   # vieja
    await repo.create(_snapshot(1, 85, datetime(2026, 6, 10)))  # mas reciente
    await repo.create(_snapshot(2, 50, datetime(2026, 6, 5)))   # otra entrega

    versiones = await repo.list_by_entrega(1)
    assert [float(v.nota) for v in versiones] == [85.0, 70.0]  # DESC por reemplazada_en


@pytest.mark.asyncio
async def test_list_by_entrega_no_carga_raw_response(db_session):
    from app.repositories.correccion_historial_repository import (
        CorreccionHistorialRepository,
    )

    repo = CorreccionHistorialRepository(db_session)
    await repo.create(_snapshot(1, 80, datetime(2026, 6, 1), raw={"gemini": "x"}))

    versiones = await repo.list_by_entrega(1)
    # raw_response es deferred: no debe venir cargada en el listado.
    assert "raw_response" in inspect(versiones[0]).unloaded


@pytest.mark.asyncio
async def test_list_by_entrega_vacio(db_session):
    from app.repositories.correccion_historial_repository import (
        CorreccionHistorialRepository,
    )

    repo = CorreccionHistorialRepository(db_session)
    assert await repo.list_by_entrega(999) == []


# ===================== CorreccionRepository.get_by_entrega_id(load_raw=True) ====


async def _mk_correccion(db, entrega_id=1, raw=None):
    from app.models.correccion import Correccion

    c = Correccion(
        entrega_id=entrega_id,
        nota=Decimal("90.00"),
        criterios_json={"criterios": []},
        raw_response=raw,
    )
    db.add(c)
    await db.commit()
    return c


@pytest.mark.asyncio
async def test_get_by_entrega_id_load_raw_trae_el_crudo(db_session):
    from app.repositories.correccion_repository import CorreccionRepository

    await _mk_correccion(db_session, 1, raw={"gemini": "respuesta cruda"})
    db_session.expire_all()  # forzar recarga como si fuera un request nuevo

    repo = CorreccionRepository(db_session)
    c = await repo.get_by_entrega_id(1, load_raw=True)
    # Con load_raw=True el crudo viene cargado (no es un atributo diferido pendiente).
    assert "raw_response" not in inspect(c).unloaded
    assert c.raw_response == {"gemini": "respuesta cruda"}


@pytest.mark.asyncio
async def test_get_by_entrega_id_sin_load_raw_deja_raw_diferido(db_session):
    from app.repositories.correccion_repository import CorreccionRepository

    await _mk_correccion(db_session, 1, raw={"gemini": "x"})
    db_session.expire_all()

    repo = CorreccionRepository(db_session)
    c = await repo.get_by_entrega_id(1)  # default load_raw=False
    assert "raw_response" in inspect(c).unloaded  # sigue diferido
