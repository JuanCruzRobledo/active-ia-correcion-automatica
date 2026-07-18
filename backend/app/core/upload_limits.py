# app/core/upload_limits.py
"""Guardas de tamaño y anti ZIP-bomb para el boundary de subidas.

Helpers compartidos por ``entrega_service`` y ``consolidacion_service`` para
aplicar los topes configurados (PERF-008 / SEC-005) sin duplicar la lógica ni
los mensajes de rechazo. Todos rechazan con ``413 Request Entity Too Large`` y
mensajes que nombran la causa (tamaño / expansión / entradas) y el tope, sin
filtrar paths internos ni stack traces.

Ref: openspec/changes/limitar-tamano-uploads-y-zip-bomb
"""

from typing import Iterable

from fastapi import HTTPException

from app.core.config import settings

# 413 Request Entity Too Large / Content Too Large: semánticamente correcto tanto
# para el exceso de tamaño de la subida como para el aborto anti ZIP-bomb. Se usa
# el literal para ser agnóstico a la renombrada del constante en Starlette.
_HTTP_413 = 413


def _mb(num_bytes: int) -> str:
    """Formatea bytes como MB con un decimal, para mensajes accionables."""
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def validar_tamano_upload(tamano: int | None, *, limite: int | None = None) -> None:
    """Rechaza con 413 si ``tamano`` supera ``limite`` (default MAX_UPLOAD_SIZE).

    Pensado para llamarse dos veces: primero con el tamaño declarado
    (``UploadFile.size`` / Content-Length) como barrera temprana barata, y luego
    con ``len(bytes_leidos)`` como barrera definitiva. ``None`` (tamaño
    desconocido) no rechaza por sí mismo.
    """
    if tamano is None:
        return
    tope = settings.MAX_UPLOAD_SIZE if limite is None else limite
    if tamano > tope:
        raise HTTPException(
            status_code=_HTTP_413,
            detail=(
                f"El archivo supera el tamaño máximo permitido de {_mb(tope)}. "
                f"Tamaño recibido: {_mb(tamano)}."
            ),
        )


def validar_zip_bomb(
    infos: Iterable,
    *,
    max_expanded: int | None = None,
    max_entries: int | None = None,
) -> None:
    """Aborta con 413 si el ZIP parece una bomba, ANTES de descomprimir nada.

    Recorre los ``ZipInfo`` (metadata del header central) acumulando
    ``file_size`` (tamaño DESCOMPRIMIDO declarado) y contando entradas. Corta
    apenas se supera el tope de expansión o de cantidad de entradas, sin llamar
    nunca a ``zf.read`` — así una ZIP-bomb no se materializa en memoria.

    Nota de robustez: ``file_size`` es un valor declarado en el ZIP; el refuerzo
    de verificar los bytes reales al leer se hace en el caller (opcional).
    """
    tope_expansion = settings.MAX_ZIP_EXPANDED_SIZE if max_expanded is None else max_expanded
    tope_entradas = settings.MAX_ZIP_ENTRIES if max_entries is None else max_entries

    total_entradas = 0
    total_expandido = 0
    for info in infos:
        total_entradas += 1
        if total_entradas > tope_entradas:
            raise HTTPException(
                status_code=_HTTP_413,
                detail=(
                    f"El ZIP contiene demasiadas entradas (más de {tope_entradas}); "
                    "se rechaza por seguridad para evitar el agotamiento de recursos."
                ),
            )
        total_expandido += getattr(info, "file_size", 0)
        if total_expandido > tope_expansion:
            raise HTTPException(
                status_code=_HTTP_413,
                detail=(
                    "El contenido descomprimido del ZIP supera el tamaño máximo "
                    f"permitido de {_mb(tope_expansion)}; se rechaza por seguridad "
                    "(posible ZIP-bomb)."
                ),
            )
