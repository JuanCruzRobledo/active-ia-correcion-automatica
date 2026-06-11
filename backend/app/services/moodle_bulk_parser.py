# app/services/moodle_bulk_parser.py
"""
Parsers PUROS de los dos CSV masivos de Moodle (refactor §R1/R2, 2026-06-08).

Reemplazan las llamadas per-alumno del snapshot (1+2N requests) por DOS descargas
masivas que se parsean en memoria:

  - Export del calificador  → {moodle_user_id: {cmid: gradeformatted}}  (= notas_tp)
  - CSV de finalización     → {moodle_user_id: [{cmid, state}]}         (= completion_statuses)

Ambos archivos keyean por NOMBRE de actividad (no por cmid). El puente nombre→cmid se
arma desde core_course_get_contents (construir_indice_nombre_cmid) y la fila→alumno por
email. Funciones PURAS (sin I/O) para testear sin tocar Moodle; el I/O vive en
moodle_service (sesión + descargas). Estructura validada en el spike R0.
"""

import csv
import io
import re

# Columnas fijas del export del calificador (antes de las columnas por item):
# Nombre, Apellido(s), Número de ID, Institución, Departamento, Dirección de correo.
_COLS_FIJAS_CALIF = 6
# Sufijos de tipo de visualización que el export agrega al header del item.
_SUFIJOS_DISPLAY = (" (real)", " (calculado)", " (porcentaje)", " (letra)")


def _norm(s: str | None) -> str:
    """Normaliza un nombre de actividad para el match: trim + colapsar espacios + casefold.

    Conserva acentos y emojis (son consistentes entre las salidas del propio Moodle).
    """
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def construir_indice_nombre_cmid(secciones: list[dict]) -> dict[str, int]:
    """{nombre_normalizado: cmid} a partir de core_course_get_contents.

    Si dos módulos comparten nombre, gana el último (ambiguo → se asume el más reciente).
    """
    idx: dict[str, int] = {}
    for sec in secciones:
        for modulo in sec.get("modules", []):
            cmid = modulo.get("id")
            nombre = _norm(modulo.get("name"))
            if cmid is not None and nombre:
                idx[nombre] = cmid
    return idx


def estado_finalizacion_a_state(texto: str | None) -> int:
    """Texto de finalización (Moodle es-AR) → state 0/1/2/3 (igual que el WS de completion).

    0 incompleta · 1 completa · 2 completa-aprobada · 3 completa-reprobada.
    Nota: el typo "califiación" es del propio Moodle; matcheamos por "ha alcanzado".
    """
    t = _norm(texto)
    if not t or "no finalizado" in t:
        return 0
    if "no ha alcanzado" in t:  # chequear antes que "ha alcanzado"
        return 3
    if "ha alcanzado" in t:
        return 2
    if "finalizado" in t:
        return 1
    return 0


def _limpiar_header_item_calif(header: str) -> list[str]:
    """Candidatos de nombre normalizado para una columna del export del calificador.

    El header viene como "<Tipo>:<Nombre> (Real)". Devuelve candidatos a probar contra
    el índice nombre→cmid: el nombre completo (sin sufijo display) y el nombre sin el
    prefijo de tipo (hasta el primer ':').
    """
    h = (header or "").strip()
    low = h.lower()
    for suf in _SUFIJOS_DISPLAY:
        if low.endswith(suf):
            h = h[: -len(suf)]
            break
    candidatos = [_norm(h)]
    if ":" in h:
        candidatos.append(_norm(h.split(":", 1)[1]))
    return [c for c in candidatos if c]


def _leer_filas(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


def parsear_export_calificador(
    csv_text: str,
    nombre_a_cmid: dict[str, int],
    email_a_uid: dict[str, int],
) -> dict[int, dict[int, str]]:
    """Export del calificador (TXT/comma) → {moodle_user_id: {cmid: gradeformatted}}.

    Las primeras 6 columnas son fijas (la 6ª, índice 5, es el email). De la 7ª en
    adelante, una columna por item con header "<Tipo>:<Nombre> (Real)". El valor (nota
    numérica o de escala "Aprobado"/"Desaprobado"/"-") se pasa tal cual (lo interpreta
    estado_tp). Items sin cmid conocido o alumnos sin email en el padrón se ignoran.
    """
    filas = _leer_filas(csv_text)
    if not filas:
        return {}
    header = filas[0]
    # Mapa columna→cmid para las columnas de item (índice >= 6).
    col_a_cmid: dict[int, int] = {}
    for i in range(_COLS_FIJAS_CALIF, len(header)):
        for cand in _limpiar_header_item_calif(header[i]):
            if cand in nombre_a_cmid:
                col_a_cmid[i] = nombre_a_cmid[cand]
                break

    out: dict[int, dict[int, str]] = {}
    for fila in filas[1:]:
        if len(fila) <= _COLS_FIJAS_CALIF:
            continue
        email = (fila[5] if len(fila) > 5 else "").strip().lower()
        uid = email_a_uid.get(email)
        if uid is None:
            continue
        notas: dict[int, str] = {}
        for col, cmid in col_a_cmid.items():
            if col < len(fila):
                notas[cmid] = fila[col].strip()
        out[uid] = notas
    return out


def parsear_csv_finalizacion(
    csv_text: str,
    nombre_a_cmid: dict[str, int],
    email_a_uid: dict[str, int],
) -> dict[int, list[dict]]:
    """CSV del reporte de finalización → {moodle_user_id: [{cmid, state}]}.

    Estructura: col0 = nombre, col1 = email, luego PARES [estado, fecha] por actividad
    (el header de la columna de fecha viene vacío → se saltea). El header de la columna
    de estado es el NOMBRE de la actividad → se mapea a cmid. Devuelve el mismo shape que
    consume avance_mapper (lista de {cmid, state}).
    """
    filas = _leer_filas(csv_text)
    if not filas:
        return {}
    header = filas[0]
    # Columnas de estado: índice >= 2 con header no vacío (las de fecha tienen header "").
    col_a_cmid: dict[int, int] = {}
    for i in range(2, len(header)):
        nombre = _norm(header[i])
        if nombre and nombre in nombre_a_cmid:
            col_a_cmid[i] = nombre_a_cmid[nombre]

    out: dict[int, list[dict]] = {}
    for fila in filas[1:]:
        if len(fila) < 2:
            continue
        email = fila[1].strip().lower()
        uid = email_a_uid.get(email)
        if uid is None:
            continue
        statuses: list[dict] = []
        for col, cmid in col_a_cmid.items():
            if col < len(fila):
                statuses.append({"cmid": cmid, "state": estado_finalizacion_a_state(fila[col])})
        out[uid] = statuses
    return out
