"""Integration tests for GET /api/v1/pendientes/moodle.

Nota de mantenimiento: este test venía fallando desde la Fase 1 del plan
multi-tenant y la falla estaba mal atribuida a `passlib`/`bcrypt`. Eran DOS
problemas encadenados: el entorno tenía instalado `bcrypt` 5.0.0 cuando
`requirements.txt` pinea 4.0.1, y eso hacía explotar `hash_password()` antes de
llegar a la línea siguiente — que era la realmente rota, porque la Fase 1
cambió la firma de `create_access_token` (de recibir un dict de claims a
`(user_id, username, *, rol, universidad_activa_id, es_superadmin)`).

Al arreglar el entorno apareció el error real. El escenario también se
actualizó al mundo multi-tenant: para llegar al 424 "sin credenciales" hace
falta una universidad activa CON campus configurado y una membresía SIN
credenciales. Sin universidad activa el resolver corta antes con 409, que es
un caso distinto y está cubierto aparte.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.dependencies import get_db
from app.core.security import hash_password, create_access_token
from app.models import Usuario
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario_universidad import UsuarioUniversidad


@pytest.fixture(autouse=True)
def _limpiar_overrides():
    yield
    app.dependency_overrides.clear()


def _make_token(user: Usuario, universidad_id: int | None, rol: RolEnum | None) -> str:
    return create_access_token(
        user.id,
        user.username,
        rol=rol.value if rol is not None else None,
        universidad_activa_id=universidad_id,
        es_superadmin=False,
    )


async def _tutor_con_membresia_sin_credenciales(
    db_session: AsyncSession,
) -> tuple[Usuario, Universidad]:
    """Tutor con membresía activa en una universidad que SÍ tiene campus,
    pero sin credenciales Moodle propias."""
    universidad = Universidad(
        nombre="Universidad Test",
        moodle_host="https://campus.test.edu",
        activa=True,
    )
    db_session.add(universidad)
    await db_session.flush()

    user = Usuario(
        username="tutor_test",
        nombre="Tutor Test",
        password_hash=hash_password("password123"),
        rol=RolEnum.TUTOR,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        UsuarioUniversidad(
            usuario_id=user.id,
            universidad_id=universidad.id,
            rol=RolEnum.TUTOR,
            moodle_username=None,
            moodle_password_encrypted=None,
            activo=True,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(universidad)
    return user, universidad


async def _get_pendientes(db_session: AsyncSession, token: str):
    # Sólo se overridea la sesión: `get_current_user`, `get_universidad_activa`
    # y el resolver de credenciales corren de verdad, que es justamente lo que
    # estos tests verifican.
    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(
            "/api/v1/pendientes/moodle",
            headers={"Authorization": f"Bearer {token}"},
        )


@pytest.mark.asyncio
async def test_pendientes_moodle_returns_424_when_no_credentials(
    db_session: AsyncSession,
):
    """424 si el usuario no tiene credenciales Moodle en su universidad activa."""
    user, universidad = await _tutor_con_membresia_sin_credenciales(db_session)

    resp = await _get_pendientes(db_session, _make_token(user, universidad.id, RolEnum.TUTOR))

    assert resp.status_code == 424
    assert "credenciales" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pendientes_moodle_returns_409_sin_universidad_activa(
    db_session: AsyncSession,
):
    """409 —no 424— cuando el token no trae universidad activa resoluble.

    Con DOS membresías activas y sin `universidad_activa_id` en el token,
    `get_universidad_activa` no puede desambiguar y pide reautenticar. Es un
    caso distinto al de credenciales faltantes y no debe confundirse con él.
    """
    user, _ = await _tutor_con_membresia_sin_credenciales(db_session)

    otra = Universidad(nombre="Otra Universidad", moodle_host="https://otro.edu", activa=True)
    db_session.add(otra)
    await db_session.flush()
    db_session.add(
        UsuarioUniversidad(
            usuario_id=user.id,
            universidad_id=otra.id,
            rol=RolEnum.TUTOR,
            activo=True,
        )
    )
    await db_session.commit()

    resp = await _get_pendientes(db_session, _make_token(user, None, None))

    assert resp.status_code == 409
