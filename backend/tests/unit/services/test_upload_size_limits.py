"""Tests para el límite de tamaño de subidas (PERF-008).

Cubre la validación de ``MAX_UPLOAD_SIZE`` en ambos endpoints de subida
(individual y masiva) y el helper compartido de validación de tamaño.

No requiere DB: los repositorios se mockean con AsyncMock. La barrera temprana
por tamaño declarado (``UploadFile.size``) se ubica ANTES de tocar la DB, así
que el rechazo por tamaño no depende de que exista comisión/rúbrica.
"""

import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.upload_limits import validar_tamano_upload
from app.services.entrega_service import EntregaService
from app.schemas.entrega import EntregaCreate


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------


class _FakeUpload:
    """Stub mínimo de UploadFile: expone ``filename``, ``size`` y ``read()``."""

    def __init__(self, contenido: bytes, *, filename: str = "entrega.txt", size=None):
        self._contenido = contenido
        self.filename = filename
        # ``size`` = tamaño declarado por Starlette al parsear (barrera temprana).
        # None simula un cliente que no lo informó → cae la barrera definitiva.
        self.size = size

    async def read(self) -> bytes:
        return self._contenido


def _service_con_repos_ok() -> EntregaService:
    """EntregaService con comisión/rúbrica válidas mockeadas (sin DB real)."""
    svc = EntregaService(AsyncMock())
    svc.comision_repo = AsyncMock()
    svc.comision_repo.get_active_by_id = AsyncMock(return_value=MagicMock())
    svc.rubrica_repo = AsyncMock()
    svc.rubrica_repo.get_active_by_id = AsyncMock(return_value=MagicMock())
    svc.entrega_repo = AsyncMock()
    svc.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    svc.entrega_repo.create = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# Helper compartido: validar_tamano_upload
# ---------------------------------------------------------------------------


class TestValidarTamanoUpload:
    def test_bajo_el_limite_no_lanza(self):
        # Justo por debajo del tope: no debe rechazar.
        validar_tamano_upload(settings.MAX_UPLOAD_SIZE - 1)

    def test_igual_al_limite_no_lanza(self):
        # El límite es inclusivo: exactamente el tope se acepta.
        validar_tamano_upload(settings.MAX_UPLOAD_SIZE)

    def test_none_no_lanza(self):
        # Tamaño desconocido (header ausente) no rechaza por sí mismo.
        validar_tamano_upload(None)

    def test_sobre_el_limite_lanza_413(self):
        with pytest.raises(HTTPException) as exc:
            validar_tamano_upload(settings.MAX_UPLOAD_SIZE + 1)
        assert exc.value.status_code == 413
        # El mensaje nombra la causa (tamaño) sin filtrar internals.
        assert "tama" in exc.value.detail.lower()

    def test_respeta_limite_custom(self):
        validar_tamano_upload(100, limite=100)
        with pytest.raises(HTTPException) as exc:
            validar_tamano_upload(101, limite=100)
        assert exc.value.status_code == 413


# ---------------------------------------------------------------------------
# Subida individual — crear_entrega_individual
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubidaIndividualTamano:
    async def test_size_declarado_excesivo_rechaza_413_sin_tocar_db(self):
        """Barrera temprana: ``size`` declarado > tope → 413 antes de la DB."""
        svc = _service_con_repos_ok()
        archivo = _FakeUpload(b"x", size=settings.MAX_UPLOAD_SIZE + 1)

        with pytest.raises(HTTPException) as exc:
            await svc.crear_entrega_individual(
                data=EntregaCreate(comision_id=1, rubrica_id=1, alumno_nombre="Ana"),
                archivo=archivo,
                subido_por_id=1,
            )

        assert exc.value.status_code == 413
        # No se creó ni buscó entrega: el corte fue temprano.
        svc.entrega_repo.get_by_rubrica_alumno.assert_not_called()
        svc.entrega_repo.create.assert_not_called()

    async def test_bytes_leidos_excesivos_rechaza_413(self):
        """Barrera definitiva: sin ``size`` declarado, ``len(bytes)`` > tope → 413."""
        svc = _service_con_repos_ok()
        # size=None pasa la barrera temprana; el contenido real excede el tope.
        contenido = b"\0" * (settings.MAX_UPLOAD_SIZE + 1)
        archivo = _FakeUpload(contenido, size=None)

        with pytest.raises(HTTPException) as exc:
            await svc.crear_entrega_individual(
                data=EntregaCreate(comision_id=1, rubrica_id=1, alumno_nombre="Ana"),
                archivo=archivo,
                subido_por_id=1,
            )

        assert exc.value.status_code == 413
        # Nunca se persiste la entrega.
        svc.entrega_repo.create.assert_not_called()

    async def test_archivo_bajo_el_limite_pasa_la_guarda(self):
        """Triangulación: un archivo chico NO es rechazado por tamaño.

        Con comisión inexistente el flujo devuelve 404, lo que prueba que la
        guarda de tamaño (413) se superó y el flujo avanzó.
        """
        svc = _service_con_repos_ok()
        svc.comision_repo.get_active_by_id = AsyncMock(return_value=None)
        archivo = _FakeUpload(b"print('hola')\n", filename="main.py", size=14)

        with pytest.raises(HTTPException) as exc:
            await svc.crear_entrega_individual(
                data=EntregaCreate(comision_id=1, rubrica_id=1, alumno_nombre="Ana"),
                archivo=archivo,
                subido_por_id=1,
            )

        assert exc.value.status_code == 404  # no 413 → guarda de tamaño superada


# ---------------------------------------------------------------------------
# Carga masiva — crear_entrega_masiva
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCargaMasivaTamano:
    async def test_zip_declarado_excesivo_rechaza_413_sin_procesar(self):
        svc = _service_con_repos_ok()
        archivo = _FakeUpload(b"PK", filename="entregas.zip", size=settings.MAX_UPLOAD_SIZE + 1)

        with pytest.raises(HTTPException) as exc:
            await svc.crear_entrega_masiva(
                comision_id=1, rubrica_id=1, archivo_zip=archivo, subido_por_id=1,
            )

        assert exc.value.status_code == 413
        svc.entrega_repo.get_by_rubrica_alumno.assert_not_called()

    async def test_zip_bytes_excesivos_rechaza_413(self):
        svc = _service_con_repos_ok()
        contenido = b"\0" * (settings.MAX_UPLOAD_SIZE + 1)
        archivo = _FakeUpload(contenido, filename="entregas.zip", size=None)

        with pytest.raises(HTTPException) as exc:
            await svc.crear_entrega_masiva(
                comision_id=1, rubrica_id=1, archivo_zip=archivo, subido_por_id=1,
            )

        assert exc.value.status_code == 413
