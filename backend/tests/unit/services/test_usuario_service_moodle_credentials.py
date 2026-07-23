"""
Fase 3 multi-tenant (multi-tenant-moodle-services, D4): rediseño del perfil.

`UsuarioService.update_moodle_credentials` deja de escribir en
`usuarios.moodle_*` (campo global viejo) y pasa a escribir en la membresía
`(usuario, universidad activa)` vía `UsuarioRepository.
update_moodle_credentials_membresia`. El `moodle_host` YA NO se acepta desde
acá (es propiedad de la `Universidad`, read-only).

Ref: openspec/changes/multi-tenant-moodle-services/design.md (D4)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.usuario import MoodleCredentialsUpdate
from app.services.usuario_service import UsuarioService


@pytest.fixture(autouse=True)
def _mock_encrypt():
    """Aísla el cifrado real (Fernet exige ENCRYPTION_KEY válida en settings,
    que en este entorno de test queda en el placeholder — no es parte de lo
    que este test verifica: que la password NUNCA viaje en texto plano)."""
    with patch(
        "app.services.usuario_service.encrypt_api_key",
        side_effect=lambda plano: f"enc({plano})",
    ):
        yield


def _make_service():
    service = UsuarioService(db=AsyncMock())
    service.repo = AsyncMock()
    return service


def _membresia(host="https://campus.tupad.edu", username="tutor1"):
    universidad = MagicMock(moodle_host=host)
    return MagicMock(
        moodle_username=username,
        moodle_password_encrypted="enc-nueva",
        universidad=universidad,
    )


@pytest.mark.asyncio
async def test_update_moodle_credentials_escribe_en_la_membresia_activa():
    service = _make_service()
    service.repo.update_moodle_credentials_membresia = AsyncMock(
        return_value=_membresia(username="tutor1")
    )

    data = MoodleCredentialsUpdate(moodle_username="tutor1", moodle_password="secreta123")
    resultado = await service.update_moodle_credentials(user_id=7, universidad_id=1, data=data)

    service.repo.update_moodle_credentials_membresia.assert_awaited_once()
    kwargs = service.repo.update_moodle_credentials_membresia.call_args.kwargs
    assert kwargs["usuario_id"] == 7
    assert kwargs["universidad_id"] == 1
    assert kwargs["username"] == "tutor1"
    assert resultado.moodle_username == "tutor1"
    assert resultado.moodle_host == "https://campus.tupad.edu"


@pytest.mark.asyncio
async def test_update_moodle_credentials_cifra_la_password():
    service = _make_service()
    service.repo.update_moodle_credentials_membresia = AsyncMock(return_value=_membresia())

    data = MoodleCredentialsUpdate(moodle_username="tutor1", moodle_password="plano-secreto")
    await service.update_moodle_credentials(user_id=7, universidad_id=1, data=data)

    kwargs = service.repo.update_moodle_credentials_membresia.call_args.kwargs
    # Nunca se manda la password en texto plano al repo.
    assert kwargs["password_encrypted"] != "plano-secreto"
    assert kwargs["password_encrypted"]


@pytest.mark.asyncio
async def test_update_moodle_credentials_sin_universidad_activa_es_409():
    """OQ5: superadmin sin universidad elegida (universidad_id=None)."""
    service = _make_service()
    data = MoodleCredentialsUpdate(moodle_username="tutor1", moodle_password="secreta123")
    with pytest.raises(HTTPException) as exc:
        await service.update_moodle_credentials(user_id=7, universidad_id=None, data=data)
    assert exc.value.status_code == 409
    service.repo.update_moodle_credentials_membresia.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_moodle_credentials_sin_membresia_activa_es_404():
    service = _make_service()
    service.repo.update_moodle_credentials_membresia = AsyncMock(return_value=None)

    data = MoodleCredentialsUpdate(moodle_username="tutor1", moodle_password="secreta123")
    with pytest.raises(HTTPException) as exc:
        await service.update_moodle_credentials(user_id=7, universidad_id=1, data=data)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_moodle_credentials_no_afecta_otra_universidad():
    """Usuario con 2 membresías: editar en B no debe pisar A (verificado por el
    argumento universidad_id pasado al repo, que aísla la escritura)."""
    service = _make_service()
    service.repo.update_moodle_credentials_membresia = AsyncMock(
        return_value=_membresia(host="https://b.edu", username="user_b")
    )

    data = MoodleCredentialsUpdate(moodle_username="user_b", moodle_password="pass_b")
    await service.update_moodle_credentials(user_id=7, universidad_id=99, data=data)

    kwargs = service.repo.update_moodle_credentials_membresia.call_args.kwargs
    assert kwargs["universidad_id"] == 99
