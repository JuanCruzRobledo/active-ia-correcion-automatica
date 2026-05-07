"""Unit tests for MoodleService.get_token."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.moodle_service import MoodleService, MoodleAuthError, MoodleConnectionError


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def service(db):
    svc = MoodleService(db)
    # Clear token cache between tests
    svc._token_cache.clear()
    return svc


@pytest.mark.asyncio
async def test_get_token_success(service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status = MagicMock()

    with patch("app.core.security.decrypt_api_key", return_value="password"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        token = await service.get_token(
            user_id=1,
            moodle_host="https://moodle.example.com",
            username="user",
            password_encrypted="encrypted",
        )

    assert token == "abc123"
    assert 1 in service._token_cache


@pytest.mark.asyncio
async def test_get_token_uses_cache(service):
    future = datetime.utcnow() + timedelta(minutes=30)
    service._token_cache[1] = ("cached_token", future)

    with patch("app.core.security.decrypt_api_key") as mock_decrypt:
        token = await service.get_token(
            user_id=1,
            moodle_host="https://moodle.example.com",
            username="user",
            password_encrypted="encrypted",
        )
        mock_decrypt.assert_not_called()

    assert token == "cached_token"


@pytest.mark.asyncio
async def test_get_token_invalid_login_raises_auth_error(service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "Invalid login, please try again"}
    mock_response.raise_for_status = MagicMock()

    with patch("app.core.security.decrypt_api_key", return_value="wrongpassword"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(MoodleAuthError):
            await service.get_token(
                user_id=2,
                moodle_host="https://moodle.example.com",
                username="user",
                password_encrypted="encrypted",
            )


@pytest.mark.asyncio
async def test_get_token_timeout_raises_connection_error(service):
    import httpx

    with patch("app.core.security.decrypt_api_key", return_value="password"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(MoodleConnectionError):
            await service.get_token(
                user_id=3,
                moodle_host="https://moodle.example.com",
                username="user",
                password_encrypted="encrypted",
            )
