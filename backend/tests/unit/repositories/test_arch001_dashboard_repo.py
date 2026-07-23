"""
ARCH-001 (rebanada Dashboard): las queries que eran TODO dashboard_service se
extrajeron a DashboardRepository. Estos tests cubren directo (SQLite real):
- get_admin_counts: cuenta solo entidades ACTIVAS
- ruta coordinador: materia_ids + conteos filtrados por materias + progreso
La ruta tutor (detalle/conteos) ya la cubre test_perf010_tutor_stats_pendientes.
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

from app.models import (
    Comision,
    ComisionTutor,
    CoordinadorMateria,
    Entrega,
    Materia,
    Rubrica,
    Usuario,
)
from app.models.base import Base
from app.models.enums import EstadoEntregaEnum, RolEnum, TipoRubricaEnum
from app.repositories.dashboard_repository import DashboardRepository

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
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _materia(db, id_, *, activa=True):
    db.add(Materia(universidad_id=UNIV_ID, id=id_, nombre=f"M{id_}", codigo=f"C{id_}", activa=activa))
    await db.flush()


async def _comision(db, id_, materia_id, *, activa=True):
    db.add(Comision(universidad_id=UNIV_ID, id=id_, materia_id=materia_id, nombre=f"Com{id_}", anio=2026, activa=activa))
    await db.flush()


async def _rubrica(db, id_, materia_id, *, activa=True):
    db.add(Rubrica(universidad_id=UNIV_ID, 
        id=id_, materia_id=materia_id, tipo=TipoRubricaEnum.TP, numero=id_, anio=2026,
        titulo=f"R{id_}", descripcion="d", puntaje_maximo=100, metadata_json={},
        criterios_json=[], penalizaciones_json=[], condiciones_desaprobacion_json=[],
        activa=activa,
    ))
    await db.flush()


async def _usuario(db, id_, *, activo=True):
    db.add(Usuario(id=id_, username=f"u{id_}", nombre=f"U{id_}",
                   password_hash="x", rol=RolEnum.TUTOR, activo=activo))
    await db.flush()


async def _entrega(db, comision_id, estado, i):
    db.add(Entrega(universidad_id=UNIV_ID, comision_id=comision_id, rubrica_id=1, alumno_nombre=f"A{comision_id}-{i}",
                   archivo_nombre="tp.zip", archivo_tipo="zip", estado=estado))
    await db.flush()


# ------------------------------------------------------------------ admin

@pytest.mark.asyncio
async def test_admin_counts_solo_activos(db):
    await _materia(db, 1, activa=True)
    await _materia(db, 2, activa=False)
    await _comision(db, 1, 1, activa=True)
    await _comision(db, 2, 1, activa=False)
    await _usuario(db, 1, activo=True)
    await _usuario(db, 2, activo=False)
    await _rubrica(db, 1, 1, activa=True)
    await _rubrica(db, 2, 1, activa=False)
    await db.commit()

    counts = await DashboardRepository(db).get_admin_counts()
    assert counts == {"materias": 1, "comisiones": 1, "usuarios": 1, "rubricas": 1}


# ------------------------------------------------------------ coordinador

@pytest.mark.asyncio
async def test_coordinador_materia_ids_y_conteos(db):
    await _materia(db, 1)
    await _materia(db, 2)  # NO coordinada
    await _usuario(db, 10)  # coordinador
    db.add(CoordinadorMateria(coordinador_id=10, materia_id=1))
    await _comision(db, 1, 1, activa=True)
    await _comision(db, 2, 1, activa=False)  # inactiva, no cuenta
    await _comision(db, 3, 2, activa=True)   # otra materia, no cuenta
    await _rubrica(db, 1, 1, activa=True)
    await _rubrica(db, 2, 2, activa=True)    # otra materia
    await _entrega(db, 1, EstadoEntregaEnum.SUBIDA, 0)
    await _entrega(db, 1, EstadoEntregaEnum.CORREGIDA, 1)
    await db.commit()
    repo = DashboardRepository(db)

    ids = await repo.get_materia_ids_de_coordinador(10)
    assert ids == [1]
    assert await repo.contar_comisiones_activas_en_materias([1]) == 1
    assert await repo.contar_rubricas_activas_en_materias([1]) == 1
    assert await repo.contar_pendientes_en_materias([1]) == 1  # solo la SUBIDA


@pytest.mark.asyncio
async def test_progreso_por_comision_agrega_totales(db):
    await _materia(db, 1)
    await _usuario(db, 10)
    await _comision(db, 1, 1, activa=True)
    db.add(ComisionTutor(comision_id=1, tutor_id=10))
    await db.flush()
    await _entrega(db, 1, EstadoEntregaEnum.SUBIDA, 0)
    await _entrega(db, 1, EstadoEntregaEnum.CORREGIDA, 1)
    await db.commit()

    rows = await DashboardRepository(db).get_progreso_por_comision_de_materias([1])
    assert len(rows) == 1
    row = rows[0]
    assert row.id == 1
    assert row.tutor_nombre == "U10"
    assert row.total_entregas == 2
    assert row.completed_entregas == 0  # sin correcciones cargadas
