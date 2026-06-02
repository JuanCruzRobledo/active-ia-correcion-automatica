# app/routers/gestion.py
"""Router de la pantalla "Gestión" (rol GESTOR / ADMIN).

- GET  /gestion/cursos                       → cursos elegibles (materias con Moodle).
- GET  /gestion/cursos/{materia_id}/filtros  → regionales/comisiones del curso + catálogos.
- POST /gestion/cursos/{materia_id}/consulta → alumnos filtrados (preview en pantalla).
- POST /gestion/cursos/{materia_id}/excel    → descarga .xlsx (una hoja por regional).

Todos requieren rol GESTOR o ADMIN. El 424 (sin credenciales Moodle) y el 404
(curso sin vínculo) los lanza GestionService.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_gestor_or_admin
from app.models import Usuario
from app.schemas.gestion import (
    ConsultaGestionResponse,
    CursoGestionResponse,
    FiltrosDisponiblesResponse,
    FiltrosGestionRequest,
)
from app.services.gestion_service import FiltrosGestion, GestionService

router = APIRouter(prefix="/gestion", tags=["gestion"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _to_filtros(req: FiltrosGestionRequest) -> FiltrosGestion:
    return FiltrosGestion(
        rol=req.rol,
        estatus=req.estatus,
        regionales=req.regionales,
        comisiones=req.comisiones,
        inactividad_tipo=req.inactividad_tipo,
        inactividad_desde=req.inactividad_desde,
        inactividad_hasta=req.inactividad_hasta,
    )


def _ascii_filename(filename: str) -> str:
    """El header Content-Disposition debe ser latin-1: limpiamos no-ASCII."""
    limpio = filename.encode("ascii", "ignore").decode().strip()
    return limpio or "gestion.xlsx"


@router.get("/cursos", response_model=list[CursoGestionResponse])
async def listar_cursos(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CursoGestionResponse]:
    require_gestor_or_admin(current_user)
    service = GestionService(db)
    cursos = await service.listar_cursos(current_user)
    return [CursoGestionResponse(**asdict(c)) for c in cursos]


@router.get("/cursos/{materia_id}/filtros", response_model=FiltrosDisponiblesResponse)
async def opciones_filtros(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FiltrosDisponiblesResponse:
    require_gestor_or_admin(current_user)
    service = GestionService(db)
    opciones = await service.opciones_filtros(current_user, materia_id)
    return FiltrosDisponiblesResponse(**asdict(opciones))


@router.post("/cursos/{materia_id}/consulta", response_model=ConsultaGestionResponse)
async def consultar(
    materia_id: int,
    filtros: FiltrosGestionRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsultaGestionResponse:
    require_gestor_or_admin(current_user)
    service = GestionService(db)
    resultado = await service.consultar(current_user, materia_id, _to_filtros(filtros))
    return ConsultaGestionResponse(**asdict(resultado))


@router.post("/cursos/{materia_id}/excel", response_class=StreamingResponse)
async def exportar_excel(
    materia_id: int,
    filtros: FiltrosGestionRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    require_gestor_or_admin(current_user)
    service = GestionService(db)
    data, filename = await service.exportar_excel(current_user, materia_id, _to_filtros(filtros))
    return StreamingResponse(
        iter([data]),
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{_ascii_filename(filename)}"'},
    )
