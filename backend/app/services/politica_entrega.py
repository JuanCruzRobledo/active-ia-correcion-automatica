"""Política determinista de archivos y presentación de una entrega.

El análisis usa nombres de entradas, nunca abre dependencias ni secretos. La
restricción se calcula después de evaluar, sin indicársela al proveedor de IA.
"""

import io
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from app.core.politica_archivos import DIRECTORIOS_PENALIZABLES

VERSION_POLITICA = 1
DIRECTORIOS_IGNORADOS = frozenset({
    ".git", ".idea", ".vscode", ".settings", ".gradle", ".mvn",
    "__pycache__", ".pytest_cache", "__macosx", ".mypy_cache", ".ruff_cache",
    ".next", ".nuxt", ".cache", "coverage", ".venv", "venv",
})
ARCHIVOS_IGNORADOS = frozenset({
    ".ds_store", "thumbs.db", "desktop.ini", "package-lock.json",
    "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
    "poetry.lock", "uv.lock", "pipfile.lock", "composer.lock",
})
ARCHIVOS_CONFIGURACION = frozenset({
    "package.json", "pom.xml", "build.gradle", "settings.gradle", "requirements.txt",
    "tsconfig.json", "vite.config.js", "vite.config.ts",
})
MARCADOR_DEVOLUCION = "[Presentación de la entrega]"


def normalizar_ruta(path: str) -> str:
    """Normaliza separadores sin extraer el archivo al disco."""
    return "/".join(part for part in path.replace("\\", "/").split("/") if part not in ("", "."))


def clasificar_ruta(path: str, directorios_permitidos: list[str] | None = None) -> tuple[str | None, str | None]:
    """Devuelve motivo de exclusión y carpeta penalizable, con coincidencia exacta."""
    path = normalizar_ruta(path)
    parts = path.split("/")
    allowed = {value.casefold() for value in directorios_permitidos or []}
    # Un residuo dentro de dependencias sigue siendo evidencia de esas dependencias.
    for index, part in enumerate(parts[:-1]):
        if part.casefold() in DIRECTORIOS_PENALIZABLES and part.casefold() not in allowed:
            return "dependencias_o_compilados", "/".join(parts[:index + 1]) + "/"
        if part.casefold() in DIRECTORIOS_IGNORADOS:
            return "metadatos_o_cache", None
    if parts[-1].casefold() in ARCHIVOS_IGNORADOS or parts[-1].startswith("._"):
        return "metadatos_o_lockfile", None
    return None, None


def directorios_permitidos_de(rubrica: Any) -> list[str]:
    """Las excepciones quedan versionadas con el análisis de la entrega."""
    metadata = getattr(rubrica, "metadata_json", None)
    if not isinstance(metadata, dict):
        return []
    policy = metadata.get("politica_entrega") or {}
    return list(policy.get("directorios_permitidos") or []) if isinstance(policy, dict) else []


def analizar_archivo(content: bytes, filename: str, included: list[str],
                     directorios_permitidos: list[str] | None = None) -> dict[str, Any]:
    """Registra exclusiones antes de perder evidencia al consolidar."""
    ignored: list[dict[str, str]] = []
    penalized: set[str] = set()
    if filename.casefold().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue  # Una carpeta vacía no contiene material no evaluable.
                path = normalizar_ruta(entry.filename)
                reason, forbidden = clasificar_ruta(path, directorios_permitidos)
                if forbidden:
                    penalized.add(forbidden)
                if reason:
                    ignored.append({"ruta": path, "motivo": reason})
                elif path not in included:
                    ignored.append({"ruta": path, "motivo": "extension_no_evaluable"})
    return {
        "version": VERSION_POLITICA,
        "archivos_incluidos": included,
        "archivos_ignorados": sorted(ignored, key=lambda item: item["ruta"]),
        "rutas_penalizables": sorted(penalized),
        "limite_nota": 50 if penalized else None,
        "directorios_permitidos": sorted(set(directorios_permitidos or [])),
    }


def aplicar_tope(nota: Decimal, analisis: dict | None) -> dict[str, Any]:
    """La nota académica ya incluye las reglas de evaluación de la rúbrica."""
    paths = (analisis or {}).get("rutas_penalizables") or []
    limit = 50 if paths and (analisis or {}).get("version") == VERSION_POLITICA else None
    return {
        "nota": min(nota, Decimal(limit)) if limit is not None else nota,
        "nota_academica": float(nota),
        "limite_nota": limit,
        "rutas_penalizables": paths if limit is not None else [],
        "version": (analisis or {}).get("version"),
    }


def aplicar_politica_correccion(correccion: Any, analisis: dict | None,
                               nota_academica: Decimal | None = None) -> None:
    """Aplica el mismo tope a IA, cargas externas y edición manual, una sola vez."""
    previous = (correccion.criterios_json or {}).get("politica_entrega", {})
    academic = nota_academica if nota_academica is not None else previous.get("nota_academica", correccion.nota)
    policy = aplicar_tope(Decimal(str(academic)), analisis)
    correccion.nota = policy.pop("nota")
    correccion.criterios_json = {**(correccion.criterios_json or {}), "politica_entrega": policy}
    correccion.comentario_general = anexar_devolucion_politica(correccion.comentario_general, correccion)


def anexar_devolucion_politica(comment: str | None, correccion: Any) -> str:
    """Mantiene la explicación aunque el tutor personalice el mensaje a Moodle."""
    policy = (correccion.criterios_json or {}).get("politica_entrega", {})
    comment = comment or ""
    comment = comment.split("\n\n" + MARCADOR_DEVOLUCION)[0]
    if policy.get("limite_nota") is not None:
        paths = ", ".join(policy["rutas_penalizables"])
        comment += (
            f"\n\n{MARCADOR_DEVOLUCION} Nota académica: {policy['nota_academica']:g}/100. "
            f"Nota final: {correccion.nota}/100 (máximo 50/100). "
            f"Se detectaron dependencias o compilados no evaluables: {paths}. "
            "Entregá nuevamente el proyecto sin esas carpetas para quitar la restricción; "
            "la nueva versión deberá evaluarse otra vez."
        )
    return comment


def es_nueva_version_moodle(entrega: Any, timemodified: int | None) -> bool:
    """No vuelve a importar la misma versión; las viejas usan fecha conocida."""
    if not timemodified:
        return False
    analysis = getattr(entrega, "analisis_archivos", None)
    previous = analysis.get("moodle_timemodified") if isinstance(analysis, dict) else None
    if isinstance(previous, int):
        return timemodified > previous
    correction = getattr(entrega, "correccion", None)
    date = getattr(correction, "updated_at", None) if correction else getattr(entrega, "created_at", None)
    if not isinstance(date, datetime):
        return False
    date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    return timemodified > date.timestamp()
