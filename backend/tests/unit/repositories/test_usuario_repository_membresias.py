"""
Fase 1 multi-tenant (multi-tenant-auth-jwt): `UsuarioRepository.get_membresias_activas`
y `get_membresia` — únicos puntos de acceso a `usuario_universidad` desde el
`AuthService` (ARCH-001: el service nunca ejecuta SQLAlchemy directo).

La relationship `Usuario.universidades` es `lazy="raise"`: estos métodos deben
usar `select(...).options(selectinload(...))` explícito, nunca navegar el
objeto `Usuario` directamente.

Ref: openspec/changes/multi-tenant-auth-jwt/design.md (D7)
Ref: openspec/changes/multi-tenant-auth-jwt/tasks.md (2.1-2.4)
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad
from app.repositories.usuario_repository import UsuarioRepository


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Usuario.__table__, Universidad.__table__, UsuarioUniversidad.__table__],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _crear_usuario(db, username="tutor1") -> Usuario:
    u = Usuario(username=username, nombre="Tutor Uno", password_hash="x", rol=RolEnum.TUTOR)
    db.add(u)
    await db.flush()
    return u


async def _crear_universidad(db, nombre="TUPaD", activa=True) -> Universidad:
    uni = Universidad(nombre=nombre, activa=activa)
    db.add(uni)
    await db.flush()
    return uni


async def _crear_membresia(
    db, usuario: Usuario, universidad: Universidad, rol=RolEnum.TUTOR, activo=True
) -> UsuarioUniversidad:
    m = UsuarioUniversidad(
        usuario_id=usuario.id, universidad_id=universidad.id, rol=rol, activo=activo
    )
    db.add(m)
    await db.flush()
    return m


# ============================== get_membresias_activas ==============================


@pytest.mark.asyncio
async def test_get_membresias_activas_solo_devuelve_activas_con_universidad_activa(db_session):
    usuario = await _crear_usuario(db_session)
    uni_ok = await _crear_universidad(db_session, "TUPaD")
    uni_membresia_inactiva = await _crear_universidad(db_session, "Otra A")
    uni_inactiva = await _crear_universidad(db_session, "Otra B", activa=False)

    await _crear_membresia(db_session, usuario, uni_ok, rol=RolEnum.COORDINADOR)
    await _crear_membresia(db_session, usuario, uni_membresia_inactiva, activo=False)
    await _crear_membresia(db_session, usuario, uni_inactiva)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    membresias = await repo.get_membresias_activas(usuario.id)

    assert len(membresias) == 1
    assert membresias[0].universidad_id == uni_ok.id
    assert membresias[0].rol == RolEnum.COORDINADOR


@pytest.mark.asyncio
async def test_get_membresias_activas_carga_la_universidad_sin_lazy_raise(db_session):
    """La Universidad debe venir precargada (selectinload), no navegada de forma
    perezosa — eso dispararía el lazy='raise' de la relationship."""
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session, "TUPaD")
    await _crear_membresia(db_session, usuario, uni)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    membresias = await repo.get_membresias_activas(usuario.id)

    assert len(membresias) == 1
    # Acceder a .universidad.nombre no debe lanzar (ya está cargada).
    assert membresias[0].universidad.nombre == "TUPaD"


@pytest.mark.asyncio
async def test_get_membresias_activas_usuario_sin_membresias_devuelve_lista_vacia(db_session):
    usuario = await _crear_usuario(db_session)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    membresias = await repo.get_membresias_activas(usuario.id)

    assert membresias == []


# ==================================== get_membresia ====================================


@pytest.mark.asyncio
async def test_get_membresia_devuelve_la_membresia_activa(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni, rol=RolEnum.ADMIN)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    m = await repo.get_membresia(usuario.id, uni.id)

    assert m is not None
    assert m.rol == RolEnum.ADMIN


@pytest.mark.asyncio
async def test_get_membresia_par_inexistente_devuelve_none(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    m = await repo.get_membresia(usuario.id, uni.id)

    assert m is None


@pytest.mark.asyncio
async def test_get_membresia_con_activo_false_devuelve_none(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni, activo=False)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    m = await repo.get_membresia(usuario.id, uni.id)

    assert m is None


@pytest.mark.asyncio
async def test_get_membresia_con_universidad_inactiva_devuelve_none(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session, activa=False)
    await _crear_membresia(db_session, usuario, uni)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    m = await repo.get_membresia(usuario.id, uni.id)

    assert m is None
