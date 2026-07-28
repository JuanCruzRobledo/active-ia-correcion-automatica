"""Fase 6 multi-tenant (multi-tenant-cleanup-rol-global, tarea 1.1/1.3/1.4).

Gate de esta fase: `usuario_repository.get_all()` / `get_tutores()` no
filtraban por universidad — un ADMIN de una universidad veía los usuarios de
las demás (agujero heredado de la Fase 4, que scopeó "lo que cuelga de
materia" y `usuarios` no cuelga de materia).

Estos tests SOLO se ven con DOS universidades cargadas: con una sola, el
filtro es indistinguible de no tener filtro (design.md, Risks).

D3: el filtro por rol se resuelve DENTRO del EXISTS de la membresía — una
persona TUTOR en A y COORDINADOR en B debe aparecer al filtrar TUTOR en A y
NO al filtrar TUTOR en B.
"""

import pytest

from app.models.enums import RolEnum
from app.repositories.usuario_repository import UsuarioRepository
from tests.helpers.usuario_membresia import crear_usuario_con_membresia, crear_universidad


# ============================== get_all: aislamiento ==============================


@pytest.mark.asyncio
async def test_get_all_universidad_a_no_ve_usuarios_exclusivos_de_b(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")

    u_a, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    u_b, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    usuarios, total = await repo.get_all(universidad_id=uni_a.id)

    ids = {u.id for u in usuarios}
    assert u_a.id in ids
    assert u_b.id not in ids
    assert total == 1


@pytest.mark.asyncio
async def test_get_all_aislamiento_simetrico_para_b(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")

    u_a, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    u_b, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    usuarios, total = await repo.get_all(universidad_id=uni_b.id)

    ids = {u.id for u in usuarios}
    assert u_b.id in ids
    assert u_a.id not in ids
    assert total == 1


@pytest.mark.asyncio
async def test_get_all_membresia_inactiva_queda_excluida(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    u_a, _, _ = await crear_usuario_con_membresia(
        db_session, rol=RolEnum.TUTOR, universidad=uni_a, membresia_activa=False
    )
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    usuarios, total = await repo.get_all(universidad_id=uni_a.id)

    assert u_a.id not in {u.id for u in usuarios}
    assert total == 0


@pytest.mark.asyncio
async def test_get_all_usuario_con_dos_membresias_aparece_en_ambas(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")

    u, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    from tests.helpers.usuario_membresia import crear_usuario_con_membresia as _crear

    # Segunda membresía del MISMO usuario en B (no crea un usuario nuevo).
    from app.models.usuario_universidad import UsuarioUniversidad

    membresia_b = UsuarioUniversidad(
        usuario_id=u.id, universidad_id=uni_b.id, rol=RolEnum.COORDINADOR, activo=True
    )
    db_session.add(membresia_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    usuarios_a, _ = await repo.get_all(universidad_id=uni_a.id)
    usuarios_b, _ = await repo.get_all(universidad_id=uni_b.id)

    assert u.id in {x.id for x in usuarios_a}
    assert u.id in {x.id for x in usuarios_b}


@pytest.mark.asyncio
async def test_get_all_universidad_id_none_devuelve_todos_modo_superadmin(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")

    u_a, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    u_b, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    usuarios, total = await repo.get_all(universidad_id=None)

    ids = {u.id for u in usuarios}
    assert u_a.id in ids
    assert u_b.id in ids
    assert total == 2


# ============================== get_all: filtro por rol dentro del EXISTS (D3) ==============================


@pytest.mark.asyncio
async def test_get_all_filtro_rol_usa_el_rol_de_la_membresia_activa(db_session):
    """La misma persona es TUTOR en A y COORDINADOR en B (D3)."""
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")

    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    from app.models.usuario_universidad import UsuarioUniversidad

    membresia_b = UsuarioUniversidad(
        usuario_id=persona.id, universidad_id=uni_b.id, rol=RolEnum.COORDINADOR, activo=True
    )
    db_session.add(membresia_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)

    # Filtrando TUTOR en A: aparece.
    usuarios_a_tutor, _ = await repo.get_all(universidad_id=uni_a.id, rol=RolEnum.TUTOR)
    assert persona.id in {u.id for u in usuarios_a_tutor}

    # Filtrando TUTOR en B (donde es COORDINADOR): NO aparece.
    usuarios_b_tutor, _ = await repo.get_all(universidad_id=uni_b.id, rol=RolEnum.TUTOR)
    assert persona.id not in {u.id for u in usuarios_b_tutor}

    # Filtrando COORDINADOR en B: aparece.
    usuarios_b_coord, _ = await repo.get_all(universidad_id=uni_b.id, rol=RolEnum.COORDINADOR)
    assert persona.id in {u.id for u in usuarios_b_coord}


# ============================== get_tutores: aislamiento ==============================


@pytest.mark.asyncio
async def test_get_tutores_no_cruza_universidades(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")

    tutor_a, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    tutor_b, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    tutores_a = await repo.get_tutores(universidad_id=uni_a.id)

    ids = {t.id for t in tutores_a}
    assert tutor_a.id in ids
    assert tutor_b.id not in ids


@pytest.mark.asyncio
async def test_get_tutores_universidad_id_none_devuelve_todos(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")

    tutor_a, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    tutor_b, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    tutores = await repo.get_tutores(universidad_id=None)

    ids = {t.id for t in tutores}
    assert tutor_a.id in ids
    assert tutor_b.id in ids
