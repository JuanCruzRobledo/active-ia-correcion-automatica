"""
Fase 3 multi-tenant (multi-tenant-moodle-services, D1/D2): helper de servicio
compartido por los ~10 services que hablan con Moodle.

`resolver_credenciales_moodle` es el ÚNICO punto donde un service traduce el
resultado del repo (`CredencialesMoodle | None`) en (host, username,
password_encrypted) o en un fail-fast HTTPException — así el 424 de "sin
credenciales" / "campus no configurado" y el 409 de "sin universidad activa"
(OQ5) no se repiten en cada uno de los servicios migrados.

Ref: openspec/changes/multi-tenant-moodle-services/design.md (D1, D2, OQ5)
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.repositories.usuario_repository import CredencialesMoodle
from app.services.moodle_credentials_resolver import resolver_credenciales_moodle


def _repo(return_value):
    repo = AsyncMock()
    repo.get_credenciales_moodle = AsyncMock(return_value=return_value)
    return repo


@pytest.mark.asyncio
async def test_resolver_caso_feliz_devuelve_la_terna():
    repo = _repo(CredencialesMoodle("https://campus.tupad.edu", "tutor1", "enc-pass"))

    host, username, password_encrypted = await resolver_credenciales_moodle(
        repo, usuario_id=7, universidad_id=1
    )

    assert host == "https://campus.tupad.edu"
    assert username == "tutor1"
    assert password_encrypted == "enc-pass"
    repo.get_credenciales_moodle.assert_awaited_once_with(7, 1)


@pytest.mark.asyncio
async def test_resolver_sin_universidad_activa_es_409():
    """OQ5: superadmin sin universidad elegida -> universidad_id=None."""
    repo = _repo(None)

    with pytest.raises(HTTPException) as exc:
        await resolver_credenciales_moodle(repo, usuario_id=7, universidad_id=None)

    assert exc.value.status_code == 409
    repo.get_credenciales_moodle.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolver_sin_membresia_es_424():
    repo = _repo(None)

    with pytest.raises(HTTPException) as exc:
        await resolver_credenciales_moodle(repo, usuario_id=7, universidad_id=1)

    assert exc.value.status_code == 424


@pytest.mark.asyncio
async def test_resolver_membresia_sin_credenciales_es_424():
    repo = _repo(CredencialesMoodle("https://campus.tupad.edu", None, None))

    with pytest.raises(HTTPException) as exc:
        await resolver_credenciales_moodle(repo, usuario_id=7, universidad_id=1)

    assert exc.value.status_code == 424
    assert "credenciales" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_resolver_host_null_es_424_sin_fallback(monkeypatch):
    """D1/OP-1: host NULL -> 424 accionable, SIN fallback a ningún host viejo.
    El resolver NUNCA lee usuarios.moodle_host (no recibe ni el objeto usuario)."""
    repo = _repo(CredencialesMoodle(None, "tutor1", "enc-pass"))

    with pytest.raises(HTTPException) as exc:
        await resolver_credenciales_moodle(repo, usuario_id=7, universidad_id=1)

    assert exc.value.status_code == 424
    assert "campus" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_resolver_host_vacio_tambien_es_424():
    repo = _repo(CredencialesMoodle("", "tutor1", "enc-pass"))

    with pytest.raises(HTTPException) as exc:
        await resolver_credenciales_moodle(repo, usuario_id=7, universidad_id=1)

    assert exc.value.status_code == 424
