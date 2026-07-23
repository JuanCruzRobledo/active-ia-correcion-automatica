"""
Fase 3 multi-tenant (multi-tenant-moodle-services): `MoodleService.get_pendientes`
migró la fuente de host+credenciales al resolver de la universidad activa
(`UsuarioRepository.get_credenciales_moodle`), reemplazando la lectura de
`usuario.moodle_*` (campo global viejo).

Se mockean comision_repo/rubrica_repo (devuelven listas vacías) para aislar el
test en la resolución de credenciales — el resto del método ya está cubierto
por otros tests de armado de pendientes.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.repositories.usuario_repository import CredencialesMoodle
from app.services.moodle_service import MoodleService


@pytest.fixture
def service():
    svc = MoodleService(AsyncMock())
    svc.usuario_repo = AsyncMock()
    svc.comision_repo = AsyncMock()
    svc.comision_repo.get_moodle_habilitadas_de_tutor = AsyncMock(return_value=[])
    svc.get_token = AsyncMock(return_value="tok")
    return svc


@pytest.mark.asyncio
async def test_get_pendientes_resuelve_credenciales_de_la_universidad_activa(service):
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://campus.a.edu", "tutor_a", "enc_a")
    )

    await service.get_pendientes(user_id=7, universidad_id=1)

    service.usuario_repo.get_credenciales_moodle.assert_awaited_once_with(7, 1)
    kwargs = service.get_token.call_args.kwargs
    assert kwargs["moodle_host"] == "https://campus.a.edu"
    assert kwargs["username"] == "tutor_a"
    assert kwargs["password_encrypted"] == "enc_a"


@pytest.mark.asyncio
async def test_get_pendientes_distingue_credenciales_por_universidad(service):
    """Invariante central: el mismo usuario, 2 universidades, credenciales DISTINTAS."""
    creds_por_uni = {
        1: CredencialesMoodle("https://a.edu", "user_a", "pass_a"),
        2: CredencialesMoodle("https://b.edu", "user_b", "pass_b"),
    }
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        side_effect=lambda uid, univ_id: creds_por_uni[univ_id]
    )

    await service.get_pendientes(user_id=7, universidad_id=1)
    assert service.get_token.call_args.kwargs["moodle_host"] == "https://a.edu"

    await service.get_pendientes(user_id=7, universidad_id=2)
    assert service.get_token.call_args.kwargs["moodle_host"] == "https://b.edu"


@pytest.mark.asyncio
async def test_get_pendientes_sin_membresia_es_424(service):
    service.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await service.get_pendientes(user_id=7, universidad_id=1)
    assert exc.value.status_code == 424
    service.get_token.assert_not_called()


@pytest.mark.asyncio
async def test_get_pendientes_host_null_es_424_sin_fallback(service):
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle(None, "tutor", "enc")
    )

    with pytest.raises(HTTPException) as exc:
        await service.get_pendientes(user_id=7, universidad_id=1)
    assert exc.value.status_code == 424
    assert "campus" in exc.value.detail.lower()
    service.get_token.assert_not_called()


@pytest.mark.asyncio
async def test_get_pendientes_sin_universidad_activa_es_409(service):
    with pytest.raises(HTTPException) as exc:
        await service.get_pendientes(user_id=7, universidad_id=None)
    assert exc.value.status_code == 409
    service.usuario_repo.get_credenciales_moodle.assert_not_called()
