"""El PDF de devolución tiene que mostrar el desglose por subcriterio.

Cuando la rúbrica ganó subcriterios (schema v2), el generador del PDF no se
actualizó: la corrección persiste `subcriterios_evaluados` con puntaje, estado y
feedback de cada subcriterio, la IA lo produce y el frontend lo muestra
(`CorreccionViewEditModal`), pero el PDF se quedaba en el nivel criterio. El
alumno veía la nota sin saber de dónde salía.

Se testea `_format_criterio` directamente en vez del PDF renderizado: devuelve
flowables de reportlab y sus celdas son inspeccionables, así que se verifica el
CONTENIDO sin sumar una dependencia de parseo de PDF al proyecto (hoy los tests
del generador solo comprueban que los bytes arranquen con %PDF).
"""

from typing import Any

from reportlab.platypus import Paragraph

from app.services.pdf_service import PDFService


def _svc() -> PDFService:
    # _format_criterio es puro: no toca la sesión, solo arma flowables.
    return PDFService(None)  # type: ignore[arg-type]


def _texto_de(table) -> str:
    """Todo el texto de la tabla, sin importar en qué celda cayó."""
    partes: list[str] = []
    for fila in table._cellvalues:
        for celda in fila:
            if isinstance(celda, Paragraph):
                partes.append(celda.text)
            elif isinstance(celda, str):
                partes.append(celda)
    return "\n".join(partes)


def _criterio(subcriterios: Any = "__ausente__") -> dict[str, Any]:
    c: dict[str, Any] = {
        "id": "C1",
        "nombre": "Ejercicio 1: Hola Mundo y Estructura",
        "puntaje_obtenido": 3,
        "puntaje_maximo": 5,
        "estado": "WARNING",
        "feedback": "Compila pero falta el mensaje pedido.",
    }
    if subcriterios != "__ausente__":
        c["subcriterios_evaluados"] = subcriterios
    return c


SUB_UNO = [
    {
        "id": "C1.1",
        "puntaje_obtenido": 3,
        "puntaje_maximo": 3,
        "estado": "OK",
        "feedback": "La clase y el método main están presentes.",
    }
]

SUB_DOS = SUB_UNO + [
    {
        "id": "C1.2",
        "puntaje_obtenido": 0,
        "puntaje_maximo": 2,
        "estado": "ERROR",
        "feedback": "No imprime el saludo por consola.",
    }
]


def test_muestra_el_id_del_subcriterio():
    tabla = _svc()._format_criterio(_criterio(SUB_UNO), 1)
    assert "C1.1" in _texto_de(tabla)


def test_muestra_el_puntaje_del_subcriterio():
    tabla = _svc()._format_criterio(_criterio(SUB_UNO), 1)
    assert "3/3" in _texto_de(tabla)


def test_muestra_el_feedback_del_subcriterio():
    tabla = _svc()._format_criterio(_criterio(SUB_UNO), 1)
    assert "La clase y el método main están presentes." in _texto_de(tabla)


def test_muestra_todos_los_subcriterios_no_solo_el_primero():
    """Triangulación: con dos, tienen que aparecer los dos."""
    texto = _texto_de(_svc()._format_criterio(_criterio(SUB_DOS), 1))
    assert "C1.1" in texto
    assert "C1.2" in texto
    assert "No imprime el saludo por consola." in texto
    assert "0/2" in texto


def test_el_criterio_sigue_mostrando_lo_suyo():
    """Triangulación: el desglose se suma, no reemplaza."""
    texto = _texto_de(_svc()._format_criterio(_criterio(SUB_UNO), 1))
    assert "C1: Ejercicio 1: Hola Mundo y Estructura" in texto
    assert "3/5" in texto
    assert "Compila pero falta el mensaje pedido." in texto


def test_sin_la_clave_no_agrega_filas():
    """Rúbricas v1: no hay desglose y el PDF debe quedar como estaba."""
    tabla = _svc()._format_criterio(_criterio(), 1)
    assert len(tabla._cellvalues) == 3


def test_con_la_clave_en_none_no_agrega_filas():
    """`subcriterios_evaluados` puede existir con valor None: correccion_service
    siempre setea la clave y `_subcriterios_para_json` devuelve None en v1."""
    tabla = _svc()._format_criterio(_criterio(None), 1)
    assert len(tabla._cellvalues) == 3


def test_con_lista_vacia_no_agrega_filas():
    tabla = _svc()._format_criterio(_criterio([]), 1)
    assert len(tabla._cellvalues) == 3


def test_escapa_el_feedback_del_subcriterio():
    """El feedback es texto libre de la IA: un < sin escapar rompe el render."""
    sub = [{
        "id": "C1.1",
        "puntaje_obtenido": 1,
        "puntaje_maximo": 1,
        "estado": "OK",
        "feedback": "Usa if (a < b) & valida <input>",
    }]
    texto = _texto_de(_svc()._format_criterio(_criterio(sub), 1))
    assert "&lt;" in texto and "&amp;" in texto
    assert "<input>" not in texto
