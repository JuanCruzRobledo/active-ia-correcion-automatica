"""
CRUD-003: modelo CorreccionHistorial — snapshot de la corrección reemplazada.

Verifica el mapeo (columnas, entrega_id indexado, raw_response deferred) contra
el shim SQLite (@compiles JSONB/ARRAY), y el nuevo tipo de auditoría.
"""

import json
import sqlite3

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# sqlite3 no sabe bindear dict/list (JSONB/ARRAY); estos adapters los serializan a JSON.
sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)


@compiles(JSONB, "sqlite")
def _jsonb(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array(element, compiler, **kw):  # noqa: D401
    return "JSON"


def test_correccion_historial_tiene_las_columnas_del_snapshot():
    from app.models.correccion import CorreccionHistorial

    cols = {c.name for c in CorreccionHistorial.__table__.columns}
    esperadas = {
        "id", "entrega_id", "nota", "criterios_json", "fortalezas",
        "recomendaciones", "comentario_general", "nota_antes_penalizaciones",
        "condicion_desaprobacion_aplicada", "penalizaciones_aplicadas",
        "editado_manualmente", "raw_response", "corregido_por_id",
        "correccion_creada_en", "reemplazada_en", "reemplazada_por_id",
    }
    assert esperadas <= cols


def test_entrega_id_esta_indexado():
    from app.models.correccion import CorreccionHistorial

    assert CorreccionHistorial.__table__.columns["entrega_id"].index is True


def test_raw_response_es_deferred():
    from app.models.correccion import CorreccionHistorial

    mapper = inspect(CorreccionHistorial)
    assert mapper.attrs["raw_response"].deferred is True


def test_tipo_de_actividad_recorregida_existe():
    from app.models.enums import TipoActividadEnum

    assert TipoActividadEnum.CORRECCION_RECORREGIDA.value == "CORRECCION_RECORREGIDA"


@pytest_asyncio.fixture
async def db_session():
    from app.models.base import Base
    from app.models.correccion import CorreccionHistorial
    from app.models.entrega import Entrega
    from app.models.usuario import Usuario

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Usuario.__table__, Entrega.__table__, CorreccionHistorial.__table__],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_persistir_un_snapshot(db_session):
    from decimal import Decimal

    from app.models.correccion import CorreccionHistorial

    h = CorreccionHistorial(
        entrega_id=1,
        nota=Decimal("80.00"),
        criterios_json={"criterios": []},
        editado_manualmente=True,
        correccion_creada_en=__import__("datetime").datetime(2026, 6, 1),
    )
    db_session.add(h)
    await db_session.commit()
    assert h.id is not None
    assert h.editado_manualmente is True
