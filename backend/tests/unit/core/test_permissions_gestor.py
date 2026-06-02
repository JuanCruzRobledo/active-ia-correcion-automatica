"""Tests de los validadores de rol GESTOR (app/core/permissions.py).

T1 del PLAN_GESTION.md. Dominio CRÍTICO (permisos): el rol GESTOR sólo debe
acceder a lo suyo, y el guard combinado debe dejar pasar también al ADMIN.
"""

import pytest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.core.permissions import require_gestor, require_gestor_or_admin
from app.models.enums import RolEnum


def _user(rol):
    return MagicMock(rol=rol)


def test_require_gestor_acepta_gestor():
    user = _user(RolEnum.GESTOR)
    assert require_gestor(user) is user


@pytest.mark.parametrize("rol", [RolEnum.ADMIN, RolEnum.COORDINADOR, RolEnum.TUTOR])
def test_require_gestor_rechaza_otros_roles(rol):
    with pytest.raises(HTTPException) as exc:
        require_gestor(_user(rol))
    assert exc.value.status_code == 403


@pytest.mark.parametrize("rol", [RolEnum.GESTOR, RolEnum.ADMIN])
def test_require_gestor_or_admin_acepta_gestor_y_admin(rol):
    user = _user(rol)
    assert require_gestor_or_admin(user) is user


@pytest.mark.parametrize("rol", [RolEnum.COORDINADOR, RolEnum.TUTOR])
def test_require_gestor_or_admin_rechaza_otros(rol):
    with pytest.raises(HTTPException) as exc:
        require_gestor_or_admin(_user(rol))
    assert exc.value.status_code == 403
