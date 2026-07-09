"""
Tests del parser/armador de URLs de entrega de Moodle (items #4 y #5).

#4: de la URL que pega el tutor extraemos cmid (param `id`) y userid para vincular una
    entrega MANUAL a Moodle y habilitar "Subir a Moodle".
#5: construimos la URL de la entrega del alumno para linkearla cuando no hay archivos.
Lógica pura (sin I/O).
"""

import pytest

from app.services.moodle_url_parser import (
    construir_url_entrega,
    parsear_url_entrega,
)


@pytest.mark.parametrize(
    "url,cmid,userid",
    [
        ("https://aulas.tup.edu/mod/assign/view.php?id=123&userid=456&action=grade", 123, 456),
        ("https://host/mod/assign/view.php?id=123", 123, None),
        ("https://host/mod/assign/view.php?userid=456", None, 456),
        ("https://host/mod/assign/view.php?id=99&rownum=0&userid=7", 99, 7),
    ],
)
def test_parsear_url_extrae_cmid_y_userid(url, cmid, userid):
    res = parsear_url_entrega(url)
    assert res["cmid"] == cmid
    assert res["userid"] == userid


@pytest.mark.parametrize("url", ["", None, "no-es-una-url", "https://host/mod/assign/view.php"])
def test_parsear_url_sin_params_devuelve_none(url):
    res = parsear_url_entrega(url)
    assert res["cmid"] is None
    assert res["userid"] is None


def test_parsear_url_ignora_params_no_numericos():
    res = parsear_url_entrega("https://host/mod/assign/view.php?id=abc&userid=xyz")
    assert res["cmid"] is None
    assert res["userid"] is None


def test_construir_url_entrega():
    url = construir_url_entrega("https://aulas.tup.edu", 123, 456)
    assert url == "https://aulas.tup.edu/mod/assign/view.php?id=123&userid=456"


def test_construir_url_normaliza_barra_final_del_host():
    url = construir_url_entrega("https://aulas.tup.edu/", 10, 20)
    assert url == "https://aulas.tup.edu/mod/assign/view.php?id=10&userid=20"


def test_construir_url_sin_datos_es_none():
    assert construir_url_entrega("", 1, 2) is None
    assert construir_url_entrega("https://host", None, 2) is None
    assert construir_url_entrega("https://host", 1, None) is None


# =====================================================================
# Bug 1 — Tipo de actividad ASSIGN vs QUIZ (test de EXPLORACIÓN)
# =====================================================================
# CRITICAL: estos tests DEBEN FALLAR sobre el código sin arreglar. La falla
# confirma el Bug 1: hoy NO existe `construir_url_actividad`, por lo que no hay
# forma de resolver el link de un examen `quiz` (siempre sale /mod/assign/...).
# NOTE: codifican el comportamiento esperado (Property 1 del design) y validarán
# el fix cuando pasen. El import es local a cada test para NO romper los tests de
# preservación de este mismo archivo (construir_url_entrega debe seguir pasando).

_HOST_MOODLE = "https://tup.sied.utn.edu.ar"


def test_construir_url_actividad_quiz_resuelve_mod_quiz():
    """Property 1: un examen quiz (cmid 17679) → /mod/quiz/view.php?id=17679."""
    from app.services.moodle_url_parser import construir_url_actividad

    url = construir_url_actividad(_HOST_MOODLE, 17679, "quiz")
    assert url == f"{_HOST_MOODLE}/mod/quiz/view.php?id=17679"


def test_construir_url_actividad_quiz_segundo_cmid():
    """Property 1: segundo quiz reportado (cmid 20467) → /mod/quiz/view.php."""
    from app.services.moodle_url_parser import construir_url_actividad

    url = construir_url_actividad(_HOST_MOODLE, 20467, "quiz")
    assert url == f"{_HOST_MOODLE}/mod/quiz/view.php?id=20467"


def test_construir_url_actividad_assign_resuelve_mod_assign():
    """Property 1: un examen assign (cmid 17648) → /mod/assign/view.php?id=17648."""
    from app.services.moodle_url_parser import construir_url_actividad

    url = construir_url_actividad(_HOST_MOODLE, 17648, "assign")
    assert url == f"{_HOST_MOODLE}/mod/assign/view.php?id=17648"


# =====================================================================
# Property 7 (Preservación) — spec cierre-cursada-quiz-recuperables-fix
# =====================================================================
#
# 3.1: los exámenes de tipo Tarea (`assign`) resuelven su link EXACTAMENTE como hoy. El
# fix de Bug 1 agrega un helper NUEVO `construir_url_actividad` que ramifica por tipo
# (`/mod/quiz/view.php` para quiz), pero `construir_url_entrega` — usado por las entregas
# del alumno, que siempre son assign — queda INTACTO y sigue armando `/mod/assign/view.php`.
# Metodología observation-first: se observa el comportamiento YA EXISTENTE de
# `construir_url_entrega` sobre el código sin arreglar; debe seguir idéntico tras el fix.
# **Validates: Requirements 3.1**

from hypothesis import given, strategies as st  # noqa: E402


@given(
    host=st.sampled_from(
        ["https://tup.sied.utn.edu.ar", "https://aulas.tup.edu", "https://host/", "https://x.y.z/"]
    ),
    cmid=st.integers(min_value=1, max_value=999_999),
    userid=st.integers(min_value=1, max_value=999_999),
)
def test_prop7_construir_url_entrega_sigue_resolviendo_mod_assign(host, cmid, userid):
    url = construir_url_entrega(host, cmid, userid)

    assert url is not None
    assert url.endswith(f"/mod/assign/view.php?id={cmid}&userid={userid}")
    # El fix de Bug 1 (quiz) NO debe filtrarse a la URL de entrega del alumno.
    assert "/mod/quiz/" not in url
