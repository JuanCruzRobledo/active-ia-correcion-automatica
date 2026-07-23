"""
Fase 5 multi-tenant (multi-tenant-frontend-workspace): `UniversidadService`.

ARCH-001: la lógica vive acá, el service nunca ejecuta SQLAlchemy directo —
consume `UniversidadRepository` (mockeado en estos tests).

Ref: openspec/changes/multi-tenant-frontend-workspace/specs/universidades-abm/spec.md
Ref: openspec/changes/multi-tenant-frontend-workspace/design.md (D5, D7)
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.schemas.universidad import UniversidadCreate, UniversidadUpdate
from app.services.universidad_service import UniversidadService

_NOW = datetime(2024, 1, 1)


def _universidad(**over):
    base = dict(
        id=1, nombre="TUPaD", moodle_host="https://moodle.tupad.edu.ar", activa=True,
        created_at=_NOW, updated_at=_NOW,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _svc(**over):
    svc = UniversidadService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.get_propias = AsyncMock(return_value=over.get("propias", []))
    svc.repo.get_activas = AsyncMock(return_value=over.get("activas", []))
    svc.repo.get_all = AsyncMock(return_value=over.get("get_all", ([], 0)))
    svc.repo.get_by_id = AsyncMock(return_value=over.get("by_id"))
    svc.repo.existe_con_nombre = AsyncMock(return_value=over.get("existe", False))
    def _create(u):
        # Simula que el repo real hace commit+refresh: la DB asigna id y timestamps.
        u.id = over.get("nuevo_id", 99)
        u.created_at = _NOW
        u.updated_at = _NOW
        return u

    svc.repo.create = AsyncMock(side_effect=_create)
    svc.repo.update = AsyncMock(side_effect=lambda u: u)

    def _soft_delete(u):
        # Simula el comportamiento real de UniversidadRepository.soft_delete
        # (activa=False) sin ejecutar SQLAlchemy: el repo está mockeado.
        u.activa = False
        return u

    svc.repo.soft_delete = AsyncMock(side_effect=_soft_delete)
    return svc


# ============================== listar_mias ==============================


@pytest.mark.asyncio
async def test_listar_mias_una_membresia():
    usuario = SimpleNamespace(id=1, es_superadmin=False)
    svc = _svc(propias=[(_universidad(id=7, nombre="TUPaD"), RolEnum.TUTOR)])

    res = await svc.listar_mias(usuario)

    assert len(res) == 1
    assert res[0].id == 7
    assert res[0].rol == RolEnum.TUTOR


@pytest.mark.asyncio
async def test_listar_mias_dos_membresias_con_roles_distintos():
    usuario = SimpleNamespace(id=1, es_superadmin=False)
    svc = _svc(
        propias=[
            (_universidad(id=1, nombre="A"), RolEnum.TUTOR),
            (_universidad(id=2, nombre="B"), RolEnum.COORDINADOR),
        ]
    )

    res = await svc.listar_mias(usuario)

    assert {(u.id, u.rol) for u in res} == {(1, RolEnum.TUTOR), (2, RolEnum.COORDINADOR)}


@pytest.mark.asyncio
async def test_listar_mias_superadmin_ve_todas_con_rol_admin_sintetico():
    usuario = SimpleNamespace(id=1, es_superadmin=True)
    svc = _svc(activas=[_universidad(id=1, nombre="A"), _universidad(id=2, nombre="B")])

    res = await svc.listar_mias(usuario)

    assert len(res) == 2
    assert all(u.rol == RolEnum.ADMIN for u in res)
    svc.repo.get_propias.assert_not_awaited()


# ============================== listar (ABM) ==============================


@pytest.mark.asyncio
async def test_listar_devuelve_paginado():
    svc = _svc(get_all=([_universidad(id=1), _universidad(id=2)], 2))

    res = await svc.listar(page=1, per_page=20, include_inactive=False, search=None)

    assert res.total == 2
    assert len(res.items) == 2


# ============================== crear ==============================


@pytest.mark.asyncio
async def test_crear_universidad_ok():
    svc = _svc(existe=False)

    res = await svc.crear(UniversidadCreate(nombre="Nueva Uni", moodle_host=None))

    assert res.nombre == "Nueva Uni"
    assert res.activa is True
    svc.repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_crear_universidad_nombre_duplicado_409():
    svc = _svc(existe=True)

    with pytest.raises(HTTPException) as exc:
        await svc.crear(UniversidadCreate(nombre="TUPaD", moodle_host=None))
    assert exc.value.status_code == 409


# ============================== actualizar ==============================


@pytest.mark.asyncio
async def test_actualizar_universidad_ok():
    svc = _svc(by_id=_universidad(id=1, nombre="TUPaD"))

    res = await svc.actualizar(1, UniversidadUpdate(nombre="TUPaD Renombrada"))

    assert res.nombre == "TUPaD Renombrada"


@pytest.mark.asyncio
async def test_actualizar_universidad_inexistente_404():
    svc = _svc(by_id=None)

    with pytest.raises(HTTPException) as exc:
        await svc.actualizar(999, UniversidadUpdate(nombre="X"))
    assert exc.value.status_code == 404


# ============================== eliminar (baja lógica) ==============================


@pytest.mark.asyncio
async def test_eliminar_es_baja_logica():
    universidad = _universidad(id=1, activa=True)
    svc = _svc(by_id=universidad)

    await svc.eliminar(1)

    assert universidad.activa is False
    svc.repo.soft_delete.assert_awaited_once_with(universidad)


@pytest.mark.asyncio
async def test_eliminar_inexistente_404():
    svc = _svc(by_id=None)

    with pytest.raises(HTTPException) as exc:
        await svc.eliminar(999)
    assert exc.value.status_code == 404
