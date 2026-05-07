"""Integration tests for GET /api/v1/pendientes/moodle."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import Usuario
from app.models.enums import RolEnum
from app.core.security import hash_password, create_access_token


def _make_token(user_id: int) -> str:
    return create_access_token({"sub": str(user_id)})


@pytest.mark.asyncio
async def test_pendientes_moodle_returns_424_when_no_credentials(db_session: AsyncSession):
    """GET /pendientes/moodle debe retornar 424 si el usuario no tiene credenciales Moodle."""
    user = Usuario(
        username="tutor_test",
        nombre="Tutor Test",
        password_hash=hash_password("password123"),
        rol=RolEnum.TUTOR,
        moodle_username=None,
        moodle_password_encrypted=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = _make_token(user.id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/pendientes/moodle",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 424
    assert "credenciales" in resp.json()["detail"].lower()
