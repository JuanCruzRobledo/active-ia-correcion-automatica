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

from app.models import Usuario
from app.models.enums import RolEnum


# =========================================
# Role Validators
# =========================================


def require_admin(user: Usuario) -> Usuario:
    """
    Validate that the user has ADMIN role.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is not an admin.

    Usage:
        from app.core.dependencies import get_current_user
        from app.core.permissions import require_admin

        @router.post("/admin-only")
        async def admin_endpoint(
            current_user: Usuario = Depends(get_current_user)
        ):
            require_admin(current_user)
            # Only admins can reach here
            pass
    """
    if user.rol != RolEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador",
        )
    return user


def require_coordinador(user: Usuario) -> Usuario:
    """
    Validate that the user has COORDINADOR role.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is not a coordinador.

    Usage:
        @router.post("/coordinador-only")
        async def coordinador_endpoint(
            current_user: Usuario = Depends(get_current_user)
        ):
            require_coordinador(current_user)
            # Only coordinadores can reach here
            pass
    """
    if user.rol != RolEnum.COORDINADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de coordinador",
        )
    return user


def require_tutor(user: Usuario) -> Usuario:
    """
    Validate that the user has TUTOR role.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is not a tutor.

    Usage:
        @router.post("/tutor-only")
        async def tutor_endpoint(
            current_user: Usuario = Depends(get_current_user)
        ):
            require_tutor(current_user)
            # Only tutores can reach here
            pass
    """
    if user.rol != RolEnum.TUTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de tutor",
        )
    return user


def require_gestor(user: Usuario) -> Usuario:
    """
    Validate that the user has GESTOR role.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is not a gestor.

    Usage:
        @router.get("/gestion/cursos")
        async def list_cursos(
            current_user: Usuario = Depends(get_current_user)
        ):
            require_gestor(current_user)
            # Only gestores can reach here
            pass
    """
    if user.rol != RolEnum.GESTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de gestor",
        )
    return user


# =========================================
# Combined Role Validators
# =========================================


def require_coordinador_or_admin(user: Usuario) -> Usuario:
    """
    Validate that the user has COORDINADOR or ADMIN role.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is neither coordinador nor admin.

    Usage:
        @router.get("/materias")
        async def list_materias(
            current_user: Usuario = Depends(get_current_user)
        ):
            require_coordinador_or_admin(current_user)
            # Coordinadores and admins can reach here
            pass
    """
    if user.rol not in (RolEnum.ADMIN, RolEnum.COORDINADOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de coordinador o administrador",
        )
    return user


def require_tutor_or_coordinador(user: Usuario) -> Usuario:
    """
    Validate that the user has TUTOR or COORDINADOR role.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is neither tutor nor coordinador.

    Usage:
        @router.get("/comisiones/{id}/entregas")
        async def list_entregas(
            current_user: Usuario = Depends(get_current_user)
        ):
            require_tutor_or_coordinador(current_user)
            # Tutores and coordinadores can reach here
            pass
    """
    if user.rol not in (RolEnum.TUTOR, RolEnum.COORDINADOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de tutor o coordinador",
        )
    return user


def require_gestor_or_admin(user: Usuario) -> Usuario:
    """
    Validate that the user has GESTOR or ADMIN role.

    Guard de la pantalla "Gestión": la usa el GESTOR, y el ADMIN puede entrar también.

    Args:
        user: Current authenticated user.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is neither gestor nor admin.
    """
    if user.rol not in (RolEnum.ADMIN, RolEnum.GESTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de gestor o administrador",
        )
    return user


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
# Resource-Specific Validators
# =========================================


def require_coordinador_of_materia(user: Usuario, materia_id: int) -> Usuario:
    """
    Validate that the user is a coordinador of the specified materia.

    Note: This is a placeholder. Full implementation requires checking
    the coordinador_materia relationship in the database.

    Args:
        user: Current authenticated user.
        materia_id: ID of the materia to check.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is not coordinador of this materia.

    TODO: Implement database check in service layer.

    Usage:
        @router.get("/materias/{materia_id}/rubricas")
        async def list_rubricas(
            materia_id: int,
            current_user: Usuario = Depends(get_current_user)
        ):
            require_coordinador_of_materia(current_user, materia_id)
            # Only coordinador of this materia can reach here
            pass
    """
    # Allow admins to bypass this check
    if user.rol == RolEnum.ADMIN:
        return user

    # For coordinadores, we need to check the relationship
    # This should be done in the service layer with database access
    # For now, just check if user is a coordinador
    if user.rol != RolEnum.COORDINADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere ser coordinador de esta materia",
        )

    # TODO: Add database check:
    # if not await coordinador_materia_repo.is_coordinador_of_materia(user.id, materia_id):
    #     raise HTTPException(403, "No eres coordinador de esta materia")

    return user


def require_tutor_of_comision(user: Usuario, comision_id: int) -> Usuario:
    """
    Validate that the user is a tutor of the specified comision.

    Note: This is a placeholder. Full implementation requires checking
    the comision_tutor relationship in the database.

    Args:
        user: Current authenticated user.
        comision_id: ID of the comision to check.

    Returns:
        Usuario: The same user object (for chaining).

    Raises:
        HTTPException 403: If user is not tutor of this comision.

    TODO: Implement database check in service layer.

    Usage:
        @router.post("/comisiones/{comision_id}/entregas")
        async def upload_entrega(
            comision_id: int,
            current_user: Usuario = Depends(get_current_user)
        ):
            require_tutor_of_comision(current_user, comision_id)
            # Only tutor of this comision can reach here
            pass
    """
    # Allow admins to bypass this check
    if user.rol == RolEnum.ADMIN:
        return user

    # For tutores, we need to check the relationship
    # This should be done in the service layer with database access
    # For now, just check if user is a tutor
    if user.rol != RolEnum.TUTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere ser tutor de esta comisión",
        )

    # TODO: Add database check:
    # if not await comision_tutor_repo.is_tutor_of_comision(user.id, comision_id):
    #     raise HTTPException(403, "No eres tutor de esta comisión")

    return user


async def verificar_acceso_materia(
    db: AsyncSession, usuario: Usuario, materia_id: int
) -> None:
    """Valida acceso a una materia consultando la DB (guard REAL, no placeholder).

    - ADMIN: acceso total.
    - COORDINADOR: sólo si está asignado a la materia (CoordinadorMateria).
    - Cualquier otro rol: 403.

    Lanza HTTPException 403 si no tiene acceso. Reemplaza al placeholder
    `require_coordinador_of_materia` (que NO consultaba la DB).
    """
    if usuario.rol == RolEnum.ADMIN:
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
    db: AsyncSession, usuario: Usuario, unidad_id: int
) -> None:
    """Resuelve la materia de una unidad y valida el acceso (ver verificar_acceso_materia)."""
    if usuario.rol == RolEnum.ADMIN:
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
    await verificar_acceso_materia(db, usuario, row[0])


async def verificar_acceso_examen(
    db: AsyncSession, usuario: Usuario, examen_id: int
) -> None:
    """Resuelve la materia de un examen y valida el acceso (ver verificar_acceso_materia)."""
    if usuario.rol == RolEnum.ADMIN:
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
    await verificar_acceso_materia(db, usuario, row[0])


async def verificar_acceso_materia_de_comision(
    db: AsyncSession, usuario: Usuario, comision_id: int
) -> None:
    """Valida acceso a una comisión POR SU MATERIA (coordinador dueño de la materia).

    A diferencia de `verificar_acceso_comision` (que mira ComisionTutor, para
    tutores asignados), esto resuelve la materia de la comisión y valida contra
    CoordinadorMateria: el coordinador gestiona las comisiones de SUS materias.

    - ADMIN: acceso total.
    - COORDINADOR: sólo si está asignado a la materia de la comisión.
    - Resto: 403. Comisión inexistente: 404.
    """
    if usuario.rol == RolEnum.ADMIN:
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
    await verificar_acceso_materia(db, usuario, row[0])


async def verificar_acceso_rubrica(
    db: AsyncSession, usuario: Usuario, rubrica_id: int
) -> None:
    """Resuelve la materia de una rúbrica y valida el acceso (ver verificar_acceso_materia)."""
    if usuario.rol == RolEnum.ADMIN:
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
    await verificar_acceso_materia(db, usuario, row[0])


async def verificar_acceso_comision(
    db: AsyncSession, usuario: Usuario, comision_id: int
) -> None:
    """Versión async REAL: valida acceso a una comisión consultando la DB.

    - ADMIN: acceso total.
    - Otros roles: sólo si están asignados a la comisión (ComisionTutor).

    Lanza HTTPException 403 si no tiene acceso. (Reemplaza el placeholder
    `require_tutor_of_comision` para los flujos de Moodle, donde sí consultamos DB.)
    """
    if usuario.rol == RolEnum.ADMIN:
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
    db: AsyncSession, usuario: Usuario, comision_id: int
) -> None:
    """Acceso si: ADMIN | tutor asignado a la comision | coordinador de su materia.

    Una sola query: el LEFT JOIN a las dos tablas puente permite distinguir
    404 (no hay fila de Comision) de 403 (hay comision pero ninguna pertenencia)
    sin pagar un segundo round-trip.

    Lanza 404 si la comision no existe, 403 si no hay pertenencia.
    """
    if usuario.rol == RolEnum.ADMIN:
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
    db: AsyncSession, usuario: Usuario, entrega_id: int
) -> None:
    """Resuelve Entrega -> comision_id y delega en el guard combinado.

    Selecciona SOLO las columnas de clave: contenido_consolidado y
    pdf_contenido_b64 son deferred=True (PERF-002/006) y un select(Entrega)
    arrastraria el codigo fuente del alumno en CADA verificacion de permisos.
    """
    if usuario.rol == RolEnum.ADMIN:
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

    await verificar_acceso_comision_o_materia(db, usuario, fila[1])


async def verificar_acceso_correccion(
    db: AsyncSession, usuario: Usuario, correccion_id: int
) -> None:
    """Resuelve Correccion -> Entrega -> comision_id y delega en el guard combinado."""
    if usuario.rol == RolEnum.ADMIN:
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

    await verificar_acceso_comision_o_materia(db, usuario, fila[1])


async def filtrar_entregas_accesibles(
    db: AsyncSession, usuario: Usuario, entrega_ids: list[int]
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
    if usuario.rol == RolEnum.ADMIN:
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


async def comisiones_visibles_para(
    db: AsyncSession, usuario: Usuario
) -> list[int] | None:
    """IDs de comisiones que el usuario puede ver. None = ADMIN, sin filtro.

    Para el scoping de GET /entregas/: ahi un 403 no aplica, hay que FILTRAR.
    El filtro debe entrar antes del count, para que el total paginado no
    revele la cantidad global.
    """
    if usuario.rol == RolEnum.ADMIN:
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

