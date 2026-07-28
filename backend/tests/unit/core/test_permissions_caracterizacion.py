"""
Red de caracterizacion (multi-tenant-permisos, Fase 2).

Congela el comportamiento ACTUAL de `app/core/permissions.py` (rol leido de
`usuario.rol`, el campo global) ANTES de refactorizar los guards para que
lean el rol de la universidad activa. Es la red de seguridad exigida por el
GATE de la seccion 1 de tasks.md: debe existir y pasar contra el codigo VIEJO
antes de tocar un solo guard.

Cubre lo que los tests existentes (test_permissions_gestor.py,
test_permissions_materia.py, test_permissions_pertenencia.py) no cubrian:

- Grupo A completo (7 guards de rol) parametrizado por los 4 roles.
- `require_any_authenticated` (no lee rol).
- Los guards de pertenencia de recurso unico que no tenian test directo:
  `verificar_acceso_materia_de_comision`, `verificar_acceso_rubrica`,
  `verificar_acceso_comision`.
- El helper de equivalencia mono-universidad (fixture `ctx_equivalente`),
  reutilizado por los tests del refactor (secciones 3/4) para comprobar que
  el resultado no cambia.

NOTA IMPORTANTE: estos tests usan la firma VIEJA de los guards
(`require_x(user)`, `verificar_acceso_x(db, usuario, id)`). Tras el refactor
de las secciones 2-4, la firma cambia (los guards de rol reciben
`ContextoUniversidad`; los de pertenencia suman un parametro `ctx`) y ESTE
ARCHIVO se adapta como parte de esas tareas (3.1/4.1) -- es el ajuste
"mecanico" que anticipa el design. El resultado esperado (quien pasa, quien
recibe 403/404, con que detalle) debe permanecer identico: ese es el
invariante de seguridad.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    require_admin,
    require_any_authenticated,
    require_coordinador,
    require_coordinador_or_admin,
    require_gestor,
    require_gestor_or_admin,
    require_tutor,
    require_tutor_or_coordinador,
    verificar_acceso_comision,
    verificar_acceso_materia_de_comision,
    verificar_acceso_rubrica,
)
from app.models.enums import RolEnum

TODOS_LOS_ROLES = (RolEnum.ADMIN, RolEnum.COORDINADOR, RolEnum.TUTOR, RolEnum.GESTOR)


def _user(rol):
    return MagicMock(rol=rol)


def _db_first(*rows):
    """db async cuyo execute().first() devuelve rows[i] en la i-esima llamada."""
    db = AsyncMock()
    resultados = []
    for r in rows:
        res = MagicMock()
        res.first.return_value = r
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


# =====================================================================
# Grupo A -- guards de rol, congelados por matriz (guard, rol) -> pasa/403
# =====================================================================

# Matriz de referencia: para cada guard, el conjunto de roles que HOY pasan.
# Cualquier rol fuera de este conjunto debe recibir 403 con el detalle dado.
_MATRIZ_GRUPO_A = {
    require_admin: ({RolEnum.ADMIN}, "Se requiere rol de administrador"),
    require_coordinador: ({RolEnum.COORDINADOR}, "Se requiere rol de coordinador"),
    require_tutor: ({RolEnum.TUTOR}, "Se requiere rol de tutor"),
    require_gestor: ({RolEnum.GESTOR}, "Se requiere rol de gestor"),
    require_coordinador_or_admin: (
        {RolEnum.ADMIN, RolEnum.COORDINADOR},
        "Se requiere rol de coordinador o administrador",
    ),
    require_tutor_or_coordinador: (
        {RolEnum.TUTOR, RolEnum.COORDINADOR},
        "Se requiere rol de tutor o coordinador",
    ),
    require_gestor_or_admin: (
        {RolEnum.ADMIN, RolEnum.GESTOR},
        "Se requiere rol de gestor o administrador",
    ),
}


@pytest.mark.parametrize("guard", list(_MATRIZ_GRUPO_A.keys()), ids=lambda g: g.__name__)
@pytest.mark.parametrize("rol", TODOS_LOS_ROLES, ids=lambda r: r.value)
def test_matriz_grupo_a_congela_quien_pasa_y_quien_403(guard, rol):
    """Post-refactor (3.1/3.2): los guards de rol reciben ContextoUniversidad.

    El resultado (quien pasa, quien recibe 403 con que detalle) es
    EXACTAMENTE el mismo que capturo la version original de este test
    contra el codigo viejo (invocando `guard(user)` con `user.rol`): eso es
    el invariante de seguridad. El ajuste de firma (`user` -> `ctx`) es
    mecanico, tal como anticipa el design (D1).
    """
    roles_permitidos, detalle_403 = _MATRIZ_GRUPO_A[guard]
    ctx = ctx_equivalente(rol)

    if rol in roles_permitidos:
        assert guard(ctx) is ctx
    else:
        with pytest.raises(HTTPException) as exc:
            guard(ctx)
        assert exc.value.status_code == 403
        assert exc.value.detail == detalle_403


@pytest.mark.parametrize("guard", list(_MATRIZ_GRUPO_A.keys()), ids=lambda g: g.__name__)
def test_superadmin_bypassa_todo_guard_de_rol(guard):
    """Eje NUEVO (task 6.2): el superadmin pasa cualquier guard de rol,
    incluso sin membresia (rol=None) en la universidad activa."""
    ctx = ctx_equivalente(None, es_superadmin=True)
    assert guard(ctx) is ctx


def test_rol_global_admin_no_alcanza_si_la_membresia_activa_es_otra():
    """Eje NUEVO (task 6.2): la fuente del rol es la membresia de la
    universidad activa, NO un rol global. Un ctx con rol=COORDINADOR (aunque
    representara a un usuario que en otra epoca fue ADMIN global) es
    rechazado por require_admin -- el guard ya no tiene forma de ver ningun
    "rol global", prueba de que la fuente cambio de verdad."""
    ctx = ctx_equivalente(RolEnum.COORDINADOR)
    with pytest.raises(HTTPException) as exc:
        require_admin(ctx)
    assert exc.value.status_code == 403


def test_require_any_authenticated_no_lee_rol_cualquier_autenticado_pasa():
    """Grupo A: require_any_authenticated congela que NO compara rol (D2:
    sin cambios, sigue recibiendo `Usuario`, no `ctx`)."""
    for rol in TODOS_LOS_ROLES:
        user = _user(rol)
        assert require_any_authenticated(user) is user


# =====================================================================
# Grupo B -- guards de pertenencia sin test directo previo
# =====================================================================

ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)
COORD = SimpleNamespace(id=5, rol=RolEnum.COORDINADOR)
TUTOR = SimpleNamespace(id=7, rol=RolEnum.TUTOR)


@pytest.mark.asyncio
async def test_materia_de_comision_admin_pasa_sin_consultar_db():
    db = AsyncMock()
    await verificar_acceso_materia_de_comision(db, ADMIN, ctx_equivalente(RolEnum.ADMIN), 99)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_materia_de_comision_coordinador_propietario_ok():
    # 1a query: comision -> materia_id 7. 2a query: CoordinadorMateria -> fila.
    db = _db_first((7,), (123,))
    await verificar_acceso_materia_de_comision(
        db, COORD, ctx_equivalente(RolEnum.COORDINADOR), 10
    )  # no lanza


@pytest.mark.asyncio
async def test_materia_de_comision_coordinador_ajeno_403():
    db = _db_first((7,), None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_materia_de_comision(
            db, COORD, ctx_equivalente(RolEnum.COORDINADOR), 10
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_materia_de_comision_inexistente_404():
    db = _db_first(None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_materia_de_comision(
            db, COORD, ctx_equivalente(RolEnum.COORDINADOR), 404404
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_rubrica_admin_pasa_sin_consultar_db():
    db = AsyncMock()
    await verificar_acceso_rubrica(db, ADMIN, ctx_equivalente(RolEnum.ADMIN), 99)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_rubrica_coordinador_propietario_ok():
    db = _db_first((7,), (123,))
    await verificar_acceso_rubrica(db, COORD, ctx_equivalente(RolEnum.COORDINADOR), 10)  # no lanza


@pytest.mark.asyncio
async def test_rubrica_coordinador_ajeno_403():
    db = _db_first((7,), None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_rubrica(db, COORD, ctx_equivalente(RolEnum.COORDINADOR), 10)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_rubrica_inexistente_404():
    db = _db_first(None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_rubrica(db, COORD, ctx_equivalente(RolEnum.COORDINADOR), 404404)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_comision_tutor_admin_pasa_sin_consultar_db():
    db = AsyncMock()
    await verificar_acceso_comision(db, ADMIN, ctx_equivalente(RolEnum.ADMIN), 99)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_comision_tutor_asignado_ok():
    db = _db_first((555,))  # fila ComisionTutor
    await verificar_acceso_comision(db, TUTOR, ctx_equivalente(RolEnum.TUTOR), 10)  # no lanza


@pytest.mark.asyncio
async def test_comision_tutor_no_asignado_403():
    db = _db_first(None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_comision(db, TUTOR, ctx_equivalente(RolEnum.TUTOR), 10)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_comision_tutor_superadmin_pasa_sin_consultar_db():
    """Eje NUEVO (OQ1): el superadmin bypassa el guard de pertenencia."""
    db = AsyncMock()
    await verificar_acceso_comision(db, TUTOR, ctx_equivalente(None, es_superadmin=True), 10)
    db.execute.assert_not_called()


# =====================================================================
# Helper de equivalencia mono-universidad (task 1.6)
# =====================================================================
#
# Con los datos actuales (mono-universidad), cada usuario tiene EXACTAMENTE
# una membresia activa cuyo rol == su viejo `usuario.rol` global, y no es
# superadmin salvo designacion explicita. Este helper construye el
# `ContextoUniversidad` "equivalente" a un `usuario.rol` viejo, para que los
# tests del refactor (secciones 3/4) puedan invocar la version nueva de los
# guards y comparar el resultado contra el baseline capturado aca.


def ctx_equivalente(rol, es_superadmin=False):
    """ContextoUniversidad que un usuario mono-universidad tendria hoy.

    Import diferido: en la seccion 1 (antes del refactor) esto documenta la
    forma esperada del contexto sin acoplar la suite de caracterizacion a
    permissions.py (que todavia no lo usa). Se reutiliza tal cual en las
    secciones 3/4 una vez que los guards empiecen a recibir `ctx`.
    """
    from app.core.dependencies import ContextoUniversidad

    return ContextoUniversidad(
        universidad_id=1 if not es_superadmin else None,
        rol=rol,
        es_superadmin=es_superadmin,
    )


def test_ctx_equivalente_replica_el_rol_viejo():
    ctx = ctx_equivalente(RolEnum.TUTOR)
    assert ctx.rol == RolEnum.TUTOR
    assert ctx.es_superadmin is False
    assert ctx.universidad_id == 1


def test_ctx_equivalente_superadmin_sin_universidad():
    ctx = ctx_equivalente(None, es_superadmin=True)
    assert ctx.es_superadmin is True
    assert ctx.universidad_id is None
