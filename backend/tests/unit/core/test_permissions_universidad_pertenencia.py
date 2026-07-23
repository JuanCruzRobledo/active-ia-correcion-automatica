"""
Fase 4 multi-tenant (multi-tenant-scoping-queries, D3): check de pertenencia
GENERAL por id a la universidad activa, con semántica 404 (no 403, no 409).

Distinto del guard 409 de Fase 3 (`verificar_materia_universidad_activa`, red de
seguridad LOCAL para sync Moodle cross-campus): acá cubrimos el acceso general
por id a cualquier recurso de las 9 entidades scopeadas. Un 403 revelaría que el
recurso EXISTE en otra universidad; 404 lo hace indistinguible de un id
inexistente (misma política que `filtrar_entregas_accesibles`).
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.dependencies import ContextoUniversidad
from app.core.permissions import verificar_pertenencia_universidad
from app.models.enums import RolEnum

CTX_UNIA = ContextoUniversidad(universidad_id=1, rol=RolEnum.ADMIN, es_superadmin=False)
CTX_UNIB = ContextoUniversidad(universidad_id=2, rol=RolEnum.ADMIN, es_superadmin=False)
CTX_SUPERADMIN_SIN_UNIVERSIDAD = ContextoUniversidad(
    universidad_id=None, rol=None, es_superadmin=True
)
CTX_SUPERADMIN_CON_UNIVERSIDAD = ContextoUniversidad(
    universidad_id=1, rol=RolEnum.ADMIN, es_superadmin=True
)


def test_recurso_de_otra_universidad_da_404():
    recurso = SimpleNamespace(id=10, universidad_id=2)
    with pytest.raises(HTTPException) as exc:
        verificar_pertenencia_universidad(recurso, CTX_UNIA.universidad_id)
    assert exc.value.status_code == 404


def test_recurso_inexistente_da_404():
    with pytest.raises(HTTPException) as exc:
        verificar_pertenencia_universidad(None, CTX_UNIA.universidad_id)
    assert exc.value.status_code == 404


def test_recurso_de_la_universidad_activa_pasa():
    recurso = SimpleNamespace(id=10, universidad_id=1)
    verificar_pertenencia_universidad(recurso, CTX_UNIA.universidad_id)  # no lanza


def test_superadmin_sin_universidad_activa_bypassa_siempre():
    """OQ2: superadmin sin universidad elegida ve TODO, sin chequear pertenencia."""
    recurso = SimpleNamespace(id=10, universidad_id=2)
    verificar_pertenencia_universidad(recurso, CTX_SUPERADMIN_SIN_UNIVERSIDAD.universidad_id)  # no lanza


def test_superadmin_sin_universidad_activa_bypassa_incluso_con_recurso_none():
    verificar_pertenencia_universidad(None, CTX_SUPERADMIN_SIN_UNIVERSIDAD.universidad_id)  # no lanza


def test_superadmin_con_universidad_elegida_filtra_como_cualquier_miembro():
    """OQ2: si el superadmin SÍ eligió universidad, se comporta como un miembro más."""
    recurso_otra = SimpleNamespace(id=10, universidad_id=2)
    with pytest.raises(HTTPException) as exc:
        verificar_pertenencia_universidad(recurso_otra, CTX_SUPERADMIN_CON_UNIVERSIDAD.universidad_id)
    assert exc.value.status_code == 404

    recurso_propia = SimpleNamespace(id=11, universidad_id=1)
    verificar_pertenencia_universidad(recurso_propia, CTX_SUPERADMIN_CON_UNIVERSIDAD.universidad_id)  # no lanza


def test_no_revela_existencia_cross_tenant_en_el_detalle():
    """El detalle del 404 no debe distinguir 'de otra universidad' de 'no existe'."""
    recurso = SimpleNamespace(id=10, universidad_id=2)
    with pytest.raises(HTTPException) as exc_otra:
        verificar_pertenencia_universidad(recurso, CTX_UNIA.universidad_id)
    with pytest.raises(HTTPException) as exc_inexistente:
        verificar_pertenencia_universidad(None, CTX_UNIA.universidad_id)
    assert exc_otra.value.detail == exc_inexistente.value.detail


def test_universidad_b_no_ve_recurso_de_universidad_a():
    """Aislamiento simétrico: UniB tampoco ve recursos de UniA."""
    recurso_de_a = SimpleNamespace(id=5, universidad_id=1)
    with pytest.raises(HTTPException) as exc:
        verificar_pertenencia_universidad(recurso_de_a, CTX_UNIB.universidad_id)
    assert exc.value.status_code == 404
