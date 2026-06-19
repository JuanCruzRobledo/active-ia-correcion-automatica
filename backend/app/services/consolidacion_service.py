# app/services/consolidacion_service.py
"""
Consolidacion service for Active-IA.

Service for consolidating code files from ZIP archives into a single
readable TXT document with directory tree, fenced code blocks, and stats.
Output format matches the project consolidator scripts used for AI processing.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7.3
"""

import io
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
    "__MACOSX",  # Apple Double Resource Fork metadata — binary, not code
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

# Modos de procesamiento: nombre mostrable + extensiones permitidas
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

    # Expose constants as class attributes
    BINARY_EXTENSIONS = BINARY_EXTENSIONS

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
                return self._consolidar_desde_zipfile(zf, extensiones, modo)

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

    def _consolidar_desde_zipfile(
        self,
        zf: zipfile.ZipFile,
        extensiones: set[str],
        modo: str,
    ) -> tuple[str, list[str]]:
        """Consolida desde un ZipFile ya abierto.

        Lee cada archivo a través de su objeto ``ZipInfo`` (no del path
        re-derivado como string): así funciona aunque la entrada del ZIP use
        backslash de Windows (`carpeta\\archivo.ext`). En Linux ``zipfile``
        conserva ese `\\` literal, y leer con el path normalizado a `/` provoca
        ``KeyError "There is no item named '...' in the archive"``.
        """
        archivos_info = self._scan_zip(zf, extensiones)

        if not archivos_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self._mensaje_sin_archivos(zf, extensiones),
            )

        # Read each file with safe encoding — siempre por el ZipInfo.
        contenidos: list[tuple[str, str]] = []
        for info, path in archivos_info:
            raw = zf.read(info)
            contenidos.append((path, self._read_safely(raw)))

        modo_nombre = self._get_modo_nombre(modo)
        contenido_final = self._build_document(contenidos, modo_nombre)

        archivos = [path for _, path in archivos_info]
        return contenido_final, archivos

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

    def consolidar_archivo_individual(
        self,
        archivo: BinaryIO,
        filename: str,
        modo: str = "solo_codigo",
        extensiones_custom: list[str] | None = None,
    ) -> tuple[str, list[str]]:
        """
        Consolidate a single code file into a formatted TXT document.

        This method is used when the student submits a single file (not ZIP, not TXT)
        such as .py, .java, .js, etc.

        Args:
            archivo: Binary file object.
            filename: Original filename.
            modo: Consolidation mode (to validate if extension is allowed).
            extensiones_custom: Custom extensions list when modo is 'personalizado'.

        Returns:
            Tuple of (consolidated_content, list with single filename).

        Raises:
            HTTPException 400: File extension not allowed in selected mode.
        """
        try:
            # Get file extension
            ext = self._get_extension(filename)

            # Validate extension is allowed in the selected mode
            extensiones = self._resolve_extensiones(modo, extensiones_custom)
            if ext not in extensiones:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"La extensión {ext} no está permitida en el modo '{modo}'. "
                    f"Extensiones permitidas: {', '.join(sorted(extensiones))}",
                )

            # Read file content
            raw = archivo.read()
            contenido = self._read_safely(raw)

            if not contenido.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo está vacío",
                )

            # Build a simple consolidated document (single file)
            modo_nombre = self._get_modo_nombre(modo)
            contenido_final = self._build_single_file_document(
                filename, contenido, modo_nombre
            )

            return contenido_final, [filename]

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo: {str(e)}",
            )

    def extraer_pdf_de_zip(self, zip_bytes: bytes) -> tuple[bytes, str] | None:
        """Devuelve (bytes, nombre) del primer PDF útil del ZIP, o None.

        Pensado como fallback cuando el ZIP no tiene código: ignora carpetas
        excluidas y ``__MACOSX``, y lee por el objeto ``ZipInfo`` (inmune al
        separador Windows). NO decide prioridad código-vs-PDF: eso lo resuelve
        el caller intentando consolidar código primero.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                candidatos: list[tuple[zipfile.ZipInfo, str]] = []
                for info in zf.filelist:
                    if info.is_dir():
                        continue
                    path = info.filename.replace("\\", "/")
                    if self._has_excluded_dir(path):
                        continue
                    if self._get_extension(path) == ".pdf":
                        candidatos.append((info, path))
                if not candidatos:
                    return None
                info, path = sorted(candidatos, key=lambda par: par[1])[0]
                return zf.read(info), path.split("/")[-1]
        except zipfile.BadZipFile:
            return None

    def generar_preview(self, contenido: str, max_chars: int = 500) -> str:
        """Generate a truncated preview of the consolidated content."""
        if len(contenido) <= max_chars:
            return contenido
        return contenido[:max_chars] + "..."

    # ------------------------------------------------------------------
    # Document builder
    # ------------------------------------------------------------------

    def _build_single_file_document(
        self, filename: str, contenido: str, modo_nombre: str
    ) -> str:
        """Build a consolidated document for a single file."""
        sections: list[str] = []

        # --- Header ---
        sections.append("# Documento de Evaluación - Entrega del Alumno\n\n")

        # --- Important notice for AI ---
        sections.append("> 📋 **IMPORTANTE PARA LA CORRECCIÓN:**  \n")
        sections.append("> Este documento fue generado automáticamente a partir de la entrega del alumno.  \n")
        sections.append("> El estudiante **NO envió este archivo TXT**, sino archivos de código fuente que fueron procesados aquí.  \n")
        sections.append("> A continuación se presenta el contenido completo de todos los archivos entregados para su evaluación.\n\n")

        sections.append(
            f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        # --- Metadata ---
        sections.append("## 📋 Metadata del Proyecto\n\n")
        sections.append(f"- **Total de archivos:** 1\n")

        # --- Directory tree ---
        sections.append("\n## 📁 Estructura de Directorios\n\n")
        sections.append("```\n")
        sections.append(f"📄 {filename}\n")
        sections.append("```\n")

        # --- File content ---
        sections.append("\n## 📄 Contenido de Archivos\n\n")
        sections.append("---\n\n")

        ext = self._get_extension(filename)
        lang = LANG_MAP.get(ext, "text")
        lines = contenido.count("\n") + 1

        sections.append(f"### 📄 `{filename}`\n\n")
        sections.append(f"**Líneas:** {lines} | **Tipo:** {ext}\n\n")
        sections.append(f"```{lang}\n")
        sections.append(contenido)
        if not contenido.endswith("\n"):
            sections.append("\n")
        sections.append("```\n\n")
        sections.append("---\n\n")

        # --- Stats ---
        sections.append("## 📊 Estadísticas del Proyecto\n\n")
        sections.append(f"- **Total de archivos procesados:** 1\n")
        sections.append(f"- **Total de líneas de código:** {lines:,}\n")

        codigo_extensions = MODOS_CONSOLIDACION["solo_codigo"]["extensiones"]
        if ext in codigo_extensions:
            sections.append(f"- **Archivos de código:** 1\n")
            sections.append(f"- **Otros archivos:** 0\n")
        else:
            sections.append(f"- **Archivos de código:** 0\n")
            sections.append(f"- **Otros archivos:** 1\n")

        return "".join(sections)

    def _build_document(
        self, contenidos: list[tuple[str, str]], modo_nombre: str
    ) -> str:
        """Assemble the full consolidated TXT document."""
        sections: list[str] = []

        # --- Header ---
        sections.append("# Documento de Evaluación - Entrega del Alumno\n\n")

        # --- Important notice for AI ---
        sections.append("> 📋 **IMPORTANTE PARA LA CORRECCIÓN:**  \n")
        sections.append("> Este documento fue generado automáticamente a partir de la entrega del alumno.  \n")
        sections.append("> El estudiante **NO envió este archivo TXT**, sino archivos de código fuente que fueron procesados aquí.  \n")
        sections.append("> A continuación se presenta el contenido completo de todos los archivos entregados para su evaluación.\n\n")

        sections.append(
            f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        sections.append(f"**Modo de procesamiento:** {modo_nombre}\n\n")

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
                detail=f"Modo de procesamiento inválido: {modo}",
            )
        return modo_config["extensiones"]

    @staticmethod
    def _get_modo_nombre(modo: str) -> str:
        """Return the human-readable name for a mode."""
        config = MODOS_CONSOLIDACION.get(modo)
        return config["nombre"] if config else modo

    def _scan_zip(
        self, zf: zipfile.ZipFile, extensiones: set[str]
    ) -> list[tuple[zipfile.ZipInfo, str]]:
        """
        Return sorted list of (ZipInfo, normalized_path) for the entries that
        pass all filters:
        - not a directory entry
        - no excluded directory component in path
        - extension not in BINARY_EXTENSIONS
        - extension in the allowed set

        El ``ZipInfo`` se conserva para leer el archivo por objeto (inmune al
        separador de la entrada); el path normalizado (`/`) es solo para mostrar.
        """
        result: list[tuple[zipfile.ZipInfo, str]] = []
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
                result.append((info, path))

        return sorted(result, key=lambda par: par[1])

    def _mensaje_sin_archivos(
        self, zf: zipfile.ZipFile, extensiones: set[str]
    ) -> str:
        """Mensaje 400 accionable cuando el ZIP no tiene archivos del modo.

        Lista las extensiones que SÍ trae el ZIP (excluyendo carpetas y dirs
        ignorados) para que el tutor distinga un ZIP anidado, un PDF/imágenes
        sueltos o un modo de consolidación mal configurado.
        """
        presentes: set[str] = set()
        for info in zf.filelist:
            if info.is_dir():
                continue
            path = info.filename.replace("\\", "/")
            if self._has_excluded_dir(path):
                continue
            ext = self._get_extension(path)
            presentes.add(ext or "(sin extensión)")

        base = (
            "No se encontraron archivos válidos en el ZIP con las extensiones "
            "especificadas"
        )
        if not presentes:
            return f"{base} (el ZIP no contiene archivos legibles, ¿es un ZIP anidado o vacío?)"

        encontradas = ", ".join(sorted(presentes))
        esperadas = ", ".join(sorted(extensiones))
        return (
            f"{base}. El ZIP contiene: {encontradas}. "
            f"Extensiones esperadas para este modo: {esperadas}. "
            "Si el alumno comprimió un ZIP dentro de otro, o subió solo "
            "documentos/imágenes, revisá el archivo o el modo de consolidación."
        )

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
        """Decode bytes trying multiple encodings (mirrors consolidator.py logic).

        After decoding, null bytes (\x00) are removed because PostgreSQL UTF-8
        columns reject them with CharacterNotInRepertoireError. These appear in
        Apple Double resource fork files (__MACOSX/._*) and some binary-adjacent
        content that slips through extension filters.
        """
        for encoding in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
            try:
                decoded = raw.decode(encoding)
                # Strip null bytes — PostgreSQL TEXT/VARCHAR rejects \x00
                return decoded.replace("\x00", "")
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
