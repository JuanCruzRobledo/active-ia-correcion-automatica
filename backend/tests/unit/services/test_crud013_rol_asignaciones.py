"""
CRUD-013: cambiar el rol de un usuario limpia las asignaciones incompatibles.

Un COORDINADOR degradado a TUTOR conservaba sus filas en CoordinadorMateria
(seguía figurando como coordinador); un TUTOR promovido conservaba sus
ComisionTutor. Ahora, al cambiar el rol, se borran las asignaciones que ya no
corresponden al rol nuevo, en la misma transacción.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.enums import RolEnum
from app.schemas.usuario import UsuarioUpdate
from app.services.usuario_service import UsuarioService


UNIVERSIDAD_ID = 1


def _user(rol: RolEnum) -> SimpleNamespace:
    """`rol` acá es sólo el rol de la membresía simulada (D5) — el `Usuario`
    real ya no tiene columna `rol` (Fase 6 multi-tenant)."""
    return SimpleNamespace(
        id=1, nombre="X", email=None, username="x", primer_login=False,
        gemini_api_key_valid=False, activo=True,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
        last_login=None, _rol_membresia=rol,
    )


def _svc(user):
    svc = UsuarioService.__new__(UsuarioService)
    membresia = SimpleNamespace(usuario_id=user.id, universidad_id=UNIVERSIDAD_ID, rol=user._rol_membresia)
    svc.repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=user),
        update=AsyncMock(return_value=user),
        update_rol_membresia=AsyncMock(return_value=membresia),
        get_rol_en_universidad=AsyncMock(return_value=user._rol_membresia),
        get_rol_mas_antiguo=AsyncMock(return_value=user._rol_membresia),
    )
    svc.coord_materia_repo = SimpleNamespace(delete_all_for_coordinador=AsyncMock(return_value=0))
    svc.comision_tutor_repo = SimpleNamespace(delete_all_for_tutor=AsyncMock(return_value=0))
    return svc


async def _update(svc, rol):
    await svc.actualizar_usuario(1, UsuarioUpdate(rol=rol), universidad_id=UNIVERSIDAD_ID)


@pytest.mark.asyncio
async def test_coordinador_a_tutor_borra_coordinador_materia():
    user = _user(RolEnum.COORDINADOR)
    svc = _svc(user)
    await _update(svc, RolEnum.TUTOR)
    svc.coord_materia_repo.delete_all_for_coordinador.assert_awaited_once_with(1)
    svc.comision_tutor_repo.delete_all_for_tutor.assert_not_called()  # nuevo rol ES tutor


@pytest.mark.asyncio
async def test_tutor_a_coordinador_borra_comision_tutor():
    user = _user(RolEnum.TUTOR)
    svc = _svc(user)
    await _update(svc, RolEnum.COORDINADOR)
    svc.comision_tutor_repo.delete_all_for_tutor.assert_awaited_once_with(1)
    svc.coord_materia_repo.delete_all_for_coordinador.assert_not_called()


@pytest.mark.asyncio
async def test_coordinador_a_admin_borra_ambas():
    user = _user(RolEnum.COORDINADOR)
    svc = _svc(user)
    await _update(svc, RolEnum.ADMIN)
    svc.coord_materia_repo.delete_all_for_coordinador.assert_awaited_once_with(1)
    svc.comision_tutor_repo.delete_all_for_tutor.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_mismo_rol_no_borra_nada():
    user = _user(RolEnum.COORDINADOR)
    svc = _svc(user)
    await _update(svc, RolEnum.COORDINADOR)  # sin cambio
    svc.coord_materia_repo.delete_all_for_coordinador.assert_not_called()
    svc.comision_tutor_repo.delete_all_for_tutor.assert_not_called()


@pytest.mark.asyncio
async def test_update_sin_rol_no_borra_nada():
    user = _user(RolEnum.COORDINADOR)
    svc = _svc(user)
    await svc.actualizar_usuario(1, UsuarioUpdate(nombre="Nuevo"))
    svc.coord_materia_repo.delete_all_for_coordinador.assert_not_called()
    svc.comision_tutor_repo.delete_all_for_tutor.assert_not_called()
