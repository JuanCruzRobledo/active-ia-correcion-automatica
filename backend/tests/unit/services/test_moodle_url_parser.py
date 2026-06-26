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
