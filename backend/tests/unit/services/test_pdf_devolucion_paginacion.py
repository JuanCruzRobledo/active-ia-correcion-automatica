"""El recuadro de un criterio no debe quedar partido al medio entre páginas.

Estos PDF se le entregan al alumno. Cuando un criterio caía justo en el corte de
página, el cuadro quedaba abierto contra el borde inferior y la página siguiente
arrancaba con una fila huérfana, sin borde superior y sin decir a qué criterio
pertenecía.

Dos defensas, en este orden:

1. `KeepTogether` sobre cada criterio: si entra completo en la página siguiente,
   se va entero en vez de partirse. Resuelve el caso real (un criterio casi nunca
   es más alto que una página).
2. `repeatRows=1` en la tabla: para el criterio que SÍ es más alto que una página
   y no queda otra que cortarlo, la continuación repite la fila de encabezado, así
   el fragmento abre con su nombre y su puntaje en vez de colgar de la nada.
"""

from types import SimpleNamespace
from typing import Any

from reportlab.platypus import KeepTogether, Table

from app.services.pdf_service import PDFService


def _svc() -> PDFService:
    return PDFService(None)  # type: ignore[arg-type]


def _criterio(numero: int, subcriterios: int = 1) -> dict[str, Any]:
    return {
        "id": f"C{numero}",
        "nombre": f"Ejercicio {numero}",
        "puntaje_obtenido": 5,
        "puntaje_maximo": 5,
        "estado": "OK",
        "feedback": "Resuelto correctamente.",
        "subcriterios_evaluados": [
            {
                "id": f"C{numero}.{j}",
                "puntaje_obtenido": 1,
                "puntaje_maximo": 1,
                "estado": "OK",
                "feedback": f"Detalle {j}.",
            }
            for j in range(1, subcriterios + 1)
        ],
    }


def _snapshot(criterios: list[dict[str, Any]]) -> SimpleNamespace:
    """Mismos atributos que arma `_snapshot_correccion`."""
    return SimpleNamespace(
        nota=90,
        condicion_desaprobacion_aplicada=None,
        nota_antes_penalizaciones=None,
        penalizaciones_aplicadas=[],
        criterios_json={"criterios": criterios},
        fortalezas=["Buen trabajo."],
        recomendaciones=["Seguir así."],
        comentario_general="Muy bien.",
        editado_manualmente=False,
        entrega=SimpleNamespace(
            alumno_nombre="RANIERO DE GIUSTO",
            comision=SimpleNamespace(
                nombre="COMI-5",
                anio=2026,
                materia=SimpleNamespace(codigo="PROG2A26", nombre="Programación 2"),
            ),
            rubrica=SimpleNamespace(
                titulo="TP01: Introducción a Java",
                tipo=SimpleNamespace(value="TP"),
                numero=1,
                condiciones_desaprobacion_json=[],
                penalizaciones_json=[],
            ),
        ),
    )


def _keeptogethers(story) -> list[KeepTogether]:
    """Solo los que envuelven un criterio.

    El pie también viaja en su propio KeepTogether, así que hay que distinguirlos
    por contenido: la tabla del criterio tiene dos columnas (nombre | puntaje) y
    la del pie una sola.
    """
    out = []
    for f in story:
        if not isinstance(f, KeepTogether):
            continue
        tablas = [c for c in f._content if isinstance(c, Table)]
        if tablas and len(tablas[0]._cellvalues[0]) == 2:
            out.append(f)
    return out


def test_cada_criterio_va_envuelto_en_keeptogether():
    story = _svc()._build_pdf_content(_snapshot([_criterio(1), _criterio(2), _criterio(3)]))
    assert len(_keeptogethers(story)) == 3, (
        "cada criterio tiene que ir en su propio KeepTogether para no partirse"
    )


def test_el_keeptogether_envuelve_la_tabla_del_criterio():
    story = _svc()._build_pdf_content(_snapshot([_criterio(1)]))
    kt = _keeptogethers(story)[0]
    assert any(isinstance(f, Table) for f in kt._content)


def test_un_solo_criterio_un_solo_keeptogether():
    """Triangulación: no se envuelve de más ni de menos."""
    story = _svc()._build_pdf_content(_snapshot([_criterio(1)]))
    assert len(_keeptogethers(story)) == 1


def test_la_tabla_repite_el_encabezado_si_igual_hay_que_partirla():
    """Un criterio más alto que la página no entra ni en una hoja vacía: ahí
    KeepTogether no puede hacer nada y la tabla se parte igual. La continuación
    tiene que abrir con el encabezado, no con una fila suelta."""
    tabla = _svc()._format_criterio(_criterio(1, subcriterios=60), 1)
    assert tabla.repeatRows == 1


def test_la_tabla_se_parte_por_fila():
    """splitByRow es lo que permite que el corte caiga entre subcriterios y no
    dentro de uno."""
    tabla = _svc()._format_criterio(_criterio(1, subcriterios=60), 1)
    assert tabla.splitByRow


def test_criterio_sin_desglose_tambien_repite_encabezado():
    """Triangulación: vale para rúbricas v1, no solo para las que tienen desglose."""
    c = _criterio(1)
    c.pop("subcriterios_evaluados")
    tabla = _svc()._format_criterio(c, 1)
    assert tabla.repeatRows == 1


def _textos_del_story(story) -> str:
    partes = []
    for f in story:
        if hasattr(f, "text"):
            partes.append(f.text)
        elif isinstance(f, KeepTogether):
            partes += [c.text for c in f._content if hasattr(c, "text")]
    return "\n".join(partes)


def test_el_pie_no_viaja_en_el_flujo_de_contenido():
    """El pie dejó de ser un flowable al final del story.

    Como elemento suelto, cualquier devolución cuyo contenido terminara cerca del
    corte de página lo mandaba solo a una hoja en blanco. Ahora se dibuja en el
    margen inferior de cada página, así que NO tiene que aparecer en el story.
    """
    story = _svc()._build_pdf_content(_snapshot([_criterio(1)]))
    assert "Documento generado por ACTIVE-IA" not in _textos_del_story(story)


def _pie_dibujado(editado: bool, total: int = 5) -> list[str]:
    """Corre el dibujo del pie sobre un canvas instrumentado."""
    import io as _io

    klass = _svc()._canvas_con_pie(editado)
    c = klass(_io.BytesIO())
    escrito: list[str] = []
    c.drawCentredString = lambda x, y, t: escrito.append(t)  # type: ignore[method-assign]
    c.drawRightString = lambda x, y, t: escrito.append(t)  # type: ignore[method-assign]
    c.drawString = lambda x, y, t: escrito.append(t)  # type: ignore[method-assign]
    c._dibujar_pie(total)
    return escrito


def test_el_pie_lleva_la_firma():
    assert any("Documento generado por ACTIVE-IA" in t for t in _pie_dibujado(False))


def test_el_pie_numera_la_pagina_sobre_el_total():
    escrito = _pie_dibujado(False, total=5)
    assert any("Página 1 de 5" in t for t in escrito), escrito


def test_el_total_de_paginas_no_esta_hardcodeado():
    """Triangulación: el total viene del documento, no de una constante."""
    assert any("Página 1 de 12" in t for t in _pie_dibujado(False, total=12))


def test_el_pie_avisa_si_la_correccion_fue_editada_a_mano():
    escrito = _pie_dibujado(True)
    assert any("editada manualmente" in t for t in escrito)


def test_sin_edicion_manual_no_lo_menciona():
    """Triangulación."""
    assert not any("editada manualmente" in t for t in _pie_dibujado(False))
