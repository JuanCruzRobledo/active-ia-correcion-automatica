"""
SEC-006: invariante estructural sobre los guards de pertenencia.

Existieron dos placeholders (require_coordinador_of_materia,
require_tutor_of_comision) que PARECIAN guards de pertenencia por el nombre pero
eran sync, no recibian db y solo miraban el rol: el chequeo real estaba comentado
como TODO. Eran indistinguibles de un guard real para quien leyera el router.

Este test es un cerrojo: cualquier funcion de permissions.py cuyo nombre hable de
acceso/pertenencia a comision o materia DEBE ser async y recibir una AsyncSession.
Si alguien vuelve a agregar un placeholder sync, este test lo caza.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession

import app.core.permissions as permissions

# Un guard de PERTENENCIA menciona un recurso concreto (comision/materia) al que
# hay que validar acceso contra la DB. `require_admin`, `require_tutor`, etc. son
# guards de ROL puro, legitimamente sync: no entran aca.
#
# Se detectan por dos patrones de nombre, para que el invariante hubiera cazado
# los placeholders muertos (require_coordinador_of_materia / _of_comision):
#   - prefijo verificar_acceso*
#   - sufijo _of_materia / _of_comision
def _es_nombre_de_pertenencia(nombre: str) -> bool:
    return (
        nombre.startswith("verificar_acceso")
        or nombre.endswith("_of_materia")
        or nombre.endswith("_of_comision")
    )


def _funciones_de_pertenencia():
    for nombre, obj in inspect.getmembers(permissions, inspect.isfunction):
        if obj.__module__ != permissions.__name__:
            continue
        if _es_nombre_de_pertenencia(nombre):
            yield nombre, obj


def test_los_guards_de_pertenencia_son_async_y_reciben_db():
    revisados = 0
    for nombre, fn in _funciones_de_pertenencia():
        revisados += 1
        assert inspect.iscoroutinefunction(fn), (
            f"{nombre} es un guard de pertenencia pero NO es async: "
            "un guard de pertenencia consulta la DB, no puede ser sync "
            "(ese fue el bug SEC-006 de los placeholders)."
        )
        params = inspect.signature(fn).parameters.values()
        anotaciones = [p.annotation for p in params]
        assert AsyncSession in anotaciones, (
            f"{nombre} no recibe una AsyncSession: un guard de pertenencia "
            "tiene que poder consultar la DB."
        )
    assert revisados >= 3, "Se esperaban al menos 3 guards de pertenencia."


def test_los_placeholders_muertos_ya_no_existen():
    """require_coordinador_of_materia / require_tutor_of_comision fueron eliminados."""
    assert not hasattr(permissions, "require_coordinador_of_materia")
    assert not hasattr(permissions, "require_tutor_of_comision")
