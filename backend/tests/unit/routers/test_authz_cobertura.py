"""
Red anti-regresion: TODA ruta de entregas/correcciones/documentos debe estar
autorizada. Falla si aparece un endpoint nuevo sin guard de pertenencia.

El bug original (SEC-001/002/004) fue que 20 endpoints usaban un guard vacio.
Este test impide que reaparezca: recorre las rutas reales de los 3 routers y
exige que cada handler o bien invoque un guard de pertenencia, o bien este en
la allowlist explicita de endpoints autorizados por otra via.
"""

import inspect

import pytest

from app.routers import correcciones as r_correcciones
from app.routers import documentos as r_documentos
from app.routers import entregas as r_entregas

# Mecanismos de autorizacion por pertenencia validos en el cuerpo del handler.
_GUARDS = (
    "verificar_acceso_entrega",
    "verificar_acceso_correccion",
    "verificar_acceso_comision_o_materia",
    "filtrar_entregas_accesibles",
    "comisiones_visibles_para",
)

# Endpoints autorizados por OTRA via, justificados uno por uno. Agregar algo aca
# es una decision consciente que queda documentada; olvidarse de un guard NO pasa
# por aca y hace fallar el test.
_ALLOWLIST = {
    # Operan sobre los datos del PROPIO usuario (derivan IDs de current_user.id),
    # no reciben un ID de recurso ajeno: no son IDOR.
    "corregir_global",
    "progreso_global",
    # Validan pertenencia dentro de MoodleGradeService (patron B), no en el router.
    "preview_correccion_moodle",
    "subir_correccion_moodle",
    # Patron B tambien: CorreccionEjercicioService.corregir() llama a
    # `verificar_acceso_materia` apenas resuelve el ejercicio por su referencia
    # externa, ANTES de crear la entrega y ANTES de gastar un token de LLM.
    #
    # El guard NO puede ir en el router porque el recurso se identifica por una
    # referencia externa opaca, no por un id: para saber a que materia pertenece
    # hay que resolver el ejercicio primero. Ponerlo en el router obligaria a
    # resolverlo dos veces, y esa duplicacion es justo donde despues se
    # desincronizan las dos resoluciones.
    "corregir_ejercicio",
}


def _handlers(router):
    vistos = {}
    for route in router.routes:
        fn = getattr(route, "endpoint", None)
        if fn is not None:
            vistos[fn.__name__] = fn
    return vistos


def _todos_los_handlers():
    handlers = {}
    for router in (r_entregas.router, r_correcciones.router, r_documentos.router):
        handlers.update(_handlers(router))
    return handlers


@pytest.mark.parametrize("nombre,fn", sorted(_todos_los_handlers().items()))
def test_cada_endpoint_esta_autorizado(nombre, fn):
    if nombre in _ALLOWLIST:
        return
    fuente = inspect.getsource(fn)
    assert any(g in fuente for g in _GUARDS), (
        f"El endpoint '{nombre}' no invoca ningun guard de pertenencia "
        f"{_GUARDS} ni esta en la allowlist justificada. "
        "Si es un endpoint nuevo, agregale el guard; si esta autorizado por "
        "otra via, agregalo a _ALLOWLIST con su justificacion."
    )


def test_ningun_endpoint_usa_el_guard_vacio():
    """require_any_authenticated (= return user) no debe reaparecer como unico guard."""
    for nombre, fn in _todos_los_handlers().items():
        if nombre in _ALLOWLIST:
            continue
        fuente = inspect.getsource(fn)
        if "require_any_authenticated" in fuente:
            assert any(g in fuente for g in _GUARDS), (
                f"'{nombre}' usa require_any_authenticated sin un guard real."
            )
