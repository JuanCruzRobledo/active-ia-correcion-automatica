# app/services/excel_cierre_cursada.py
"""
Genera el .xlsx de un cierre de cursada (CierreCursadaRun + CierreCursadaAlumno ya
calculados y persistidos — este módulo NO calcula nada, solo escribe lo que ya está en
la corrida).

Layout = modelo `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx` (ver diseño,
sección "Layout exacto del modelo CORREGIDO") + una columna `Nota Final` agregada al
final:
  R1: "TOTAL MATERIA {NOMBRE}" (merge A1:B1, mayúsculas)
  R2-R4: resumen PROMOCIONADOS/REGULARES/RECURSANTES con conteo (A=etiqueta, B=conteo)
  R5: vacía (separador)
  R6+: por comisión, barra "{comisión} — Tutor: {tutor}" (merge desde la columna C hasta
       la última) + encabezados + filas de alumnos.

Columnas dinámicas, derivadas de `run.examenes_snapshot` (config de exámenes congelada
en la corrida): `Nombre y Apellido | Email | Parcial n… | Global TPI | Estado Alumno |
Nota Final`. Sin columnas de TPs y sin gráfico de dona (a diferencia del sistema viejo).
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.services import excel_estilos
from app.services.excel_estilos import (
    CENTER,
    FILL_BLOQUE,
    FONT_BLOQUE,
    FONT_SECCION,
    banda_titulo,
    celda_header,
    fila_datos,
)
from app.utils.orden_natural import natural_key


def _fmt_valor(valor: float | int | None) -> str | float | int:
    """Valor numérico (`Parcial n` / `Global TPI`) o `N/E` si no hay nota."""
    return "N/E" if valor is None else valor


def _fmt_nota_final(valor: int | None) -> str | int:
    """Nota Final: celda en blanco (`""`) si no hay nota (alumno no promociona).
    Diverge a propósito de `_fmt_valor` (columnas de examen), que sigue devolviendo
    `"N/E"` ante `None` (preserva 3.10)."""
    return "" if valor is None else valor


def _parciales_y_global(
    examenes_snapshot: list[dict] | None,
) -> tuple[list[dict], dict | None]:
    """(parciales ordenados por orden/id, examen GLOBAL o None) desde la config congelada."""
    snapshot = examenes_snapshot or []
    parciales = sorted(
        (e for e in snapshot if e.get("tipo") == "PARCIAL"),
        key=lambda e: (e.get("orden") if e.get("orden") is not None else 0, e.get("id") or 0),
    )
    globales = [e for e in snapshot if e.get("tipo") == "GLOBAL"]
    return parciales, (globales[0] if globales else None)


def _headers(parciales: list[dict], global_examen: dict | None) -> list[str]:
    headers = ["Nombre y Apellido", "Email"]
    headers += [f"Parcial {i}" for i in range(1, len(parciales) + 1)]
    if global_examen is not None:
        headers.append("Global TPI")
    headers += ["Estado Alumno", "Nota Final"]
    return headers


def _valor_parcial(alumno: CierreCursadaAlumno, examen_id: int) -> float | None:
    """`valor_real` del examen `examen_id` en `alumno.resultados_examenes` (matcheo por id)."""
    for r in alumno.resultados_examenes or []:
        if r.get("examen_id") == examen_id:
            return r.get("valor_real")
    return None


def _barra_bloque_desde_c(ws, fila: int, texto: str, ncols: int) -> None:
    """Barra de bloque por comisión, igual a `excel_estilos.barra_bloque` pero mergeando
    desde la columna **C** (no desde A, a diferencia del helper estándar) hasta la última
    columna (`Nota Final`). Reutiliza los estilos de la casa (`FILL_BLOQUE`/`FONT_BLOQUE`);
    NO modifica la firma pública de `excel_estilos.barra_bloque` (la usan otros reportes).
    """
    ws.merge_cells(start_row=fila, start_column=3, end_row=fila, end_column=ncols)
    for col in range(3, ncols + 1):
        ws.cell(fila, col).fill = FILL_BLOQUE
    c = ws.cell(fila, 3, texto)
    c.font = FONT_BLOQUE
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[fila].height = 20


_SIN_COMISION = "Sin comisión asignada"


def _agrupar_por_comision(alumnos: list[CierreCursadaAlumno]) -> dict[str, list[CierreCursadaAlumno]]:
    """{titulo_bloque: [alumnos]} — un bloque por comisión (+ tutor), ORDENADO por el
    orden numérico natural de `comision_nombre` (alfabético si no hay sufijo numérico),
    con "Sin comisión asignada" siempre al final. El título compuesto ("{comisión} —
    Tutor: {tutor}") se conserva por bloque; el orden se calcula sobre el nombre de
    comisión subyacente, no sobre ese título compuesto.
    """
    grupos: dict[str, tuple[str, list[CierreCursadaAlumno]]] = {}
    for a in alumnos:
        nombre = a.comision_nombre or _SIN_COMISION
        titulo = f"{nombre} — Tutor: {a.tutor_nombre}" if a.tutor_nombre else nombre
        if nombre not in grupos:
            grupos[nombre] = (titulo, [])
        grupos[nombre][1].append(a)

    def _clave_orden(item: tuple[str, tuple[str, list[CierreCursadaAlumno]]]):
        nombre = item[0]
        if nombre == _SIN_COMISION:
            return (1, ())
        return (0, natural_key(nombre))

    return {
        titulo: alumnos_del_grupo
        for _, (titulo, alumnos_del_grupo) in sorted(grupos.items(), key=_clave_orden)
    }


def _escribir_resumen(ws, materia_nombre: str, run: CierreCursadaRun) -> None:
    """R1: título (merge A1:B1, mayúsculas). R2-R4: conteo PROMOCIONADOS/REGULARES/
    RECURSANTES en A:B. R5 queda vacía (separador antes del primer bloque)."""
    banda_titulo(ws, f"TOTAL MATERIA {materia_nombre.upper()}", ncols=2)

    resumen = [
        ("PROMOCIONADOS", run.total_promociona),
        ("REGULARES", run.total_regulariza),
        ("RECURSANTES", run.total_recursa),
    ]
    for fila, (etiqueta, conteo) in enumerate(resumen, start=2):
        ws.cell(fila, 1, etiqueta).font = FONT_SECCION
        celda_conteo = ws.cell(fila, 2, conteo)
        celda_conteo.alignment = CENTER


def _escribir_detalle(
    ws,
    alumnos: list[CierreCursadaAlumno],
    parciales: list[dict],
    global_examen: dict | None,
    headers: list[str],
    fila_inicio: int,
) -> int:
    """Escribe los bloques por comisión desde `fila_inicio`. Devuelve la última fila usada."""
    ncols = len(headers)
    col_estado = ncols - 1  # Estado Alumno: penúltima columna (Nota Final es la última).
    fila = fila_inicio
    for titulo, del_grupo in _agrupar_por_comision(alumnos).items():
        fila += 1
        _barra_bloque_desde_c(ws, fila, titulo, ncols)
        fila += 1
        for col, h in enumerate(headers, 1):
            celda_header(ws, fila, col, h)
        fila += 1
        for i, a in enumerate(sorted(del_grupo, key=lambda x: (x.apellido or "", x.nombre or ""))):
            estado = a.estado.value
            valores = [f"{a.apellido}, {a.nombre}".strip(", "), a.email]
            valores += [_fmt_valor(_valor_parcial(a, p["id"])) for p in parciales]
            if global_examen is not None:
                valores.append(_fmt_valor(a.global_valor))
            valores.append(estado)
            valores.append(_fmt_nota_final(a.nota_final))
            fila_datos(
                ws, fila, valores,
                zebra=(i % 2 == 1),
                resaltar_col=col_estado if estado == "RECURSA" else None,
                center_cols=tuple(range(3, ncols + 1)),
            )
            fila += 1
        fila += 1  # separador entre bloques
    return fila


def generar_excel_cierre(materia_nombre: str, run: CierreCursadaRun) -> tuple[bytes, str]:
    """(bytes, filename) del .xlsx de un cierre ya generado. `run.alumnos` debe venir cargado."""
    wb = Workbook()
    ws = wb.active
    ws.title = excel_estilos.sheet_title(materia_nombre, default="Cierre")

    parciales, global_examen = _parciales_y_global(run.examenes_snapshot)
    headers = _headers(parciales, global_examen)

    _escribir_resumen(ws, materia_nombre, run)
    _escribir_detalle(ws, run.alumnos, parciales, global_examen, headers, fila_inicio=5)

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 26 if col <= 2 else 16

    buffer = io.BytesIO()
    wb.save(buffer)
    fecha = datetime.utcnow().strftime("%Y%m%d")
    filename = excel_estilos.sanitize_filename(f"Cierre_{materia_nombre}_{fecha}.xlsx")
    return buffer.getvalue(), filename
