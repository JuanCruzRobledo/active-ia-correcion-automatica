# app/services/notificacion_agg.py
"""
Agregación PURA de destinatarios de notificaciones (PLAN_NOTIFICACIONES_EMAIL.md §5.2).

Recibe los AvanceAlumno de los últimos snapshots (ya cargados por el repo) y arma
los destinatarios de cada tipo. Sin I/O → fácil de testear. Reglas:
- Solo se reporta lo que FALTA (formatear_faltantes != "").
- Se omiten destinatarios sin email.
- Alumno: agrupado por moodle_user_id, una fila por materia con faltantes.
- Tutor académico: matchea sus comisiones por `comision == moodle_group_code`.
- Tutor nexo: matchea por `regional`.

Estructuras de entrada:
- avances_por_materia: list[{"materia_id": int, "materia": str, "etiqueta": str,
   "alumnos": [AvanceAlumno-like]}]  ("etiqueta" = "Unidad"|"Semana", default "Unidad";
   cada alumno expone: moodle_user_id, nombre, apellido, email, comision, regional,
   actividades_faltantes).
- tutores: list[{"email", "nombre", "comisiones": [{"materia_id","materia","grupo_code"}]}]
- nexos: list[{"email", "nombre", "regional"}]
"""

import re

from app.services.notificacion_render import (
    examen_para_atender,
    formatear_examenes,
    formatear_faltantes,
    label_resultado_examen,
    tiene_examen_desaprobado,
)

# Número de comisión al final del texto: "M26 C1-09" → 9, "COMI-9" → 9, "COMI -7" → 7.
# Necesario porque el moodle_group_code de Comisión está mal cargado ("m26"); el matching
# tutor↔alumno se hace por (materia_id, número de comisión). Ver T6/QA.
_NUM_RE = re.compile(r"(\d+)\s*$")


def numero_comision(texto: str | None) -> int | None:
    """Extrae el número de comisión del final del texto. None si no hay."""
    if not texto:
        return None
    m = _NUM_RE.search(texto)
    return int(m.group(1)) if m else None


def construir_destinatarios_alumnos(avances_por_materia: list[dict]) -> list[dict]:
    """Un destinatario por alumno (con email) que tenga faltantes en ≥1 materia.

    Returns: [{"moodle_user_id", "email", "nombre",
               "filas": [{"comision","materia","actividad","examenes"}]}]
    Se incluye una fila si el alumno tiene faltantes O reprobó algún examen en esa materia.
    """
    por_alumno: dict[int, dict] = {}
    for mat in avances_por_materia:
        materia_nombre = mat.get("materia") or ""
        etiqueta = mat.get("etiqueta") or "Unidad"
        ua = mat.get("unidad_actual")
        corte = f"{etiqueta} {ua}" if ua is not None else "—"
        for a in mat.get("alumnos", []):
            actividad = formatear_faltantes(getattr(a, "actividades_faltantes", None), etiqueta)
            resultados = getattr(a, "resultados_examenes", None)
            examenes = formatear_examenes(resultados)
            # Reportable si le falta algo O reprobó un examen (no por ausente: ver helper).
            if not actividad and not tiene_examen_desaprobado(resultados):
                continue
            uid = a.moodle_user_id
            d = por_alumno.get(uid)
            if d is None:
                d = por_alumno[uid] = {
                    "moodle_user_id": uid,
                    "email": a.email,
                    "nombre": a.nombre or "",
                    "filas": [],
                }
            d["filas"].append({
                "comision": a.comision or "—",
                "materia": materia_nombre,
                "actividad": actividad,
                "examenes": examenes,
                "corte": corte,
            })
    return [d for d in por_alumno.values() if d["email"] and d["filas"]]


def construir_destinatarios_tutores_academicos(
    tutores: list[dict],
    avances_por_materia: list[dict],
    comisiones_objetivo: set[tuple[int, int]] | None = None,
) -> list[dict]:
    """Un destinatario por tutor (con email) con alumnos faltantes en SUS comisiones.

    El matching alumno↔comisión es por (materia_id, número de comisión): el alumno
    "M26 C1-09" pertenece a la comisión "COMI-9" de su materia (el moodle_group_code
    está mal cargado y no sirve). Cada comisión del tutor trae {materia_id, materia,
    numero, nombre}.

    comisiones_objetivo: si se pasa, SOLO se incluyen las comisiones cuyo
    (materia_id, numero) esté en el set (modo prueba/QA). None = todas.

    El PDF tiene DOS partes por comisión:
    - faltantes: alumnos con actividades pendientes (texto agrupado por unidad).
    - exámenes: MATRIZ alumno × examen (una columna por parcial/global), SOLO con los
      alumnos que tienen algo para atender (desaprobado o ausente). El rescatado queda
      aprobado y no entra.

    Returns: [{"email","nombre",
               "materias": [{"materia","unidad_actual","etiqueta",
                 "comisiones": [{"comision",
                                 "faltantes": [{"apellido","nombre","detalle"}],
                                 "examenes_columnas": [str],
                                 "examenes_filas": [{"apellido","nombre","celdas":[str]}]}]}]}]
    """
    idx = {m["materia_id"]: m for m in avances_por_materia}
    out: list[dict] = []
    for t in tutores:
        if not t.get("email"):
            continue
        materias_dict: dict[str, dict] = {}
        for com in t.get("comisiones", []):
            materia_id = com.get("materia_id")
            numero = com.get("numero")
            if numero is None:
                continue
            if comisiones_objetivo is not None and (materia_id, numero) not in comisiones_objetivo:
                continue
            mat = idx.get(materia_id)
            if not mat:
                continue
            etiqueta = mat.get("etiqueta") or "Unidad"
            alumnos_com = [
                a for a in mat.get("alumnos", []) if numero_comision(a.comision) == numero
            ]

            # --- Parte 1: faltantes (solo alumnos con deudas) ---
            faltantes = []
            for a in alumnos_com:
                fmt = formatear_faltantes(getattr(a, "actividades_faltantes", None), etiqueta)
                if fmt:
                    faltantes.append(
                        {"apellido": a.apellido or "", "nombre": a.nombre or "", "detalle": fmt}
                    )

            # --- Parte 2: matriz de exámenes (todos comparten las mismas columnas) ---
            columnas: list[str] = []
            for a in alumnos_com:
                exs = (getattr(a, "resultados_examenes", None) or {}).get("examenes") or []
                if exs:
                    columnas = [e.get("etiqueta") for e in exs]
                    break
            examenes_filas = []
            for a in alumnos_com:
                resultados = getattr(a, "resultados_examenes", None)
                if not examen_para_atender(resultados):
                    continue  # solo desaprobados/ausentes
                por_etq = {e.get("etiqueta"): e for e in (resultados.get("examenes") or [])}
                examenes_filas.append({
                    "apellido": a.apellido or "",
                    "nombre": a.nombre or "",
                    "celdas": [label_resultado_examen(por_etq.get(c)) for c in columnas],
                })

            if not faltantes and not examenes_filas:
                continue
            nombre_mat = mat.get("materia") or com.get("materia") or ""
            nombre_comision = com.get("nombre") or f"Comisión {numero}"
            entry = materias_dict.setdefault(
                nombre_mat,
                {
                    "materia": nombre_mat,
                    "unidad_actual": mat.get("unidad_actual"),
                    "etiqueta": mat.get("etiqueta") or "Unidad",
                    "comisiones": [],
                },
            )
            entry["comisiones"].append({
                "comision": nombre_comision,
                "faltantes": faltantes,
                "examenes_columnas": columnas,
                "examenes_filas": examenes_filas,
            })
        materias = [m for m in materias_dict.values() if m["comisiones"]]
        if materias:
            out.append({"email": t["email"], "nombre": t.get("nombre") or "", "materias": materias})
    return out


def construir_destinatarios_tutores_nexo(
    nexos: list[dict], avances_por_materia: list[dict]
) -> list[dict]:
    """Un destinatario por tutor nexo (con email) con los alumnos faltantes de su regional.

    Returns: [{"email","nombre","regional",
               "materias": [{"materia","unidad_actual","etiqueta",
                             "filas": [{"comision","apellido","nombre","faltantes"}]}]}]
    `unidad_actual`/`etiqueta` dan al nexo el contexto de en qué unidad está la materia.
    """
    out: list[dict] = []
    for n in nexos:
        if not n.get("email"):
            continue
        regional = n.get("regional")
        materias: list[dict] = []
        for mat in avances_por_materia:
            etiqueta = mat.get("etiqueta") or "Unidad"
            filas = [
                {
                    "comision": a.comision or "—",
                    "apellido": a.apellido or "",
                    "nombre": a.nombre or "",
                    "faltantes": formatear_faltantes(getattr(a, "actividades_faltantes", None), etiqueta),
                }
                for a in mat.get("alumnos", [])
                if a.regional == regional
                and formatear_faltantes(getattr(a, "actividades_faltantes", None), etiqueta)
            ]
            if filas:
                materias.append({
                    "materia": mat.get("materia") or "",
                    "unidad_actual": mat.get("unidad_actual"),
                    "etiqueta": mat.get("etiqueta") or "Unidad",
                    "filas": filas,
                })
        if materias:
            out.append(
                {"email": n["email"], "nombre": n.get("nombre") or "", "regional": regional, "materias": materias}
            )
    return out
