"""
Fase 3 multi-tenant (multi-tenant-moodle-services, D2): resolver único de
credenciales Moodle en la capa Repository.

`UsuarioRepository.get_credenciales_moodle(usuario_id, universidad_id)` es el
ÚNICO punto donde los services obtienen host+usuario+contraseña Moodle: lee de
la membresía activa `(usuario, universidad)` (`UsuarioUniversidad.moodle_*`) +
el `moodle_host` de su `Universidad`, NUNCA de `usuarios.moodle_*` (campo
viejo, Fase 6 lo borra). Reusa `get_membresia` (Fase 1), que ya precarga
`.universidad` (selectinload) en una sola consulta.

`update_moodle_credentials_membresia` es el nuevo write-path del perfil (D4):
escribe las credenciales en la membresía activa, no en `usuarios`.

Ref: openspec/changes/multi-tenant-moodle-services/design.md (D2, D4)
Ref: openspec/changes/multi-tenant-moodle-services/specs/moodle-credenciales-por-universidad/spec.md
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
from app.repositories.usuario_repository import CredencialesMoodle, UsuarioRepository


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
    u = Usuario(username=username, nombre="Tutor Uno", password_hash="x")
    db.add(u)
    await db.flush()
    return u


async def _crear_universidad(db, nombre="TUPaD", host="https://campus.tupad.edu", activa=True) -> Universidad:
    uni = Universidad(nombre=nombre, moodle_host=host, activa=activa)
    db.add(uni)
    await db.flush()
    return uni


async def _crear_membresia(
    db, usuario: Usuario, universidad: Universidad, *,
    rol=RolEnum.TUTOR, activo=True, username=None, password_encrypted=None,
) -> UsuarioUniversidad:
    m = UsuarioUniversidad(
        usuario_id=usuario.id, universidad_id=universidad.id, rol=rol, activo=activo,
        moodle_username=username, moodle_password_encrypted=password_encrypted,
    )
    db.add(m)
    await db.flush()
    return m


# ============================== get_credenciales_moodle ==============================


@pytest.mark.asyncio
async def test_get_credenciales_moodle_caso_feliz(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session, host="https://campus.tupad.edu")
    await _crear_membresia(
        db_session, usuario, uni, username="tutor1", password_encrypted="enc-pass"
    )
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    creds = await repo.get_credenciales_moodle(usuario.id, uni.id)

    assert creds == CredencialesMoodle(
        host="https://campus.tupad.edu",
        username="tutor1",
        password_encrypted="enc-pass",
    )


@pytest.mark.asyncio
async def test_get_credenciales_moodle_sin_membresia_devuelve_none(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    creds = await repo.get_credenciales_moodle(usuario.id, uni.id)

    assert creds is None


@pytest.mark.asyncio
async def test_get_credenciales_moodle_membresia_inactiva_devuelve_none(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(
        db_session, usuario, uni, activo=False, username="x", password_encrypted="y"
    )
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    creds = await repo.get_credenciales_moodle(usuario.id, uni.id)

    assert creds is None


@pytest.mark.asyncio
async def test_get_credenciales_moodle_host_null_devuelve_terna_con_host_vacio(db_session):
    """OP-1: el resolver NO decide el 424 — sólo refleja el dato. El host NULL
    se propaga como None en la terna; el fail-fast lo decide el service (D1/D2)."""
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session, host=None)
    await _crear_membresia(
        db_session, usuario, uni, username="tutor1", password_encrypted="enc-pass"
    )
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    creds = await repo.get_credenciales_moodle(usuario.id, uni.id)

    assert creds is not None
    assert creds.host is None
    assert creds.username == "tutor1"


@pytest.mark.asyncio
async def test_get_credenciales_moodle_membresia_sin_credenciales_cargadas(db_session):
    """Membresía activa, pero el usuario todavía no configuró usuario/contraseña Moodle."""
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni, username=None, password_encrypted=None)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    creds = await repo.get_credenciales_moodle(usuario.id, uni.id)

    assert creds is not None
    assert creds.username is None
    assert creds.password_encrypted is None


@pytest.mark.asyncio
async def test_get_credenciales_moodle_no_lee_universidad_inactiva(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session, activa=False)
    await _crear_membresia(db_session, usuario, uni, username="x", password_encrypted="y")
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    creds = await repo.get_credenciales_moodle(usuario.id, uni.id)

    assert creds is None


@pytest.mark.asyncio
async def test_get_credenciales_moodle_distingue_universidades_del_mismo_usuario(db_session):
    """Invariante central de la fase: 2 membresías del mismo usuario, credenciales
    y host DISTINTOS por universidad — el resolver devuelve las de la universidad pedida."""
    usuario = await _crear_usuario(db_session)
    uni_a = await _crear_universidad(db_session, nombre="Uni A", host="https://a.edu")
    uni_b = await _crear_universidad(db_session, nombre="Uni B", host="https://b.edu")
    await _crear_membresia(db_session, usuario, uni_a, username="user_a", password_encrypted="pass_a")
    await _crear_membresia(db_session, usuario, uni_b, username="user_b", password_encrypted="pass_b")
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    creds_a = await repo.get_credenciales_moodle(usuario.id, uni_a.id)
    creds_b = await repo.get_credenciales_moodle(usuario.id, uni_b.id)

    assert creds_a == CredencialesMoodle("https://a.edu", "user_a", "pass_a")
    assert creds_b == CredencialesMoodle("https://b.edu", "user_b", "pass_b")


# ==================================== update_moodle_credentials_membresia ====================================


@pytest.mark.asyncio
async def test_update_moodle_credentials_membresia_escribe_en_la_membresia_activa(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    actualizada = await repo.update_moodle_credentials_membresia(
        usuario.id, uni.id, username="nuevo_user", password_encrypted="nuevo_enc"
    )

    assert actualizada is not None
    assert actualizada.moodle_username == "nuevo_user"
    assert actualizada.moodle_password_encrypted == "nuevo_enc"

    releida = await repo.get_credenciales_moodle(usuario.id, uni.id)
    assert releida.username == "nuevo_user"
    assert releida.password_encrypted == "nuevo_enc"


@pytest.mark.asyncio
async def test_update_moodle_credentials_membresia_no_afecta_otra_universidad(db_session):
    """Un usuario con 2 membresías edita las credenciales de B: A no se toca."""
    usuario = await _crear_usuario(db_session)
    uni_a = await _crear_universidad(db_session, nombre="Uni A")
    uni_b = await _crear_universidad(db_session, nombre="Uni B")
    await _crear_membresia(db_session, usuario, uni_a, username="user_a", password_encrypted="pass_a")
    await _crear_membresia(db_session, usuario, uni_b, username="user_b_viejo", password_encrypted="pass_b_vieja")
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    await repo.update_moodle_credentials_membresia(
        usuario.id, uni_b.id, username="user_b_nuevo", password_encrypted="pass_b_nueva"
    )

    creds_a = await repo.get_credenciales_moodle(usuario.id, uni_a.id)
    creds_b = await repo.get_credenciales_moodle(usuario.id, uni_b.id)
    assert creds_a == CredencialesMoodle(uni_a.moodle_host, "user_a", "pass_a")
    assert creds_b == CredencialesMoodle(uni_b.moodle_host, "user_b_nuevo", "pass_b_nueva")


@pytest.mark.asyncio
async def test_update_moodle_credentials_membresia_sin_membresia_devuelve_none(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    resultado = await repo.update_moodle_credentials_membresia(
        usuario.id, uni.id, username="x", password_encrypted="y"
    )

    assert resultado is None
