"""
Tests para el manejo de PDF dentro de un ZIP.

Reglas de negocio (pedido del usuario):
  1. ZIP vacío / sin contenido útil  → se MANTIENE el error 400.
  2. ZIP con un PDF y sin código      → se procesa el PDF (entrega tipo "pdf").
  3. ZIP con código Y un PDF          → prioriza el código, descarta el PDF.

`extraer_pdf_de_zip` solo extrae (no decide prioridad); la prioridad la aplica
`EntregaService._procesar_contenido`, que intenta consolidar código primero.
"""

import io
import zipfile

import pytest
from fastapi import HTTPException

from app.services.consolidacion_service import ConsolidacionService
from app.services.entrega_service import EntregaService


def _zip(entradas: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in entradas.items():
            zf.writestr(nombre, contenido)
    return buffer.getvalue()


@pytest.fixture
def consol() -> ConsolidacionService:
    return ConsolidacionService()


@pytest.fixture
def service() -> EntregaService:
    # _procesar_contenido no toca la DB; basta con db=None.
    return EntregaService(None)


class TestExtraerPdfDeZip:
    def test_zip_solo_pdf_devuelve_bytes_y_nombre(self, consol: ConsolidacionService):
        zip_bytes = _zip({"informe/Trabajo.pdf": b"%PDF-1.4 contenido"})
        resultado = consol.extraer_pdf_de_zip(zip_bytes)
        assert resultado is not None
        data, nombre = resultado
        assert data == b"%PDF-1.4 contenido"
        assert nombre == "Trabajo.pdf"

    def test_zip_sin_pdf_devuelve_none(self, consol: ConsolidacionService):
        assert consol.extraer_pdf_de_zip(_zip({"main.py": b"x = 1"})) is None

    def test_ignora_pdf_en_macosx(self, consol: ConsolidacionService):
        zip_bytes = _zip({"__MACOSX/._Trabajo.pdf": b"basura"})
        assert consol.extraer_pdf_de_zip(zip_bytes) is None

    def test_zip_invalido_devuelve_none(self, consol: ConsolidacionService):
        assert consol.extraer_pdf_de_zip(b"no soy un zip") is None


@pytest.mark.asyncio
class TestProcesarContenidoPrioridad:
    async def test_zip_solo_pdf_se_procesa_como_pdf(self, service: EntregaService):
        """Regla 2: ZIP con solo PDF → entrega tipo pdf con base64."""
        zip_bytes = _zip({"entrega/Informe.pdf": b"%PDF-1.4 hola"})
        tipo, consolidado, preview, archivos, pdf_b64 = await service._procesar_contenido(
            zip_bytes, "zip", "solo_codigo", "entrega.zip", None
        )
        assert tipo == "pdf"
        assert consolidado is None
        assert pdf_b64 is not None
        assert archivos == ["Informe.pdf"]

    async def test_zip_codigo_y_pdf_prioriza_codigo(self, service: EntregaService):
        """Regla 3: hay código → se usa el código y se descarta el PDF."""
        zip_bytes = _zip(
            {"src/Main.java": b"class Main {}\n", "doc/Informe.pdf": b"%PDF-1.4"}
        )
        tipo, consolidado, preview, archivos, pdf_b64 = await service._procesar_contenido(
            zip_bytes, "zip", "proyecto_completo", "entrega.zip", None
        )
        assert tipo == "zip"
        assert pdf_b64 is None
        assert consolidado is not None and "class Main {}" in consolidado
        assert not any("Informe.pdf" in a for a in archivos)

    async def test_zip_vacio_mantiene_error(self, service: EntregaService):
        """Regla 1: ZIP sin código ni PDF → 400 (caso Sabina)."""
        with pytest.raises(HTTPException) as exc:
            await service._procesar_contenido(
                _zip({}), "zip", "solo_codigo", "vacio.zip", None
            )
        assert exc.value.status_code == 400

    async def test_zip_solo_binarios_mantiene_error(self, service: EntregaService):
        with pytest.raises(HTTPException) as exc:
            await service._procesar_contenido(
                _zip({"captura.png": b"\x89PNG"}), "zip", "solo_codigo", "x.zip", None
            )
        assert exc.value.status_code == 400

    async def test_pdf_directo_sin_cambios(self, service: EntregaService):
        """Un PDF subido directo sigue siendo tipo pdf."""
        tipo, consolidado, preview, archivos, pdf_b64 = await service._procesar_contenido(
            b"%PDF-1.4 directo", "pdf", "solo_codigo", "Trabajo.pdf", None
        )
        assert tipo == "pdf"
        assert pdf_b64 is not None
        assert consolidado is None

    async def test_zip_codigo_normal_sin_cambios(self, service: EntregaService):
        tipo, consolidado, preview, archivos, pdf_b64 = await service._procesar_contenido(
            _zip({"main.py": b"print('hi')\n"}), "zip", "solo_codigo", "e.zip", None
        )
        assert tipo == "zip"
        assert pdf_b64 is None
        assert "print('hi')" in consolidado
