"""
Fase 0 multi-tenant: `usuarios.es_superadmin` (flag de admin global) y
convivencia de los campos viejos de Usuario.

Ref: openspec/changes/multi-tenant-modelo-datos/specs/usuario-universidad-membresia/spec.md
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def test_es_superadmin_existe_como_boolean_not_null_default_false():
    from app.models.usuario import Usuario

    col = Usuario.__table__.columns["es_superadmin"]
    assert col.nullable is False
    assert str(col.server_default.arg).strip("'\"") in ("false", "0")


def test_los_campos_viejos_siguen_presentes():
    from app.models.usuario import Usuario

    cols = {c.name for c in Usuario.__table__.columns}
    assert {"rol", "moodle_username", "moodle_password_encrypted", "moodle_host"} <= cols


@pytest_asyncio.fixture
async def db_session():
    from app.models.base import Base
    from app.models.usuario import Usuario

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Usuario.__table__])
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_usuario_nuevo_queda_con_es_superadmin_false(db_session):
    from app.models.enums import RolEnum
    from app.models.usuario import Usuario

    u = Usuario(username="tutor1", nombre="Tutor Uno", password_hash="x", rol=RolEnum.TUTOR)
    db_session.add(u)
    await db_session.commit()

    assert u.es_superadmin is False


@pytest.mark.asyncio
async def test_usuario_puede_marcarse_como_superadmin_explicitamente(db_session):
    from app.models.enums import RolEnum
    from app.models.usuario import Usuario

    u = Usuario(
        username="admin1",
        nombre="Admin Uno",
        password_hash="x",
        rol=RolEnum.ADMIN,
        es_superadmin=True,
    )
    db_session.add(u)
    await db_session.commit()

    assert u.es_superadmin is True
