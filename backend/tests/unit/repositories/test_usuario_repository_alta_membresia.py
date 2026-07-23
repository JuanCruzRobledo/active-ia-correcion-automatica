"""Fase 6 multi-tenant (multi-tenant-cleanup-rol-global, D4, tareas 2.1/2.3/2.5).

`create_con_membresia`: alta atómica de Usuario + UsuarioUniversidad.
`update_rol_membresia`: el cambio de rol afecta SÓLO la membresía activa en
la universidad indicada.
"""

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad
from app.repositories.usuario_repository import UsuarioRepository
from tests.helpers.usuario_membresia import crear_universidad, crear_usuario_con_membresia


# ============================== create_con_membresia: alta exitosa ==============================


@pytest.mark.asyncio
async def test_create_con_membresia_crea_usuario_y_membresia_activa(db_session):
    uni = await crear_universidad(db_session, "TUPaD")
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    user = Usuario(
        username="nuevo_tutor", nombre="Nuevo Tutor", password_hash="x"
    )
    creado = await repo.create_con_membresia(user, uni.id, RolEnum.TUTOR)

    assert creado.id is not None
    membresia = await repo.get_membresia(creado.id, uni.id)
    assert membresia is not None
    assert membresia.rol == RolEnum.TUTOR
    assert membresia.activo is True


@pytest.mark.asyncio
async def test_create_con_membresia_usuario_no_aparece_en_otra_universidad(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    user = Usuario(username="tutor_a", nombre="Tutor A", password_hash="x")
    creado = await repo.create_con_membresia(user, uni_a.id, RolEnum.TUTOR)

    usuarios_a, _ = await repo.get_all(universidad_id=uni_a.id)
    usuarios_b, _ = await repo.get_all(universidad_id=uni_b.id)

    assert creado.id in {u.id for u in usuarios_a}
    assert creado.id not in {u.id for u in usuarios_b}


# ============================== create_con_membresia: atomicidad ==============================


@pytest_asyncio.fixture
async def db_session_fk():
    """Motor propio con `PRAGMA foreign_keys=ON` — el `db_session` compartido
    de conftest no lo activa (para no afectar el resto de la suite). Acá lo
    necesitamos para poder forzar un fallo real de integridad y probar que
    el usuario NO queda creado (atomicidad, D4/tarea 2.3)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Usuario.__table__, Universidad.__table__, UsuarioUniversidad.__table__],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_con_membresia_si_falla_la_membresia_no_queda_usuario_creado(db_session_fk):
    """`universidad_id` inexistente ⇒ FK viola al hacer commit de la
    membresía ⇒ la transacción entera se revierte ⇒ el Usuario tampoco queda."""
    repo = UsuarioRepository(db_session_fk)
    user = Usuario(
        username="usuario_huerfano", nombre="X", password_hash="x"
    )

    with pytest.raises(Exception):
        await repo.create_con_membresia(user, universidad_id=99999, rol=RolEnum.TUTOR)

    await db_session_fk.rollback()
    result = await db_session_fk.execute(
        select(Usuario).where(Usuario.username == "usuario_huerfano")
    )
    assert result.scalar_one_or_none() is None


# ============================== update_rol_membresia ==============================


@pytest.mark.asyncio
async def test_update_rol_membresia_afecta_solo_la_universidad_activa(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    membresia_b = UsuarioUniversidad(
        usuario_id=persona.id, universidad_id=uni_b.id, rol=RolEnum.TUTOR, activo=True
    )
    db_session.add(membresia_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    actualizada = await repo.update_rol_membresia(persona.id, uni_a.id, RolEnum.COORDINADOR)

    assert actualizada is not None
    assert actualizada.rol == RolEnum.COORDINADOR

    membresia_a = await repo.get_membresia(persona.id, uni_a.id)
    membresia_b_recargada = await repo.get_membresia(persona.id, uni_b.id)
    assert membresia_a.rol == RolEnum.COORDINADOR
    assert membresia_b_recargada.rol == RolEnum.TUTOR  # intacta


@pytest.mark.asyncio
async def test_update_rol_membresia_sin_membresia_activa_devuelve_none(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    resultado = await repo.update_rol_membresia(persona.id, uni_b.id, RolEnum.COORDINADOR)

    assert resultado is None
