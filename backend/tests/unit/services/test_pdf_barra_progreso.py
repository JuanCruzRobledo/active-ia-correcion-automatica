"""La barra de progreso no puede desbordarse del recuadro del criterio.

Con el criterio en 100%, `empty_width` da 0 y la tabla quedaba armada con DOS
celdas pero UN solo ancho declarado. Reportlab le asignaba a la segunda columna
el mismo ancho que a la primera, así que la barra medía el doble: 648pt en una
página de 612. Se veía como una línea que escapaba del cuadro hasta el borde de
la hoja, y como los criterios bien resueltos son justamente los que sacan 100%,
pasaba en casi todas las devoluciones.
"""

import pytest
from reportlab.lib import colors
from reportlab.lib.units import inch

from app.services.pdf_service import PDFService

ANCHO_BARRA = 4.5 * inch
COLOR = colors.HexColor("#22c55e")


def _barra(porcentaje: float):
    return PDFService(None)._create_progress_bar(porcentaje, COLOR)  # type: ignore[arg-type]


@pytest.mark.parametrize("porcentaje", [0, 1, 33.3, 50, 99.9, 100])
def test_la_barra_mide_siempre_lo_mismo(porcentaje):
    """El ancho total no depende del puntaje: solo cambia el reparto interno."""
    tabla = _barra(porcentaje)
    assert sum(tabla._argW) == pytest.approx(ANCHO_BARRA), (
        f"con {porcentaje}% la barra mide {sum(tabla._argW)}pt en vez de {ANCHO_BARRA}pt"
    )


@pytest.mark.parametrize("porcentaje", [0, 1, 50, 99.9, 100])
def test_hay_un_ancho_declarado_por_celda(porcentaje):
    """La invariante que estaba rota: si sobran celdas, reportlab les inventa
    un ancho y la tabla se agranda sin que nadie lo pida."""
    tabla = _barra(porcentaje)
    assert len(tabla._argW) == len(tabla._cellvalues[0])


def test_al_100_no_se_duplica():
    """El caso que se veía roto en producción."""
    tabla = _barra(100)
    assert sum(tabla._argW) == pytest.approx(ANCHO_BARRA)
    assert sum(tabla._argW) < 612, "no puede ser más ancha que la página"


def test_la_barra_entra_en_la_celda_del_criterio():
    """La fila de la barra ocupa las dos columnas del criterio (6.5in) menos
    12pt de padding a cada lado."""
    disponible = 6.5 * inch - 24
    assert sum(_barra(100)._argW) <= disponible


def test_al_50_se_reparte_en_dos_columnas():
    """Triangulación: el reparto sigue existiendo cuando hay parte vacía."""
    tabla = _barra(50)
    assert len(tabla._argW) == 2
    assert tabla._argW[0] == pytest.approx(ANCHO_BARRA / 2)
    assert tabla._argW[1] == pytest.approx(ANCHO_BARRA / 2)


def test_al_0_es_una_sola_columna_vacia():
    """Triangulación."""
    tabla = _barra(0)
    assert len(tabla._argW) == 1
    assert tabla._argW[0] == pytest.approx(ANCHO_BARRA)


@pytest.mark.parametrize("porcentaje", [100.5, 140, 200])
def test_un_puntaje_mayor_al_maximo_no_estira_la_barra(porcentaje):
    """La nota la escribe un modelo generativo: si alguna vez devuelve un
    puntaje por encima del máximo, el PDF no puede romperse por eso."""
    tabla = _barra(porcentaje)
    assert sum(tabla._argW) == pytest.approx(ANCHO_BARRA)
    assert len(tabla._argW) == len(tabla._cellvalues[0])
