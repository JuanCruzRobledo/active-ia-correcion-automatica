"""
Tests for ConsolidacionService.

Tests cover:
- Extracting code from ZIP files
- Consolidating multiple files into single text
- Different consolidation modes (solo_codigo, web_completo, etc.)
- Handling invalid ZIPs
- Preview generation

Nota de mantenimiento: este archivo venía del commit inicial del repo y nunca
llegó a ejecutarse — importaba `EXTENSIONES_POR_MODO`, un símbolo que jamás
existió, así que pytest cortaba en la colección. Se reescribió contra la API
real conservando la intención de los 10 tests originales. La API había
derivado en seis puntos independientes:

1. `EXTENSIONES_POR_MODO` -> `MODOS_CONSOLIDACION`, y cambió de forma:
   `dict[str, list[str]]` pasó a `dict[str, dict]` con las extensiones en un
   `set` bajo la clave "extensiones".
2. `consolidar_zip` es SÍNCRONO (los tests originales le hacían `await`).
3. El primer parámetro es `archivo_zip` y recibe un `BinaryIO`, no `zip_bytes`.
4. El parámetro custom se llama `extensiones_custom`, no
   `extensiones_personalizadas`.
5. Devuelve `tuple[str, list[str]]` — (contenido, archivos incluidos) — y los
   tests originales lo trataban como un `str` suelto.
6. Un ZIP sin archivos que matcheen ya no devuelve vacío: levanta
   HTTPException 400.
"""

import io
import zipfile

import pytest
from fastapi import HTTPException

from app.services.consolidacion_service import (
    ConsolidacionService,
    MODOS_CONSOLIDACION,
)


@pytest.fixture
def consolidacion_service():
    """Create ConsolidacionService instance."""
    return ConsolidacionService()


def crear_zip_con_archivos(archivos: dict[str, str | bytes]) -> io.BytesIO:
    """
    Create a ZIP file with given files.

    Args:
        archivos: Dict mapping file paths to content.

    Returns:
        BinaryIO listo para `consolidar_zip`.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in archivos.items():
            zf.writestr(path, content)
    buffer.seek(0)
    return buffer


class TestConsolidacionService:
    """Tests for ConsolidacionService."""

    def test_consolidar_zip_solo_codigo(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with solo_codigo mode."""
        zip_file = crear_zip_con_archivos(
            {
                "main.py": "print('hello')\n",
                "utils.py": "def helper():\n    pass\n",
                "README.md": "This is a readme",  # Should be excluded
                "data.json": '{"key": "value"}',  # Should be excluded
            }
        )

        contenido, archivos = consolidacion_service.consolidar_zip(
            archivo_zip=zip_file,
            modo="solo_codigo",
        )

        assert "main.py" in archivos
        assert "utils.py" in archivos
        assert "README.md" not in archivos
        assert "data.json" not in archivos
        assert "print('hello')" in contenido

    def test_consolidar_zip_web_completo(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with web_completo mode."""
        zip_file = crear_zip_con_archivos(
            {
                "index.html": "<html></html>",
                "style.css": "body { margin: 0; }",
                "script.js": "console.log('test');",
                "config.json": '{"port": 3000}',
                "README.md": "Readme",  # Should be excluded
            }
        )

        _, archivos = consolidacion_service.consolidar_zip(
            archivo_zip=zip_file,
            modo="web_completo",
        )

        assert "index.html" in archivos
        assert "style.css" in archivos
        assert "script.js" in archivos
        assert "config.json" in archivos
        assert "README.md" not in archivos

    def test_consolidar_zip_proyecto_completo(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with proyecto_completo mode."""
        zip_file = crear_zip_con_archivos(
            {
                "main.py": "print('hello')",
                "README.md": "# Project",
                "docker-compose.yml": "version: '3'",
                "package.json": '{"name": "test"}',
            }
        )

        _, archivos = consolidacion_service.consolidar_zip(
            archivo_zip=zip_file,
            modo="proyecto_completo",
        )

        assert "main.py" in archivos
        assert "README.md" in archivos
        assert "docker-compose.yml" in archivos
        assert "package.json" in archivos

    def test_consolidar_zip_extensiones_personalizadas(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP with custom extensions."""
        zip_file = crear_zip_con_archivos(
            {
                "query.sql": "SELECT * FROM users;",
                "script.sh": "#!/bin/bash\necho 'test'",
                "main.py": "print('hello')",
                "data.json": '{"key": "value"}',
            }
        )

        _, archivos = consolidacion_service.consolidar_zip(
            archivo_zip=zip_file,
            modo="personalizado",
            extensiones_custom=[".sql", ".sh", ".py"],
        )

        assert "query.sql" in archivos
        assert "script.sh" in archivos
        assert "main.py" in archivos
        assert "data.json" not in archivos  # Not in custom list

    def test_modo_personalizado_sin_extensiones_falla(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """El modo personalizado exige la lista de extensiones."""
        zip_file = crear_zip_con_archivos({"main.py": "print('hello')"})

        with pytest.raises(HTTPException) as exc_info:
            consolidacion_service.consolidar_zip(
                archivo_zip=zip_file,
                modo="personalizado",
            )

        assert exc_info.value.status_code == 400

    def test_consolidar_zip_estructura_directorios(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test consolidating ZIP preserves directory structure in output."""
        zip_file = crear_zip_con_archivos(
            {
                "src/main.py": "print('main')",
                "src/utils/helper.py": "def help(): pass",
                "tests/test_main.py": "def test_main(): pass",
            }
        )

        _, archivos = consolidacion_service.consolidar_zip(
            archivo_zip=zip_file,
            modo="solo_codigo",
        )

        assert "src/main.py" in archivos
        assert "src/utils/helper.py" in archivos
        assert "tests/test_main.py" in archivos

    def test_consolidar_zip_devuelve_contenido_y_archivos(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """El retorno es la tupla (contenido, archivos incluidos)."""
        zip_file = crear_zip_con_archivos({"main.py": "x" * 1000})

        resultado = consolidacion_service.consolidar_zip(
            archivo_zip=zip_file,
            modo="solo_codigo",
        )

        assert isinstance(resultado, tuple)
        contenido, archivos = resultado
        assert isinstance(contenido, str)
        assert archivos == ["main.py"]
        assert len(contenido) >= 1000  # el documento envuelve el contenido

    def test_consolidar_zip_vacio_falla(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Un ZIP sin archivos que matcheen corta con 400.

        El test original esperaba un string vacío; hoy el service falla
        explícito en vez de dejar seguir una entrega sin contenido.
        """
        zip_file = crear_zip_con_archivos({})

        with pytest.raises(HTTPException) as exc_info:
            consolidacion_service.consolidar_zip(
                archivo_zip=zip_file,
                modo="solo_codigo",
            )

        assert exc_info.value.status_code == 400

    def test_consolidar_zip_no_es_zip_falla(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Un archivo que no es ZIP corta con 400, no con un 500."""
        with pytest.raises(HTTPException) as exc_info:
            consolidacion_service.consolidar_zip(
                archivo_zip=io.BytesIO(b"esto no es un zip"),
                modo="solo_codigo",
            )

        assert exc_info.value.status_code == 400
        assert "ZIP" in exc_info.value.detail

    def test_consolidar_zip_archivos_binarios_ignorados(
        self,
        consolidacion_service: ConsolidacionService,
    ):
        """Test that binary files are ignored during consolidation."""
        zip_file = crear_zip_con_archivos(
            {
                "main.py": "print('hello')",
                "image.png": b"\x89PNG\r\n\x1a\n",  # Binary content
            }
        )

        _, archivos = consolidacion_service.consolidar_zip(
            archivo_zip=zip_file,
            modo="solo_codigo",
        )

        assert "main.py" in archivos
        assert "image.png" not in archivos  # Binary file ignored

    def test_modos_consolidacion_definidos(self):
        """Todos los modos declaran nombre y un set de extensiones válidas."""
        assert "solo_codigo" in MODOS_CONSOLIDACION
        assert "web_completo" in MODOS_CONSOLIDACION
        assert "proyecto_completo" in MODOS_CONSOLIDACION

        for modo, config in MODOS_CONSOLIDACION.items():
            assert isinstance(config["nombre"], str) and config["nombre"]
            extensiones = config["extensiones"]
            assert isinstance(extensiones, set)
            assert extensiones, f"El modo {modo} no declara extensiones"
            assert all(isinstance(ext, str) for ext in extensiones)
            assert all(ext.startswith(".") for ext in extensiones)
