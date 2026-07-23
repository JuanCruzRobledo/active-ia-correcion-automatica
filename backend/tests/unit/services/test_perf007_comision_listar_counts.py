"""PERF-007 — ComisionService.listar_comisiones: conteos de tutores/entregas.

Antes: por cada comisión del listado se hacía `get_tutores_for_comision(id)` (1 query)
y `len(comision.entregas)` (materializa la colección selectin). Ahora: UNA query
agregada con GROUP BY que cuenta ambos con COUNT(DISTINCT ...).

Regla de oro: los NÚMEROS que ve el usuario (num_tutores, num_entregas por comisión)
NO cambian. El caso clave del test es una comisión con VARIOS tutores Y VARIAS entregas:
un join agregado ingenuo (sin DISTINCT) daría el producto cartesiano (p.ej. 2×3=6);
el conteo correcto es (2, 3). Ese caso ancla que el fix no altera los números.

SQLite en memoria con el subconjunto de tablas necesario + UDF regexp_replace (que
`orden_natural_sql` usa en el ORDER BY del listado). Patrón: test_orden_natural_comision.py.
"""

import re

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models.base import Base
from app.models.comision import Comision, ComisionTutor
from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum, RolEnum
from app.models.materia import Materia
from app.models.usuario import Usuario
from app.services.comision_service import ComisionService

UNIV_ID = 1  # multi-tenant-scoping-queries: universidad_id ahora NOT NULL



@compiles(JSONB, "sqlite")
def _jsonb_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


def _regexp_replace_sqlite(source, pattern, replacement):
    if source is None:
        return None
    return re.sub(pattern, replacement, source, count=1)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _reg(dbapi_connection, connection_record):
        dbapi_connection.create_function("regexp_replace", 3, _regexp_replace_sqlite)

    # Con los shims JSONB/ARRAY registrados, todo el metadata compila en SQLite;
    # se crean todas las tablas para cubrir las cascadas lazy="selectin" del ORM.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


async def _tutor(db, username) -> Usuario:
    u = Usuario(username=username, nombre=username, password_hash="x")
    db.add(u)
    await db.flush()
    return u


async def _entregas(db, comision_id, n):
    for i in range(n):
        db.add(
            Entrega(universidad_id=UNIV_ID, 
                comision_id=comision_id,
                rubrica_id=1,
                alumno_nombre=f"C{comision_id}-Alumno {i}",
                archivo_nombre="tp.zip",
                archivo_tipo="zip",
                estado=EstadoEntregaEnum.SUBIDA,
            )
        )


@pytest_asyncio.fixture
async def seeded(db_session):
    """3 comisiones con distinta combinación de tutores/entregas.

    - C-multi: 2 tutores, 3 entregas  → (2, 3)  [ancla anti-cartesiano]
    - C-uno:   1 tutor,  0 entregas   → (1, 0)
    - C-cero:  0 tutores, 0 entregas  → (0, 0)
    """
    materia = Materia(universidad_id=UNIV_ID, nombre="Programación 1", codigo="P1")
    db_session.add(materia)
    await db_session.flush()

    t1 = await _tutor(db_session, "tutor1")
    t2 = await _tutor(db_session, "tutor2")

    c_multi = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-2", anio=2026, activa=True)
    c_uno = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    c_cero = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-3", anio=2026, activa=True)
    db_session.add_all([c_multi, c_uno, c_cero])
    await db_session.flush()

    db_session.add_all(
        [
            ComisionTutor(comision_id=c_multi.id, tutor_id=t1.id),
            ComisionTutor(comision_id=c_multi.id, tutor_id=t2.id),
            ComisionTutor(comision_id=c_uno.id, tutor_id=t1.id),
        ]
    )
    await _entregas(db_session, c_multi.id, 3)
    await db_session.commit()
    return {"multi": c_multi.id, "uno": c_uno.id, "cero": c_cero.id}


@pytest.mark.asyncio
async def test_listar_conteos_por_comision_identicos_al_loop(db_session, seeded):
    service = ComisionService(db_session)
    result = await service.listar_comisiones(per_page=50)

    por_id = {item.id: item for item in result.items}
    assert result.total == 3

    # Comisión con 2 tutores y 3 entregas: NO 6/6 (cartesiano), sino 2/3.
    assert (por_id[seeded["multi"]].num_tutores, por_id[seeded["multi"]].num_entregas) == (2, 3)
    # 1 tutor, 0 entregas.
    assert (por_id[seeded["uno"]].num_tutores, por_id[seeded["uno"]].num_entregas) == (1, 0)
    # 0 tutores, 0 entregas.
    assert (por_id[seeded["cero"]].num_tutores, por_id[seeded["cero"]].num_entregas) == (0, 0)


@pytest.mark.asyncio
async def test_listar_conteos_coinciden_con_los_repos_viejos(db_session, seeded):
    """Paridad explícita: el conteo nuevo == el que daban los métodos del loop viejo
    (`get_tutores_for_comision` y la colección `comision.entregas`)."""
    service = ComisionService(db_session)
    result = await service.listar_comisiones(per_page=50)

    for item in result.items:
        tutores_viejo = await service.comision_tutor_repo.get_tutores_for_comision(item.id)
        comi = await service.comision_repo.get_by_id(item.id)
        # entregas via query directa (equivalente a len(comision.entregas))
        from sqlalchemy import func, select

        entregas_viejo = await db_session.scalar(
            select(func.count(Entrega.id)).where(Entrega.comision_id == comi.id)
        )
        assert item.num_tutores == len(tutores_viejo)
        assert item.num_entregas == entregas_viejo
