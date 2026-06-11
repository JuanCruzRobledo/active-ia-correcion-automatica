# app/core/fecha.py
"""
Utilidades de fecha/hora en horario de Argentina (America/Argentina/Buenos_Aires, UTC-3).

El sistema persiste los timestamps en UTC (datetime.utcnow, naive). Para mostrarlos en los
informes (Excel/PDF/emails) hay que convertirlos a hora local Argentina, si no aparecen
+3hs. Estas funciones asumen que un datetime naive está en UTC.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def ahora_ar() -> datetime:
    """Fecha/hora ACTUAL en Argentina (aware)."""
    return datetime.now(TZ_ARGENTINA)


def a_argentina(dt: datetime) -> datetime:
    """Convierte un datetime a horario Argentina. Naive → se asume UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_ARGENTINA)


def fmt_fecha_ar(dt: datetime | None, *, formato: str = "%d/%m/%Y %H:%M") -> str:
    """Formatea un datetime en horario Argentina. None → '—'."""
    if dt is None:
        return "—"
    return a_argentina(dt).strftime(formato)
