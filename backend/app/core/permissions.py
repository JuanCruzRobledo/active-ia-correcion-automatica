# app/core/permissions.py
"""
Permission validators for Active-IA.

Provides role-based access control (RBAC) functions to validate
user permissions in endpoints.

Ref: docs/specs/11-SEGURIDAD.md section 2.2
Ref: .claude/rules/backend.md
"""

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad
from app.models import Usuario
from app.models.enums import RolEnum


def _acceso_total(ctx: ContextoUniversidad) -> bool:
    """Unico punto de decision de "acceso total" (D5, multi-tenant-permisos).

    True si el usuario es superadmin (bypass global, no depende de una
    universidad concreta -- OQ1) o si su rol en la universidad activa es
    ADMIN. Reutilizado por los guards de pertenencia (Grupo B) para no
    repetir la condicion.
    """
    return ctx.es_superadmin or ctx.rol == RolEnum.ADMIN


# =========================================
# Role Validators
# =========================================


def require_admin(ctx: ContextoUniversidad) -> ContextoUniversidad:
    """
    Validate that the user has ADMIN role in the active university.

    Fase 2 multi-tenant: el rol se lee del contexto de la universidad activa
    (`get_universidad_activa`, Fase 1), no de `usuario.rol` global. Bypass
    total para `es_superadmin`.

    Args:
        ctx: Contexto de la universidad activa (rol + es_superadmin).

    Returns:
        ContextoUniversidad: The same context object (for chaining).

    Raises:
        HTTPException 403: If user is not an admin (and not superadmin).

    Usage:
        from app.core.dependencies import get_universidad_activa
        from app.core.permissions import require_admin

        @router.post("/admin-only")
        async def admin_endpoint(
            ctx: ContextoUniversidad = Depends(get_universidad_activa)
        ):
            require_admin(ctx)
            # Only admins can reach here
            pass
    """
    if ctx.es_superadmin:
        return ctx
    if ctx.rol != RolEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador",
        )
    return ctx


def require_coordinador(ctx: ContextoUniversidad) -> ContextoUniversidad:
    """
    Validate that the user has COORDINADOR role in the active university.

    Fase 2 multi-tenant: ver `require_admin`.

    Args:
        ctx: Contexto de la universidad activa (rol + es_superadmin).

    Returns:
        ContextoUniversidad: The same context object (for chaining).

    Raises:
        HTTPException 403: If user is not a coordinador (and not superadmin).

    Usage:
        @router.post("/coordinador-only")
        async def coordinador_endpoint(
            ctx: ContextoUniversidad = Depends(get_universidad_activa)
        ):
            require_coordinador(ctx)
            # Only coordinadores can reach here
            pass
    """
    if ctx.es_superadmin:
        return ctx
    if ctx.rol != RolEnum.COORDINADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de coordinador",
        )
    return ctx


def require_tutor(ctx: ContextoUniversidad) -> ContextoUniversidad:
    """
    Validate that the user has TUTOR role in the active university.

    Fase 2 multi-tenant: ver `require_admin`.

    Args:
        ctx: Contexto de la universidad activa (rol + es_superadmin).

    Returns:
        ContextoUniversidad: The same context object (for chaining).

    Raises:
        HTTPException 403: If user is not a tutor (and not superadmin).

    Usage:
        @router.post("/tutor-only")
        async def tutor_endpoint(
            ctx: ContextoUniversidad = Depends(get_universidad_activa)
        ):
            require_tutor(ctx)
            # Only tutores can reach here
            pass
    """
    if ctx.es_superadmin:
        return ctx
    if ctx.rol != RolEnum.TUTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de tutor",
        )
    return ctx


def require_gestor(ctx: ContextoUniversidad) -> ContextoUniversidad:
    """
    Validate that the user has GESTOR role in the active university.

    Fase 2 multi-tenant: ver `require_admin`.

    Args:
        ctx: Contexto de la universidad activa (rol + es_superadmin).

    Returns:
        ContextoUniversidad: The same context object (for chaining).

    Raises:
        HTTPException 403: If user is not a gestor (and not superadmin).

    Usage:
        @router.get("/gestion/cursos")
        async def list_cursos(
            ctx: ContextoUniversidad = Depends(get_universidad_activa)
        ):
            require_gestor(ctx)
            # Only gestores can reach here
            pass
    """
    if ctx.es_superadmin:
        return ctx
    if ctx.rol != RolEnum.GESTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de gestor",
        )
    return ctx


# =========================================
# Combined Role Validators
# =========================================


def require_coordinador_or_admin(ctx: ContextoUniversidad) -> ContextoUniversidad:
    """
    Validate that the user has COORDINADOR or ADMIN role in the active university.

    Fase 2 multi-tenant: ver `require_admin`.

    Args:
        ctx: Contexto de la universidad activa (rol + es_superadmin).

    Returns:
        ContextoUniversidad: The same context object (for chaining).

    Raises:
        HTTPException 403: If user is neither coordinador nor admin (and not superadmin).

    Usage:
        @router.get("/materias")
        async def list_materias(
            ctx: ContextoUniversidad = Depends(get_universidad_activa)
        ):
            require_coordinador_or_admin(ctx)
            # Coordinadores and admins can reach here
            pass
    """
    if ctx.es_superadmin:
        return ctx
    if ctx.rol not in (RolEnum.ADMIN, RolEnum.COORDINADOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de coordinador o administrador",
        )
    return ctx


def require_tutor_or_coordinador(ctx: ContextoUniversidad) -> ContextoUniversidad:
    """
    Validate that the user has TUTOR or COORDINADOR role in the active university.

    Fase 2 multi-tenant: ver `require_admin`.

    Args:
        ctx: Contexto de la universidad activa (rol + es_superadmin).

    Returns:
        ContextoUniversidad: The same context object (for chaining).

    Raises:
        HTTPException 403: If user is neither tutor nor coordinador (and not superadmin).

    Usage:
        @router.get("/comisiones/{id}/entregas")
        async def list_entregas(
            ctx: ContextoUniversidad = Depends(get_universidad_activa)
        ):
            require_tutor_or_coordinador(ctx)
            # Tutores and coordinadores can reach here
            pass
    """
    if ctx.es_superadmin:
        return ctx
    if ctx.rol not in (RolEnum.TUTOR, RolEnum.COORDINADOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de tutor o coordinador",
        )
    return ctx


def require_gestor_or_admin(ctx: ContextoUniversidad) -> ContextoUniversidad:
    """
    Validate that the user has GESTOR or ADMIN role in the active university.

    Guard de la pantalla "Gestión": la usa el GESTOR, y el ADMIN puede entrar también.
    Fase 2 multi-tenant: ver `require_admin`.

    Args:
        ctx: Contexto de la universidad activa (rol + es_superadmin).

    Returns:
        ContextoUniversidad: The same context object (for chaining).

    Raises:
        HTTPException 403: If user is neither gestor nor admin (and not superadmin).
    """
    if ctx.es_superadmin:
        return ctx
    if ctx.rol not in (RolEnum.ADMIN, RolEnum.GESTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de gestor o administrador",
        )
    return ctx


def require_any_authenticated(user: Usuario) -> Usuario:
    """
    Validate that the user is authenticated (any role).

    This is mostly a semantic function since get_current_user already
    validates authentication. Use this for clarity when any authenticated
    user is allowed.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Usage:
        @router.get("/profile")
        async def get_profile(
            current_user: Usuario = Depends(get_current_user)
        ):
            require_any_authenticated(current_user)
            # Any authenticated user can reach here
            return current_user
    """
    # User is already authenticated if we got here via get_current_user
    return user


# =========================================
# Resource-Specific Validators (guards de pertenencia REALES, con DB)
# =========================================
#
# SEC-006: acá vivían require_coordinador_of_materia y require_tutor_of_comision,
# dos placeholders sync que NO consultaban la DB (el chequeo real estaba comentado
# como TODO) y solo miraban el rol. Eran código muerto — ningún router los usaba —
# e indistinguibles de un guard real por el nombre. Se eliminaron. Los guards de
# pertenencia de verdad son los `verificar_acceso_*` de acá abajo: todos async,
# todos consultan la DB. El test tests/unit/core/test_permissions_invariante.py
# impide que vuelva a colarse un placeholder sync.


async def verificar_acceso_materia(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, materia_id: int
) -> None:
    """Valida acceso a una materia consultando la DB (guard REAL, no placeholder).

    - Acceso total (superadmin o ADMIN en la universidad activa): pasa sin consultar.
    - COORDINADOR: sólo si está asignado a la materia (CoordinadorMateria).
    - Cualquier otro rol: 403.

    Lanza HTTPException 403 si no tiene acceso. Reemplaza al placeholder
    `require_coordinador_of_materia` (que NO consultaba la DB).
    """
    if _acceso_total(ctx):
        return

    from app.models.materia import CoordinadorMateria

    result = await db.execute(
        select(CoordinadorMateria.id)
        .where(
            CoordinadorMateria.materia_id == materia_id,
            CoordinadorMateria.coordinador_id == usuario.id,
        )
        .limit(1)
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a esta materia",
        )


async def verificar_acceso_unidad(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, unidad_id: int
) -> None:
    """Resuelve la materia de una unidad y valida el acceso (ver verificar_acceso_materia)."""
    if _acceso_total(ctx):
        return

    from app.models.unidad import Unidad

    result = await db.execute(
        select(Unidad.materia_id).where(Unidad.id == unidad_id).limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unidad no encontrada"
        )
    await verificar_acceso_materia(db, usuario, ctx, row[0])


async def verificar_acceso_examen(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, examen_id: int
) -> None:
    """Resuelve la materia de un examen y valida el acceso (ver verificar_acceso_materia)."""
    if _acceso_total(ctx):
        return

    from app.models.examen_materia import ExamenMateria

    result = await db.execute(
        select(ExamenMateria.materia_id).where(ExamenMateria.id == examen_id).limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado"
        )
    await verificar_acceso_materia(db, usuario, ctx, row[0])


async def verificar_acceso_materia_de_comision(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, comision_id: int
) -> None:
    """Valida acceso a una comisión POR SU MATERIA (coordinador dueño de la materia).

    A diferencia de `verificar_acceso_comision` (que mira ComisionTutor, para
    tutores asignados), esto resuelve la materia de la comisión y valida contra
    CoordinadorMateria: el coordinador gestiona las comisiones de SUS materias.

    - Acceso total (superadmin o ADMIN en la universidad activa): pasa sin consultar.
    - COORDINADOR: sólo si está asignado a la materia de la comisión.
    - Resto: 403. Comisión inexistente: 404.
    """
    if _acceso_total(ctx):
        return

    from app.models.comision import Comision

    result = await db.execute(
        select(Comision.materia_id).where(Comision.id == comision_id).limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comisión no encontrada"
        )
    await verificar_acceso_materia(db, usuario, ctx, row[0])


async def verificar_acceso_rubrica(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, rubrica_id: int
) -> None:
    """Resuelve la materia de una rúbrica y valida el acceso (ver verificar_acceso_materia)."""
    if _acceso_total(ctx):
        return

    from app.models.rubrica import Rubrica

    result = await db.execute(
        select(Rubrica.materia_id).where(Rubrica.id == rubrica_id).limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rúbrica no encontrada"
        )
    await verificar_acceso_materia(db, usuario, ctx, row[0])


async def verificar_acceso_comision(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, comision_id: int
) -> None:
    """Versión async REAL: valida acceso a una comisión consultando la DB.

    - Acceso total (superadmin o ADMIN en la universidad activa): pasa sin consultar.
    - Otros roles: sólo si están asignados a la comisión (ComisionTutor).

    Lanza HTTPException 403 si no tiene acceso. (Reemplaza el placeholder
    `require_tutor_of_comision` para los flujos de Moodle, donde sí consultamos DB.)
    """
    if _acceso_total(ctx):
        return

    from app.models.comision import ComisionTutor

    result = await db.execute(
        select(ComisionTutor.id)
        .where(
            ComisionTutor.comision_id == comision_id,
            ComisionTutor.tutor_id == usuario.id,
        )
        .limit(1)
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a esta comisión",
        )


# =========================================
# Guards de pertenencia combinados (SEC-001 / SEC-002 / SEC-004)
# =========================================
#
# Los guards de arriba cubren ejes MUTUAMENTE EXCLUYENTES:
#   verificar_acceso_comision            -> solo ComisionTutor (el coordinador recibe 403)
#   verificar_acceso_materia_de_comision -> solo CoordinadorMateria (el tutor recibe 403)
# Los flujos de entregas/correcciones/documentos necesitan la UNION de ambos.
# No se modifican los existentes: los usan otros routers con su semantica actual.


async def verificar_acceso_comision_o_materia(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, comision_id: int
) -> None:
    """Acceso si: acceso total | tutor asignado a la comision | coordinador de su materia.

    Una sola query: el LEFT JOIN a las dos tablas puente permite distinguir
    404 (no hay fila de Comision) de 403 (hay comision pero ninguna pertenencia)
    sin pagar un segundo round-trip.

    Lanza 404 si la comision no existe, 403 si no hay pertenencia.
    """
    if _acceso_total(ctx):
        return

    from app.models.comision import Comision, ComisionTutor
    from app.models.materia import CoordinadorMateria

    result = await db.execute(
        select(Comision.id, ComisionTutor.id, CoordinadorMateria.id)
        .select_from(Comision)
        .outerjoin(
            ComisionTutor,
            and_(
                ComisionTutor.comision_id == Comision.id,
                ComisionTutor.tutor_id == usuario.id,
            ),
        )
        .outerjoin(
            CoordinadorMateria,
            and_(
                CoordinadorMateria.materia_id == Comision.materia_id,
                CoordinadorMateria.coordinador_id == usuario.id,
            ),
        )
        .where(Comision.id == comision_id)
        .limit(1)
    )
    fila = result.first()
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comisión no encontrada",
        )

    _, es_tutor, es_coordinador = fila
    if es_tutor is None and es_coordinador is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a esta comisión",
        )


async def verificar_acceso_entrega(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, entrega_id: int
) -> None:
    """Resuelve Entrega -> comision_id y delega en el guard combinado.

    Selecciona SOLO las columnas de clave: contenido_consolidado y
    pdf_contenido_b64 son deferred=True (PERF-002/006) y un select(Entrega)
    arrastraria el codigo fuente del alumno en CADA verificacion de permisos.
    """
    if _acceso_total(ctx):
        return

    from app.models.entrega import Entrega

    result = await db.execute(
        select(Entrega.id, Entrega.comision_id)
        .where(Entrega.id == entrega_id)
        .limit(1)
    )
    fila = result.first()
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrega no encontrada",
        )

    await verificar_acceso_comision_o_materia(db, usuario, ctx, fila[1])


async def verificar_acceso_correccion(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, correccion_id: int
) -> None:
    """Resuelve Correccion -> Entrega -> comision_id y delega en el guard combinado."""
    if _acceso_total(ctx):
        return

    from app.models.correccion import Correccion
    from app.models.entrega import Entrega

    result = await db.execute(
        select(Correccion.id, Entrega.comision_id)
        .join(Entrega, Correccion.entrega_id == Entrega.id)
        .where(Correccion.id == correccion_id)
        .limit(1)
    )
    fila = result.first()
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corrección no encontrada",
        )

    await verificar_acceso_comision_o_materia(db, usuario, ctx, fila[1])


async def filtrar_entregas_accesibles(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad, entrega_ids: list[int]
) -> tuple[set[int], set[int]]:
    """Particiona un lote de IDs en (permitidos, denegados) con UNA sola query.

    Los IDs inexistentes caen en denegados a proposito: no distinguir "no existe"
    de "no tenes acceso" en un lote evita convertir el endpoint en un oraculo de
    enumeracion de IDs. Los endpoints de recurso unico si distinguen 404 de 403,
    porque ahi el 404 ya es observable por otras vias.
    """
    solicitados = set(entrega_ids)
    if not solicitados:
        return set(), set()
    if _acceso_total(ctx):
        return solicitados, set()

    from app.models.comision import Comision, ComisionTutor
    from app.models.entrega import Entrega
    from app.models.materia import CoordinadorMateria

    result = await db.execute(
        select(Entrega.id)
        .select_from(Entrega)
        .join(Comision, Entrega.comision_id == Comision.id)
        .outerjoin(
            ComisionTutor,
            and_(
                ComisionTutor.comision_id == Comision.id,
                ComisionTutor.tutor_id == usuario.id,
            ),
        )
        .outerjoin(
            CoordinadorMateria,
            and_(
                CoordinadorMateria.materia_id == Comision.materia_id,
                CoordinadorMateria.coordinador_id == usuario.id,
            ),
        )
        .where(
            Entrega.id.in_(solicitados),
            or_(
                ComisionTutor.id.is_not(None),
                CoordinadorMateria.id.is_not(None),
            ),
        )
    )
    permitidos = set(result.scalars().all())
    return permitidos, solicitados - permitidos


# =========================================
# Guard defensivo de sync Moodle cross-campus (OQ1, multi-tenant-moodle-services Fase 3)
# =========================================
#
# NO es el aislamiento general de queries por universidad_id (eso es Fase 4).
# Es una red de seguridad LOCAL en los entrypoints que mintean un token Moodle
# de la universidad activa y lo usan contra un course_id/group_id de una
# Materia/Comisión: si esa Materia perteneciera a OTRA universidad, el
# course_id podría 404 en el campus activo o, peor, coincidir por casualidad
# con un curso de otra materia. El guard corta ANTES de pegarle a Moodle.
#
# `materia.universidad_id` es nullable (Fase 0, backfill histórico): una
# materia SIN universidad asignada NO se considera mismatch (no rompe el
# estado mono-universidad actual ni bloquea datos aún no migrados).


def verificar_materia_universidad_activa(materia, universidad_id_activa: int | None) -> None:
    """Guard defensivo (OQ1): la materia debe pertenecer a la universidad activa.

    Lanza HTTPException 409 si `materia.universidad_id` está seteado y
    difiere de `universidad_id_activa`. No aplica si la materia no tiene
    `universidad_id` (dato legado sin migrar) — ver nota arriba.

    Args:
        materia: instancia de `Materia` (o cualquier objeto con `.universidad_id`).
        universidad_id_activa: `ctx.universidad_id` del request.
    """
    if materia is None:
        return
    materia_universidad_id = getattr(materia, "universidad_id", None)
    if materia_universidad_id is None:
        return
    if materia_universidad_id != universidad_id_activa:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La materia no pertenece a la universidad activa",
        )


def materia_pertenece_a_universidad_activa(materia, universidad_id_activa: int | None) -> bool:
    """Versión booleana (sin excepción) para filtrar listas de materias/comisiones
    en los entrypoints que iteran varias a la vez (p. ej. `moodle_service.get_pendientes`,
    `moodle_import_service._resolver_pares`): descarta silenciosamente las que no
    pertenecen a la universidad activa, en vez de abortar todo el lote."""
    if materia is None:
        return False
    materia_universidad_id = getattr(materia, "universidad_id", None)
    if materia_universidad_id is None:
        return True
    return materia_universidad_id == universidad_id_activa


# =========================================
# Check de pertenencia GENERAL por id, semántica 404 (Fase 4, D3)
# =========================================
#
# Distinto del guard 409 de arriba (Fase 3, sync Moodle cross-campus): este es
# el check que se monta en TODO acceso por id a un recurso de las 9 entidades
# scopeadas (materia, comision, entrega, correccion, unidad, rubrica, examen,
# cierre_cursada_run, avance_snapshot). Un 403 revelaría que el recurso EXISTE
# en otra universidad; 404 lo vuelve indistinguible de un id inexistente
# (mismo criterio que `filtrar_entregas_accesibles`, OQ1 del design).


def verificar_pertenencia_universidad(
    recurso,
    universidad_id_activa: int | None,
    *,
    detail: str = "Recurso no encontrado",
) -> None:
    """Valida que `recurso` pertenezca a la universidad activa. 404 si no.

    Firma calcada de `verificar_materia_universidad_activa` (Fase 3): recibe el
    `int | None` ya resuelto (`ctx.universidad_id`), NO el `ContextoUniversidad`
    completo — mantiene consistencia con el resto de las firmas de servicio
    (D4: "un solo valor viaja"), y permite usarlo también desde flujos sin
    request/JWT (p. ej. el cron) que ya resuelven su propio `universidad_id`.

    - `universidad_id_activa is None` (superadmin SIN universidad activa elegida):
      bypass total, no valida nada (ve cualquier recurso de cualquier universidad).
    - `recurso is None` (no existe): 404.
    - `recurso.universidad_id != universidad_id_activa`: 404 (NO 403 — no revela
      que el recurso existe en otra universidad).
    - Resto (recurso de la universidad activa, incluido un superadmin que SÍ
      eligió universidad y por ende queda scopeado como cualquier miembro): pasa.

    Args:
        recurso: instancia de modelo (o cualquier objeto con `.universidad_id`).
        universidad_id_activa: `ctx.universidad_id` de la universidad activa del
            request (None = superadmin sin universidad elegida, bypass).
        detail: mensaje del 404. Usar el MISMO texto que el "no encontrado" propio
            de la entidad en el call site (p. ej. "Materia no encontrada"), para
            que el caso cross-tenant sea indistinguible del caso "no existe".

    Raises:
        HTTPException 404: recurso inexistente o de otra universidad.
    """
    if universidad_id_activa is None:
        return
    if (
        recurso is None
        or getattr(recurso, "universidad_id", None) != universidad_id_activa
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


async def comisiones_visibles_para(
    db: AsyncSession, usuario: Usuario, ctx: ContextoUniversidad
) -> list[int] | None:
    """IDs de comisiones que el usuario puede ver. None = acceso total, sin filtro.

    Para el scoping de GET /entregas/: ahi un 403 no aplica, hay que FILTRAR.
    El filtro debe entrar antes del count, para que el total paginado no
    revele la cantidad global.
    """
    if _acceso_total(ctx):
        return None

    from app.models.comision import Comision, ComisionTutor
    from app.models.materia import CoordinadorMateria

    result = await db.execute(
        select(Comision.id)
        .select_from(Comision)
        .outerjoin(
            ComisionTutor,
            and_(
                ComisionTutor.comision_id == Comision.id,
                ComisionTutor.tutor_id == usuario.id,
            ),
        )
        .outerjoin(
            CoordinadorMateria,
            and_(
                CoordinadorMateria.materia_id == Comision.materia_id,
                CoordinadorMateria.coordinador_id == usuario.id,
            ),
        )
        .where(
            or_(
                ComisionTutor.id.is_not(None),
                CoordinadorMateria.id.is_not(None),
            )
        )
        .order_by(Comision.id)
    )
    return list(result.scalars().all())

