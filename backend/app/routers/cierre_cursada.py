# app/routers/cierre_cursada.py
"""Router del cierre de cursada (admin panel).

- POST /cierre-cursada/materias/{materia_id}/generar     → calcula y persiste una corrida
  (dirigida por la config de ExamenMateria de la materia).
- GET  /cierre-cursada/runs/{run_id}/excel                → descarga el .xlsx de una corrida.
- GET  /cierre-cursada/materias/{materia_id}/historial    → corridas pasadas de la materia.

ADMIN: acceso total. COORDINADOR: solo materias que coordina (verificar_acceso_materia).
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import verificar_acceso_materia
from app.models import Usuario
from app.repositories.materia_repository import MateriaRepository
from app.schemas.cierre_cursada import (
    CierreHistorialResponse,
    CierreRunResponse,
    GenerarCierreRequest,
)
from app.services.cierre_cursada_service import CierreCursadaService
from app.services.excel_cierre_cursada import generar_excel_cierre
from app.services.moodle_service import MoodleAuthError, MoodleConnectionError

router = APIRouter(prefix="/cierre-cursada", tags=["cierre-cursada"])

_SIN_CREDENCIALES = "Configurá tus credenciales de Moodle en tu perfil"


def _requerir_credenciales_moodle(usuario: Usuario) -> None:
    if not usuario.moodle_username or not usuario.moodle_password_encrypted:
        raise HTTPException(status.HTTP_424_FAILED_DEPENDENCY, detail=_SIN_CREDENCIALES)


def _ascii_filename(filename: str) -> str:
    """El header Content-Disposition debe ser latin-1: limpiamos no-ASCII."""
    limpio = filename.encode("ascii", "ignore").decode().strip()
    return limpio or "cierre_cursada.xlsx"


@router.post("/materias/{materia_id}/generar", response_model=CierreRunResponse)
async def generar_cierre(
    materia_id: int,
    payload: GenerarCierreRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CierreRunResponse:
    await verificar_acceso_materia(db, current_user, materia_id)
    _requerir_credenciales_moodle(current_user)
    service = CierreCursadaService(db)
    try:
        run = await service.generar(materia_id, payload.cuatrimestre_id, current_user)
    except MoodleAuthError as e:
        raise HTTPException(status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except MoodleConnectionError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return CierreRunResponse.model_validate(run)


@router.get("/runs/{run_id}/excel", response_class=StreamingResponse)
async def descargar_excel(
    run_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    service = CierreCursadaService(db)
    run = await service.obtener_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Corrida no encontrada")
    await verificar_acceso_materia(db, current_user, run.materia_id)

    materia = await MateriaRepository(db).get_by_id(run.materia_id)
    # PERF-004: render openpyxl (CPU-bound) en un thread para no bloquear el event loop.
    # `run.alumnos` ya viene eager-loaded (selectinload en get_run), así que el builder
    # no dispara lazy loads dentro del thread.
    data, filename = await asyncio.to_thread(
        generar_excel_cierre, materia.nombre if materia else "Materia", run
    )
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_ascii_filename(filename)}"'},
    )


@router.get("/materias/{materia_id}/historial", response_model=CierreHistorialResponse)
async def historial(
    materia_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CierreHistorialResponse:
    await verificar_acceso_materia(db, current_user, materia_id)
    service = CierreCursadaService(db)
    runs = await service.listar_historial(materia_id)
    return CierreHistorialResponse(runs=[CierreRunResponse.model_validate(r) for r in runs])
