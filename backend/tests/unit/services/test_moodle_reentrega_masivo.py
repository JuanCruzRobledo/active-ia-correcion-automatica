"""
Tests del soporte de re-entrega en la subida MASIVA a Moodle (item #3b).

Señal de re-entrega = la del propio Moodle: submission.timemodified > grade.timemodified
(el alumno volvió a entregar DESPUÉS de la última nota). NO se usa el moodle_sync local
porque al re-corregir se borra (cascade) — ver descubrimiento item#3b.
"""

from app.services.moodle_service import (
    es_reentrega,
    parse_submission_timemod_map,
)


# ===================== es_reentrega (puro) =====================


def test_reentrega_cuando_submission_es_posterior_a_la_nota():
    assert es_reentrega(sub_tm=200, grade_tm=100) is True


def test_no_reentrega_si_la_nota_es_posterior_o_igual():
    assert es_reentrega(sub_tm=100, grade_tm=200) is False
    assert es_reentrega(sub_tm=100, grade_tm=100) is False


def test_no_reentrega_si_falta_algun_timestamp():
    assert es_reentrega(sub_tm=0, grade_tm=100) is False
    assert es_reentrega(sub_tm=200, grade_tm=0) is False
    assert es_reentrega(sub_tm=None, grade_tm=None) is False


# ===================== parse_submission_timemod_map (puro) =====================


def _data(subs):
    return {"assignments": [{"assignmentid": 1, "submissions": subs}]}


def test_parse_toma_el_timemodified_mas_alto_por_user():
    data = _data([
        {"userid": 5, "status": "submitted", "timemodified": 100},
        {"userid": 5, "status": "submitted", "timemodified": 300},  # re-entrega
    ])
    assert parse_submission_timemod_map(data) == {5: 300}


def test_parse_ignora_no_submitted():
    data = _data([
        {"userid": 5, "status": "new", "timemodified": 999},
        {"userid": 5, "status": "submitted", "timemodified": 100},
    ])
    assert parse_submission_timemod_map(data) == {5: 100}


def test_parse_varios_usuarios():
    data = _data([
        {"userid": 5, "status": "submitted", "timemodified": 100},
        {"userid": 6, "status": "submitted", "timemodified": 200},
    ])
    assert parse_submission_timemod_map(data) == {5: 100, 6: 200}


def test_parse_vacio():
    assert parse_submission_timemod_map({}) == {}
    assert parse_submission_timemod_map({"assignments": []}) == {}
