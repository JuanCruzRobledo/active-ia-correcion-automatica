"""Per-user OpenRouter model reaches preferences, validation and corrections."""
import json
import runpy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.config import Settings
from app.core.exceptions import N8NTimeoutError
from app.integrations import ia_provider, openrouter_client
from app.models.usuario import Usuario
from app.routers.perfil import get_profile, update_api_key, update_correction_provider
from app.schemas.perfil import UpdateApiKeyRequest, UpdateCorrectionProviderRequest
from app.services.correccion_service import CorreccionService
from pydantic import ValidationError

DEFAULT = "google/gemini-3.8-flash"
CUSTOM = "anthropic/claude-sonnet-5.5"


def test_defaults_and_persisted_model():
    assert Settings.model_fields["GEMINI_MODEL"].default == "gemini-3.8-flash"
    assert Settings.model_fields["OPENROUTER_MODEL"].default == DEFAULT
    assert Usuario.__table__.c.openrouter_model.default.arg == DEFAULT


def test_migration_backfills_existing_users_persists_model_and_downgrades():
    migration = runpy.run_path(str(Path(__file__).parents[2] / "alembic" / "versions" /
        "20261022_1200_f8b4d2e6c901_usuario_openrouter_model.py"))
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, updated_at DATETIME)")
        connection.exec_driver_sql("INSERT INTO usuarios (id) VALUES (1)")
        with Operations.context(MigrationContext.configure(connection)):
            migration["upgrade"]()
            assert connection.execute(sa.select(Usuario.openrouter_model)).scalar_one() == DEFAULT
            connection.exec_driver_sql("INSERT INTO usuarios (id) VALUES (2)")
            connection.execute(sa.update(Usuario).where(Usuario.id == 1).values(openrouter_model=CUSTOM))
            assert connection.execute(sa.select(Usuario.openrouter_model).order_by(Usuario.id)).scalars().all() == [CUSTOM, DEFAULT]
            migration["downgrade"]()
        assert [column["name"] for column in sa.inspect(connection).get_columns("usuarios")] == ["id", "updated_at"]
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM usuarios").scalar_one() == 2


@pytest.mark.parametrize("value, expected", [("", DEFAULT), ("  ", DEFAULT), (f" {CUSTOM} ", CUSTOM)])
def test_preference_normalizes_model(value, expected):
    req = UpdateCorrectionProviderRequest(provider="openrouter", openrouter_model=value)
    assert req.openrouter_model == expected


@pytest.mark.parametrize("value", ["claude", "provider/model with spaces", "provider/", "x" * 201])
def test_preference_rejects_malformed_model(value):
    with pytest.raises(ValidationError):
        UpdateCorrectionProviderRequest(provider="openrouter", openrouter_model=value)


@pytest.mark.asyncio
async def test_save_model_without_reentering_key_and_profile_roundtrip():
    user = SimpleNamespace(id=1, username="u", nombre="U", email=None, primer_login=False,
        correction_provider="openrouter", openrouter_model=DEFAULT,
        gemini_api_key_encrypted=None, gemini_api_key_valid=False,
        openrouter_api_key_encrypted=None, activo=True, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc), last_login=None)
    with patch("app.routers.perfil.UsuarioRepository.update", new_callable=AsyncMock):
        result = await update_correction_provider(
            UpdateCorrectionProviderRequest(provider="openrouter", openrouter_model=CUSTOM),
            current_user=user, db=AsyncMock())
    assert result.openrouter_model == CUSTOM
    profile = await get_profile(current_user=user, db=AsyncMock(),
        ctx=SimpleNamespace(universidad_id=None, rol=None))
    assert profile.openrouter_model == CUSTOM
    assert user.openrouter_api_key_encrypted is None


@pytest.mark.asyncio
async def test_switching_provider_preserves_saved_model():
    user = SimpleNamespace(openrouter_model=CUSTOM)
    with patch("app.routers.perfil.UsuarioRepository.update", new_callable=AsyncMock):
        await update_correction_provider(UpdateCorrectionProviderRequest(provider="gemini"),
            current_user=user, db=AsyncMock())
    assert user.openrouter_model == CUSTOM


@pytest.mark.asyncio
async def test_api_key_validation_uses_saved_model():
    user = SimpleNamespace(id=1, openrouter_model=CUSTOM)
    with patch.object(ia_provider, "validar_api_key", new_callable=AsyncMock, return_value=False) as validate:
        await update_api_key(UpdateApiKeyRequest(provider="openrouter", gemini_api_key="k" * 25),
            current_user=user, db=AsyncMock())
    assert validate.call_args.kwargs["model"] == CUSTOM


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [DEFAULT, CUSTOM])
async def test_model_reaches_http_request_metadata_and_key_check(model):
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": json.dumps({"nota": 8})}}]}
    client = AsyncMock()
    client.post.return_value = response
    with patch.object(openrouter_client.httpx, "AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        result = await openrouter_client.corregir({"codigo": "x", "rubrica": {}, "api_key": "k", "model": model})
        assert client.post.call_args.kwargs["json"]["model"] == model
        assert result["metadata"]["modelo"] == model
        assert await ia_provider.validar_api_key("openrouter", "k", model=model)
        assert client.post.call_args.kwargs["json"]["model"] == model


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openrouter", "gemini"])
async def test_primary_and_failover_use_user_model(provider):
    service = CorreccionService(MagicMock())
    service.usuario_repo.get_by_id = AsyncMock(return_value=SimpleNamespace(openrouter_model=CUSTOM))
    service._credencial_secundaria = AsyncMock(return_value="secondary")
    service._build_correction_payload = MagicMock(return_value={"api_key": "secondary"})
    async def call(payload, provider="gemini"):
        if provider == "gemini":
            raise N8NTimeoutError("timeout")
        assert payload["model"] == CUSTOM
        return {"ok": True}
    service._call_ia_with_retry = AsyncMock(side_effect=call)
    result, effective = await service._corregir_codigo_con_failover(
        {"api_key": "primary"}, MagicMock(), MagicMock(), provider, 1)
    assert effective == "openrouter"
    assert result == {"ok": True}
