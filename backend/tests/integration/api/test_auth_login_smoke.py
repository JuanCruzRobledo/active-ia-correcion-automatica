"""
Smoke test end-to-end (Fase 1 multi-tenant, multi-tenant-auth-jwt, tarea 8.2):
`POST /auth/login` contra una DB real (SQLite in-memory, sin mockear
`AuthService`) para confirmar que el login normal de un usuario TUPaD (estado
post-Fase-0: 1 sola membresía activa) sigue funcionando end-to-end tras el
cambio de firma de `create_access_token` y la ramificación nueva: router real
→ AuthService real → UsuarioRepository/UniversidadRepository reales → DB real
→ create_access_token/decode_token reales → serialización real de la respuesta.

Nota de entorno (ajeno a este change): `hash_password`/`verify_password`
reales rompen en esta máquina — `passlib` no puede inicializar el backend de
`bcrypt` instalado (`AttributeError: module 'bcrypt' has no attribute
'__about__'`, reproducible con un `hash_password("x")` suelto, sin tocar
nada de auth/JWT). Es la MISMA causa raíz del fallo pre-existente y
order-dependent de `tests/integration/api/test_pendientes.py` en el baseline.
Por eso acá se mockea únicamente `verify_password` (igual que
`test_arch001_auth_service.py`) — todo el resto del stack (DB, repos,
AuthService, JWT, router, HTTP) es real.

No usa el `db_session` global de conftest.py (SQLite sin JSONB/ARRAY rompe
otras tablas) — arma su propio engine con `Base.metadata.create_all` completo
(igual que test_cierre_cursada.py) porque `Usuario` tiene relationships
`lazy="selectin"` (`materias_coordinadas`/`comisiones_asignadas`) que
SQLAlchemy precarga en CUALQUIER `select(Usuario)`, incluida la que hace
`UsuarioRepository.get_by_username` — así que sus tablas dependientes
(`coordinador_materia`, `comision_tutor`, `materias`, `comisiones`, ...)
también deben existir, aunque el test no las use.
"""

from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import get_db
from app.main import app
from app.models.base import Base
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad


@compiles(JSONB, "sqlite")
def _jsonb_como_json(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json(element, compiler, **kw):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_smoke_login_usuario_tupad_una_universidad_devuelve_token_valido(db_session):
    """Estado real post-Fase-0: usuario TUTOR con exactamente 1 membresía
    activa en TUPaD. El login debe seguir funcionando end-to-end (router →
    AuthService → repos → DB real) y el token debe llevar esa universidad."""
    tupad = Universidad(nombre="TUPaD", activa=True)
    db_session.add(tupad)
    await db_session.flush()

    user = Usuario(
        username="tutor_smoke",
        nombre="Tutor Smoke",
        password_hash="hash-real-irrelevante-para-este-smoke",
        rol=RolEnum.TUTOR,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        UsuarioUniversidad(
            usuario_id=user.id, universidad_id=tupad.id, rol=RolEnum.TUTOR, activo=True
        )
    )
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session

    with patch("app.services.auth_service.verify_password", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "tutor_smoke", "password": "password123"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "requiere_seleccion" not in body
    assert body["user"]["rol"] == "TUTOR"
    assert body["user"]["universidad_activa_id"] == tupad.id
    assert body["user"]["es_superadmin"] is False

    # El token emitido debe ser un JWT válido y decodificable con los claims correctos.
    from app.core.security import decode_token

    payload = decode_token(body["access_token"])
    assert payload["user_id"] == user.id
    assert payload["universidad_activa_id"] == tupad.id
    assert payload["rol"] == "TUTOR"
    assert payload["es_superadmin"] is False


@pytest.mark.asyncio
async def test_smoke_login_credenciales_invalidas_sigue_401(db_session):
    user = Usuario(
        username="tutor_smoke2",
        nombre="Tutor Smoke 2",
        password_hash="hash-real-irrelevante-para-este-smoke",
        rol=RolEnum.TUTOR,
    )
    db_session.add(user)
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session

    with patch("app.services.auth_service.verify_password", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "tutor_smoke2", "password": "incorrecta"},
            )

    assert resp.status_code == 401
