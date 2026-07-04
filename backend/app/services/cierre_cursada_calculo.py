# app/services/cierre_cursada_calculo.py
"""
Lógica PURA del cierre de cursada (PROMOCIONA / REGULARIZA / RECURSA) —
portada 1:1 desde el script de referencia validado de la skill
`informe-cierre-cursada` (generar_informe_cierre.py / reglas-cierre.md).

Sin I/O: opera sobre notas ya clasificadas y normalizadas a porcentaje del
máximo de cada ítem (el caller filtra las unidades marcadas "opcional" antes
de llamar a estas funciones — este módulo nunca ve una unidad opcional).

Árbol de decisión (por alumno):
  - autoeval_ok: TODAS las unidades no-opcionales dieron >= autoeval_min_pct
    (una sola por debajo ya rompe la condición, NO es un promedio).
  - tp_ok: % de TPs "Aprobado" >= umbral_tp_pct. "N/E" cuenta como NO
    aprobado, igual que "Desaprobado" — no es una categoría neutra.
  - p1_max/p2_max/tpi_max: nota más alta entre TODAS las instancias rendidas
    (entrega + recuperatorio + extraordinaria + extensión); None si ninguna.
  - Nota Final (0-10, entero) solo se calcula si PROMOCIONA; REGULARIZA/
    RECURSA la dejan en None ("N/E" en el reporte).
"""

import math
import re

CATEGORIA_TP = "TP"
CATEGORIA_AUTOEVAL = "AUTOEVAL"
CATEGORIA_PARCIAL_1 = "PARCIAL_1"
CATEGORIA_PARCIAL_2 = "PARCIAL_2"
CATEGORIA_TPI = "TPI"
CATEGORIA_IGNORAR = "IGNORAR"

# Unidades universalmente opcionales en las 3 materias de Programación —
# cualquier otra particularidad (ej. Unidad 1/2 de Prog I) es un toggle
# manual del coordinador, nunca hardcodeado acá: ya cambió una vez.
_UNIDADES_OPCIONALES_DEFAULT = {9, 10}

# Regex de sugerencia (ver references/moodle-export.md de la skill). Se
# evalúan en este orden porque "Cuestionario de Actividad N" (miniquiz,
# ignorar) y "Cuestionario de Autoevaluación... Unidad N" comparten el
# prefijo "Cuestionario de" pero son cosas distintas.
_RE_MINIQUIZ = re.compile(r"Cuestionario de Actividad\s*\d", re.IGNORECASE)
_RE_DIAGNOSTICO = re.compile(r"Antes de comenzar", re.IGNORECASE)
_RE_TP = re.compile(r"Actividad de cierre.*unidad\s*(\d+)", re.IGNORECASE)
_RE_AUTOEVAL = re.compile(
    r"(Cuestionario de )?Autoevaluaci[oó]n.*Unidad\s*(\d+)", re.IGNORECASE
)
_RE_PARCIAL_1 = re.compile(r"Primer(a)?\s+(Examen\s+)?Parcial", re.IGNORECASE)
_RE_PARCIAL_2 = re.compile(r"Segundo\s+(Examen\s+)?Parcial", re.IGNORECASE)
_RE_TPI = re.compile(r"Entrega.*Trabajo Integrador", re.IGNORECASE)


def round_half_up(x: float) -> int:
    """Redondeo estándar (no bankers' rounding) — 6.5 -> 7, no 6."""
    return math.floor(x + 0.5)


def max_o_none(valores: list[float | None] | None) -> float | None:
    """Nota más alta entre instancias rendidas, o None si ninguna se rindió."""
    limpios = [v for v in (valores or []) if v is not None]
    return max(limpios) if limpios else None


def tp_ok(tps: list[str], umbral_tp_pct: float) -> bool:
    """% de TPs "Aprobado" >= umbral. Sin TPs -> True (vacuamente cumplido).

    "N/E" (no entregado) cuenta como NO aprobado, igual que "Desaprobado".
    """
    if not tps:
        return True
    aprobados = sum(1 for t in tps if t == "Aprobado")
    return (aprobados / len(tps) * 100) >= umbral_tp_pct


def autoeval_ok(autoeval_pcts: list[float | None], minimo: float) -> bool:
    """TODAS las unidades no-opcionales >= minimo. Lista vacía -> False:
    sin ninguna unidad evaluable no se puede afirmar que el alumno cumplió.
    """
    return len(autoeval_pcts) > 0 and all(
        v is not None and v >= minimo for v in autoeval_pcts
    )


def calcular_estado(alumno: dict, reglas: dict, umbral_tp_pct: float) -> dict:
    """Veredicto de cierre de un alumno: PROMOCIONA / REGULARIZA / RECURSA.

    alumno: {"tps": [...], "autoeval_pcts": [...], "parcial1_pcts": [...],
             "parcial2_pcts": [...], "tpi_pcts": [...]} — ya normalizados a
    porcentaje del máximo de cada ítem, unidades opcionales ya excluidas.
    reglas: {"autoeval_min_pct", "parcial_promocion_min_pct",
             "parcial_regulariza_min_pct", "tpi_min_pct"}.
    """
    tp_cumple = tp_ok(alumno.get("tps", []), umbral_tp_pct)
    autoeval_cumple = autoeval_ok(alumno.get("autoeval_pcts", []), reglas["autoeval_min_pct"])

    p1_max = max_o_none(alumno.get("parcial1_pcts"))
    p2_max = max_o_none(alumno.get("parcial2_pcts"))
    tpi_max = max_o_none(alumno.get("tpi_pcts"))

    promociona = (
        autoeval_cumple
        and tp_cumple
        and p1_max is not None and p1_max >= reglas["parcial_promocion_min_pct"]
        and p2_max is not None and p2_max >= reglas["parcial_promocion_min_pct"]
        and tpi_max is not None and tpi_max >= reglas["tpi_min_pct"]
    )
    regulariza = (not promociona) and (
        autoeval_cumple
        and tp_cumple
        and p1_max is not None and p1_max >= reglas["parcial_regulariza_min_pct"]
        and p2_max is not None and p2_max >= reglas["parcial_regulariza_min_pct"]
    )

    if promociona:
        nf_cruda = ((p1_max + p2_max) / 2) * 0.4 + tpi_max * 0.6
        nota_final = round_half_up(nf_cruda / 10)
        habilitado_final = "No aplica (promocionó)"
        estado = "PROMOCIONA"
    elif regulariza:
        nota_final = None
        habilitado_final = (
            "Sí" if (tpi_max is not None and tpi_max >= reglas["tpi_min_pct"])
            else "No (falta aprobar TPI)"
        )
        estado = "REGULARIZA"
    else:
        nota_final = None
        habilitado_final = "No"
        estado = "RECURSA"

    return {
        "estado": estado,
        "nota_final": nota_final,
        "habilitado_final": habilitado_final,
        "tp_ok": tp_cumple,
        "autoeval_ok": autoeval_cumple,
        "p1_max": p1_max,
        "p2_max": p2_max,
        "tpi_max": tpi_max,
    }


def sugerir_categoria(nombre_moodle: str) -> dict:
    """Sugiere categoria/unidad/opcional para un ítem del calificador, por
    nombre — SOLO una sugerencia inicial para precargar la UI de mapeo; el
    coordinador siempre confirma antes de que se use para calcular (los
    nombres de ítem cambian de cohorte a cohorte, confiar en esto a ciegas
    rompería el cálculo en silencio).

    opcional se sugiere True SOLO para unidad 9/10 (regla universal a las 3
    materias) — cualquier otra particularidad queda para el toggle manual.
    """
    if _RE_MINIQUIZ.search(nombre_moodle) or _RE_DIAGNOSTICO.search(nombre_moodle):
        return {"categoria": CATEGORIA_IGNORAR, "unidad": None, "opcional": False}

    m = _RE_TP.search(nombre_moodle)
    if m:
        unidad = int(m.group(1))
        return {"categoria": CATEGORIA_TP, "unidad": unidad, "opcional": unidad in _UNIDADES_OPCIONALES_DEFAULT}

    m = _RE_AUTOEVAL.search(nombre_moodle)
    if m:
        unidad = int(m.group(2))
        return {"categoria": CATEGORIA_AUTOEVAL, "unidad": unidad, "opcional": unidad in _UNIDADES_OPCIONALES_DEFAULT}

    if _RE_PARCIAL_1.search(nombre_moodle):
        return {"categoria": CATEGORIA_PARCIAL_1, "unidad": None, "opcional": False}

    if _RE_PARCIAL_2.search(nombre_moodle):
        return {"categoria": CATEGORIA_PARCIAL_2, "unidad": None, "opcional": False}

    if _RE_TPI.search(nombre_moodle):
        return {"categoria": CATEGORIA_TPI, "unidad": None, "opcional": False}

    return {"categoria": CATEGORIA_IGNORAR, "unidad": None, "opcional": False}
