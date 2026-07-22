"""Tests anti ZIP-bomb (SEC-005).

Verifican que el pipeline de descompresión/consolidación corta ANTES de
materializar contenido cuando un ZIP declara un tamaño descomprimido acumulado
excesivo (``ZipInfo.file_size``) o demasiadas entradas, tanto en
``ConsolidacionService`` como en el loop de carga masiva de ``EntregaService``.

Las ZIP-bombs se fabrican con datos altamente compresibles (``b"\\0" * N``): el
ZIP resultante pesa poco pero declara un ``file_size`` grande. Los topes se
bajan por monkeypatch para no allocar 100 MB en el test.
"""

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.upload_limits import validar_zip_bomb
from app.services.consolidacion_service import ConsolidacionService
from app.services.entrega_service import EntregaService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _crear_zip(archivos: dict[str, bytes]) -> bytes:
    """Crea un ZIP comprimido a partir de {path: contenido_bytes}."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, contenido in archivos.items():
            zf.writestr(path, contenido)
    return buffer.getvalue()


class _FakeInfo:
    """ZipInfo mínimo para probar el helper en aislamiento."""

    def __init__(self, file_size: int):
        self.file_size = file_size


class _FakeUpload:
    def __init__(self, contenido: bytes, *, filename="entregas.zip", size=None):
        self._contenido = contenido
        self.filename = filename
        self.size = size

    async def read(self) -> bytes:
        return self._contenido


# ---------------------------------------------------------------------------
# Helper compartido: validar_zip_bomb
# ---------------------------------------------------------------------------


class TestValidarZipBomb:
    def test_dentro_de_topes_no_lanza(self):
        infos = [_FakeInfo(100), _FakeInfo(200)]
        validar_zip_bomb(infos, max_expanded=1000, max_entries=10)

    def test_expansion_acumulada_excesiva_lanza_413(self):
        infos = [_FakeInfo(600), _FakeInfo(600)]  # 1200 > 1000
        with pytest.raises(HTTPException) as exc:
            validar_zip_bomb(infos, max_expanded=1000, max_entries=10)
        assert exc.value.status_code == 413
        assert "descomprimido" in exc.value.detail.lower()

    def test_demasiadas_entradas_lanza_413(self):
        infos = [_FakeInfo(1) for _ in range(11)]  # 11 > 10
        with pytest.raises(HTTPException) as exc:
            validar_zip_bomb(infos, max_expanded=10_000, max_entries=10)
        assert exc.value.status_code == 413
        assert "entradas" in exc.value.detail.lower()

    def test_corta_sin_recorrer_todas_las_entradas(self):
        """La expansión se corta apenas se supera el tope (no recorre el resto)."""
        visitadas = []

        def infos_gen():
            for size in (600, 600, 600):
                visitadas.append(size)
                yield _FakeInfo(size)

        with pytest.raises(HTTPException):
            validar_zip_bomb(infos_gen(), max_expanded=1000, max_entries=10)
        # Cortó en la 2da (600+600=1200>1000); nunca llegó a la 3ra.
        assert visitadas == [600, 600]


# ---------------------------------------------------------------------------
# ConsolidacionService
# ---------------------------------------------------------------------------


class TestConsolidacionAntiZipBomb:
    def test_expansion_excesiva_aborta_413_sin_materializar(self, monkeypatch):
        """Bomba por expansión: aborta 413 y NUNCA descomprime (zf.read no se llama)."""
        monkeypatch.setattr(settings, "MAX_ZIP_EXPANDED_SIZE", 1000)
        zip_bytes = _crear_zip({"main.py": b"\0" * 5000})  # declara file_size=5000

        # Prueba de no-materialización: si se intentara leer, explotaría.
        def _boom(self, *a, **k):
            raise AssertionError("zf.read fue llamado: la bomba se materializó")

        monkeypatch.setattr(zipfile.ZipFile, "read", _boom)

        svc = ConsolidacionService()
        with pytest.raises(HTTPException) as exc:
            svc.consolidar_zip(io.BytesIO(zip_bytes), modo="solo_codigo")
        assert exc.value.status_code == 413
        assert "descomprimido" in exc.value.detail.lower()

    def test_demasiadas_entradas_aborta_413(self, monkeypatch):
        monkeypatch.setattr(settings, "MAX_ZIP_ENTRIES", 3)
        archivos = {f"f{i}.py": b"x = 1\n" for i in range(5)}  # 5 > 3
        zip_bytes = _crear_zip(archivos)

        svc = ConsolidacionService()
        with pytest.raises(HTTPException) as exc:
            svc.consolidar_zip(io.BytesIO(zip_bytes), modo="solo_codigo")
        assert exc.value.status_code == 413
        assert "entradas" in exc.value.detail.lower()

    def test_zip_legitimo_consolida_normalmente(self):
        """Triangulación: un ZIP dentro de los topes se consolida sin 413."""
        zip_bytes = _crear_zip(
            {"main.py": b"print('hola')\n", "utils.py": b"def f():\n    pass\n"}
        )
        svc = ConsolidacionService()
        contenido, archivos = svc.consolidar_zip(io.BytesIO(zip_bytes), modo="solo_codigo")
        assert "main.py" in contenido
        assert "utils.py" in contenido
        assert len(archivos) == 2


# ---------------------------------------------------------------------------
# EntregaService — loop de carga masiva
# ---------------------------------------------------------------------------


def _service_masiva() -> EntregaService:
    svc = EntregaService(AsyncMock())
    svc.comision_repo = AsyncMock()
    svc.comision_repo.get_active_by_id = AsyncMock(return_value=MagicMock())
    svc.rubrica_repo = AsyncMock()
    svc.rubrica_repo.get_active_by_id = AsyncMock(return_value=MagicMock())
    svc.entrega_repo = AsyncMock()
    svc.entrega_repo.get_by_rubrica_alumno = AsyncMock(return_value=None)
    svc.entrega_repo.create = AsyncMock()
    return svc


@pytest.mark.asyncio
class TestCargaMasivaAntiZipBomb:
    async def test_bomba_por_expansion_aborta_413_sin_crear_entregas(self, monkeypatch):
        monkeypatch.setattr(settings, "MAX_ZIP_EXPANDED_SIZE", 1000)
        # ZIP de carpetas de alumnos: la entrada declara file_size=5000.
        zip_bytes = _crear_zip({"alumno1/proyecto.py": b"\0" * 5000})
        archivo = _FakeUpload(zip_bytes, filename="entregas.zip", size=None)

        svc = _service_masiva()
        with pytest.raises(HTTPException) as exc:
            await svc.crear_entrega_masiva(
                comision_id=1, rubrica_id=1, archivo_zip=archivo, subido_por_id=1,
            )
        assert exc.value.status_code == 413
        svc.entrega_repo.create.assert_not_called()
