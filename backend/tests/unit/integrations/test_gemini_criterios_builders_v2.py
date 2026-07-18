"""Tests de `_build_criterios_texto` / `_build_criterios_pdf_texto` con branch v1/v2.

Change: peso-por-subcriterio (D5): los builders de prompt reciben un nuevo
parámetro `schema_version` (default 1). El camino v1 debe quedar
BYTE A BYTE idéntico al actual (test de caracterización / safety net); v2
imprime cada subcriterio como `[C1.1] (N pts) <descripción>` + evidencias, con
instrucciones de asignar puntaje por subcriterio.
"""

from app.integrations.gemini_correction_client import (
    _build_criterios_pdf_texto,
    _build_criterios_texto,
)

_CRITERIOS = [
    {
        "id": "C1",
        "nombre": "Estructura",
        "peso": 40,
        "descripcion": "Organizacion de archivos",
        "instrucciones_puntuacion": "Maximo 50% si falta carpeta src",
        "subcriterios": [
            {
                "id": "C1.1",
                "descripcion": "package.json presente",
                "evidencias": ["Archivo existe", "Dependencias correctas"],
                "peso": 25,
            },
            {
                "id": "C1.2",
                "descripcion": "estructura carpetas",
                "evidencias": ["Carpeta src existe"],
                "peso": 15,
            },
        ],
    },
    {
        "id": "C2",
        "nombre": "Endpoints",
        "peso": 60,
        "descripcion": "CRUD implementado",
        "subcriterios": [
            {"id": "C2.1", "descripcion": "GET funciona", "evidencias": ["Devuelve 200"], "peso": 60},
        ],
    },
]

# Golden output capturado de la implementación v1 ANTES de agregar schema_version
# (safety net / test de caracterización — 4.1).
_GOLDEN_TEXTO_V1 = (
    "- ID: C1\n"
    "  Nombre: Estructura\n"
    "  Peso: 40 pts\n"
    "  Descripción: Organizacion de archivos\n"
    "  Instrucciones de puntuación (TOPES/REGLAS OBLIGATORIAS): Maximo 50% si falta carpeta src\n"
    "  Evidencias esperadas (checklist verificable en el código):\n"
    "  - package.json presente\n"
    "    * Archivo existe\n"
    "    * Dependencias correctas\n"
    "  - estructura carpetas\n"
    "    * Carpeta src existe\n"
    "\n"
    "- ID: C2\n"
    "  Nombre: Endpoints\n"
    "  Peso: 60 pts\n"
    "  Descripción: CRUD implementado\n"
    "  Evidencias esperadas (checklist verificable en el código):\n"
    "  - GET funciona\n"
    "    * Devuelve 200\n"
    "\n"
)

_GOLDEN_PDF_TEXTO_V1 = (
    "- [C1] Estructura (40 pts): Organizacion de archivos\n"
    "  Instrucciones de puntuación (TOPES/REGLAS OBLIGATORIAS): Maximo 50% si falta carpeta src\n"
    "  * package.json presente\n"
    "    - [ ] Archivo existe\n"
    "    - [ ] Dependencias correctas\n"
    "  * estructura carpetas\n"
    "    - [ ] Carpeta src existe\n"
    "- [C2] Endpoints (60 pts): CRUD implementado\n"
    "  * GET funciona\n"
    "    - [ ] Devuelve 200\n"
)


# ---------------------------------------------------------------------------
# 4.1 — Caracterización v1 (default y explícito): BYTE A BYTE idéntico a hoy
# ---------------------------------------------------------------------------


def test_build_criterios_texto_v1_default_sin_cambios():
    assert _build_criterios_texto(_CRITERIOS) == _GOLDEN_TEXTO_V1


def test_build_criterios_texto_schema_version_1_explicito_sin_cambios():
    assert _build_criterios_texto(_CRITERIOS, schema_version=1) == _GOLDEN_TEXTO_V1


def test_build_criterios_pdf_texto_v1_default_sin_cambios():
    assert _build_criterios_pdf_texto(_CRITERIOS) == _GOLDEN_PDF_TEXTO_V1


def test_build_criterios_pdf_texto_schema_version_1_explicito_sin_cambios():
    assert _build_criterios_pdf_texto(_CRITERIOS, schema_version=1) == _GOLDEN_PDF_TEXTO_V1


# ---------------------------------------------------------------------------
# 4.2 — v2: subcriterio como "[C1.1] (N pts) <descripción>" + instrucciones
# ---------------------------------------------------------------------------


def test_build_criterios_texto_v2_imprime_peso_por_subcriterio():
    texto = _build_criterios_texto(_CRITERIOS, schema_version=2)
    assert "[C1.1] (25 pts) package.json presente" in texto
    assert "[C1.2] (15 pts) estructura carpetas" in texto
    assert "[C2.1] (60 pts) GET funciona" in texto
    # Las evidencias se siguen listando debajo de cada subcriterio.
    assert "Archivo existe" in texto
    assert "Dependencias correctas" in texto


def test_build_criterios_texto_v2_instruye_puntaje_por_subcriterio():
    texto = _build_criterios_texto(_CRITERIOS, schema_version=2)
    assert "puntaje" in texto.lower()
    assert "subcriterio" in texto.lower()
    assert "suma" in texto.lower()


def test_build_criterios_texto_v2_preserva_header_de_criterio():
    """El header de criterio (ID/Nombre/Peso/Descripción/instrucciones) no cambia."""
    texto = _build_criterios_texto(_CRITERIOS, schema_version=2)
    assert "- ID: C1\n" in texto
    assert "  Nombre: Estructura\n" in texto
    assert "  Peso: 40 pts\n" in texto
    assert "Maximo 50% si falta carpeta src" in texto


def test_build_criterios_pdf_texto_v2_imprime_peso_por_subcriterio():
    texto = _build_criterios_pdf_texto(_CRITERIOS, schema_version=2)
    assert "[C1.1] (25 pts) package.json presente" in texto
    assert "[C1.2] (15 pts) estructura carpetas" in texto
    assert "[C2.1] (60 pts) GET funciona" in texto
    assert "- [ ] Archivo existe" in texto


def test_build_criterios_pdf_texto_v2_instruye_puntaje_por_subcriterio():
    texto = _build_criterios_pdf_texto(_CRITERIOS, schema_version=2)
    assert "puntaje" in texto.lower()
    assert "subcriterio" in texto.lower()
    assert "suma" in texto.lower()


def test_build_criterios_texto_v2_distinto_de_v1():
    """Confirma que v2 realmente ramifica (no es un no-op que ignora la versión)."""
    assert _build_criterios_texto(_CRITERIOS, schema_version=2) != _GOLDEN_TEXTO_V1
    assert _build_criterios_pdf_texto(_CRITERIOS, schema_version=2) != _GOLDEN_PDF_TEXTO_V1
