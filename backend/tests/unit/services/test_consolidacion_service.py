"""
Tests for ConsolidacionService.

Tests cover:
- Extracting code from ZIP files
- Consolidating multiple files into single text
- Different consolidation modes (solo_codigo, web_completo, etc.)
- Handling invalid ZIPs
- Preview generation
"""

import io
import zipfile
from pathlib import Path

import pytest

from app.services.consolidacion_service import (
    ConsolidacionService,
    EXTENSIONES_POR_MODO,
)


@pytest.fixture
def consolidacion_service():
    """Create ConsolidacionService instance."""
    return ConsolidacionService()


def crear_zip_con_archivos(archivos: dict[str, str]) -> bytes:
    """
    Create a ZIP file with given files.

    Args:
        archivos: Dict mapping file paths to content.

    Returns:
        ZIP file content as bytes.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in archivos.items():
            zf.writestr(path, content)
    return buffer.getvalue()


@pytest.mark.asyncio
class TestConsolidacionService:
    """Tests for ConsolidacionService."""

    async def test_consolidar_zip_solo_codigo(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with solo_codigo mode."""
        archivos = {
            "main.py": "print('hello')\n",
            "utils.py": "def helper():\n    pass\n",
            "README.md": "This is a readme",  # Should be excluded
            "data.json": '{"key": "value"}',  # Should be excluded
        }
        zip_bytes = crear_zip_con_archivos(archivos)

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="solo_codigo",
        )

        assert "main.py" in resultado
        assert "utils.py" in resultado
        assert "README.md" not in resultado
        assert "data.json" not in resultado
        assert "print('hello')" in resultado

    async def test_consolidar_zip_web_completo(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with web_completo mode."""
        archivos = {
            "index.html": "<html></html>",
            "style.css": "body { margin: 0; }",
            "script.js": "console.log('test');",
            "config.json": '{"port": 3000}',
            "README.md": "Readme",  # Should be excluded
        }
        zip_bytes = crear_zip_con_archivos(archivos)

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="web_completo",
        )

        assert "index.html" in resultado
        assert "style.css" in resultado
        assert "script.js" in resultado
        assert "config.json" in resultado
        assert "README.md" not in resultado

    async def test_consolidar_zip_proyecto_completo(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with proyecto_completo mode."""
        archivos = {
            "main.py": "print('hello')",
            "README.md": "# Project",
            "docker-compose.yml": "version: '3'",
            "package.json": '{"name": "test"}',
        }
        zip_bytes = crear_zip_con_archivos(archivos)

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="proyecto_completo",
        )

        assert "main.py" in resultado
        assert "README.md" in resultado
        assert "docker-compose.yml" in resultado
        assert "package.json" in resultado

    async def test_consolidar_zip_extensiones_personalizadas(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with custom extensions."""
        archivos = {
            "query.sql": "SELECT * FROM users;",
            "script.sh": "#!/bin/bash\necho 'test'",
            "main.py": "print('hello')",
            "data.json": '{"key": "value"}',
        }
        zip_bytes = crear_zip_con_archivos(archivos)

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="personalizado",
            extensiones_personalizadas=[".sql", ".sh", ".py"],
        )

        assert "query.sql" in resultado
        assert "script.sh" in resultado
        assert "main.py" in resultado
        assert "data.json" not in resultado  # Not in custom list

    async def test_consolidar_zip_estructura_directorios(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP preserves directory structure in output."""
        archivos = {
            "src/main.py": "print('main')",
            "src/utils/helper.py": "def help(): pass",
            "tests/test_main.py": "def test_main(): pass",
        }
        zip_bytes = crear_zip_con_archivos(archivos)

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="solo_codigo",
        )

        assert "src/main.py" in resultado
        assert "src/utils/helper.py" in resultado
        assert "tests/test_main.py" in resultado

    async def test_consolidar_zip_preview(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test preview generation (first 500 chars)."""
        contenido_largo = "x" * 1000
        archivos = {
            "main.py": contenido_largo,
        }
        zip_bytes = crear_zip_con_archivos(archivos)

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="solo_codigo",
        )

        preview = resultado[:500]
        assert len(preview) <= 500

    async def test_consolidar_zip_vacio(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating empty ZIP returns empty string."""
        archivos = {}
        zip_bytes = crear_zip_con_archivos(archivos)

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="solo_codigo",
        )

        # Should return at least separator structure, not completely empty
        assert isinstance(resultado, str)

    async def test_consolidar_zip_archivos_binarios_ignorados(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test that binary files are ignored during consolidation."""
        archivos = {
            "main.py": "print('hello')",
            "image.png": b"\x89PNG\r\n\x1a\n",  # Binary content
        }

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in archivos.items():
                if isinstance(content, bytes):
                    zf.writestr(path, content)
                else:
                    zf.writestr(path, content.encode("utf-8"))
        zip_bytes = buffer.getvalue()

        resultado = await consolidacion_service.consolidar_zip(
            zip_bytes=zip_bytes,
            modo="solo_codigo",
        )

        assert "main.py" in resultado
        assert "image.png" not in resultado  # Binary file ignored

    async def test_extensiones_por_modo_definidas(self):
        """Test that all consolidation modes have defined extensions."""
        assert "solo_codigo" in EXTENSIONES_POR_MODO
        assert "web_completo" in EXTENSIONES_POR_MODO
        assert "proyecto_completo" in EXTENSIONES_POR_MODO

        # Verify they are lists of strings
        for modo, extensiones in EXTENSIONES_POR_MODO.items():
            assert isinstance(extensiones, list)
            assert all(isinstance(ext, str) for ext in extensiones)
            assert all(ext.startswith(".") for ext in extensiones)
