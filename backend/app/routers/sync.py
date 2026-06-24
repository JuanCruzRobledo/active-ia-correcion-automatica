# app/routers/sync.py
"""Router de versiones de recursos para el banner 'hay novedades' (item #2, Capa B)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models import Usuario
from app.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/version", response_model=dict[str, str])
async def get_version(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Token de versión por recurso (entregas, rúbricas) para detectar novedades.

    Cada token = MAX(updated_at)|COUNT; el frontend lo poolea y, si cambió respecto al
    que tenía renderizado, ofrece actualizar SIN reemplazar lo que el usuario está viendo.
    Es barato (un MAX+COUNT por recurso) y un hint global (no scopeado por usuario).
    """
    return await SyncService(db).get_versiones()
