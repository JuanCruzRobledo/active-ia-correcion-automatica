# app/services/consolidacion_service.py
"""
Consolidacion service for Active-IA.

Service for consolidating code files from ZIP archives.
Extracts and combines code files into a single text for AI processing.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7.3
"""

import io
import zipfile
from typing import BinaryIO

from fastapi import HTTPException, status

# Modos de consolidación predefinidos
MODOS_CONSOLIDACION = {
    "solo_codigo": {
        "nombre": "Solo código",
        "descripcion": "Solo archivos de código fuente",
        "extensiones": [".py", ".java", ".js", ".ts", ".c", ".cpp", ".go", ".rs"],
    },
    "web_completo": {
        "nombre": "Web completo",
        "descripcion": "Código + archivos web",
        "extensiones": [
            ".py",
            ".java",
            ".js",
            ".ts",
            ".c",
            ".cpp",
            ".go",
            ".rs",
            ".html",
            ".css",
            ".json",
        ],
    },
    "proyecto_completo": {
        "nombre": "Proyecto completo",
        "descripcion": "Todo excepto binarios/media",
        "extensiones": [
            ".py",
            ".java",
            ".js",
            ".ts",
            ".c",
            ".cpp",
            ".go",
            ".rs",
            ".html",
            ".css",
            ".json",
            ".md",
            ".txt",
            ".yml",
            ".yaml",
            ".xml",
            ".sql",
            ".sh",
        ],
    },
}

# Extensiones a excluir siempre (binarios, media, etc.)
EXTENSIONES_EXCLUIDAS = [
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
]


class ConsolidacionService:
    """Service for code consolidation from ZIP files."""

    def __init__(self):
        """Initialize consolidation service."""
        pass

    def consolidar_zip(
        self,
        archivo_zip: BinaryIO,
        modo: str = "solo_codigo",
        extensiones_custom: list[str] | None = None,
    ) -> tuple[str, list[str]]:
        """
        Consolidate code files from a ZIP archive.

        Args:
            archivo_zip: Binary file object of the ZIP archive.
            modo: Consolidation mode (solo_codigo, web_completo, proyecto_completo, personalizado).
            extensiones_custom: Custom extensions if modo is 'personalizado'.

        Returns:
            Tuple of (consolidated_content, list_of_included_files).

        Raises:
            HTTPException 400: Invalid ZIP file or no valid files found.
        """
        # Determinar extensiones a incluir
        if modo == "personalizado":
            if not extensiones_custom:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Modo personalizado requiere extensiones_custom",
                )
            extensiones = extensiones_custom
        else:
            modo_config = MODOS_CONSOLIDACION.get(modo)
            if not modo_config:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Modo de consolidación inválido: {modo}",
                )
            extensiones = modo_config["extensiones"]

        # Normalizar extensiones (asegurar que empiecen con punto)
        extensiones = [
            ext if ext.startswith(".") else f".{ext}" for ext in extensiones
        ]

        try:
            # Leer ZIP
            with zipfile.ZipFile(archivo_zip, "r") as zip_ref:
                archivos_incluidos = []
                contenido_consolidado = []

                # Iterar sobre archivos en el ZIP
                for file_info in zip_ref.filelist:
                    # Saltar directorios
                    if file_info.is_dir():
                        continue

                    # Obtener nombre y extensión
                    nombre_archivo = file_info.filename
                    extension = self._get_extension(nombre_archivo)

                    # Saltar archivos excluidos
                    if extension in EXTENSIONES_EXCLUIDAS:
                        continue

                    # Verificar si la extensión está en la lista de inclusión
                    if extension not in extensiones:
                        continue

                    # Leer contenido del archivo
                    try:
                        with zip_ref.open(file_info) as file:
                            contenido = file.read().decode("utf-8", errors="ignore")

                        # Agregar al consolidado
                        contenido_consolidado.append(
                            f"# ===== Archivo: {nombre_archivo} =====\n"
                        )
                        contenido_consolidado.append(contenido)
                        contenido_consolidado.append("\n\n")

                        archivos_incluidos.append(nombre_archivo)

                    except Exception as e:
                        # Si falla la lectura de un archivo, continuar con el siguiente
                        print(f"Error leyendo {nombre_archivo}: {e}")
                        continue

                # Verificar que se encontraron archivos
                if not archivos_incluidos:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No se encontraron archivos válidos en el ZIP con las extensiones especificadas",
                    )

                # Unir todo el contenido
                contenido_final = "".join(contenido_consolidado)

                return contenido_final, archivos_incluidos

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es un ZIP válido",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo ZIP: {str(e)}",
            )

    def consolidar_txt(self, archivo_txt: BinaryIO) -> tuple[str, list[str]]:
        """
        Consolidate content from a TXT file.

        Args:
            archivo_txt: Binary file object of the TXT file.

        Returns:
            Tuple of (content, list with single filename).

        Raises:
            HTTPException 400: Invalid TXT file.
        """
        try:
            contenido = archivo_txt.read().decode("utf-8", errors="ignore")

            if not contenido.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo TXT está vacío",
                )

            return contenido, ["archivo.txt"]

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo TXT: {str(e)}",
            )

    def _get_extension(self, filename: str) -> str:
        """
        Get file extension in lowercase.

        Args:
            filename: Name of the file.

        Returns:
            Extension with dot (e.g., '.py') or empty string if no extension.
        """
        if "." not in filename:
            return ""

        return "." + filename.rsplit(".", 1)[-1].lower()

    def generar_preview(self, contenido: str, max_chars: int = 500) -> str:
        """
        Generate a preview of the content.

        Args:
            contenido: Full content.
            max_chars: Maximum characters for preview.

        Returns:
            Preview string.
        """
        if len(contenido) <= max_chars:
            return contenido

        return contenido[:max_chars] + "..."
