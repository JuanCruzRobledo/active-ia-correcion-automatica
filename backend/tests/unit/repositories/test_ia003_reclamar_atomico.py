"""
IA-003: reclamo atómico del estado para no disparar dos correcciones (dos llamadas
al LLM) sobre la misma entrega. Un doble click / retry / lote con una entrega ya en
curso disparaba dos requests a Gemini; la carrera recién se resolvía al insertar
(unique de correccion.entrega_id) DESPUÉS de pagar los dos.

reclamar_para_correccion hace UPDATE ... WHERE estado != 'PENDIENTE' RETURNING: el
primero gana (estado -> PENDIENTE), el segundo no matchea -> False -> el service da 409.
"""

import json
import sqlite3

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.comision import Comision
from app.models.entrega import Entrega, EntregaHistorial
from app.models.enums import EstadoEntregaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.repositories.entrega_repository import EntregaRepository

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
            tables=[Materia.__table__, Comision.__table__, Rubrica.__table__,
                    Entrega.__table__, EntregaHistorial.__table__],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _entrega(db, estado=EstadoEntregaEnum.SUBIDA):
    m = Materia(nombre="M", codigo="M")
    db.add(m)
    await db.flush()
    c = Comision(materia_id=m.id, nombre="C", anio=2026, activa=True)
    db.add(c)
    await db.flush()
    e = Entrega(comision_id=c.id, rubrica_id=1, alumno_nombre="A",
                archivo_nombre="a.py", archivo_tipo="individual", estado=estado)
    db.add(e)
    await db.commit()
    return e


@pytest.mark.asyncio
async def test_reclamar_desde_subida_gana_y_deja_pendiente(db_session):
    e = await _entrega(db_session, EstadoEntregaEnum.SUBIDA)
    repo = EntregaRepository(db_session)
    assert await repo.reclamar_para_correccion(e.id) is True
    refreshed = await repo.get_by_id(e.id)
    assert refreshed.estado == EstadoEntregaEnum.PENDIENTE


@pytest.mark.asyncio
async def test_reclamar_sobre_pendiente_falla(db_session):
    """El segundo intento (ya en curso) no reclama -> False."""
    e = await _entrega(db_session, EstadoEntregaEnum.PENDIENTE)
    repo = EntregaRepository(db_session)
    assert await repo.reclamar_para_correccion(e.id) is False


@pytest.mark.asyncio
async def test_reclamar_desde_corregida_permite_recorregir(db_session):
    """Recorregir una CORREGIDA es legítimo (secuencial), no una carrera."""
    e = await _entrega(db_session, EstadoEntregaEnum.CORREGIDA)
    repo = EntregaRepository(db_session)
    assert await repo.reclamar_para_correccion(e.id) is True


@pytest.mark.asyncio
async def test_reclamar_dos_veces_seguidas_solo_una_gana(db_session):
    e = await _entrega(db_session, EstadoEntregaEnum.SUBIDA)
    repo = EntregaRepository(db_session)
    primero = await repo.reclamar_para_correccion(e.id)
    segundo = await repo.reclamar_para_correccion(e.id)
    assert primero is True and segundo is False
