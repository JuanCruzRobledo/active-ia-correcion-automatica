# app/services/avance_mapper.py
"""
Lógica PURA de mapeo unidad ↔ sección de Moodle (Dashboard de Gestores).

Funciones sin I/O, fáciles de testear. Son la base del cálculo de avance (T5)
y de la auto-detección de cabeceras del ABM (T4).

Modelo (validado en spike T0, §6.1 del plan):
- Una UNIDAD = sección cabecera "N- Tema" + sus secciones satélite siguientes.
- El bloque de la unidad se DERIVA por orden de `section#`: una actividad pertenece
  a la unidad de la cabecera con mayor `section#` <= el `section#` de su sección.
- Las actividades cuyo `section#` >= el tope (materia.moodle_section_fin_id) NO cuentan.
"""

import re

from app.models.enums import EstadoAvanceEnum

# Cabecera de unidad: el nombre empieza con un número o "Unidad N", seguido de
# separador. Cubre "1- Estructuras…", "Unidad 1: Teoría…", "Unidad 1 - …", "1. …".
# Es solo una SUGERENCIA para pre-tildar en el ABM; el admin confirma manualmente.
_CABECERA_RE = re.compile(r"^\s*(?:unidad\s+)?(\d+)\s*[-:.]", re.IGNORECASE)

# Estados de completion de Moodle que cuentan como "actividad realizada" para el avance:
# 1 = completa, 2 = completa-aprobada, 3 = completa-reprobada. Lo que importa es que el
# alumno REALIZÓ la actividad (incluso desaprobada). (0 = incompleta NO cuenta.)
ESTADOS_COMPLETADOS = {1, 2, 3}
# state 3 = completa pero REPROBADA → se marca aparte para mostrarla como "desaprobada".
ESTADO_REPROBADA = 3


def detectar_cabeceras(secciones: list[dict]) -> list[dict]:
    """Detecta las secciones cabecera de unidad por el patrón 'N- Tema'.

    Args:
        secciones: lista de secciones de core_course_get_contents
                   (cada una con 'id', 'section', 'name').

    Returns:
        Lista de sugerencias [{numero, moodle_section_id, section, nombre}],
        ordenada por numero de unidad.
    """
    out: list[dict] = []
    for sec in secciones:
        nombre = (sec.get("name") or "").strip()
        m = _CABECERA_RE.match(nombre)
        if not m:
            continue
        out.append(
            {
                "numero": int(m.group(1)),
                "moodle_section_id": sec.get("id"),
                "section": sec.get("section"),
                "nombre": nombre,
            }
        )
    out.sort(key=lambda c: c["numero"])
    return out


def section_num_de_cmid(secciones: list[dict]) -> dict[int, int]:
    """Mapa cmid → section# de la sección que contiene cada módulo."""
    mapa: dict[int, int] = {}
    for sec in secciones:
        section_num = sec.get("section")
        for modulo in sec.get("modules", []):
            cmid = modulo.get("id")
            if cmid is not None:
                mapa[cmid] = section_num
    return mapa


def section_id_a_num(secciones: list[dict]) -> dict[int, int]:
    """Mapa section_id → section# (orden visual)."""
    return {
        sec.get("id"): sec.get("section")
        for sec in secciones
        if sec.get("id") is not None
    }


def unidad_de_section_num(
    section_num: int | None,
    cabeceras: list[tuple[int, int]],
    *,
    tope_section_num: int | None = None,
) -> int | None:
    """Devuelve el número de unidad al que pertenece una sección.

    Args:
        section_num: el `section#` de la sección de la actividad.
        cabeceras: lista de (numero_unidad, section#_de_la_cabecera).
        tope_section_num: section# a partir del cual (inclusive) las secciones
                          NO cuentan (parciales/integrador). None = sin tope.

    Returns:
        El numero de la unidad de la cabecera con mayor section# <= section_num,
        o None si está antes de la primera cabecera o en/después del tope.
    """
    if section_num is None:
        return None
    if tope_section_num is not None and section_num >= tope_section_num:
        return None

    mejor_numero: int | None = None
    mejor_section = -1
    for numero, cab_section in cabeceras:
        if cab_section <= section_num and cab_section > mejor_section:
            mejor_section = cab_section
            mejor_numero = numero
    return mejor_numero


def nombre_por_cmid(secciones: list[dict]) -> dict[int, str]:
    """Mapa cmid → nombre del módulo."""
    mapa: dict[int, str] = {}
    for sec in secciones:
        for modulo in sec.get("modules", []):
            cmid = modulo.get("id")
            if cmid is not None:
                mapa[cmid] = (modulo.get("name") or "").strip()
    return mapa


def unidad_alcanzada(
    completion_statuses: list[dict],
    section_num_por_cmid: dict[int, int],
    cabeceras: list[tuple[int, int]],
    tope_section_num: int | None = None,
) -> int | None:
    """Unidad MÁS ALTA completada por un alumno (su punto más avanzado).

    Args:
        completion_statuses: statuses de core_completion (cada uno con cmid, state).
        section_num_por_cmid: mapa cmid → section# (de section_num_de_cmid).
        cabeceras: list de (numero_unidad, section#_de_la_cabecera).
        tope_section_num: section# tope (las actividades >= tope no cuentan).

    Returns:
        El máximo numero de unidad entre las actividades con state ∈ {1,2}, o None.
    """
    mejor: int | None = None
    for st in completion_statuses:
        if st.get("state") not in ESTADOS_COMPLETADOS:
            continue
        section_num = section_num_por_cmid.get(st.get("cmid"))
        u = unidad_de_section_num(section_num, cabeceras, tope_section_num=tope_section_num)
        if u is not None and (mejor is None or u > mejor):
            mejor = u
    return mejor


def clasificar_estado(
    unidad_alcanzada_val: int | None, unidad_actual: int
) -> EstadoAvanceEnum:
    """Clasifica el estado de avance comparando la unidad alcanzada vs la actual.

    delta = unidad_actual − unidad_alcanzada: <=0 AL_DIA · 1 RIESGO_MEDIO · >=2 RIESGO_ALTO.
    Sin actividad (alcanzada None) → SIN_ACTIVIDAD.
    """
    if unidad_alcanzada_val is None:
        return EstadoAvanceEnum.SIN_ACTIVIDAD
    delta = unidad_actual - unidad_alcanzada_val
    if delta <= 0:
        return EstadoAvanceEnum.AL_DIA
    if delta == 1:
        return EstadoAvanceEnum.RIESGO_MEDIO
    return EstadoAvanceEnum.RIESGO_ALTO


def calcular_avance_alumno(
    completion_statuses: list[dict],
    secciones: list[dict],
    cabeceras_section_ids: list[tuple[int, int]],
    *,
    unidad_actual: int,
    tope_section_id: int | None = None,
) -> dict:
    """Calcula el avance de UN alumno a partir de su completion y la config del curso.

    Args:
        completion_statuses: statuses de core_completion del alumno.
        secciones: contents del curso (core_course_get_contents).
        cabeceras_section_ids: list de (numero_unidad, moodle_section_id de la cabecera),
                               derivada de las Unidades CONFIGURADAS de la materia.
        unidad_actual: materia.unidad_actual.
        tope_section_id: materia.moodle_section_fin_id (section_id del tope) o None.

    Returns:
        dict {unidad_alcanzada, actividad_actual_nombre, actividad_actual_unidad, estado}.
    """
    sec_id_num = section_id_a_num(secciones)
    section_num_por_cmid = section_num_de_cmid(secciones)
    nombres = nombre_por_cmid(secciones)

    # cabeceras (numero, section#) — descartar las que no estén en el curso actual
    cabeceras = [
        (numero, sec_id_num[sid])
        for numero, sid in cabeceras_section_ids
        if sid in sec_id_num
    ]
    tope_section_num = (
        sec_id_num.get(tope_section_id) if tope_section_id is not None else None
    )

    alcanzada = unidad_alcanzada(
        completion_statuses, section_num_por_cmid, cabeceras, tope_section_num
    )
    estado = clasificar_estado(alcanzada, unidad_actual)

    # Actividad actual: la realizada de mayor timecompleted DENTRO de la unidad alcanzada.
    actividad_nombre: str | None = None
    actividad_desaprobada = False
    if alcanzada is not None:
        mejor_tc = -1
        for st in completion_statuses:
            if st.get("state") not in ESTADOS_COMPLETADOS:
                continue
            section_num = section_num_por_cmid.get(st.get("cmid"))
            u = unidad_de_section_num(section_num, cabeceras, tope_section_num=tope_section_num)
            if u != alcanzada:
                continue
            tc = st.get("timecompleted") or 0
            if tc >= mejor_tc:
                mejor_tc = tc
                actividad_nombre = nombres.get(st.get("cmid"))
                actividad_desaprobada = st.get("state") == ESTADO_REPROBADA

    return {
        "unidad_alcanzada": alcanzada,
        "actividad_actual_nombre": actividad_nombre,
        "actividad_actual_unidad": alcanzada,
        "actividad_actual_desaprobada": actividad_desaprobada,
        "estado": estado,
    }
