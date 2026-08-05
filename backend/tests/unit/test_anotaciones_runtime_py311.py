"""Guardrail: ninguna anotación evaluada puede usar un nombre fuera de scope.

Contexto (incidente 2026-08-04). Un commit anotó
`EntregaService._resolver_modo(rubrica: Any, ...)` sin importar `Any`. La suite
completa pasó en verde —1666 tests— y el contenedor de producción no levantó:

    File "/app/app/services/entrega_service.py", line 380, in EntregaService
        rubrica: Any,
    NameError: name 'Any' is not defined

La causa es una diferencia de versión, no un descuido puntual:

- El entorno de desarrollo corre **Python 3.14**, donde PEP 649 evalúa las
  anotaciones de forma perezosa. Un nombre no importado en una anotación nunca
  se resuelve, así que no falla nunca.
- El `Dockerfile` usa **python:3.11-slim**, que evalúa las anotaciones al
  definir la clase o función. Revienta al importar el módulo, antes de que
  arranque uvicorn.

Es decir: en 3.14 esta clase de error es INDETECTABLE por la suite normal, por
más tests que se agreguen. Este módulo cubre ese agujero con análisis estático,
que da igual en toda versión.

Qué NO cuenta como problema:
- Forward refs en string (`Mapped["Materia"]`, `-> "Rubrica"`): no se evalúan al
  importar en ninguna versión. Es el patrón normal de los modelos SQLAlchemy.
- Módulos con `from __future__ import annotations`: ahí todas las anotaciones
  son perezosas también en 3.11.

Qué SÍ cuenta:
- Un nombre importado sólo bajo `if TYPE_CHECKING:` y usado sin comillas. No
  existe en runtime y rompe igual que un import olvidado.
"""

import ast
import builtins
import pathlib

APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"
BUILTINS = frozenset(dir(builtins))


def _nombres_evaluados(nodo: ast.AST) -> list[tuple[str, int]]:
    """Names que el intérprete resuelve al importar.

    Todo lo que viva dentro de una constante string es un forward ref: no se
    evalúa, así que se descarta junto con su subárbol.
    """
    encontrados: list[tuple[str, int]] = []
    for hijo in ast.walk(nodo):
        if isinstance(hijo, ast.Constant) and isinstance(hijo.value, str):
            continue
        if isinstance(hijo, ast.Name):
            encontrados.append((hijo.id, hijo.lineno))
    return encontrados


def _es_bloque_type_checking(nodo: ast.AST) -> bool:
    """`if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` — no corre en runtime."""
    if not isinstance(nodo, ast.If):
        return False
    test = nodo.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _nombres_en_scope(arbol: ast.Module) -> set[str]:
    """Nombres disponibles en runtime a nivel módulo."""
    disponibles = set(BUILTINS)

    # Los imports de TYPE_CHECKING no existen en runtime: se saltea el subárbol
    # entero para no darlos por definidos.
    solo_type_checking: set[int] = set()
    for nodo in ast.walk(arbol):
        if _es_bloque_type_checking(nodo):
            for interno in ast.walk(nodo):
                solo_type_checking.add(id(interno))

    for nodo in ast.walk(arbol):
        if id(nodo) in solo_type_checking:
            continue
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                disponibles.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom):
            for alias in nodo.names:
                disponibles.add(alias.asname or alias.name)
        elif isinstance(nodo, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            disponibles.add(nodo.name)
        elif isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Store):
            disponibles.add(nodo.id)
        elif isinstance(nodo, ast.arg):
            disponibles.add(nodo.arg)

    return disponibles


def _anotaciones(arbol: ast.Module) -> list[ast.expr]:
    """Anotaciones que el intérprete evalúa al importar el módulo."""
    encontradas: list[ast.expr] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = nodo.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
                if arg is not None and arg.annotation is not None:
                    encontradas.append(arg.annotation)
            if nodo.returns is not None:
                encontradas.append(nodo.returns)
        elif isinstance(nodo, ast.AnnAssign) and nodo.annotation is not None:
            encontradas.append(nodo.annotation)
    return encontradas


def _tiene_future_annotations(arbol: ast.Module) -> bool:
    return any(
        isinstance(nodo, ast.ImportFrom)
        and nodo.module == "__future__"
        and any(alias.name == "annotations" for alias in nodo.names)
        for nodo in arbol.body
    )


def analizar_fuente(fuente: str, nombre_archivo: str = "<test>") -> list[tuple[int, str]]:
    """Devuelve `(línea, nombre)` por cada anotación que rompería en 3.11."""
    arbol = ast.parse(fuente, filename=nombre_archivo)
    if _tiene_future_annotations(arbol):
        return []

    en_scope = _nombres_en_scope(arbol)
    problemas: list[tuple[int, str]] = []
    for anotacion in _anotaciones(arbol):
        for nombre, linea in _nombres_evaluados(anotacion):
            if nombre not in en_scope:
                problemas.append((linea, nombre))
    return problemas


# ----------------------------------------------------------------------------
# El detector tiene que detectar. Sin esto, romperlo lo dejaría en verde para
# siempre — que es exactamente el modo de falla que este módulo existe para
# evitar: un test que pasa porque no mira, no porque esté todo bien.
# ----------------------------------------------------------------------------


def test_detecta_el_nombre_no_importado_del_incidente():
    """Reproduce el bug real: `Any` usado en una anotación sin importarlo."""
    fuente = (
        "from typing import BinaryIO, Literal\n"
        "\n"
        "class EntregaService:\n"
        "    @staticmethod\n"
        "    def _resolver_modo(rubrica: Any, modo: str | None) -> str:\n"
        "        return modo or 'solo_codigo'\n"
    )

    assert analizar_fuente(fuente) == [(5, "Any")]


def test_detecta_import_solo_bajo_type_checking_usado_sin_comillas():
    """Un import de TYPE_CHECKING no existe en runtime: sin comillas, rompe."""
    fuente = (
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from app.models.rubrica import Rubrica\n"
        "\n"
        "def f(r: Rubrica) -> None:\n"
        "    pass\n"
    )

    assert analizar_fuente(fuente) == [(6, "Rubrica")]


def test_no_marca_forward_refs_en_string():
    """`Mapped["Materia"]` es el patrón normal de SQLAlchemy: no se evalúa."""
    fuente = (
        "from sqlalchemy.orm import Mapped\n"
        "\n"
        "class Rubrica:\n"
        "    materia: Mapped['Materia']\n"
        "\n"
        "def f() -> 'Rubrica':\n"
        "    ...\n"
    )

    assert analizar_fuente(fuente) == []


def test_no_marca_modulos_con_future_annotations():
    """Con `from __future__ import annotations` todo es perezoso también en 3.11."""
    fuente = (
        "from __future__ import annotations\n"
        "\n"
        "def f(x: Any) -> Rubrica:\n"
        "    ...\n"
    )

    assert analizar_fuente(fuente) == []


def test_no_marca_una_anotacion_correcta():
    """Control: el nombre está importado, no hay nada que reportar."""
    fuente = (
        "from typing import Any\n"
        "\n"
        "def f(x: Any) -> str:\n"
        "    return str(x)\n"
    )

    assert analizar_fuente(fuente) == []


# ----------------------------------------------------------------------------
# El guardrail propiamente dicho, sobre el código real.
# ----------------------------------------------------------------------------


def test_ninguna_anotacion_de_app_rompe_en_python_311():
    """Ninguna anotación evaluada de `app/` usa un nombre fuera de scope.

    Si esto falla, el contenedor de producción NO va a levantar, por más que el
    resto de la suite esté en verde: el error ocurre al importar el módulo.
    """
    fallas: list[str] = []
    archivos = sorted(APP_DIR.rglob("*.py"))
    assert archivos, f"No se encontró código en {APP_DIR}"

    for archivo in archivos:
        for linea, nombre in analizar_fuente(
            archivo.read_text(encoding="utf-8"), str(archivo)
        ):
            relativo = archivo.relative_to(APP_DIR.parent)
            fallas.append(f"{relativo}:{linea} -> NameError: name '{nombre}' is not defined")

    assert not fallas, (
        "Anotaciones que rompen el arranque en Python 3.11 (prod), "
        "invisibles para el resto de la suite en 3.14:\n  " + "\n  ".join(fallas)
    )
