"""Tests del mapeo de nota Active-IA → nota Moodle (Fase 3, lógica crítica).

Cubre:
- TP (escala cualitativa): nota >= 60 → índice 'Aprobado'; < 60 → 'Desaprobado'.
  ⚠️ En TUPaD, scale_id=5 tiene el orden INVERTIDO (1=Aprobado, 2=Desaprobado).

Todos los casos de acá fijan el comportamiento de **TUPaD**, y por eso pasan su
host explícito: los `scale_id` son por instancia de Moodle. La resolución por
campus tiene sus propios tests en `test_moodle_escalas_por_campus.py`.
- No-TP (numérica): nota escalada al máximo REAL del assignment (no se asume 100).
- Discordancias de escala → error explícito (no se envía a ciegas).
"""

import pytest

from app.services.moodle_grade_service import MoodleGradeService, GradeMapError
from app.services.moodle_service import AssignmentGradeConfig

# Campus al que corresponden los scale_id de este archivo.
TUPAD = "https://tup.sied.utn.edu.ar"


def _escala(scale_id=5, instance_id=478):
    return AssignmentGradeConfig(instance_id=instance_id, tipo="escala", scale_id=scale_id)


def _numerica(grade_max=100, instance_id=484):
    return AssignmentGradeConfig(instance_id=instance_id, tipo="numerica", grade_max=grade_max)


# ── TP → escala cualitativa (scale 5: 1=Aprobado, 2=Desaprobado) ──

@pytest.mark.parametrize("nota,indice_esperado", [
    (100, 1.0),  # Aprobado
    (60, 1.0),   # Aprobado (umbral)
    (59, 2.0),   # Desaprobado
    (0, 2.0),    # Desaprobado
])
def test_tp_mapea_a_indice_de_escala(nota, indice_esperado):
    grade = MoodleGradeService._mapear_nota("TP", nota, _escala(), moodle_host=TUPAD)
    assert grade == indice_esperado


def test_tp_con_assignment_numerico_es_error():
    # Si la rúbrica es TP pero el assignment resultó numérico → discordancia, no se envía
    with pytest.raises(GradeMapError):
        MoodleGradeService._mapear_nota("TP", 80, _numerica(), moodle_host=TUPAD)


def test_tp_con_escala_no_mapeada_es_error():
    with pytest.raises(GradeMapError):
        MoodleGradeService._mapear_nota("TP", 80, _escala(scale_id=99), moodle_host=TUPAD)


# ── No-TP → numérica, escalada al máximo real ──

def test_no_tp_numerica_max_100():
    assert MoodleGradeService._mapear_nota("PARCIAL_1", 90, _numerica(100), moodle_host=TUPAD) == 90.0


def test_no_tp_numerica_max_10_escala():
    # ¡Trabajo Integrador era sobre 10! 90/100*10 = 9.0
    assert MoodleGradeService._mapear_nota("GLOBAL", 90, _numerica(10), moodle_host=TUPAD) == 9.0


def test_no_tp_con_assignment_escala_es_error():
    with pytest.raises(GradeMapError):
        MoodleGradeService._mapear_nota("PARCIAL_1", 90, _escala(), moodle_host=TUPAD)
