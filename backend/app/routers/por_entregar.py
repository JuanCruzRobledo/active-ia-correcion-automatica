# app/routers/por_entregar.py
"""Router para 'Por entregar': correcciones corregidas pendientes de subir a Moodle.

- GET  /por-entregar            → listado LOCAL (instantáneo, sin tocar Moodle).
- POST /por-entregar/entregar/stream → subida masiva (SSE) de las de comentario automático.

La subida individual reusa los endpoints existentes de /correcciones (preview + POST moodle).
"""

import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models import Usuario
from app.schemas.por_entregar import PorEntregarResponse
from app.services.por_entregar_service import PorEntregarService

router = APIRouter(prefix="/por-entregar", tags=["por-entregar"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("", response_model=PorEntregarResponse)
async def listar_por_entregar(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PorEntregarResponse:
    """Lista las correcciones del tutor pendientes de subir a Moodle (todo local).

    Un tutor ve sólo las de sus comisiones; ADMIN ve todas. Las correcciones no
    vinculadas a Moodle no se listan, pero se informan en `no_vinculadas`.
    """
    service = PorEntregarService(db)
    resultado = await service.listar(current_user)
    return PorEntregarResponse(**asdict(resultado))


@router.post("/entregar/stream")
async def entregar_todo_stream(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sube en bloque (SSE) las correcciones de comentario automático (TP).

    Emite eventos `data: {...}`:
    - {"tipo":"inicio","total":N}
    - {"tipo":"progreso","procesadas":i,"total":N}
    - {"tipo":"resumen", enviadas, ya_enviadas, omitidas_requieren_comentario, errores[]}
    - {"tipo":"error","detail":"..."}

    Las credenciales Moodle se validan ANTES de iniciar el stream (424 si faltan).
    """
    if not current_user.moodle_username or not current_user.moodle_password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="Configurá tus credenciales Moodle en tu perfil",
        )

    service = PorEntregarService(db)
    base_url = str(request.base_url)

    async def event_gen():
        try:
            async for ev in service.entregar_masivo_stream(current_user, base_url):
                yield _sse(ev)
        except Exception:  # noqa: BLE001
            yield _sse({"tipo": "error", "detail": "Error inesperado durante la entrega masiva"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
