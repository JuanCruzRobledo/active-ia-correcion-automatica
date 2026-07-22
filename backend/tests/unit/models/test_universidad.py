"""
Fase 0 multi-tenant: modelo `Universidad` — tenant de primer nivel.

Ref: openspec/changes/multi-tenant-modelo-datos/specs/universidad-entidad/spec.md
"""

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def test_universidad_tiene_las_columnas_esperadas():
    from app.models.universidad import Universidad

    cols = {c.name for c in Universidad.__table__.columns}
    esperadas = {"id", "nombre", "moodle_host", "activa", "created_at", "updated_at"}
    assert esperadas <= cols


def test_nombre_es_unique_y_not_null():
    from app.models.universidad import Universidad

    nombre_col = Universidad.__table__.columns["nombre"]
    assert nombre_col.nullable is False
    assert nombre_col.unique is True or any(
        nombre_col.name in uc.columns.keys()
        for uc in Universidad.__table__.constraints
        if uc.__class__.__name__ == "UniqueConstraint"
    )


def test_moodle_host_es_nullable():
    from app.models.universidad import Universidad

    assert Universidad.__table__.columns["moodle_host"].nullable is True


def test_activa_default_true():
    from app.models.universidad import Universidad

    activa_col = Universidad.__table__.columns["activa"]
    assert activa_col.nullable is False
    assert str(activa_col.server_default.arg).strip("'\"") in ("true", "1")


@pytest_asyncio.fixture
async def db_session():
    from app.models.base import Base
    from app.models.universidad import Universidad

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Universidad.__table__])
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_se_puede_crear_una_universidad_sin_moodle_host(db_session):
    from app.models.universidad import Universidad

    u = Universidad(nombre="TUPaD")
    db_session.add(u)
    await db_session.commit()

    assert u.id is not None
    assert u.moodle_host is None
    assert u.activa is True


@pytest.mark.asyncio
async def test_dos_universidades_no_pueden_compartir_nombre(db_session):
    from app.models.universidad import Universidad

    db_session.add(Universidad(nombre="TUPaD"))
    await db_session.commit()

    db_session.add(Universidad(nombre="TUPaD"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
