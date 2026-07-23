"""
Fase 5 multi-tenant (multi-tenant-frontend-workspace): `UniversidadRepository`
a nivel DB (sqlite in-memory) — mismo patrón que
`test_usuario_repository_membresias.py`.

Cubre los escenarios de la spec que no se pueden verificar con un repo
mockeado: membresía inactiva excluida (2.6) y que la baja lógica preserva
los datos asociados (2.8, CRUD-002 — nunca borrado físico).

Ref: openspec/changes/multi-tenant-frontend-workspace/specs/universidades-abm/spec.md
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.enums import RolEnum
from app.models.materia import Materia
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad
from app.repositories.universidad_repository import UniversidadRepository


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                Usuario.__table__,
                Universidad.__table__,
                UsuarioUniversidad.__table__,
                Materia.__table__,
            ],
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


async def _crear_membresia(db, usuario, universidad, rol=RolEnum.TUTOR, activo=True):
    m = UsuarioUniversidad(
        usuario_id=usuario.id, universidad_id=universidad.id, rol=rol, activo=activo
    )
    db.add(m)
    await db.flush()
    return m


# ==================================== get_propias ====================================


@pytest.mark.asyncio
async def test_get_propias_excluye_membresia_inactiva(db_session):
    usuario = await _crear_usuario(db_session)
    uni_ok = await _crear_universidad(db_session, "TUPaD")
    uni_membresia_inactiva = await _crear_universidad(db_session, "Otra")
    await _crear_membresia(db_session, usuario, uni_ok, rol=RolEnum.COORDINADOR)
    await _crear_membresia(db_session, usuario, uni_membresia_inactiva, activo=False)
    await db_session.commit()

    repo = UniversidadRepository(db_session)
    propias = await repo.get_propias(usuario.id)

    assert len(propias) == 1
    assert propias[0][0].id == uni_ok.id
    assert propias[0][1] == RolEnum.COORDINADOR


@pytest.mark.asyncio
async def test_get_propias_dos_membresias_con_roles_distintos(db_session):
    """Triangulación: 2 universidades activas, cada una con su propio rol."""
    usuario = await _crear_usuario(db_session)
    uni_a = await _crear_universidad(db_session, "A")
    uni_b = await _crear_universidad(db_session, "B")
    await _crear_membresia(db_session, usuario, uni_a, rol=RolEnum.TUTOR)
    await _crear_membresia(db_session, usuario, uni_b, rol=RolEnum.COORDINADOR)
    await db_session.commit()

    repo = UniversidadRepository(db_session)
    propias = await repo.get_propias(usuario.id)

    assert {(u.id, rol) for u, rol in propias} == {
        (uni_a.id, RolEnum.TUTOR),
        (uni_b.id, RolEnum.COORDINADOR),
    }


# ==================================== soft_delete ====================================


@pytest.mark.asyncio
async def test_soft_delete_preserva_la_fila_y_los_datos_asociados(db_session):
    """CRUD-002: baja SIEMPRE lógica. La Materia asociada no se toca.

    Insert/select de Materia por SQL crudo (no vía el modelo ORM completo):
    `Materia.examenes` es `lazy="selectin"` y arrastraría todo el grafo de
    relaciones (examenes_materia, etc.) que este schema mínimo no crea —
    igual que test_usuario_repository_membresias.py evita instanciar modelos
    con relationships que no hacen falta para lo que se está probando.
    """
    from sqlalchemy import text

    uni = await _crear_universidad(db_session, "TUPaD")
    await db_session.execute(
        text(
            "INSERT INTO materias (codigo, nombre, universidad_id, activa, created_at, updated_at) "
            "VALUES ('PROG1', 'Programación 1', :uid, 1, datetime('now'), datetime('now'))"
        ),
        {"uid": uni.id},
    )
    await db_session.commit()

    repo = UniversidadRepository(db_session)
    await repo.soft_delete(uni)

    # La fila de Universidad sigue existiendo, sólo activa=False.
    recargada = await repo.get_by_id(uni.id)
    assert recargada is not None
    assert recargada.activa is False

    # La Materia asociada NO se toca.
    result = await db_session.execute(
        text("SELECT activa, universidad_id FROM materias WHERE codigo = 'PROG1'")
    )
    row = result.one()
    assert bool(row[0]) is True
    assert row[1] == uni.id


@pytest.mark.asyncio
async def test_soft_delete_desaparece_de_mias(db_session):
    """2.8: la universidad dada de baja desaparece de get_propias (→ /mias)."""
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session, "TUPaD")
    await _crear_membresia(db_session, usuario, uni)
    await db_session.commit()

    repo = UniversidadRepository(db_session)
    await repo.soft_delete(uni)

    propias = await repo.get_propias(usuario.id)
    assert propias == []
