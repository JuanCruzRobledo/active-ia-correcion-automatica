# app/routers/pendientes.py
"""Router para pendientes Moodle."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.models import Usuario
from app.schemas.pendientes import MateriasPendientesResponse
from app.services.moodle_service import MoodleAuthError, MoodleConnectionError, MoodleService

router = APIRouter(prefix="/pendientes", tags=["pendientes"])


@router.get("/moodle", response_model=MateriasPendientesResponse)
async def get_pendientes_moodle(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> MateriasPendientesResponse:
    """
    Retorna las entregas pendientes de corrección agrupadas por Materia → Unidad → Comisión.

    Requiere credenciales Moodle configuradas en el perfil (PATCH /usuarios/me/moodle-credentials)
    para la universidad activa (Fase 3 multi-tenant).
    - HTTP 424: credenciales/campus no configurados (universidad activa)
    - HTTP 409: sin universidad activa elegida (superadmin, OQ5)
    - HTTP 502: Moodle no disponible
    """
    service = MoodleService(db)
    try:
        return await service.get_pendientes(current_user.id, ctx.universidad_id)
    except MoodleAuthError as e:
        return JSONResponse(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            content={"detail": str(e)},
        )
    except MoodleConnectionError as e:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": str(e)},
        )
