"""
Fase 1 multi-tenant (multi-tenant-auth-jwt): dependency `get_universidad_activa`.

`get_current_user`/`get_current_user_optional` NO se tocan — este dependency
nuevo los reusa (Depends(get_current_user)) y agrega la resolución/validación
de la universidad activa. Es opt-in: en Fase 1 no se monta en ningún endpoint
existente.

Ref: openspec/changes/multi-tenant-auth-jwt/design.md (D3, D5, D6)
Ref: openspec/changes/multi-tenant-auth-jwt/specs/dependency-universidad-activa/spec.md
Ref: openspec/changes/multi-tenant-auth-jwt/tasks.md (5.1-5.7)
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import get_universidad_activa
from app.core.security import create_access_token
from app.models.base import Base
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad
from app.repositories.usuario_repository import UsuarioRepository


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Usuario.__table__, Universidad.__table__, UsuarioUniversidad.__table__],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _crear_usuario(db, username="tutor1", es_superadmin=False) -> Usuario:
    u = Usuario(
        username=username,
        nombre="Usuario Test",
        password_hash="x",
        rol=RolEnum.TUTOR,
        es_superadmin=es_superadmin,
    )
    db.add(u)
    await db.flush()
    return u


async def _crear_universidad(db, nombre="TUPaD", activa=True) -> Universidad:
    uni = Universidad(nombre=nombre, activa=activa)
    db.add(uni)
    await db.flush()
    return uni


async def _crear_membresia(db, usuario, universidad, rol=RolEnum.TUTOR, activo=True):
    m = UsuarioUniversidad(
        usuario_id=usuario.id, universidad_id=universidad.id, rol=rol, activo=activo
    )
    db.add(m)
    await db.flush()
    return m


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _resolver(db, token: str, current_user: Usuario):
    """Llama get_universidad_activa como si FastAPI ya hubiera resuelto sus
    dependencias (current_user via get_current_user, credentials via el token)."""
    return await get_universidad_activa(
        credentials=_creds(token), current_user=current_user, db=db
    )


# ============================ 5.1: miembro activo obtiene contexto ============================


@pytest.mark.asyncio
async def test_miembro_activo_obtiene_contexto_de_su_universidad(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni, rol=RolEnum.TUTOR)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol="TUTOR", universidad_activa_id=uni.id,
        es_superadmin=False,
    )

    ctx = await _resolver(db_session, token, usuario)

    assert ctx.universidad_id == uni.id
    assert ctx.rol == RolEnum.TUTOR
    assert ctx.es_superadmin is False


# =================== 5.2: membresía revocada / universidad inactiva -> 403 ===================


@pytest.mark.asyncio
async def test_membresia_revocada_es_rechazada_403(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni, activo=False)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol="TUTOR", universidad_activa_id=uni.id,
        es_superadmin=False,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolver(db_session, token, usuario)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_universidad_inactiva_es_rechazada_403(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session, activa=False)
    await _crear_membresia(db_session, usuario, uni)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol="TUTOR", universidad_activa_id=uni.id,
        es_superadmin=False,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolver(db_session, token, usuario)
    assert exc.value.status_code == 403


# ============================ 5.3: rol viene de la base, no del claim ============================


@pytest.mark.asyncio
async def test_rol_del_contexto_viene_de_la_base_no_del_claim(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni, rol=RolEnum.COORDINADOR)
    await db_session.commit()

    # El claim del token dice ADMIN, pero la membresía real es COORDINADOR.
    token = create_access_token(
        usuario.id, usuario.username, rol="ADMIN", universidad_activa_id=uni.id,
        es_superadmin=False,
    )

    ctx = await _resolver(db_session, token, usuario)

    assert ctx.rol == RolEnum.COORDINADOR


# ==================== 5.5: fallback de token viejo sin universidad_activa_id ====================


@pytest.mark.asyncio
async def test_token_viejo_con_una_sola_membresia_se_autoresuelve(db_session):
    usuario = await _crear_usuario(db_session)
    uni = await _crear_universidad(db_session)
    await _crear_membresia(db_session, usuario, uni, rol=RolEnum.TUTOR)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol=None, universidad_activa_id=None,
        es_superadmin=False,
    )

    ctx = await _resolver(db_session, token, usuario)

    assert ctx.universidad_id == uni.id
    assert ctx.rol == RolEnum.TUTOR


@pytest.mark.asyncio
async def test_token_viejo_sin_membresias_exige_reautenticacion(db_session):
    usuario = await _crear_usuario(db_session)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol=None, universidad_activa_id=None,
        es_superadmin=False,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolver(db_session, token, usuario)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_token_viejo_con_dos_membresias_exige_reautenticacion(db_session):
    usuario = await _crear_usuario(db_session)
    uni_a = await _crear_universidad(db_session, "TUPaD")
    uni_b = await _crear_universidad(db_session, "Otra")
    await _crear_membresia(db_session, usuario, uni_a)
    await _crear_membresia(db_session, usuario, uni_b)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol=None, universidad_activa_id=None,
        es_superadmin=False,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolver(db_session, token, usuario)
    assert exc.value.status_code == 409


# ============================ 5.6: bypass de membresía para superadmin ============================


@pytest.mark.asyncio
async def test_superadmin_accede_a_universidad_activa_sin_ser_miembro(db_session):
    usuario = await _crear_usuario(db_session, "root", es_superadmin=True)
    uni = await _crear_universidad(db_session)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol=None, universidad_activa_id=uni.id,
        es_superadmin=True,
    )

    ctx = await _resolver(db_session, token, usuario)

    assert ctx.universidad_id == uni.id
    assert ctx.es_superadmin is True


@pytest.mark.asyncio
async def test_superadmin_a_universidad_inexistente_es_rechazado(db_session):
    usuario = await _crear_usuario(db_session, "root", es_superadmin=True)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol=None, universidad_activa_id=999,
        es_superadmin=True,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolver(db_session, token, usuario)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_a_universidad_inactiva_es_rechazado(db_session):
    usuario = await _crear_usuario(db_session, "root", es_superadmin=True)
    uni = await _crear_universidad(db_session, activa=False)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol=None, universidad_activa_id=uni.id,
        es_superadmin=True,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolver(db_session, token, usuario)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_sin_universidad_elegida_no_exige_membresia(db_session):
    """Modo superadmin puro: sin universidad_activa_id y sin ninguna membresía,
    el dependency NO debe pedir reautenticación (a diferencia de un no-superadmin
    en la misma situación)."""
    usuario = await _crear_usuario(db_session, "root", es_superadmin=True)
    await db_session.commit()

    token = create_access_token(
        usuario.id, usuario.username, rol=None, universidad_activa_id=None,
        es_superadmin=True,
    )

    ctx = await _resolver(db_session, token, usuario)

    assert ctx.universidad_id is None
    assert ctx.es_superadmin is True


# ========================= 5.7: get_current_user/optional intactos =========================


def test_get_current_user_no_fue_modificado_de_firma():
    import inspect

    from app.core.dependencies import get_current_user

    params = list(inspect.signature(get_current_user).parameters)
    assert params == ["credentials", "db"]


def test_get_universidad_activa_esta_montado_en_routers_con_guard_de_rol_o_pertenencia():
    """Fase 2 (multi-tenant-permisos): el dependency pasa a montarse en todo
    endpoint que ya tenga un guard de rol (`require_*`) o de pertenencia
    (`verificar_acceso_*`), reemplazando el boundary de Fase 1 (que
    deliberadamente no lo montaba en ningún lado todavía).

    OQ2: los endpoints cuyo ÚNICO guard es `require_any_authenticated` (sin
    guard de pertenencia) NO deben montarlo -- se verifica en rubricas.py,
    que tiene ambos casos en el mismo archivo.
    """
    from pathlib import Path

    routers_dir = Path(__file__).resolve().parents[3] / "app" / "routers"

    # Al menos un router con guard de rol/pertenencia lo monta (la refactorización
    # de Fase 2 no quedó a mitad de camino).
    montado_en_algun_router = any(
        "get_universidad_activa" in path.read_text(encoding="utf-8")
        for path in routers_dir.glob("*.py")
    )
    assert montado_en_algun_router, (
        "get_universidad_activa debería estar montado en al menos un router "
        "tras el refactor de Fase 2 (multi-tenant-permisos)."
    )

    # rubricas.py es el caso mixto de OQ2: algunos endpoints lo montan
    # (require_coordinador_or_admin) y otros deliberadamente NO
    # (require_any_authenticated puro).
    rubricas_source = (routers_dir / "rubricas.py").read_text(encoding="utf-8")
    assert "get_universidad_activa" in rubricas_source
    assert rubricas_source.count("ctx: ContextoUniversidad = Depends(get_universidad_activa)") < (
        rubricas_source.count("require_any_authenticated(current_user)")
        + rubricas_source.count("require_coordinador_or_admin(ctx)")
    ), "rubricas.py debería tener endpoints SIN ctx (OQ2: solo require_any_authenticated)"
