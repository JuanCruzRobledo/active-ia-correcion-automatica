# app/routers/universidades.py
"""
Universidades router for Active-IA — Fase 5 multi-tenant (multi-tenant-frontend-workspace).

Endpoints:
    GET    /universidades/mias  - Universidades del usuario autenticado (selector)
    GET    /universidades       - Listado paginado (ABM, superadmin)
    POST   /universidades       - Alta (ABM, superadmin)
    PUT    /universidades/{id}  - Edición (ABM, superadmin)
    DELETE /universidades/{id}  - Baja lógica (ABM, superadmin)

D5: `GET /universidades/mias` monta SÓLO autenticación (`get_current_user`),
NUNCA `get_universidad_activa` — es el endpoint que alimenta el selector,
incluyendo el momento en que todavía no hay universidad activa (superadmin en
modo global, o justo después del login). Montarle `get_universidad_activa`
crearía un deadlock: el endpoint que permite elegir universidad exigiría
haber elegido una.

D7: el resto del ABM reutiliza el bypass de superadmin existente
(`ctx.es_superadmin`, vía `get_universidad_activa`) — no hay mecanismo nuevo.

Ref: openspec/changes/multi-tenant-frontend-workspace/specs/universidades-abm/spec.md
Ref: openspec/changes/multi-tenant-frontend-workspace/design.md (D5, D7)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    ContextoUniversidad,
    get_current_user,
    get_db,
    get_universidad_activa,
)
from app.models import Usuario
from app.schemas.universidad import (
    UniversidadCreate,
    UniversidadList,
    UniversidadPropia,
    UniversidadResponse,
    UniversidadUpdate,
)
from app.services.universidad_service import UniversidadService

router = APIRouter(prefix="/universidades", tags=["universidades"])


def _require_superadmin(ctx: ContextoUniversidad) -> None:
    """Guard del ABM (D7): reutiliza `ctx.es_superadmin`, sin mecanismo nuevo."""
    if not ctx.es_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sólo un superadmin puede administrar universidades",
        )


@router.get(
    "/mias",
    response_model=list[UniversidadPropia],
    summary="Universidades del usuario autenticado (selector)",
    description=(
        "Universidades donde el usuario tiene membresía activa, con su rol "
        "en cada una. Para un superadmin devuelve todas las activas con rol "
        "ADMIN sintético. Sólo exige autenticación — NUNCA universidad activa "
        "(D5): es el endpoint que alimenta el selector."
    ),
)
async def listar_mias(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UniversidadPropia]:
    service = UniversidadService(db)
    return await service.listar_mias(current_user)


@router.get(
    "",
    response_model=UniversidadList,
    summary="Listado paginado de universidades (ABM, superadmin)",
)
async def listar(
    include_inactive: bool = Query(False, description="Incluir universidades inactivas"),
    search: str | None = Query(None, description="Buscar por nombre"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> UniversidadList:
    _require_superadmin(ctx)
    service = UniversidadService(db)
    return await service.listar(
        page=page, per_page=per_page, include_inactive=include_inactive, search=search
    )


@router.post(
    "",
    response_model=UniversidadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de universidad (ABM, superadmin)",
    responses={409: {"description": "Ya existe una universidad con ese nombre"}},
)
async def crear(
    data: UniversidadCreate,
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> UniversidadResponse:
    _require_superadmin(ctx)
    service = UniversidadService(db)
    return await service.crear(data)


@router.put(
    "/{universidad_id}",
    response_model=UniversidadResponse,
    summary="Edición de universidad (ABM, superadmin)",
    responses={404: {"description": "Universidad no encontrada"}},
)
async def actualizar(
    universidad_id: int,
    data: UniversidadUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> UniversidadResponse:
    _require_superadmin(ctx)
    service = UniversidadService(db)
    return await service.actualizar(universidad_id, data)


@router.delete(
    "/{universidad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de universidad (ABM, superadmin)",
    description="Baja SIEMPRE lógica (activa=False, CRUD-002). Nunca borrado físico.",
    responses={404: {"description": "Universidad no encontrada"}},
)
async def eliminar(
    universidad_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> None:
    _require_superadmin(ctx)
    service = UniversidadService(db)
    await service.eliminar(universidad_id)
