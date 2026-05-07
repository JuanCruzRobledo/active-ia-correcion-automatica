# app/routers/pendientes.py
"""Router para pendientes Moodle."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models import Usuario
from app.schemas.pendientes import MateriasPendientesResponse
from app.services.moodle_service import MoodleAuthError, MoodleConnectionError, MoodleService

router = APIRouter(prefix="/pendientes", tags=["pendientes"])


@router.get("/moodle", response_model=MateriasPendientesResponse)
async def get_pendientes_moodle(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MateriasPendientesResponse:
    """
    Retorna las entregas pendientes de corrección agrupadas por Materia → Unidad → Comisión.

    Requiere credenciales Moodle configuradas en el perfil (PATCH /usuarios/me/moodle-credentials).
    - HTTP 424: credenciales no configuradas o inválidas
    - HTTP 502: Moodle no disponible
    """
    if not current_user.moodle_username or not current_user.moodle_password_encrypted:
        return JSONResponse(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            content={"detail": "Configurá tus credenciales Moodle en tu perfil"},
        )

    service = MoodleService(db)
    try:
        return await service.get_pendientes(current_user.id)
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
