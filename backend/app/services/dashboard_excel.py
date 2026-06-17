# app/services/dashboard_excel.py
"""
Armado del Excel de avance académico (Dashboard de Gestores).

Hoja 1 "Resumen": tabla por estado (con chips de color) + gráfico de dona.
Hojas 2-5: desglose de alumnos por estado (Al día / Riesgo medio / Riesgo alto / Sin actividad).

Función pura (recibe datos ya consultados, devuelve bytes). El diseño (paleta, bordes,
banding, barras) se comparte con los Excel de tutores vía excel_estilos. Ref:
PLAN_DASHBOARD_GESTORES.md.
"""

import io

from openpyxl import Workbook
from openpyxl.chart import DoughnutChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.fecha import ahora_ar, fmt_fecha_ar
from app.models.avance import AvanceAlumno
from app.models.enums import EstadoAvanceEnum
from app.services import excel_estilos as xl
from app.services.notificacion_render import formatear_examenes, formatear_faltantes

_LABEL: dict[EstadoAvanceEnum, str] = {
    EstadoAvanceEnum.AL_DIA: "Al día",
    EstadoAvanceEnum.RIESGO_MEDIO: "Riesgo medio",
    EstadoAvanceEnum.RIESGO_ALTO: "Riesgo alto",
    EstadoAvanceEnum.SIN_ACTIVIDAD: "Sin actividad",
}
_ORDEN: list[EstadoAvanceEnum] = [
    EstadoAvanceEnum.AL_DIA,
    EstadoAvanceEnum.RIESGO_MEDIO,
    EstadoAvanceEnum.RIESGO_ALTO,
    EstadoAvanceEnum.SIN_ACTIVIDAD,
]
# Mismos colores que el gráfico del dashboard web (verde/naranja/rojo/gris).
_COLOR: dict[EstadoAvanceEnum, str] = {
    EstadoAvanceEnum.AL_DIA: "16A34A",
    EstadoAvanceEnum.RIESGO_MEDIO: "D97706",
    EstadoAvanceEnum.RIESGO_ALTO: "DC2626",
    EstadoAvanceEnum.SIN_ACTIVIDAD: "6B7280",
}


def _headers(etiqueta: str) -> list[str]:
    return [
        "Apellido", "Nombre", "Email", "Comisión",
        f"{etiqueta} alcanzada", "Le falta", "Exámenes",
    ]


def _autoancho(ws, anchos: list[int]) -> None:
    for i, ancho in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho


def _hoja_resumen(ws, titulo, conteos, etiqueta, unidad_actual) -> None:
    """Hoja Resumen: banda de título + tabla por estado (chips de color) + dona."""
    info = f"Documento generado el {fmt_fecha_ar(ahora_ar())}"
    if unidad_actual is not None:
        info += f" · Corte: hasta {etiqueta} {unidad_actual}"
    # ncols=7 para que la banda y el gráfico tengan aire a la derecha de la tabla.
    xl.banda_titulo(ws, titulo, 7, subtitulo=info)

    # Tabla por estado (header en R4; un chip de color por estado).
    xl.celda_header(ws, 4, 1, "Estado")
    xl.celda_header(ws, 4, 2, "Alumnos")
    primera = 5
    for i, estado in enumerate(_ORDEN):
        chip = ws.cell(primera + i, 1, _LABEL[estado])
        chip.fill = PatternFill("solid", fgColor=_COLOR[estado])
        chip.font = Font(bold=True, color="FFFFFF")
        chip.border = xl.BORDER
        cnt = ws.cell(primera + i, 2, conteos.get(estado, 0))
        cnt.alignment = xl.CENTER
        cnt.border = xl.BORDER
    ultima = primera + len(_ORDEN) - 1

    total_row = ultima + 1
    tlabel = ws.cell(total_row, 1, "Total")
    tval = ws.cell(total_row, 2, sum(conteos.get(e, 0) for e in _ORDEN))
    for c in (tlabel, tval):
        c.font = Font(bold=True)
        c.border = xl.BORDER
        c.fill = xl.FILL_TITULO
    tval.alignment = xl.CENTER

    # Gráfico de DONA con porcentajes + leyenda, coloreado por estado.
    chart = DoughnutChart()
    chart.title = "Distribución por estado"
    chart.height = 8.5
    chart.width = 13
    chart.holeSize = 55
    data = Reference(ws, min_col=2, min_row=4, max_row=ultima)  # incluye header
    labels = Reference(ws, min_col=1, min_row=primera, max_row=ultima)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(labels)
    if chart.series:
        serie = chart.series[0]
        for i, estado in enumerate(_ORDEN):
            punto = DataPoint(idx=i)
            punto.graphicalProperties.solidFill = _COLOR[estado]
            serie.data_points.append(punto)
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showPercent = True
    ws.add_chart(chart, "D4")

    _autoancho(ws, [16, 10])
    ws.freeze_panes = "A3"


def _hoja_estado(wb, estado, alumnos, etiqueta) -> None:
    """Hoja de desglose de un estado: header azul + filas con borde, banding y resaltado."""
    hoja = wb.create_sheet(_LABEL[estado][:31])
    headers = _headers(etiqueta)
    for col, header in enumerate(headers, 1):
        xl.celda_header(hoja, 1, col, header)

    fila = 2
    for i, a in enumerate(alumnos):
        # "Le falta": las deudas del alumno (igual que los emails).
        le_falta = formatear_faltantes(a.actividades_faltantes, etiqueta)
        xl.fila_datos(
            hoja, fila,
            [a.apellido, a.nombre, a.email, a.comision, a.unidad_alcanzada,
             le_falta, formatear_examenes(a.resultados_examenes)],
            zebra=bool(i % 2),
            center_cols=(4, 5),
            # Si la actividad de la unidad alcanzada quedó DESAPROBADA, se pinta "Le falta".
            resaltar_col=6 if a.actividad_actual_desaprobada else None,
        )
        fila += 1

    if alumnos:
        total = hoja.cell(fila + 1, 1, f"Total: {len(alumnos)} alumnos")
        total.font = Font(bold=True)

    hoja.freeze_panes = "A2"
    _autoancho(hoja, [22, 22, 30, 14, 16, 42, 40])


def construir_excel_avance(
    titulo: str,
    conteos: dict[EstadoAvanceEnum, int],
    alumnos_por_estado: dict[EstadoAvanceEnum, list[AvanceAlumno]],
    etiqueta: str = "Unidad",
    unidad_actual: int | None = None,
) -> bytes:
    """Arma el .xlsx de avance (Resumen + 4 hojas de desglose). Devuelve los bytes.

    `etiqueta` ("Unidad"|"Semana") nombra la progresión en los headers y en la columna
    'Le falta' (deudas del alumno, ej. "Semana 8: Quiz, TP"). `unidad_actual` es la unidad
    hasta donde se evalúa el avance (línea de corte del informe).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    _hoja_resumen(ws, titulo, conteos, etiqueta, unidad_actual)
    for estado in _ORDEN:
        _hoja_estado(wb, estado, alumnos_por_estado.get(estado, []), etiqueta)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
