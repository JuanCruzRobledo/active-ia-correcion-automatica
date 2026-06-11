# app/services/avance_mapper.py
"""
Lógica PURA de avance por unidad (Dashboard de Gestores + Notificaciones).

Modelo de UNIDAD (extensión §9.bis F, 2026-06-07): cada unidad tiene N componentes
evaluables DINÁMICOS configurados a mano en el ABM. Cada componente es:
  - tipo: etiqueta para el reporte (TP / QUIZ / AUTOEVALUACION / CIERRE).
  - cmid: la actividad de Moodle vinculada.
  - fuente: cómo se decide si está realizado — "SEGUIMIENTO" o "CALIFICACION".

La lógica depende de la FUENTE, no del tipo:
  - CALIFICACION (por nota, como el TP en E7): realizado/alcance si la nota es
    "aprobado" o "desaprobado" (entregó y se calificó). DEUDA "desaprobado" si la
    nota es desaprobada. Si NO hay nota todavía, se cruza con finalización: si Moodle
    marca la entrega como finalizada → el alumno entregó y el tutor aún no corrigió
    (cuenta para el alcance, NO es deuda); si no → "no entregado" (deuda).
  - SEGUIMIENTO (por completion de Moodle): realizado/alcance si state ∈ {1,2,3}.
    DEUDA ("pendiente") si state 0 o ausente.
  - unidad ALCANZADA = la más alta con ≥1 de sus componentes realizado.
  - Estado del alumno = delta unidad_actual − unidad_alcanzada (clasificar_estado).

Contrato del config (lo arma snapshot_service desde la tabla componentes_unidad):
  [{"numero": int, "componentes": [{"tipo": str, "cmid": int, "fuente": str}, ...]}]
La `fuente` viaja como string ("CALIFICACION"/"SEGUIMIENTO") para que este módulo sea puro.

Las funciones de cabeceras (detectar_cabeceras / unidad_de_section_num / …) ya NO se usan
para el cálculo (los cmids son explícitos); quedan para el ABM (auto-sugerencia / rango).
"""

import re

from app.models.enums import EstadoAvanceEnum

# Cabecera de unidad: "1- Tema", "Unidad 1: Tema", etc. (solo para el ABM).
_CABECERA_RE = re.compile(r"^\s*(?:unidad\s+)?(\d+)\s*[-:.]", re.IGNORECASE)

# Estados de completion de Moodle: el alumno "tocó" la actividad (cuenta para el avance).
ESTADOS_REALIZADOS = {1, 2, 3}
# Fuentes de verdad de un componente (deben coincidir con FuenteComponenteEnum).
FUENTE_CALIFICACION = "CALIFICACION"
FUENTE_SEGUIMIENTO = "SEGUIMIENTO"


# ===================== helpers de secciones (ABM) =====================


def detectar_cabeceras(secciones: list[dict]) -> list[dict]:
    """Detecta las secciones cabecera de unidad por el patrón 'N- Tema' (para el ABM)."""
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
    """Número de unidad de una sección (cabecera con mayor section# <= section_num). ABM."""
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


# ===================== cálculo de avance (3 componentes) =====================


def clasificar_estado(
    unidad_alcanzada_val: int | None, unidad_actual: int
) -> EstadoAvanceEnum:
    """delta = unidad_actual − unidad_alcanzada: <=0 AL_DIA · 1 RIESGO_MEDIO · >=2 RIESGO_ALTO.
    Sin unidad alcanzada (None) → SIN_ACTIVIDAD."""
    if unidad_alcanzada_val is None:
        return EstadoAvanceEnum.SIN_ACTIVIDAD
    delta = unidad_actual - unidad_alcanzada_val
    if delta <= 0:
        return EstadoAvanceEnum.AL_DIA
    if delta == 1:
        return EstadoAvanceEnum.RIESGO_MEDIO
    return EstadoAvanceEnum.RIESGO_ALTO


def _estado_por_cmid(completion_statuses: list[dict]) -> dict[int, int]:
    return {
        s.get("cmid"): s.get("state")
        for s in completion_statuses
        if s.get("cmid") is not None
    }


def estado_tp(nota_formateada: str | None) -> str:
    """Interpreta el texto de la calificación → 'aprobado' | 'desaprobado' | 'sin_nota'.

    Por CALIFICACIÓN (no por seguimiento), leyendo el gradereport de Moodle:
      - vacío o "-": sin calificar todavía → 'sin_nota'.
      - contiene "desaprob": 'desaprobado'.
      - cualquier otra nota presente (escala "Aprobado" O nota NUMÉRICA, ej. "7,00"):
        'aprobado'. Regla "tiene nota = realizado" (decisión §9.bis F): no distinguimos
        umbral en notas numéricas; basta con que haya nota.
    """
    t = (nota_formateada or "").strip().lower()
    if not t or t == "-":
        return "sin_nota"
    if "desaprob" in t:  # chequear primero: "desaprobado" contiene "aprob"
        return "desaprobado"
    return "aprobado"


def _evaluar_componente(
    comp: dict, estados: dict[int, int], notas_tp: dict[int, str]
) -> tuple[bool, str | None]:
    """Evalúa UN componente → (realizado, deuda_estado).

    - realizado: el alumno tocó el componente (cuenta para la unidad alcanzada).
    - deuda_estado: etiqueta de deuda ("desaprobado"|"no entregado"|"pendiente") o None.
    La regla depende de la `fuente` del componente, no de su tipo.
    """
    cmid = comp.get("cmid")
    if cmid is None:
        return False, None
    if comp.get("fuente") == FUENTE_CALIFICACION:
        est = estado_tp(notas_tp.get(cmid))
        if est == "aprobado":
            return True, None
        if est == "desaprobado":
            return True, "desaprobado"  # entregó y se calificó: cuenta y debe
        # Sin nota: el calificador NO distingue "no entregó" de "entregó y el tutor no
        # corrigió". Se cruza con finalización: si Moodle marca la entrega como finalizada,
        # el alumno SÍ entregó (pendiente de corrección) → cuenta para el alcance y NO es
        # deuda (no es culpa del alumno). Si no, asumimos que no entregó → deuda.
        if estados.get(cmid) in ESTADOS_REALIZADOS:
            return True, None
        return False, "no entregado"
    # SEGUIMIENTO (default): por completion de Moodle.
    if estados.get(cmid) in ESTADOS_REALIZADOS:
        return True, None
    return False, "pendiente"


def calcular_deudas_y_alcance(
    completion_statuses: list[dict],
    notas_tp: dict[int, str],
    unidades_config: list[dict],
    *,
    unidad_actual: int,
) -> tuple[int | None, list[dict]]:
    """Calcula (unidad_alcanzada, deudas) a partir de los componentes dinámicos por unidad.

    unidades_config: [{"numero", "componentes": [{"tipo", "cmid", "fuente"}, ...]}].
    deudas: [{"unidad", "tipo", "estado"}] de las unidades hasta unidad_actual.
    """
    estados = _estado_por_cmid(completion_statuses)
    alcanzada: int | None = None
    deudas: list[dict] = []

    for u in sorted(unidades_config, key=lambda x: x.get("numero") or 0):
        numero = u.get("numero")
        if numero is None:
            continue
        hechos = 0

        for comp in u.get("componentes", []):
            realizado, deuda = _evaluar_componente(comp, estados, notas_tp)
            if realizado:
                hechos += 1
            if deuda is not None and numero <= unidad_actual:
                deudas.append({"unidad": numero, "tipo": comp.get("tipo"), "estado": deuda})

        if hechos >= 1:
            alcanzada = numero  # recorrido ascendente → queda la máxima alcanzada

    return alcanzada, deudas


def calcular_actividades_faltantes(
    completion_statuses: list[dict],
    notas_tp: dict[int, str],
    unidades_config: list[dict],
    *,
    unidad_actual: int,
) -> dict | None:
    """Deudas del alumno hasta unidad_actual: {"deudas": [...]} o None si no debe nada."""
    _, deudas = calcular_deudas_y_alcance(
        completion_statuses, notas_tp, unidades_config, unidad_actual=unidad_actual
    )
    return {"deudas": deudas} if deudas else None


def calcular_avance_alumno(
    completion_statuses: list[dict],
    notas_tp: dict[int, str],
    unidades_config: list[dict],
    *,
    unidad_actual: int,
) -> dict:
    """Avance de UN alumno según los 3 componentes configurados por unidad.

    - TP por calificación (notas_tp: {cmid → texto}); autoeval/cierre por completion_statuses.
    Returns dict {unidad_alcanzada, actividad_actual_nombre, actividad_actual_unidad,
    actividad_actual_desaprobada, estado, actividades_faltantes}.
    """
    alcanzada, deudas = calcular_deudas_y_alcance(
        completion_statuses, notas_tp, unidades_config, unidad_actual=unidad_actual
    )
    estado = clasificar_estado(alcanzada, unidad_actual)

    # ¿Algún componente por CALIFICACIÓN de la unidad alcanzada quedó desaprobado?
    # (para la columna del dashboard).
    actividad_desaprobada = False
    if alcanzada is not None:
        cfg = next((u for u in unidades_config if u.get("numero") == alcanzada), None)
        for comp in (cfg or {}).get("componentes", []):
            if comp.get("fuente") == FUENTE_CALIFICACION and (
                estado_tp(notas_tp.get(comp.get("cmid"))) == "desaprobado"
            ):
                actividad_desaprobada = True
                break

    return {
        "unidad_alcanzada": alcanzada,
        "actividad_actual_nombre": f"Unidad {alcanzada}" if alcanzada is not None else None,
        "actividad_actual_unidad": alcanzada,
        "actividad_actual_desaprobada": actividad_desaprobada,
        "estado": estado,
        "actividades_faltantes": {"deudas": deudas} if deudas else None,
    }
