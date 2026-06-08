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
- avances_por_materia: list[{"materia_id": int, "materia": str, "alumnos": [AvanceAlumno-like]}]
  (cada alumno expone: moodle_user_id, nombre, apellido, email, comision, regional,
   actividades_faltantes).
- tutores: list[{"email", "nombre", "comisiones": [{"materia_id","materia","grupo_code"}]}]
- nexos: list[{"email", "nombre", "regional"}]
"""

import re

from app.services.notificacion_render import formatear_faltantes

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
               "filas": [{"comision","materia","actividad"}]}]
    """
    por_alumno: dict[int, dict] = {}
    for mat in avances_por_materia:
        materia_nombre = mat.get("materia") or ""
        for a in mat.get("alumnos", []):
            actividad = formatear_faltantes(getattr(a, "actividades_faltantes", None))
            if not actividad:
                continue  # no le falta nada en esta materia
            uid = a.moodle_user_id
            d = por_alumno.get(uid)
            if d is None:
                d = por_alumno[uid] = {
                    "moodle_user_id": uid,
                    "email": a.email,
                    "nombre": a.nombre or "",
                    "filas": [],
                }
            d["filas"].append(
                {"comision": a.comision or "—", "materia": materia_nombre, "actividad": actividad}
            )
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

    Returns: [{"email","nombre",
               "materias": [{"materia",
                             "comisiones": [{"comision",
                                             "alumnos": [{"apellido","nombre","faltantes"}]}]}]}]
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
            alumnos = [
                {
                    "apellido": a.apellido or "",
                    "nombre": a.nombre or "",
                    "faltantes": fmt,
                }
                for a in mat.get("alumnos", [])
                if numero_comision(a.comision) == numero
                and (fmt := formatear_faltantes(getattr(a, "actividades_faltantes", None)))
            ]
            if not alumnos:
                continue
            nombre_mat = mat.get("materia") or com.get("materia") or ""
            etiqueta = com.get("nombre") or f"Comisión {numero}"
            entry = materias_dict.setdefault(nombre_mat, {"materia": nombre_mat, "comisiones": []})
            entry["comisiones"].append({"comision": etiqueta, "alumnos": alumnos})
        materias = [m for m in materias_dict.values() if m["comisiones"]]
        if materias:
            out.append({"email": t["email"], "nombre": t.get("nombre") or "", "materias": materias})
    return out


def construir_destinatarios_tutores_nexo(
    nexos: list[dict], avances_por_materia: list[dict]
) -> list[dict]:
    """Un destinatario por tutor nexo (con email) con los alumnos faltantes de su regional.

    Returns: [{"email","nombre","regional",
               "materias": [{"materia",
                             "filas": [{"comision","apellido","nombre","faltantes"}]}]}]
    """
    out: list[dict] = []
    for n in nexos:
        if not n.get("email"):
            continue
        regional = n.get("regional")
        materias: list[dict] = []
        for mat in avances_por_materia:
            filas = [
                {
                    "comision": a.comision or "—",
                    "apellido": a.apellido or "",
                    "nombre": a.nombre or "",
                    "faltantes": formatear_faltantes(getattr(a, "actividades_faltantes", None)),
                }
                for a in mat.get("alumnos", [])
                if a.regional == regional
                and formatear_faltantes(getattr(a, "actividades_faltantes", None))
            ]
            if filas:
                materias.append({"materia": mat.get("materia") or "", "filas": filas})
        if materias:
            out.append(
                {"email": n["email"], "nombre": n.get("nombre") or "", "regional": regional, "materias": materias}
            )
    return out
