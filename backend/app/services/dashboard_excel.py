# app/services/dashboard_excel.py
"""
Armado del Excel de avance académico (Dashboard de Gestores).

Hoja 1 "Resumen": gráfico de torta + conteo por estado.
Hojas 2-5: desglose de alumnos por estado (Al día / Riesgo medio / Riesgo alto / Sin actividad).

Función pura (recibe datos ya consultados, devuelve bytes). Ref: PLAN_DASHBOARD_GESTORES.md.
"""

import io

from openpyxl import Workbook
from openpyxl.chart import PieChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.styles import Alignment, Font, PatternFill

from app.core.fecha import ahora_ar, fmt_fecha_ar
from app.models.avance import AvanceAlumno
from app.models.enums import EstadoAvanceEnum
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
# Mismos colores que el gráfico del dashboard.
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

# Relleno rojo para la actividad cuando el alumno la completó pero la DESAPROBÓ.
_FILL_DESAPROBADA = PatternFill("solid", fgColor="E06666")


def _autoancho(ws, anchos: list[int]) -> None:
    from openpyxl.utils import get_column_letter

    for i, ancho in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho


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

    # ---------- Hoja Resumen ----------
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14)

    # Fecha de creación + línea de corte (en horario Argentina).
    info = f"Documento generado el {fmt_fecha_ar(ahora_ar())}"
    if unidad_actual is not None:
        info += f" · Corte: hasta {etiqueta} {unidad_actual}"
    ws["A2"] = info
    ws["A2"].font = Font(italic=True, size=10)

    ws["A3"] = "Estado"
    ws["B3"] = "Alumnos"
    for cell in ("A3", "B3"):
        ws[cell].font = Font(bold=True)
        ws[cell].fill = PatternFill("solid", fgColor="EEEEEE")

    primera = 4
    for i, estado in enumerate(_ORDEN):
        ws.cell(primera + i, 1, _LABEL[estado])
        ws.cell(primera + i, 2, conteos.get(estado, 0))
    ultima = primera + len(_ORDEN) - 1

    total_row = ultima + 1
    ws.cell(total_row, 1, "Total").font = Font(bold=True)
    ws.cell(total_row, 2, sum(conteos.get(e, 0) for e in _ORDEN)).font = Font(bold=True)

    # Gráfico de torta (referencia la tabla de arriba)
    chart = PieChart()
    chart.title = "Distribución por estado"
    chart.height = 8
    chart.width = 14
    data = Reference(ws, min_col=2, min_row=3, max_row=ultima)  # incluye header
    labels = Reference(ws, min_col=1, min_row=primera, max_row=ultima)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(labels)
    if chart.series:
        serie = chart.series[0]
        for i, estado in enumerate(_ORDEN):
            punto = DataPoint(idx=i)
            punto.graphicalProperties.solidFill = _COLOR[estado]
            serie.data_points.append(punto)
    ws.add_chart(chart, "D3")
    _autoancho(ws, [16, 10])

    # ---------- Hojas de desglose por estado ----------
    headers = _headers(etiqueta)
    for estado in _ORDEN:
        hoja = wb.create_sheet(_LABEL[estado][:31])
        for col, header in enumerate(headers, 1):
            celda = hoja.cell(1, col, header)
            celda.font = Font(bold=True)
            celda.fill = PatternFill("solid", fgColor="EEEEEE")

        fila = 2
        for a in alumnos_por_estado.get(estado, []):
            # "Le falta": las deudas del alumno (igual que los emails), no un placeholder.
            le_falta = formatear_faltantes(a.actividades_faltantes, etiqueta)
            hoja.cell(fila, 1, a.apellido)
            hoja.cell(fila, 2, a.nombre)
            hoja.cell(fila, 3, a.email)
            hoja.cell(fila, 4, a.comision)
            hoja.cell(fila, 5, a.unidad_alcanzada)
            celda_actividad = hoja.cell(fila, 6, le_falta)
            # Si alguna deuda está DESAPROBADA, se pinta de rojo.
            if a.actividad_actual_desaprobada:
                celda_actividad.fill = _FILL_DESAPROBADA
            hoja.cell(fila, 7, formatear_examenes(a.resultados_examenes))
            fila += 1

        hoja.freeze_panes = "A2"
        _autoancho(hoja, [22, 22, 30, 14, 16, 40, 40])
        for celda in hoja[1]:
            celda.alignment = Alignment(horizontal="left")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
