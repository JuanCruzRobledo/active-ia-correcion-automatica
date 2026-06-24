# app/services/sync_service.py
"""
SyncService — tokens de versión para el banner "hay novedades" (item #2, Capa B).

Devuelve un token barato por recurso que cambia ante cualquier alta/edición/borrado,
para que el frontend lo poolee y avise SIN reemplazar los datos que el usuario está
viendo (no interrumpe una edición en curso). Token = MAX(updated_at)|COUNT:
- el MAX(updated_at) cambia ante alta o edición,
- el COUNT cambia ante borrado (que no toca el max).

Es un HINT GLOBAL (no scopeado por usuario): puede sobre-disparar (un cambio de otro
tutor avisa igual), pero nunca se pierde un cambio. El refresco real lo hace la query
de la pantalla; esto solo decide cuándo mostrar el aviso.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.entrega_repository import EntregaRepository
from app.repositories.rubrica_repository import RubricaRepository


def construir_token(max_updated_at: datetime | None, count: int) -> str:
    """(MAX(updated_at), COUNT) → token comparable. 'none' si no hay filas."""
    if not count:
        return "none"
    ts = max_updated_at.isoformat() if max_updated_at else "0"
    return f"{ts}|{count}"


class SyncService:
    """Calcula tokens de versión por recurso (entregas, rúbricas)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.entrega_repo = EntregaRepository(db)
        self.rubrica_repo = RubricaRepository(db)

    async def get_versiones(self) -> dict[str, str]:
        e_ts, e_n = await self.entrega_repo.version()
        r_ts, r_n = await self.rubrica_repo.version()
        return {
            "entregas": construir_token(e_ts, e_n),
            "rubricas": construir_token(r_ts, r_n),
        }
