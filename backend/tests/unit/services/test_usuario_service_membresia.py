"""Fase 6 multi-tenant (multi-tenant-cleanup-rol-global, D4/D5, tareas 2.1-2.7).

`UsuarioService.crear_usuario` pasa a ser transaccional (usuario + membresía
en la universidad activa); `actualizar_usuario` aplica el cambio de rol a la
membresía activa, no a un rol global.
"""

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.services.usuario_service import UsuarioService
from tests.helpers.usuario_membresia import crear_universidad, crear_usuario_con_membresia


# ============================== crear_usuario ==============================


@pytest.mark.asyncio
async def test_crear_usuario_crea_membresia_en_la_universidad_activa(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    await db_session.commit()

    service = UsuarioService(db_session)
    data = UsuarioCreate(username="tutornuevo", nombre="Tutor Nuevo", rol=RolEnum.TUTOR)
    resultado = await service.crear_usuario(data, current_user_id=None, universidad_id=uni_a.id)

    assert resultado.usuario.rol == RolEnum.TUTOR

    membresia = await service.repo.get_membresia(resultado.usuario.id, uni_a.id)
    assert membresia is not None
    assert membresia.rol == RolEnum.TUTOR


@pytest.mark.asyncio
async def test_crear_usuario_aparece_en_el_listado_de_su_universidad_y_no_en_otra(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    await db_session.commit()

    service = UsuarioService(db_session)
    data = UsuarioCreate(username="tutornuevo2", nombre="Tutor Nuevo 2", rol=RolEnum.TUTOR)
    resultado = await service.crear_usuario(data, current_user_id=None, universidad_id=uni_a.id)

    listado_a = await service.listar_usuarios(universidad_id=uni_a.id)
    listado_b = await service.listar_usuarios(universidad_id=uni_b.id)

    ids_a = {u.id for u in listado_a.items}
    ids_b = {u.id for u in listado_b.items}
    assert resultado.usuario.id in ids_a
    assert resultado.usuario.id not in ids_b


@pytest.mark.asyncio
async def test_crear_usuario_sin_universidad_activa_responde_400(db_session):
    service = UsuarioService(db_session)
    data = UsuarioCreate(username="fantasma", nombre="Fantasma", rol=RolEnum.TUTOR)

    with pytest.raises(HTTPException) as exc_info:
        await service.crear_usuario(data, current_user_id=None, universidad_id=None)

    assert exc_info.value.status_code == 400


# ============================== actualizar_usuario: rol -> membresía ==============================


@pytest.mark.asyncio
async def test_actualizar_usuario_cambia_solo_la_membresia_de_la_universidad_activa(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    from app.models.usuario_universidad import UsuarioUniversidad

    membresia_b = UsuarioUniversidad(
        usuario_id=persona.id, universidad_id=uni_b.id, rol=RolEnum.TUTOR, activo=True
    )
    db_session.add(membresia_b)
    await db_session.commit()

    service = UsuarioService(db_session)
    await service.actualizar_usuario(
        persona.id, UsuarioUpdate(rol=RolEnum.COORDINADOR), universidad_id=uni_a.id
    )

    membresia_a_recargada = await service.repo.get_membresia(persona.id, uni_a.id)
    membresia_b_recargada = await service.repo.get_membresia(persona.id, uni_b.id)
    assert membresia_a_recargada.rol == RolEnum.COORDINADOR
    assert membresia_b_recargada.rol == RolEnum.TUTOR  # intacta


@pytest.mark.asyncio
async def test_actualizar_usuario_sin_membresia_activa_aca_responde_404(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_b)
    await db_session.commit()

    service = UsuarioService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await service.actualizar_usuario(
            persona.id, UsuarioUpdate(rol=RolEnum.COORDINADOR), universidad_id=uni_a.id
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_actualizar_usuario_sin_cambio_de_rol_no_requiere_universidad(db_session):
    """Sólo tocar `nombre`/`email` no debería exigir universidad activa: el
    404/400 de membresía es específico del cambio de ROL (spec: 'El cambio
    de rol afecta a la membresía activa')."""
    uni_a = await crear_universidad(db_session, "Universidad A")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    await db_session.commit()

    service = UsuarioService(db_session)
    resultado = await service.actualizar_usuario(
        persona.id, UsuarioUpdate(nombre="Nuevo Nombre"), universidad_id=None
    )

    assert resultado.nombre == "Nuevo Nombre"
