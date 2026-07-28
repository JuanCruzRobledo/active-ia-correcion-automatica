"""
Fase 3 multi-tenant (multi-tenant-moodle-services): `CierreCursadaService`
migró `token_de_usuario` y `generar` a resolver host+credenciales de la
universidad activa (D1/D2), y `generar` aplica el guard OQ1 (la materia debe
pertenecer a esa universidad antes de mintear el token).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.repositories.usuario_repository import CredencialesMoodle
from app.services.cierre_cursada_service import CierreCursadaService


@pytest.fixture
def service():
    svc = CierreCursadaService(AsyncMock())
    svc.usuario_repo = AsyncMock()
    svc.moodle = AsyncMock()
    svc.moodle.get_token = AsyncMock(return_value="tok")
    return svc


# ============================== token_de_usuario ==============================


@pytest.mark.asyncio
async def test_token_de_usuario_resuelve_de_la_universidad_activa(service):
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://a.edu", "user_a", "pass_a")
    )
    usuario = MagicMock(id=7)

    token, host = await service.token_de_usuario(usuario, universidad_id=1)

    assert token == "tok"
    assert host == "https://a.edu"
    service.usuario_repo.get_credenciales_moodle.assert_awaited_once_with(7, 1)


@pytest.mark.asyncio
async def test_token_de_usuario_sin_membresia_es_424(service):
    service.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await service.token_de_usuario(MagicMock(id=7), universidad_id=1)
    assert exc.value.status_code == 424


@pytest.mark.asyncio
async def test_token_de_usuario_host_null_es_424_sin_fallback(service):
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle(None, "user_a", "pass_a")
    )
    with pytest.raises(HTTPException) as exc:
        await service.token_de_usuario(MagicMock(id=7), universidad_id=1)
    assert exc.value.status_code == 424
    assert "campus" in exc.value.detail.lower()


# ============================== generar: guard OQ1 ==============================


@pytest.mark.asyncio
async def test_generar_materia_de_otra_universidad_es_409(service):
    materia = MagicMock(universidad_id=2, moodle_course_id=555)
    service._get_materia_configurada = AsyncMock(return_value=materia)

    with pytest.raises(HTTPException) as exc:
        await service.generar(materia_id=10, cuatrimestre_id=3, usuario=MagicMock(id=7), universidad_id=1)

    assert exc.value.status_code == 409
    service.moodle.get_token.assert_not_called()
