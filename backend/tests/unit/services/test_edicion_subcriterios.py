from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.services.edicion_subcriterios import preparar_criterios_editados


def criterio():
    return {
        "id": "C1", "nombre": "Criterio", "puntaje_obtenido": 12,
        "puntaje_maximo": 20, "estado": "WARNING", "feedback": "Padre",
        "subcriterios_evaluados": [{
            "id": "C1.1", "puntaje_obtenido": 12, "puntaje_maximo": 20,
            "estado": "WARNING", "feedback": "Original",
        }],
    }


def test_editar_puntaje_recalcula_padre_sin_mutar_snapshot():
    original = criterio()
    edited = deepcopy(original)
    edited["subcriterios_evaluados"][0]["puntaje_obtenido"] = Decimal(16)
    result = preparar_criterios_editados([edited], [original])
    assert result[0]["puntaje_obtenido"] == 16
    assert original["puntaje_obtenido"] == 12
    assert result[0]["subcriterios_evaluados"][0]["estado"] == "WARNING"


@pytest.mark.parametrize("score", [0, 20, Decimal("2.5")])
def test_limites_y_decimales_validos(score):
    original = criterio()
    edited = deepcopy(original)
    edited["subcriterios_evaluados"][0]["puntaje_obtenido"] = score
    assert preparar_criterios_editados([edited], [original])[0]["puntaje_obtenido"] == score


@pytest.mark.parametrize("score", [-1, 21, Decimal("NaN"), Decimal("Infinity")])
def test_rechaza_puntajes_invalidos(score):
    original = criterio()
    edited = deepcopy(original)
    edited["subcriterios_evaluados"][0]["puntaje_obtenido"] = score
    with pytest.raises(HTTPException) as error:
        preparar_criterios_editados([edited], [original])
    assert error.value.status_code == 400
    assert original == criterio()


@pytest.mark.parametrize("feedback", ["", "   "])
def test_rechaza_comentarios_vacios(feedback):
    edited = criterio()
    edited["subcriterios_evaluados"][0]["feedback"] = feedback
    with pytest.raises(HTTPException):
        preparar_criterios_editados([edited], [criterio()])


@pytest.mark.parametrize("field,value", [("id", "C2.1"), ("puntaje_maximo", 30), ("estado", "OK")])
def test_rechaza_alterar_snapshot(field, value):
    edited = criterio()
    edited["subcriterios_evaluados"][0][field] = value
    with pytest.raises(HTTPException):
        preparar_criterios_editados([edited], [criterio()])


@pytest.mark.parametrize("subs", [None, []])
def test_rechaza_borrado_explicito(subs):
    edited = criterio()
    edited["subcriterios_evaluados"] = subs
    with pytest.raises(HTTPException):
        preparar_criterios_editados([edited], [criterio()])


def test_omision_preserva_desglose_y_feedback_no_repara_historia():
    original = criterio()
    original["puntaje_obtenido"] = 19
    edited = deepcopy(original)
    edited.pop("subcriterios_evaluados")
    result = preparar_criterios_editados([edited], [original])[0]
    assert result["subcriterios_evaluados"] == original["subcriterios_evaluados"]
    edited = deepcopy(original)
    edited["subcriterios_evaluados"][0]["feedback"] = "Nuevo"
    assert preparar_criterios_editados([edited], [original])[0]["puntaje_obtenido"] == 19


def test_rechaza_composicion_duplicados_y_suma_mayor_al_padre():
    original = criterio()
    duplicated = deepcopy(original)
    duplicated["subcriterios_evaluados"] *= 2
    with pytest.raises(HTTPException):
        preparar_criterios_editados([duplicated], [original])
    with pytest.raises(HTTPException):
        preparar_criterios_editados([], [original])
    original["puntaje_maximo"] = 10
    edited = deepcopy(original)
    edited["subcriterios_evaluados"][0]["puntaje_obtenido"] = 15
    with pytest.raises(HTTPException):
        preparar_criterios_editados([edited], [original])


@pytest.mark.parametrize("subs", [None, []])
def test_historico_sin_desglose_conserva_edicion(subs):
    original = criterio()
    original["subcriterios_evaluados"] = subs
    edited = deepcopy(original)
    edited["puntaje_obtenido"] = 7
    assert preparar_criterios_editados([edited], [original])[0]["puntaje_obtenido"] == 7


def test_no_inventa_desglose_sin_snapshot():
    with pytest.raises(HTTPException):
        preparar_criterios_editados([criterio()], [])


def test_suma_dos_subcriterios_y_preserva_criterio_hermano():
    first = criterio()
    first["puntaje_maximo"] = 40
    first["subcriterios_evaluados"].append({**first["subcriterios_evaluados"][0], "id": "C1.2", "puntaje_obtenido": 5})
    second = {**criterio(), "id": "C2"}
    second["subcriterios_evaluados"][0]["id"] = "C2.1"
    edited = deepcopy([first, second])
    edited[0]["subcriterios_evaluados"][0]["puntaje_obtenido"] = Decimal("2.5")
    result = preparar_criterios_editados(edited, [first, second])
    assert result[0]["puntaje_obtenido"] == Decimal("7.5")
    assert result[1] == second
    edited[0]["subcriterios_evaluados"][0], edited[1]["subcriterios_evaluados"][0] = (
        edited[1]["subcriterios_evaluados"][0], edited[0]["subcriterios_evaluados"][0],
    )
    with pytest.raises(HTTPException):
        preparar_criterios_editados(edited, [first, second])
