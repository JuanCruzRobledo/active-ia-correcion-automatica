"""
Fase 0 multi-tenant: modelo `UsuarioUniversidad` — membresía usuario<->universidad
con rol scopeado y credenciales Moodle por membresía.

Ref: openspec/changes/multi-tenant-modelo-datos/specs/usuario-universidad-membresia/spec.md
"""

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def test_usuario_universidad_tiene_las_columnas_esperadas():
    from app.models.usuario_universidad import UsuarioUniversidad

    cols = {c.name for c in UsuarioUniversidad.__table__.columns}
    esperadas = {
        "id",
        "usuario_id",
        "universidad_id",
        "rol",
        "moodle_username",
        "moodle_password_encrypted",
        "activo",
    }
    assert esperadas <= cols


def test_usuario_id_y_universidad_id_son_fk_not_null():
    from app.models.usuario_universidad import UsuarioUniversidad

    usuario_id_col = UsuarioUniversidad.__table__.columns["usuario_id"]
    universidad_id_col = UsuarioUniversidad.__table__.columns["universidad_id"]

    assert usuario_id_col.nullable is False
    assert universidad_id_col.nullable is False
    assert any(fk.column.table.name == "usuarios" for fk in usuario_id_col.foreign_keys)
    assert any(
        fk.column.table.name == "universidades" for fk in universidad_id_col.foreign_keys
    )


def test_existe_unique_constraint_usuario_universidad():
    from sqlalchemy import UniqueConstraint

    from app.models.usuario_universidad import UsuarioUniversidad

    uniques = [
        uc
        for uc in UsuarioUniversidad.__table__.constraints
        if isinstance(uc, UniqueConstraint)
    ]
    assert any(
        set(uc.columns.keys()) == {"usuario_id", "universidad_id"} for uc in uniques
    )


@pytest_asyncio.fixture
async def db_session():
    from app.models.base import Base
    from app.models.universidad import Universidad
    from app.models.usuario import Usuario
    from app.models.usuario_universidad import UsuarioUniversidad

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


async def _crear_usuario(db_session, username="tutor1"):
    from app.models.enums import RolEnum
    from app.models.usuario import Usuario

    u = Usuario(
        username=username,
        nombre="Tutor Uno",
        password_hash="x",
        rol=RolEnum.TUTOR,
    )
    db_session.add(u)
    await db_session.flush()
    return u


async def _crear_universidad(db_session, nombre="TUPaD"):
    from app.models.universidad import Universidad

    uni = Universidad(nombre=nombre)
    db_session.add(uni)
    await db_session.flush()
    return uni


@pytest.mark.asyncio
async def test_un_usuario_puede_tener_roles_distintos_en_dos_universidades(db_session):
    from app.models.enums import RolEnum
    from app.models.usuario_universidad import UsuarioUniversidad

    usuario = await _crear_usuario(db_session)
    uni_a = await _crear_universidad(db_session, "TUPaD")
    uni_b = await _crear_universidad(db_session, "Otra Universidad")

    db_session.add(
        UsuarioUniversidad(usuario_id=usuario.id, universidad_id=uni_a.id, rol=RolEnum.ADMIN)
    )
    db_session.add(
        UsuarioUniversidad(usuario_id=usuario.id, universidad_id=uni_b.id, rol=RolEnum.TUTOR)
    )
    await db_session.commit()

    membresias = (await db_session.execute(
        __import__("sqlalchemy").select(UsuarioUniversidad).where(
            UsuarioUniversidad.usuario_id == usuario.id
        )
    )).scalars().all()
    assert {m.rol for m in membresias} == {RolEnum.ADMIN, RolEnum.TUTOR}


@pytest.mark.asyncio
async def test_no_se_permite_membresia_duplicada(db_session):
    from app.models.enums import RolEnum
    from app.models.usuario_universidad import UsuarioUniversidad

    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)

    db_session.add(
        UsuarioUniversidad(usuario_id=usuario.id, universidad_id=uni.id, rol=RolEnum.ADMIN)
    )
    await db_session.commit()

    db_session.add(
        UsuarioUniversidad(usuario_id=usuario.id, universidad_id=uni.id, rol=RolEnum.TUTOR)
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
