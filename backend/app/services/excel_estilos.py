# app/services/excel_estilos.py
"""
Lenguaje visual compartido de los Excel (reportes de tutores/nexos y de gestores).

Fuente ÚNICA del diseño: paleta, bordes, rellenos y helpers de celda. Así los tres
reportes (avance de tutor nexo/académico y dashboard de gestores) se ven idénticos y
un cambio de estilo se hace en un solo lugar.
"""

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# ===================== paleta =====================

AZUL_TITULO = "1F4E78"   # títulos y encabezados de columna
AZUL_BLOQUE = "2E75B6"   # barra de cada bloque (unidad/comisión/estado)
ROJO_TXT = "C00000"      # texto de "desaprobado"
GRIS_FECHA = "808080"

_THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

FILL_HEADER = PatternFill("solid", fgColor=AZUL_TITULO)
FILL_TITULO = PatternFill("solid", fgColor="DCE6F1")    # banda suave del título
FILL_BLOQUE = PatternFill("solid", fgColor=AZUL_BLOQUE)
FILL_ZEBRA = PatternFill("solid", fgColor="F2F6FA")     # fila alterna
FILL_DESAPROB = PatternFill("solid", fgColor="FCE4E4")  # celda con desaprobado

CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

FONT_TITULO = Font(bold=True, size=16, color=AZUL_TITULO)
FONT_SUBTITULO = Font(italic=True, size=10, color=GRIS_FECHA)
FONT_SECCION = Font(bold=True, size=12, color=AZUL_TITULO)
FONT_BLOQUE = Font(bold=True, size=11, color="FFFFFF")
FONT_HEADER = Font(bold=True, color="FFFFFF")


# ===================== helpers de celda =====================


def celda_header(ws, row: int, col: int, valor) -> None:
    """Celda de cabecera de columna (azul, blanca, negrita, centrada, con borde)."""
    c = ws.cell(row, col, valor)
    c.font = FONT_HEADER
    c.fill = FILL_HEADER
    c.alignment = CENTER
    c.border = BORDER


def banda_titulo(ws, titulo: str, ncols: int, *, subtitulo: str | None = None) -> None:
    """Título sobre banda azul clara (R1) + subtítulo opcional (R2), abarcando ncols."""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    ws["A1"] = titulo
    ws["A1"].font = FONT_TITULO
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    for col in range(1, ncols + 1):
        ws.cell(1, col).fill = FILL_TITULO
    ws.row_dimensions[1].height = 28
    if subtitulo is not None:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
        ws["A2"] = subtitulo
        ws["A2"].font = FONT_SUBTITULO


def barra_bloque(ws, fila: int, texto: str, ncols: int) -> None:
    """Barra de encabezado de un bloque (merge + fill azul + texto blanco)."""
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=ncols)
    for col in range(1, ncols + 1):
        ws.cell(fila, col).fill = FILL_BLOQUE
    c = ws.cell(fila, 1, texto)
    c.font = FONT_BLOQUE
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[fila].height = 20


def fila_datos(
    ws,
    fila: int,
    valores: list,
    *,
    zebra: bool = False,
    resaltar_col: int | None = None,
    center_cols: tuple[int, ...] = (),
) -> None:
    """Escribe una fila de datos con borde, banding y resaltado opcional.

    - zebra: fondo gris-azulado claro (filas alternas).
    - center_cols: columnas (1-based) centradas; el resto va a la izquierda con wrap.
    - resaltar_col: columna (1-based) a pintar de rojo claro (deuda desaprobada).
    """
    for col, val in enumerate(valores, 1):
        c = ws.cell(fila, col, val)
        c.border = BORDER
        c.alignment = CENTER if col in center_cols else LEFT
        if zebra:
            c.fill = FILL_ZEBRA
    if resaltar_col is not None:
        u = ws.cell(fila, resaltar_col)
        u.fill = FILL_DESAPROB
        u.font = Font(color=ROJO_TXT)
