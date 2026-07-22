"""
Tests del helper `_acceso_total(ctx)` (multi-tenant-permisos, Fase 2, seccion 2).

Unico punto de decision de "quien tiene acceso total": superadmin O rol ADMIN
en la universidad activa. Reutilizado por los 11 guards de pertenencia (D5).
"""

import pytest

from app.core.dependencies import ContextoUniversidad
from app.core.permissions import _acceso_total
from app.models.enums import RolEnum


def _ctx(rol, es_superadmin=False, universidad_id=1):
    return ContextoUniversidad(
        universidad_id=universidad_id, rol=rol, es_superadmin=es_superadmin
    )


def test_superadmin_tiene_acceso_total():
    assert _acceso_total(_ctx(None, es_superadmin=True, universidad_id=None)) is True


def test_admin_de_la_universidad_activa_tiene_acceso_total():
    assert _acceso_total(_ctx(RolEnum.ADMIN)) is True


def test_tutor_no_tiene_acceso_total():
    assert _acceso_total(_ctx(RolEnum.TUTOR)) is False


@pytest.mark.parametrize("rol", [RolEnum.COORDINADOR, RolEnum.GESTOR])
def test_coordinador_y_gestor_no_tienen_acceso_total(rol):
    assert _acceso_total(_ctx(rol)) is False


def test_superadmin_con_rol_none_tiene_acceso_total_por_bypass():
    """Superadmin sin universidad activa (ctx.rol=None): bypass igual aplica (OQ1)."""
    assert _acceso_total(_ctx(None, es_superadmin=True, universidad_id=None)) is True
