# app/services/notificacion_render.py
"""
Render de los adjuntos/cuerpos de las notificaciones (PLAN_NOTIFICACIONES_EMAIL.md §5.1).

Funciones PURAS (reciben datos ya resueltos, devuelven str/bytes):
- formatear_faltantes: JSONB de deudas → texto legible.
- construir_excel_avance: Excel (openpyxl) con el formato de análisis por materia,
  agrupado por unidad/semana (tutor nexo) o por comisión (tutor académico).

El HTML del alumno se arma acá también, reutilizando formatear_faltantes.
"""

import io
import re

from app.core.fecha import ahora_ar, fmt_fecha_ar
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from app.services import excel_estilos as xl


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


# ===================== helpers de texto (escape HTML) =====================


def _escape(text: str) -> str:
    """Escapa &, <, > para no inyectar markup en el HTML del email."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ===================== helpers de Excel (compartidos) =====================

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


# ===================== Excel de avance (formato análisis por regional/materia) =====================
# El diseño (paleta, bordes, banding, barras) vive en excel_estilos (xl), compartido con
# el Excel del Dashboard de Gestores para que los tres reportes se vean idénticos.


def _nombre_alumno(a: dict) -> str:
    """'APELLIDO, NOMBRE' (como en el análisis de referencia)."""
    return f"{a.get('apellido', '')}, {a.get('nombre', '')}".strip(", ")


def _tipos_de_deudas(deudas: list[dict]) -> str:
    """Tipos de un conjunto de deudas (de UNA unidad) → 'TP, Autoevaluación, Quiz (desaprobado)'."""
    partes = []
    for d in deudas:
        tipo = _LABEL_DEUDA.get(d.get("tipo"), d.get("tipo") or "?")
        if d.get("estado") == "desaprobado":
            tipo += " (desaprobado)"
        partes.append(tipo)
    return ", ".join(partes)


def _agrupar_avance(alumnos: list[dict], por_unidad: bool) -> list[tuple]:
    """Agrupa los alumnos con deudas. Devuelve [(clave_raw, [alumnos])] ordenado.

    - por_unidad: clave = número de unidad; un alumno aparece en CADA unidad donde debe.
    - por comisión: clave = comisión; un alumno aparece una vez (con todas sus deudas).
    """
    grupos: dict = {}
    if por_unidad:
        for a in alumnos:
            for u in sorted({d.get("unidad") for d in a.get("deudas", []) if d.get("unidad") is not None}):
                grupos.setdefault(u, []).append(a)
    else:
        for a in alumnos:
            grupos.setdefault(a.get("comision") or "—", []).append(a)
    return sorted(grupos.items(), key=lambda kv: kv[0])


def _hoja_avance(wb: Workbook, mat: dict, usados: set[str], por_unidad: bool) -> None:
    """Arma la hoja de UNA materia con el formato de referencia (resumen + listado)."""
    etiqueta = mat.get("etiqueta") or "Unidad"
    nombre_mat = mat.get("materia") or "Materia"
    ws = wb.create_sheet(_safe_sheet_name(nombre_mat, usados))
    ncols = 3 if por_unidad else 2
    # Solo alumnos con al menos una deuda (los que están al día no se listan).
    alumnos = [a for a in mat.get("alumnos", []) if a.get("deudas")]
    grupos = _agrupar_avance(alumnos, por_unidad)

    # --- Título (R1, banda) + fecha de creación (R2) ---
    xl.banda_titulo(
        ws, nombre_mat, 4, subtitulo=f"Documento generado el {fmt_fecha_ar(ahora_ar())}"
    )

    # --- Resumen (R4 header, R5..) ---
    fila = 4
    xl.celda_header(ws, fila, 1, etiqueta if por_unidad else "Comisión")
    xl.celda_header(ws, fila, 2, "Alumnos que deben")
    fila += 1
    for i, (clave, miembros) in enumerate(grupos):
        clave_txt = f"{etiqueta} {clave}" if por_unidad else str(clave)
        xl.fila_datos(ws, fila, [clave_txt, len(miembros)], zebra=bool(i % 2), center_cols=(2,))
        fila += 1

    # --- Listado detallado ---
    fila += 1
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
    titulo = (
        f"LISTADO DE ALUMNOS POR {etiqueta.upper()} (por comisión y alfabético)"
        if por_unidad
        else "LISTADO DE ALUMNOS POR COMISIÓN (alfabético)"
    )
    ws.cell(fila, 1, titulo).font = xl.FONT_SECCION
    fila += 2

    for clave, miembros in grupos:
        plural = "alumno" if len(miembros) == 1 else "alumnos"
        encabezado = (
            f"{etiqueta} {clave}  ({len(miembros)} {plural})"
            if por_unidad
            else f"Comisión {clave}  ({len(miembros)} {plural})"
        )
        xl.barra_bloque(ws, fila, encabezado, ncols)
        fila += 1

        if por_unidad:
            xl.celda_header(ws, fila, 1, "Comisión")
            xl.celda_header(ws, fila, 2, "Alumno")
            xl.celda_header(ws, fila, 3, "Pendiente")
            fila += 1
            ordenados = sorted(
                miembros,
                key=lambda x: (x.get("comision") or "", x.get("apellido") or "", x.get("nombre") or ""),
            )
            for i, a in enumerate(ordenados):
                deudas_u = [d for d in a.get("deudas", []) if d.get("unidad") == clave]
                desaprob = any(d.get("estado") == "desaprobado" for d in deudas_u)
                xl.fila_datos(
                    ws, fila, [a.get("comision") or "—", _nombre_alumno(a), _tipos_de_deudas(deudas_u)],
                    zebra=bool(i % 2), center_cols=(1,), resaltar_col=3 if desaprob else None,
                )
                fila += 1
        else:
            xl.celda_header(ws, fila, 1, "Alumno")
            xl.celda_header(ws, fila, 2, "Pendiente")
            fila += 1
            ordenados = sorted(miembros, key=lambda x: (x.get("apellido") or "", x.get("nombre") or ""))
            for i, a in enumerate(ordenados):
                pendiente = formatear_faltantes({"deudas": a.get("deudas", [])}, etiqueta)
                desaprob = any(d.get("estado") == "desaprobado" for d in a.get("deudas", []))
                xl.fila_datos(
                    ws, fila, [_nombre_alumno(a), pendiente],
                    zebra=bool(i % 2), resaltar_col=2 if desaprob else None,
                )
                fila += 1
        fila += 1  # fila vacía entre bloques

    # Título visible al scrollear; anchos prolijos.
    ws.freeze_panes = "A3"
    anchos = (20, 40, 46, 3) if por_unidad else (40, 66, 3, 3)
    for i, ancho in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho


def construir_excel_avance(materias: list[dict], *, agrupar: str = "unidad") -> bytes:
    """Excel de avance con el formato del análisis por regional/materia (1 hoja por materia).

    materias: [{"materia": str, "etiqueta": str, "alumnos": [
        {"comision": str, "apellido": str, "nombre": str,
         "deudas": [{"unidad": int, "tipo": str, "estado": str}, ...]}]}]
    agrupar:
      - "unidad" (tutor nexo): resumen y listado por unidad/semana; columnas Comisión|Alumno|Pendiente.
        El Pendiente de cada bloque son las deudas de ESA unidad.
      - "comision" (tutor académico): resumen y listado por comisión; columnas Alumno|Pendiente.
        El Pendiente trae todas las unidades del alumno (formatear_faltantes).
    Solo se listan alumnos con ≥1 deuda. Respeta la etiqueta (Unidad/Semana) de la materia.
    """
    por_unidad = agrupar == "unidad"
    wb = Workbook()
    wb.remove(wb.active)
    usados: set[str] = set()
    if not materias:
        ws = wb.create_sheet(_safe_sheet_name("Sin datos", usados))
        ws["A1"] = "Sin alumnos con pendientes"
    for mat in materias:
        _hoja_avance(wb, mat, usados, por_unidad)
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
