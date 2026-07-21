"""
CRUD-013: cambiar el rol de un usuario limpia las asignaciones incompatibles.

Un COORDINADOR degradado a TUTOR conservaba sus filas en CoordinadorMateria
(seguía figurando como coordinador); un TUTOR promovido conservaba sus
ComisionTutor. Ahora, al cambiar el rol, se borran las asignaciones que ya no
corresponden al rol nuevo, en la misma transacción.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.enums import RolEnum
from app.schemas.usuario import UsuarioUpdate
from app.services.usuario_service import UsuarioService


def _svc(user):
    svc = UsuarioService.__new__(UsuarioService)
    svc.repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=user),
        update=AsyncMock(return_value=user),
    )
    svc.coord_materia_repo = SimpleNamespace(delete_all_for_coordinador=AsyncMock(return_value=0))
    svc.comision_tutor_repo = SimpleNamespace(delete_all_for_tutor=AsyncMock(return_value=0))
    return svc


async def _update(svc, rol):
    with patch("app.services.usuario_service.UsuarioResponse") as MockResp:
        MockResp.model_validate.return_value = "OK"
        await svc.actualizar_usuario(1, UsuarioUpdate(rol=rol))


@pytest.mark.asyncio
async def test_coordinador_a_tutor_borra_coordinador_materia():
    user = SimpleNamespace(id=1, nombre="X", rol=RolEnum.COORDINADOR, email=None)
    svc = _svc(user)
    await _update(svc, RolEnum.TUTOR)
    svc.coord_materia_repo.delete_all_for_coordinador.assert_awaited_once_with(1)
    svc.comision_tutor_repo.delete_all_for_tutor.assert_not_called()  # nuevo rol ES tutor


@pytest.mark.asyncio
async def test_tutor_a_coordinador_borra_comision_tutor():
    user = SimpleNamespace(id=1, nombre="X", rol=RolEnum.TUTOR, email=None)
    svc = _svc(user)
    await _update(svc, RolEnum.COORDINADOR)
    svc.comision_tutor_repo.delete_all_for_tutor.assert_awaited_once_with(1)
    svc.coord_materia_repo.delete_all_for_coordinador.assert_not_called()


@pytest.mark.asyncio
async def test_coordinador_a_admin_borra_ambas():
    user = SimpleNamespace(id=1, nombre="X", rol=RolEnum.COORDINADOR, email=None)
    svc = _svc(user)
    await _update(svc, RolEnum.ADMIN)
    svc.coord_materia_repo.delete_all_for_coordinador.assert_awaited_once_with(1)
    svc.comision_tutor_repo.delete_all_for_tutor.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_mismo_rol_no_borra_nada():
    user = SimpleNamespace(id=1, nombre="X", rol=RolEnum.COORDINADOR, email=None)
    svc = _svc(user)
    await _update(svc, RolEnum.COORDINADOR)  # sin cambio
    svc.coord_materia_repo.delete_all_for_coordinador.assert_not_called()
    svc.comision_tutor_repo.delete_all_for_tutor.assert_not_called()


@pytest.mark.asyncio
async def test_update_sin_rol_no_borra_nada():
    user = SimpleNamespace(id=1, nombre="X", rol=RolEnum.COORDINADOR, email=None)
    svc = _svc(user)
    with patch("app.services.usuario_service.UsuarioResponse") as MockResp:
        MockResp.model_validate.return_value = "OK"
        await svc.actualizar_usuario(1, UsuarioUpdate(nombre="Nuevo"))
    svc.coord_materia_repo.delete_all_for_coordinador.assert_not_called()
    svc.comision_tutor_repo.delete_all_for_tutor.assert_not_called()
