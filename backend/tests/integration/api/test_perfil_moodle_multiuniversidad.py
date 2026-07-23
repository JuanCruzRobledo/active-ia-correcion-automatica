"""
Integration tests — Fase 3 multi-tenant (multi-tenant-moodle-services, D4):
rediseño del perfil.

- GET /perfil: `moodle_host`/`moodle_username`/`moodle_configured` se leen de
  la membresía `(usuario, universidad activa)`, con `moodle_host` READ-ONLY
  (propiedad de la Universidad de la membresía), no de `usuarios.moodle_*`.
- PATCH /usuarios/me/moodle-credentials: escribe en esa misma membresía; ya
  NO acepta `moodle_host`; un usuario con 2 membresías que edita en B no
  afecta A.

Sin DB real Postgres: SQLite en memoria con SOLO las tablas necesarias (mismo
patrón que test_usuario_repository_credenciales_moodle.py), montando la app
real vía ASGITransport y overrideando get_db/get_current_user/get_universidad_activa.
"""

import json
import sqlite3
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.main import app
from app.models.base import Base
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad

sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)


@compiles(JSONB, "sqlite")
def _j(e, c, **k):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _a(e, c, **k):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    # Usuario.materias_coordinadas/comisiones_asignadas son lazy="selectin": se
    # cargan SIEMPRE al consultar un Usuario, así que hace falta el metadata
    # COMPLETO (no un subset de tablas) — mismo patrón que test_arch001_moodle_repos.py.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _crear_usuario_con_membresias(db) -> tuple[Usuario, Universidad, Universidad]:
    usuario = Usuario(username="tutor1", nombre="Tutor Uno", password_hash="x", rol=RolEnum.TUTOR)
    uni_a = Universidad(nombre="Uni A", moodle_host="https://a.edu")
    uni_b = Universidad(nombre="Uni B", moodle_host="https://b.edu")
    db.add_all([usuario, uni_a, uni_b])
    await db.flush()
    db.add(UsuarioUniversidad(
        usuario_id=usuario.id, universidad_id=uni_a.id, rol=RolEnum.TUTOR,
        moodle_username="user_a", moodle_password_encrypted="enc_a",
    ))
    db.add(UsuarioUniversidad(
        usuario_id=usuario.id, universidad_id=uni_b.id, rol=RolEnum.TUTOR,
        moodle_username=None, moodle_password_encrypted=None,
    ))
    await db.commit()
    await db.refresh(usuario)
    return usuario, uni_a, uni_b


def _override(db, usuario, universidad_id):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: usuario
    app.dependency_overrides[get_universidad_activa] = lambda: ContextoUniversidad(
        universidad_id=universidad_id, rol=RolEnum.TUTOR, es_superadmin=False
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_perfil_host_read_only_desde_universidad_activa(db_session):
    usuario, uni_a, uni_b = await _crear_usuario_con_membresias(db_session)
    _override(db_session, usuario, uni_a.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/perfil")

    assert resp.status_code == 200
    body = resp.json()
    assert body["moodle_host"] == "https://a.edu"
    assert body["moodle_username"] == "user_a"
    assert body["moodle_configured"] is True


@pytest.mark.asyncio
async def test_get_perfil_cambia_con_la_universidad_activa(db_session):
    """El mismo usuario, universidad B activa: host y configured DISTINTOS."""
    usuario, uni_a, uni_b = await _crear_usuario_con_membresias(db_session)
    _override(db_session, usuario, uni_b.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/perfil")

    assert resp.status_code == 200
    body = resp.json()
    assert body["moodle_host"] == "https://b.edu"
    assert body["moodle_username"] is None
    assert body["moodle_configured"] is False


@pytest.mark.asyncio
async def test_patch_moodle_credentials_escribe_en_membresia_activa_sin_afectar_otra(db_session):
    usuario, uni_a, uni_b = await _crear_usuario_con_membresias(db_session)
    _override(db_session, usuario, uni_b.id)

    with patch(
        "app.services.usuario_service.encrypt_api_key",
        side_effect=lambda plano: f"enc({plano})",
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/usuarios/me/moodle-credentials",
                json={"moodle_username": "user_b_nuevo", "moodle_password": "secreta123"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["moodle_username"] == "user_b_nuevo"
    assert body["moodle_host"] == "https://b.edu"

    # A no se tocó.
    _override(db_session, usuario, uni_a.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_a = await client.get("/api/v1/perfil")
    assert resp_a.json()["moodle_username"] == "user_a"


@pytest.mark.asyncio
async def test_patch_moodle_credentials_no_acepta_moodle_host():
    """D4: el schema ya no tiene moodle_host — un intento de mandarlo se ignora
    (Pydantic descarta campos extra por default), la validación no lo exige."""
    from app.schemas.usuario import MoodleCredentialsUpdate

    assert "moodle_host" not in MoodleCredentialsUpdate.model_fields
