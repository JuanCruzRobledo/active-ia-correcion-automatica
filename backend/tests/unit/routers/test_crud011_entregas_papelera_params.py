"""CRUD-011: el listado de entregas expone los filtros de papelera.

El service y el repositorio ya saben mostrar las borradas, pero si el router no
declara los query params nadie puede pedírselo desde afuera y la papelera queda
igual de inalcanzable que antes. Este test mira la firma real de la ruta en la
app, así un pass-through olvidado no pasa desapercibido.
"""

import pytest

from app.main import app


def _query_params_de_listar_entregas() -> set[str]:
    for ruta in app.routes:
        path = getattr(ruta, "path", "")
        metodos = getattr(ruta, "methods", set()) or set()
        if path.endswith("/entregas/") and "GET" in metodos:
            return {p.name for p in ruta.dependant.query_params}
    raise AssertionError("no se encontró la ruta GET .../entregas/ en la app")


@pytest.mark.parametrize("param", ["incluir_eliminadas", "solo_eliminadas"])
def test_listar_entregas_declara_el_filtro(param):
    assert param in _query_params_de_listar_entregas(), (
        f"CRUD-011: falta el query param '{param}' en GET /entregas/. "
        "Sin él la papelera no se puede pedir desde el panel."
    )


def test_no_se_perdieron_los_filtros_que_ya_estaban():
    """Triangulación: agregar los nuevos no debe pisar los existentes."""
    params = _query_params_de_listar_entregas()
    for previo in (
        "comision_id",
        "rubrica_id",
        "estado",
        "include_archivadas",
        "solo_archivadas",
        "search",
        "page",
        "per_page",
    ):
        assert previo in params, f"se perdió el query param '{previo}'"
