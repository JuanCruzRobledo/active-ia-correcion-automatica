# app/services/notificacion_render.py
"""
Render de los adjuntos/cuerpos de las notificaciones (PLAN_NOTIFICACIONES_EMAIL.md §5.1).

Funciones PURAS (reciben datos ya resueltos, devuelven str/bytes):
- formatear_faltantes: JSONB {modo, unidades, actividades} → texto legible.
- construir_pdf_tutor_academico: PDF (reportlab), 1 página por materia.
- construir_excel_tutor_nexo: Excel (openpyxl), 1 hoja por materia.

El HTML del alumno se arma en T5 (también acá), reutilizando formatear_faltantes.
"""

import io
import re

from app.core.fecha import ahora_ar, fmt_fecha_ar
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ===================== texto =====================


def _unir_y(items: list[str]) -> str:
    """['4'] → '4'; ['4','5'] → '4 y 5'; ['4','5','6'] → '4, 5 y 6'."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


_LABEL_DEUDA = {
    "TP": "TP",
    "QUIZ": "Quiz",
    "AUTOEVALUACION": "Autoevaluación",
    "CIERRE": "Cierre",
}


def formatear_faltantes(faltantes: dict | None, etiqueta: str = "Unidad") -> str:
    """Convierte el JSONB de deudas (§9.bis F) en texto para el reporte, agrupado por unidad.

    Formato esperado: {"deudas": [{"unidad", "tipo": "TP"|"QUIZ"|"AUTOEVALUACION"|"CIERRE", "estado"}]}.
    `etiqueta` es cómo se llama la progresión en esta materia ("Unidad" por defecto,
    "Semana" para materias por semana como PYE).
    Ej (etiqueta="Unidad"): "Unidad 3: TP (desaprobado), Autoevaluación · Unidad 5: Cierre".
    Ej (etiqueta="Semana"): "Semana 3: Quiz · Semana 5: Cierre". "" si no hay deudas.
    """
    if not faltantes:
        return ""
    deudas = faltantes.get("deudas") or []
    if not deudas:
        return ""
    por_unidad: dict[int, list[str]] = {}
    for d in deudas:
        tipo = _LABEL_DEUDA.get(d.get("tipo"), d.get("tipo") or "?")
        if d.get("estado") == "desaprobado":
            tipo += " (desaprobado)"
        por_unidad.setdefault(d.get("unidad"), []).append(tipo)
    partes = [
        f"{etiqueta} {u}: {', '.join(items)}"
        for u, items in sorted(por_unidad.items(), key=lambda kv: kv[0] if kv[0] is not None else 0)
    ]
    return " · ".join(partes)


_LABEL_RESULTADO = {"aprobado": "Aprobó", "desaprobado": "Desaprobó", "ausente": "Ausente"}


def formatear_examenes(resultados: dict | None) -> str:
    """Resultados de exámenes (JSONB) → texto para el reporte.

    Formato esperado: {"examenes": [{"etiqueta", "resultado", "rescatado"}, ...]}.
    Ej: "Parcial 1: Aprobó · Parcial 2: Aprobó (recuperado) · Global 1: Ausente".
    "" si no hay exámenes. `rescatado` marca un parcial reprobado/ausente que su
    recuperatorio/extensión rescató.
    """
    if not resultados:
        return ""
    examenes = resultados.get("examenes") or []
    if not examenes:
        return ""
    partes = []
    for e in examenes:
        label = _LABEL_RESULTADO.get(e.get("resultado"), e.get("resultado") or "?")
        if e.get("rescatado"):
            label += " (recuperado)"
        partes.append(f"{e.get('etiqueta')}: {label}")
    return " · ".join(partes)


def tiene_examen_desaprobado(resultados: dict | None) -> bool:
    """True si algún examen quedó DESAPROBADO (con rescate ya aplicado).

    Dispara la inclusión del alumno en los reportes aunque esté al día. NO usa "ausente":
    antes de que se tome el examen todos figuran ausentes y dispararía a toda la materia.
    """
    if not resultados:
        return False
    return any(
        e.get("resultado") == "desaprobado" for e in (resultados.get("examenes") or [])
    )


def examen_para_atender(resultados: dict | None) -> bool:
    """True si algún examen quedó DESAPROBADO o AUSENTE (con rescate ya aplicado).

    Lo usa la matriz de exámenes del PDF del tutor: muestra a quienes tienen algo para
    atender (reprobó o no rindió). El rescatado queda 'aprobado' → no entra.
    """
    if not resultados:
        return False
    return any(
        e.get("resultado") in ("desaprobado", "ausente")
        for e in (resultados.get("examenes") or [])
    )


def label_resultado_examen(e: dict | None) -> str:
    """Resultado de UN examen → 'Aprobó' / 'Desaprobó' / 'Ausente' (+ ' (R)' si rescatado)."""
    if not e:
        return "—"
    label = _LABEL_RESULTADO.get(e.get("resultado"), e.get("resultado") or "?")
    if e.get("rescatado"):
        label += " (R)"
    return label


# ===================== PDF (tutor académico) =====================


def _escape(text: str) -> str:
    """Escapa &, <, > para que reportlab no los tome como markup."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def construir_pdf_tutor_academico(tutor_nombre: str, materias: list[dict]) -> bytes:
    """PDF de actividades faltantes para un tutor académico.

    materias: [{"materia": str,
                "comisiones": [{"comision": str,
                                "faltantes": [{"apellido","nombre","detalle"}],
                                "examenes_columnas": [str],
                                "examenes_filas": [{"apellido","nombre","celdas":[str]}]}]}]
    1 página por materia (PageBreak). Por comisión: tabla de actividades faltantes +
    MATRIZ de exámenes (alumno × examen) con los alumnos que tienen algo para atender.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=0.6 * inch, leftMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    estilos = getSampleStyleSheet()
    h_materia = ParagraphStyle("hMateria", parent=estilos["Heading1"], fontSize=15, spaceAfter=6)
    h_comision = ParagraphStyle("hComision", parent=estilos["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    h_examenes = ParagraphStyle("hExamenes", parent=estilos["Heading3"], fontSize=10, spaceBefore=8, spaceAfter=3)
    normal = estilos["BodyText"]

    story: list = [
        Paragraph("Actividades faltantes de tus alumnos", estilos["Title"]),
        Paragraph(f"Tutor: {_escape(tutor_nombre)}", normal),
        Paragraph(f"Documento generado el {fmt_fecha_ar(ahora_ar())}", normal),
        Spacer(1, 10),
    ]

    if not materias:
        story.append(Paragraph("No hay alumnos con actividades pendientes.", normal))

    for idx, mat in enumerate(materias):
        if idx > 0:
            story.append(PageBreak())
        story.append(Paragraph(_escape(mat.get("materia") or "Materia"), h_materia))
        # Línea de corte: hasta qué unidad/semana se evalúa el avance de esta materia.
        ua = mat.get("unidad_actual")
        if ua is not None:
            etq = mat.get("etiqueta") or "Unidad"
            story.append(Paragraph(f"Corte: hasta {_escape(f'{etq} {ua}')}", normal))

        estilo_tabla = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ])
        for com in mat.get("comisiones", []):
            story.append(Paragraph(f"Comisión {_escape(com.get('comision') or '—')}", h_comision))

            # Parte 1: actividades faltantes (solo alumnos con deudas).
            faltantes = com.get("faltantes", [])
            if faltantes:
                story.append(Paragraph("Actividades faltantes", h_examenes))
                filas = [["Alumno", "Actividades faltantes"]]
                for al in faltantes:
                    alumno = f"{al.get('apellido','')}, {al.get('nombre','')}".strip(", ")
                    filas.append([
                        Paragraph(_escape(alumno), normal),
                        Paragraph(_escape(al.get("detalle") or "—"), normal),
                    ])
                tabla = Table(filas, colWidths=[2.6 * inch, 4.4 * inch], repeatRows=1)
                tabla.setStyle(estilo_tabla)
                story.append(tabla)

            # Parte 2: MATRIZ de exámenes (alumno × examen), solo desaprobados/ausentes.
            columnas = com.get("examenes_columnas", [])
            exfilas = com.get("examenes_filas", [])
            if exfilas and columnas:
                story.append(Paragraph("Exámenes (a atender)", h_examenes))
                filas = [["Alumno", *columnas]]
                for al in exfilas:
                    alumno = f"{al.get('apellido','')}, {al.get('nombre','')}".strip(", ")
                    filas.append([
                        Paragraph(_escape(alumno), normal),
                        *[Paragraph(_escape(c), normal) for c in al.get("celdas", [])],
                    ])
                # Anchos dinámicos: 2.2" para el alumno, el resto repartido entre exámenes.
                ancho_examen = (7.0 - 2.2) / len(columnas)
                colWidths = [2.2 * inch] + [ancho_examen * inch] * len(columnas)
                tabla = Table(filas, colWidths=colWidths, repeatRows=1)
                tabla.setStyle(estilo_tabla)
                story.append(tabla)

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# ===================== Excel (tutor nexo) =====================

_HEADERS_NEXO = ["Comisión", "Alumno", "Actividades faltantes"]
_FILL_HEADER = PatternFill("solid", fgColor="1F4E78")
_INVALIDOS_HOJA = re.compile(r"[:\\/?*\[\]]")


def _safe_sheet_name(nombre: str, usados: set[str]) -> str:
    """Nombre de hoja válido para Excel: sin caracteres prohibidos, <=31, único."""
    base = _INVALIDOS_HOJA.sub(" ", (nombre or "Hoja")).strip()[:31] or "Hoja"
    nombre_final = base
    i = 2
    while nombre_final in usados:
        sufijo = f" ({i})"
        nombre_final = base[: 31 - len(sufijo)] + sufijo
        i += 1
    usados.add(nombre_final)
    return nombre_final


def construir_excel_tutor_nexo(regional: str, materias: list[dict]) -> bytes:
    """Excel de avance de una regional para el tutor nexo. 1 hoja por materia.

    materias: [{"materia": str, "unidad_actual": int|None, "etiqueta": str,
                "filas": [{"comision","apellido","nombre","faltantes"}]}]
    Cada hoja muestra en qué unidad/semana está la materia (contexto que el nexo no tiene).
    """
    wb = Workbook()
    wb.remove(wb.active)  # arrancamos sin la hoja por defecto
    usados: set[str] = set()

    if not materias:
        ws = wb.create_sheet(_safe_sheet_name("Sin datos", usados))
        ws["A1"] = f"Regional {regional}: sin alumnos con pendientes"

    for mat in materias:
        ws = wb.create_sheet(_safe_sheet_name(mat.get("materia") or "Materia", usados))
        ws["A1"] = f"Regional {regional} — {mat.get('materia') or ''}".strip(" —")
        ws["A1"].font = Font(bold=True, size=13)

        # Línea de corte: hasta qué unidad/semana se evalúa (contexto que el nexo no tiene).
        etq = mat.get("etiqueta") or "Unidad"
        ua = mat.get("unidad_actual")
        ws["A2"] = f"Corte: hasta {etq} {ua}" if ua is not None else "Corte: —"
        ws["A2"].font = Font(italic=True, size=11)
        # Fecha de creación del documento (horario Argentina).
        ws["A3"] = f"Documento generado el {fmt_fecha_ar(ahora_ar())}"
        ws["A3"].font = Font(italic=True, size=10)

        # Header en la fila 4
        for col, header in enumerate(_HEADERS_NEXO, 1):
            celda = ws.cell(4, col, header)
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = _FILL_HEADER

        fila = 5
        # ordenado por comisión y luego apellido
        for f in sorted(
            mat.get("filas", []),
            key=lambda r: (r.get("comision") or "", r.get("apellido") or ""),
        ):
            alumno = f"{f.get('apellido','')}, {f.get('nombre','')}".strip(", ")
            ws.cell(fila, 1, f.get("comision") or "—")
            ws.cell(fila, 2, alumno)
            ws.cell(fila, 3, f.get("faltantes") or "—")
            fila += 1

        ws.freeze_panes = "A5"
        for i, ancho in enumerate((18, 32, 50), 1):
            ws.column_dimensions[get_column_letter(i)].width = ancho
        for celda in ws[4]:
            celda.alignment = Alignment(horizontal="left")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ===================== HTML (cuerpo del email del alumno) =====================

# Estilos INLINE: los clientes de correo ignoran <style>/CSS externo.
_TH = (
    "background:#1F4E78;color:#ffffff;text-align:left;"
    "padding:8px 10px;border:1px solid #cccccc;font-size:13px"
)
_TD = "padding:8px 10px;border:1px solid #cccccc;font-size:13px"
_WRAP = "font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#333333"


def construir_html_alumno(nombre_alumno: str, filas: list[dict]) -> str:
    """Tabla HTML inline (Comisión / Materia / Actividad) para el cuerpo del email del alumno.

    filas: [{"comision", "materia", "actividad"}] — 'actividad' ya formateada (texto).
    Sin filas → mensaje "estás al día" (no debería ocurrir: el caller filtra, T6).
    """
    nombre = _escape(nombre_alumno or "")
    if not filas:
        return (
            f'<div style="{_WRAP}">'
            f"<p>Hola {nombre},</p>"
            "<p>¡Estás al día! No registramos actividades pendientes. 🎉</p>"
            "</div>"
        )

    filas_html = "".join(
        "<tr>"
        f'<td style="{_TD}">{_escape(f.get("comision") or "—")}</td>'
        f'<td style="{_TD}">{_escape(f.get("materia") or "—")}</td>'
        f'<td style="{_TD}">{_escape(f.get("corte") or "—")}</td>'
        f'<td style="{_TD}">{_escape(f.get("actividad") or "—")}</td>'
        f'<td style="{_TD}">{_escape(f.get("examenes") or "—")}</td>'
        "</tr>"
        for f in filas
    )
    generado = fmt_fecha_ar(ahora_ar())
    return (
        f'<div style="{_WRAP}">'
        f"<p>Hola {nombre},</p>"
        "<p>Este es tu resumen de actividades pendientes y de tus exámenes. La columna "
        "<strong>Hasta</strong> indica hasta qué unidad/semana se evalúa cada materia. Te "
        "recomendamos completar lo pendiente para no atrasarte:</p>"
        '<table style="border-collapse:collapse;width:100%;max-width:760px">'
        "<thead><tr>"
        f'<th style="{_TH}">Comisión</th>'
        f'<th style="{_TH}">Materia</th>'
        f'<th style="{_TH}">Hasta</th>'
        f'<th style="{_TH}">Actividad</th>'
        f'<th style="{_TH}">Exámenes</th>'
        "</tr></thead>"
        f"<tbody>{filas_html}</tbody>"
        "</table>"
        f'<p style="color:#999999;font-size:11px;margin-top:10px">Documento generado el {generado}</p>'
        '<p style="color:#666666;font-size:12px;margin-top:14px">'
        "Ante cualquier duda, escribile a tu tutor. ¡Éxitos! 💪</p>"
        "</div>"
    )
