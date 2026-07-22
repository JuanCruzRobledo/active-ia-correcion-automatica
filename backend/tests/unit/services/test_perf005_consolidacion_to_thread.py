"""
PERF-005 (parte segura): la consolidación CPU-pura de la carga masiva debe
correr fuera del event loop vía asyncio.to_thread, SIN cambiar qué se consolida.

Estos tests están en un archivo aparte a propósito: test_entrega_service.py y
test_consolidacion_service.py están rotos por ImportError preexistente (no
relacionados con PERF-005) y se ignoran al correr la suite.

Se valida:
  1. La consolidación de un ZIP corre en un thread DISTINTO al del event loop
     (prueba de que to_thread está cableado, no inline).
  2. Lo mismo para el path txt (otro camino de código → triangulación).
  3. No-regresión de contenido: el consolidado devuelto por el método async es
     IDÉNTICO al que produce ConsolidacionService de forma síncrona (salvo la
     línea volátil de fecha de generación). El to_thread cambia DÓNDE corre,
     nunca QUÉ se consolida.
"""

import io
import threading
import zipfile
from unittest.mock import MagicMock

import pytest

from app.services.consolidacion_service import ConsolidacionService
from app.services.entrega_service import EntregaService


def _zip_de_alumno() -> bytes:
    """ZIP en memoria con código de un alumno, como en la carga masiva."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("proyecto/main.py", "def main():\n    print('hola')\n")
        zf.writestr("proyecto/util.py", "def suma(a, b):\n    return a + b\n")
    return buffer.getvalue()


def _sin_linea_fecha(contenido: str) -> str:
    """Quita la línea volátil de 'Fecha de generación' para comparar contenido."""
    return "\n".join(
        linea
        for linea in contenido.splitlines()
        if not linea.startswith("**Fecha de generación:**")
    )


def _make_service() -> EntregaService:
    # _consolidar_archivo no toca DB/ORM/sesión: un MagicMock como db alcanza.
    return EntregaService(MagicMock())


@pytest.mark.asyncio
async def test_consolidacion_zip_corre_fuera_del_event_loop():
    service = _make_service()
    zip_bytes = _zip_de_alumno()

    hilo_event_loop = threading.get_ident()
    hilos_registrados: list[int] = []

    real_consolidar = service.consolidacion_service.consolidar_zip

    def _spy(*args, **kwargs):
        hilos_registrados.append(threading.get_ident())
        return real_consolidar(*args, **kwargs)

    service.consolidacion_service.consolidar_zip = _spy

    contenido, archivos = await service._consolidar_archivo(
        zip_bytes, "zip", modo="solo_codigo"
    )

    # La consolidación efectivamente corrió, y en OTRO thread (to_thread).
    assert len(hilos_registrados) == 1
    assert hilos_registrados[0] != hilo_event_loop
    # Y produjo un consolidado real, con ambos archivos del alumno.
    assert "proyecto/main.py" in contenido
    assert "proyecto/util.py" in contenido
    assert set(archivos) == {"proyecto/main.py", "proyecto/util.py"}


@pytest.mark.asyncio
async def test_consolidacion_txt_corre_fuera_del_event_loop():
    service = _make_service()
    txt_bytes = b"contenido de la entrega del alumno\nlinea 2\n"

    hilo_event_loop = threading.get_ident()
    hilos_registrados: list[int] = []

    real_consolidar_txt = service.consolidacion_service.consolidar_txt

    def _spy(*args, **kwargs):
        hilos_registrados.append(threading.get_ident())
        return real_consolidar_txt(*args, **kwargs)

    service.consolidacion_service.consolidar_txt = _spy

    contenido, _archivos = await service._consolidar_archivo(
        txt_bytes, "txt", modo="solo_codigo"
    )

    assert len(hilos_registrados) == 1
    assert hilos_registrados[0] != hilo_event_loop
    assert "contenido de la entrega del alumno" in contenido


@pytest.mark.asyncio
async def test_contenido_consolidado_identico_a_referencia_sincrona():
    """No-regresión: mismo consolidado que la ruta síncrona (salvo la fecha)."""
    service = _make_service()
    zip_bytes = _zip_de_alumno()

    # Ruta bajo prueba (async, con to_thread).
    contenido_async, archivos_async = await service._consolidar_archivo(
        zip_bytes, "zip", modo="solo_codigo"
    )

    # Referencia: consolidación síncrona directa del mismo servicio.
    referencia = ConsolidacionService()
    contenido_sync, archivos_sync = referencia.consolidar_zip(
        io.BytesIO(zip_bytes), modo="solo_codigo"
    )

    assert archivos_async == archivos_sync
    assert _sin_linea_fecha(contenido_async) == _sin_linea_fecha(contenido_sync)
