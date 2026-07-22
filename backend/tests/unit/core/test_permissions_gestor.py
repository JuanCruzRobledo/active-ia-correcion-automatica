"""Tests de los validadores de rol GESTOR (app/core/permissions.py).

T1 del PLAN_GESTION.md. Dominio CRÍTICO (permisos): el rol GESTOR sólo debe
acceder a lo suyo, y el guard combinado debe dejar pasar también al ADMIN.
"""

import pytest

from fastapi import HTTPException

from app.core.dependencies import ContextoUniversidad
from app.core.permissions import require_gestor, require_gestor_or_admin
from app.models.enums import RolEnum


def _ctx(rol):
    """Fase 2 multi-tenant: los guards de rol reciben ContextoUniversidad,
    no `Usuario` (D1). `es_superadmin=False` explicito porque un mock
    permisivo (MagicMock sin ese atributo fijado) evaluaria truthy y
    bypassaria el guard."""
    return ContextoUniversidad(universidad_id=1, rol=rol, es_superadmin=False)


def test_require_gestor_acepta_gestor():
    ctx = _ctx(RolEnum.GESTOR)
    assert require_gestor(ctx) is ctx


@pytest.mark.parametrize("rol", [RolEnum.ADMIN, RolEnum.COORDINADOR, RolEnum.TUTOR])
def test_require_gestor_rechaza_otros_roles(rol):
    with pytest.raises(HTTPException) as exc:
        require_gestor(_ctx(rol))
    assert exc.value.status_code == 403


@pytest.mark.parametrize("rol", [RolEnum.GESTOR, RolEnum.ADMIN])
def test_require_gestor_or_admin_acepta_gestor_y_admin(rol):
    ctx = _ctx(rol)
    assert require_gestor_or_admin(ctx) is ctx


@pytest.mark.parametrize("rol", [RolEnum.COORDINADOR, RolEnum.TUTOR])
def test_require_gestor_or_admin_rechaza_otros(rol):
    with pytest.raises(HTTPException) as exc:
        require_gestor_or_admin(_ctx(rol))
    assert exc.value.status_code == 403
