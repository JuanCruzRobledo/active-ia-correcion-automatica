# app/services/consolidacion_service.py
"""
Consolidacion service for Active-IA.

Service for consolidating code files from ZIP archives into a single
readable TXT document with directory tree, fenced code blocks, and stats.
Output format matches the project consolidator scripts used for AI processing.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7.3
"""

import zipfile
from datetime import datetime
from typing import BinaryIO

from fastapi import HTTPException, status

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Directorios que siempre se excluyen al escanear el ZIP
EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".settings",
    "target",
    "build",
    "out",
    "bin",
    "node_modules",
    ".gradle",
    ".mvn",
    "__pycache__",
    ".pytest_cache",
}

# Extensiones binarias que se excluyen siempre
BINARY_EXTENSIONS = {
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".bmp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".pdf",
    ".doc",
    ".docx",
    ".bin",
}

# Extension → language name for fenced code blocks
LANG_MAP = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".md": "markdown",
    ".txt": "text",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".xml": "xml",
    ".sql": "sql",
    ".sh": "bash",
    ".bat": "batch",
    ".cmd": "batch",
    ".properties": "properties",
    ".gradle": "gradle",
}

# Modos de consolidación: nombre mostrable + extensiones permitidas
MODOS_CONSOLIDACION = {
    "solo_codigo": {
        "nombre": "Solo código",
        "extensiones": {
            ".py",
            ".java",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".go",
            ".rs",
            ".kt",
            ".rb",
            ".php",
            ".swift",
        },
    },
    "web_completo": {
        "nombre": "Web completo",
        "extensiones": {
            ".py",
            ".java",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".go",
            ".rs",
            ".kt",
            ".rb",
            ".php",
            ".swift",
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".json",
        },
    },
    "proyecto_completo": {
        "nombre": "Proyecto completo",
        "extensiones": {
            ".py",
            ".java",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".go",
            ".rs",
            ".kt",
            ".rb",
            ".php",
            ".swift",
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".json",
            ".md",
            ".txt",
            ".yml",
            ".yaml",
            ".xml",
            ".sql",
            ".sh",
            ".bat",
            ".cmd",
            ".properties",
            ".gradle",
            ".kts",
        },
    },
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ConsolidacionService:
    """Service for code consolidation from ZIP files.

    Produces a single TXT document with markdown-style structure:
    header, directory tree, fenced code blocks per file, and project stats.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consolidar_zip(
        self,
        archivo_zip: BinaryIO,
        modo: str = "solo_codigo",
        extensiones_custom: list[str] | None = None,
    ) -> tuple[str, list[str]]:
        """
        Consolidate code files from a ZIP archive into a single TXT document.

        Args:
            archivo_zip: Binary file object of the ZIP archive.
            modo: Consolidation mode (solo_codigo, web_completo,
                  proyecto_completo, personalizado).
            extensiones_custom: Custom extensions list when modo is 'personalizado'.

        Returns:
            Tuple of (consolidated_content, list_of_included_file_paths).

        Raises:
            HTTPException 400: Invalid ZIP or no matching files.
        """
        extensiones = self._resolve_extensiones(modo, extensiones_custom)

        try:
            with zipfile.ZipFile(archivo_zip, "r") as zf:
                archivos = self._scan_zip(zf, extensiones)

                if not archivos:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No se encontraron archivos válidos en el ZIP "
                        "con las extensiones especificadas",
                    )

                # Read each file with safe encoding
                contenidos: list[tuple[str, str]] = []
                for path in archivos:
                    raw = zf.read(path)
                    contenidos.append((path, self._read_safely(raw)))

                # Assemble the full document
                modo_nombre = self._get_modo_nombre(modo)
                contenido_final = self._build_document(contenidos, modo_nombre)

                return contenido_final, archivos

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es un ZIP válido",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo ZIP: {str(e)}",
            )

    def consolidar_txt(self, archivo_txt: BinaryIO) -> tuple[str, list[str]]:
        """
        Read content from an already-consolidated TXT file.

        Args:
            archivo_txt: Binary file object of the TXT file.

        Returns:
            Tuple of (content, list with single filename).

        Raises:
            HTTPException 400: Empty TXT file.
        """
        try:
            raw = archivo_txt.read()
            contenido = self._read_safely(raw)

            if not contenido.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo TXT está vacío",
                )

            return contenido, ["archivo.txt"]

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo TXT: {str(e)}",
            )

    def generar_preview(self, contenido: str, max_chars: int = 500) -> str:
        """Generate a truncated preview of the consolidated content."""
        if len(contenido) <= max_chars:
            return contenido
        return contenido[:max_chars] + "..."

    # ------------------------------------------------------------------
    # Document builder
    # ------------------------------------------------------------------

    def _build_document(
        self, contenidos: list[tuple[str, str]], modo_nombre: str
    ) -> str:
        """Assemble the full consolidated TXT document."""
        sections: list[str] = []

        # --- Header ---
        sections.append("# Proyecto Consolidado\n\n")
        sections.append(
            f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        sections.append(f"**Modo de consolidación:** {modo_nombre}\n\n")

        # --- Metadata ---
        sections.append("## 📋 Metadata del Proyecto\n\n")
        sections.append(f"- **Total de archivos:** {len(contenidos)}\n")

        # --- Directory tree ---
        paths = [p for p, _ in contenidos]
        sections.append("\n## 📁 Estructura de Directorios\n\n")
        sections.append("```\n")
        sections.append(self._build_directory_tree(paths))
        sections.append("\n```\n")

        # --- File contents ---
        sections.append("\n## 📄 Contenido de Archivos\n\n")
        sections.append("---\n\n")

        total_lines = 0
        codigo_files = 0
        codigo_extensions = MODOS_CONSOLIDACION["solo_codigo"]["extensiones"]

        for path, content in contenidos:
            ext = self._get_extension(path)
            lang = LANG_MAP.get(ext, "text")
            lines = content.count("\n") + 1
            total_lines += lines

            if ext in codigo_extensions:
                codigo_files += 1

            sections.append(f"### 📄 `{path}`\n\n")
            sections.append(f"**Líneas:** {lines} | **Tipo:** {ext}\n\n")
            sections.append(f"```{lang}\n")
            sections.append(content)
            if not content.endswith("\n"):
                sections.append("\n")
            sections.append("```\n\n")
            sections.append("---\n\n")

        # --- Stats ---
        sections.append("## 📊 Estadísticas del Proyecto\n\n")
        sections.append(
            f"- **Total de archivos procesados:** {len(contenidos)}\n"
        )
        sections.append(f"- **Total de líneas de código:** {total_lines:,}\n")
        sections.append(f"- **Archivos de código:** {codigo_files}\n")
        sections.append(
            f"- **Otros archivos:** {len(contenidos) - codigo_files}\n"
        )

        return "".join(sections)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_extensiones(
        self, modo: str, extensiones_custom: list[str] | None
    ) -> set[str]:
        """Resolve the set of allowed extensions for the given mode."""
        if modo == "personalizado":
            if not extensiones_custom:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Modo personalizado requiere extensiones_custom",
                )
            return {
                ext if ext.startswith(".") else f".{ext}"
                for ext in extensiones_custom
            }

        modo_config = MODOS_CONSOLIDACION.get(modo)
        if not modo_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Modo de consolidación inválido: {modo}",
            )
        return modo_config["extensiones"]

    @staticmethod
    def _get_modo_nombre(modo: str) -> str:
        """Return the human-readable name for a mode."""
        config = MODOS_CONSOLIDACION.get(modo)
        return config["nombre"] if config else modo

    def _scan_zip(
        self, zf: zipfile.ZipFile, extensiones: set[str]
    ) -> list[str]:
        """
        Return sorted list of paths inside the ZIP that pass all filters:
        - not a directory entry
        - no excluded directory component in path
        - extension not in BINARY_EXTENSIONS
        - extension in the allowed set
        """
        result: list[str] = []
        for info in zf.filelist:
            if info.is_dir():
                continue

            path = info.filename.replace("\\", "/")

            if self._has_excluded_dir(path):
                continue

            ext = self._get_extension(path)
            if ext in BINARY_EXTENSIONS:
                continue

            if ext in extensiones:
                result.append(path)

        return sorted(result)

    @staticmethod
    def _has_excluded_dir(path: str) -> bool:
        """Check if any directory component of path is in EXCLUDED_DIRS."""
        parts = path.split("/")
        for part in parts[:-1]:  # all except filename
            if part in EXCLUDED_DIRS:
                return True
        return False

    @staticmethod
    def _read_safely(raw: bytes) -> str:
        """Decode bytes trying multiple encodings (mirrors consolidator.py logic)."""
        for encoding in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "[Error: No se pudo leer el archivo con encodings comunes]"

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Get lowercase extension including dot, or empty string."""
        if "." not in filename:
            return ""
        return "." + filename.rsplit(".", 1)[-1].lower()

    @staticmethod
    def _build_directory_tree(file_paths: list[str]) -> str:
        """Build an indented directory tree from file paths (max 50 entries)."""
        # Collect all path prefixes (directories) and full paths (files)
        entries: set[str] = set()
        for path in file_paths:
            parts = path.split("/")
            for i in range(len(parts)):
                entries.add("/".join(parts[: i + 1]))

        file_set = set(file_paths)
        sorted_entries = sorted(entries)
        display = sorted_entries[:50]

        lines: list[str] = []
        for entry in display:
            level = entry.count("/")
            indent = "  " * level
            name = entry.split("/")[-1]
            prefix = "📄 " if entry in file_set else "📁 "
            lines.append(f"{indent}{prefix}{name}")

        if len(sorted_entries) > 50:
            lines.append(f"\n... y {len(sorted_entries) - 50} elementos más")

        return "\n".join(lines)
