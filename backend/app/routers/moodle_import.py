# app/routers/moodle_import.py
"""Router para importar entregas pendientes desde Moodle a Active-IA (Fase 2)."""

import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models import Usuario
from app.schemas.moodle_import import ImportarMoodleRequest, ImportarMoodleResponse
from app.services.moodle_import_service import MoodleImportService
from app.services.moodle_service import MoodleAuthError, MoodleConnectionError

router = APIRouter(prefix="/moodle", tags=["moodle"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/importar/stream")
async def importar_pendientes_stream(
    data: ImportarMoodleRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Importa entregas con progreso en vivo (Server-Sent Events).

    Emite eventos `data: {...}`:
    - {"tipo":"inicio","total":N}
    - {"tipo":"progreso","procesadas":i,"total":N}
    - {"tipo":"resumen", ...conteos...}
    - {"tipo":"error","detail":"..."}  (Moodle no disponible / credenciales)

    Las credenciales se validan ANTES de iniciar el stream (424 si faltan).
    """
    if not current_user.moodle_username or not current_user.moodle_password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="Configurá tus credenciales Moodle en tu perfil",
        )

    service = MoodleImportService(db)

    async def event_gen():
        try:
            async for ev in service.importar_stream(
                user_id=current_user.id,
                scope=data.scope,
                rubrica_id=data.rubrica_id,
                comision_id=data.comision_id,
                materia_id=data.materia_id,
            ):
                yield _sse(ev)
        except (MoodleAuthError, MoodleConnectionError) as e:
            yield _sse({"tipo": "error", "detail": str(e)})
        except Exception:  # noqa: BLE001
            yield _sse({"tipo": "error", "detail": "Error inesperado durante la importación"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/importar", response_model=ImportarMoodleResponse)
async def importar_pendientes_moodle(
    data: ImportarMoodleRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Importa las entregas pendientes desde Moodle a Active-IA.

    Seguridad: el importador resuelve los pares Rúbrica×Comisión filtrando por
    `ComisionTutor.tutor_id == current_user.id`, por lo que un tutor sólo puede
    importar entregas de SUS comisiones (nunca de comisiones ajenas).

    Códigos:
    - 200: resumen de la importación (cargadas/duplicadas/omitidas/reentregas/errores).
    - 400: scope inválido o faltan parámetros requeridos.
    - 424: credenciales Moodle no configuradas o inválidas.
    - 502: Moodle no disponible.
    """
    service = MoodleImportService(db)
    try:
        resumen = await service.importar(
            user_id=current_user.id,
            scope=data.scope,
            rubrica_id=data.rubrica_id,
            comision_id=data.comision_id,
            materia_id=data.materia_id,
        )
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

    return ImportarMoodleResponse(**asdict(resumen))
