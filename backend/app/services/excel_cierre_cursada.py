# app/services/excel_cierre_cursada.py
"""
Genera el .xlsx de un cierre de cursada (CierreCursadaRun +
CierreCursadaAlumno ya calculados y persistidos — este módulo NO calcula
nada, solo escribe lo que ya está en la corrida).

Layout (una hoja por materia, igual al de la skill `informe-cierre-cursada`):
  resumen de conteo (Promociona/Regulariza/Recursa) arriba + dona,
  agrupado por comisión/tutor abajo, con las filas de RECURSA resaltadas.
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.chart import Reference
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.services import excel_estilos
from app.services.excel_estilos import (
    BORDER,
    CENTER,
    FONT_HEADER,
    FONT_SECCION,
    banda_titulo,
    barra_bloque,
    celda_header,
    fila_datos,
    grafico_dona,
)

ESTADO_LABEL = {"PROMOCIONA": "Promociona", "REGULARIZA": "Regulariza", "RECURSA": "Recursa"}
ESTADO_COLOR = {"PROMOCIONA": "16A34A", "REGULARIZA": "D97706", "RECURSA": "DC2626"}
ESTADO_ORDEN = ["PROMOCIONA", "REGULARIZA", "RECURSA"]

HEADERS = [
    "Nombre y Apellido", "Email", "TPs Aprobados", "Autoeval OK",
    "Parcial 1", "Parcial 2", "TPI", "Nota Final", "Estado Alumno", "Habilitado para Final",
]
_COL_ESTADO = 9  # 1-based, coincide con HEADERS


def _fmt_pct(valor: float | None) -> str:
    return "N/E" if valor is None else f"{valor:.2f}"


def _fmt_bool(valor: bool) -> str:
    return "Sí" if valor else "No"


def _fmt_nota_final(valor: int | None) -> str | int:
    return "N/E" if valor is None else valor


def _agrupar_por_comision(alumnos: list[CierreCursadaAlumno]) -> dict[str, list[CierreCursadaAlumno]]:
    """{titulo_bloque: [alumnos]} — un bloque por comisión (+ tutor), orden estable."""
    grupos: dict[str, list[CierreCursadaAlumno]] = {}
    for a in alumnos:
        nombre = a.comision_nombre or "Sin comisión asignada"
        titulo = f"{nombre} — Tutor: {a.tutor_nombre}" if a.tutor_nombre else nombre
        grupos.setdefault(titulo, []).append(a)
    return grupos


def _escribir_resumen(ws, materia_nombre: str, run: CierreCursadaRun) -> None:
    banda_titulo(ws, f"CIERRE DE CURSADA — {materia_nombre.upper()}", len(HEADERS),
                 subtitulo=f"Generado el {run.created_at:%d/%m/%Y %H:%M} — umbral TPs {run.umbral_tp_pct:.0f}%")

    fila_header = 4
    celda_header(ws, fila_header, 4, "Estado")
    celda_header(ws, fila_header, 5, "Alumnos")
    conteos = {
        "PROMOCIONA": run.total_promociona,
        "REGULARIZA": run.total_regulariza,
        "RECURSA": run.total_recursa,
    }
    fila = fila_header + 1
    for estado in ESTADO_ORDEN:
        chip = ws.cell(fila, 4, ESTADO_LABEL[estado])
        chip.font = FONT_HEADER
        chip.fill = PatternFill("solid", fgColor=ESTADO_COLOR[estado])
        chip.border = BORDER
        cnt = ws.cell(fila, 5, conteos[estado])
        cnt.alignment = CENTER
        cnt.border = BORDER
        fila += 1
    total = ws.cell(fila, 4, "Total")
    total.font = FONT_SECCION
    ws.cell(fila, 5, run.total_alumnos).font = FONT_SECCION

    grafico_dona(
        ws, "H4", "Distribución del cierre",
        cat_ref=Reference(ws, min_col=4, min_row=fila_header + 1, max_row=fila_header + len(ESTADO_ORDEN)),
        data_ref=Reference(ws, min_col=5, min_row=fila_header, max_row=fila_header + len(ESTADO_ORDEN)),
        colores=[ESTADO_COLOR[e] for e in ESTADO_ORDEN],
    )


def _escribir_detalle(ws, alumnos: list[CierreCursadaAlumno], fila_inicio: int) -> int:
    """Escribe los bloques por comisión desde `fila_inicio`. Devuelve la última fila usada."""
    fila = fila_inicio
    for titulo, del_grupo in _agrupar_por_comision(alumnos).items():
        fila += 1
        barra_bloque(ws, fila, titulo, len(HEADERS))
        fila += 1
        for col, h in enumerate(HEADERS, 1):
            celda_header(ws, fila, col, h)
        fila += 1
        for i, a in enumerate(sorted(del_grupo, key=lambda x: (x.apellido or "", x.nombre or ""))):
            estado = a.estado.value
            valores = [
                f"{a.apellido}, {a.nombre}".strip(", "),
                a.email,
                _fmt_bool(a.tp_ok),
                _fmt_bool(a.autoeval_ok),
                _fmt_pct(a.p1_max),
                _fmt_pct(a.p2_max),
                _fmt_pct(a.tpi_max),
                _fmt_nota_final(a.nota_final),
                ESTADO_LABEL[estado],
                a.habilitado_final,
            ]
            fila_datos(
                ws, fila, valores,
                zebra=(i % 2 == 1),
                resaltar_col=_COL_ESTADO if estado == "RECURSA" else None,
                center_cols=(3, 4, 5, 6, 7, 8, 9, 10),
            )
            fila += 1
        fila += 1  # separador entre bloques
    return fila


def generar_excel_cierre(materia_nombre: str, run: CierreCursadaRun) -> tuple[bytes, str]:
    """(bytes, filename) del .xlsx de un cierre ya generado. `run.alumnos` debe venir cargado."""
    wb = Workbook()
    ws = wb.active
    ws.title = excel_estilos.sheet_title(materia_nombre, default="Cierre")

    _escribir_resumen(ws, materia_nombre, run)
    _escribir_detalle(ws, run.alumnos, fila_inicio=13)

    for col in range(1, len(HEADERS) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 26 if col <= 2 else 16

    buffer = io.BytesIO()
    wb.save(buffer)
    fecha = datetime.utcnow().strftime("%Y%m%d")
    filename = excel_estilos.sanitize_filename(f"Cierre_{materia_nombre}_{fecha}.xlsx")
    return buffer.getvalue(), filename
