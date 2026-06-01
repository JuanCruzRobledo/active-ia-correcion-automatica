"""Tests del criterio MoodleService.es_calificacion_real.

Es el corazón del fix: Moodle deja un grade con grade=-1 al entregar (antes de
calificar), así que NO alcanza con timemodified>0 — hay que mirar el valor.
"""

import pytest

from app.services.moodle_service import MoodleService


@pytest.mark.parametrize(
    "entry,esperado",
    [
        (None, False),                                          # sin registro
        ({}, False),                                            # vacío
        ({"timemodified": 0, "grade": "85.0"}, False),         # nunca tocado
        ({"timemodified": 123, "grade": "-1.00000"}, False),   # entregado, sin nota
        ({"timemodified": 123, "grade": None}, False),         # sin valor
        ({"timemodified": 123, "grade": "0.00000"}, True),     # 0 ES nota válida
        ({"timemodified": 123, "grade": "85.00000"}, True),    # numérica
        ({"timemodified": 123, "grade": "1.00000"}, True),     # escala (Aprobado)
        ({"timemodified": 123, "grade": "2.00000"}, True),     # escala (Desaprobado)
    ],
)
def test_es_calificacion_real(entry, esperado):
    assert MoodleService.es_calificacion_real(entry) is esperado
