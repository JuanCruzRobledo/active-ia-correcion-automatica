"""Fase 6 multi-tenant (multi-tenant-cleanup-rol-global, hallazgo tarea 3.5).

`get_rol_en_universidad`: resuelve el rol de la membresía activa de un
usuario CUALQUIERA (no necesariamente el solicitante) en una universidad
dada. Reemplaza lecturas de `usuario.rol` (global) en `comision_service` /
`materia_service` al validar candidatos a tutor/coordinador — un gap que el
grep original de design.md no había anticipado (esos servicios no aparecen
en la lista de "últimos lectores" del design).
"""

import pytest

from app.models.enums import RolEnum
from app.models.usuario_universidad import UsuarioUniversidad
from app.repositories.usuario_repository import UsuarioRepository
from tests.helpers.usuario_membresia import crear_universidad, crear_usuario_con_membresia


@pytest.mark.asyncio
async def test_get_rol_en_universidad_devuelve_el_rol_de_la_membresia_activa(db_session):
    uni = await crear_universidad(db_session)
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    rol = await repo.get_rol_en_universidad(persona.id, uni.id)

    assert rol == RolEnum.TUTOR


@pytest.mark.asyncio
async def test_get_rol_en_universidad_usa_la_universidad_correcta_no_otra(db_session):
    """La misma persona: TUTOR en A, COORDINADOR en B (D3)."""
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    db_session.add(
        UsuarioUniversidad(usuario_id=persona.id, universidad_id=uni_b.id, rol=RolEnum.COORDINADOR, activo=True)
    )
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    assert await repo.get_rol_en_universidad(persona.id, uni_a.id) == RolEnum.TUTOR
    assert await repo.get_rol_en_universidad(persona.id, uni_b.id) == RolEnum.COORDINADOR


@pytest.mark.asyncio
async def test_get_rol_en_universidad_sin_membresia_devuelve_none(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    assert await repo.get_rol_en_universidad(persona.id, uni_b.id) is None


# ============================== get_roles_en_universidad (batch) ==============================


@pytest.mark.asyncio
async def test_get_roles_en_universidad_batch_resuelve_varios_de_una(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    p1, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    p2, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.COORDINADOR, universidad=uni_a)
    p3, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    roles = await repo.get_roles_en_universidad([p1.id, p2.id, p3.id], uni_a.id)

    assert roles == {p1.id: RolEnum.TUTOR, p2.id: RolEnum.COORDINADOR}
    assert p3.id not in roles


@pytest.mark.asyncio
async def test_get_roles_en_universidad_lista_vacia_devuelve_dict_vacio(db_session):
    repo = UsuarioRepository(db_session)
    assert await repo.get_roles_en_universidad([], 1) == {}


# ============================== get_roles_mas_antiguos (batch) ==============================


@pytest.mark.asyncio
async def test_get_roles_mas_antiguos_batch(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    db_session.add(
        UsuarioUniversidad(usuario_id=persona.id, universidad_id=uni_b.id, rol=RolEnum.COORDINADOR, activo=True)
    )
    otra_persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.ADMIN, universidad=uni_b)
    await db_session.commit()

    repo = UsuarioRepository(db_session)
    roles = await repo.get_roles_mas_antiguos([persona.id, otra_persona.id])

    # La membresía más antigua de `persona` es la de uni_a (creada primero).
    assert roles == {persona.id: RolEnum.TUTOR, otra_persona.id: RolEnum.ADMIN}
