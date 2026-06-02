"""Parsers de los nombres de grupo de Moodle para la pantalla "Gestión".

Formatos reales (validados en el spike T0 contra el Moodle de la UTN):
  - Comisión: "M26 C1-09" / "A25 C2-01"  → {cohorte}{año} C{semestre}-{NN}
    El prefijo es la cohorte de ingreso: M = marzo, A = agosto.
  - Regional: "R-Mendoza"  → grupo con prefijo "R-"

El resto de los grupos (Grupo_NN, NO_RINDIO_*, Cohorte *, Z-*, "Requiere final *",
etc.) se ignora: no son ni regional ni comisión.

Funciones puras, sin dependencias: el filtrado/derivación se hace en GestionService.
"""

import re

# Fallbacks cuando el alumno no tiene un grupo del tipo esperado.
SIN_REGIONAL = "Sin regional"
SIN_COMISION = "—"

# Comisión completa: "M26 C1-09" / "A25 C2-01" (cohorte marzo=M o agosto=A).
# Se conserva el nombre tal cual (sin descomponer).
_COMISION_RE = re.compile(r"^[MA]\d+\s+C\d+-\d+$")
# Regional: "R-<nombre>". El nombre puede tener espacios y tildes ("R-Concepción del Uruguay").
_REGIONAL_RE = re.compile(r"^R-(.+)$")


def parse_comision(nombre: str) -> str | None:
    """Devuelve el nombre de comisión completo (ej. "M26 C1-09") si el grupo matchea
    el formato, o None si no es un grupo de comisión."""
    if not nombre:
        return None
    limpio = nombre.strip()
    return limpio if _COMISION_RE.match(limpio) else None


def parse_regional(nombre: str) -> str | None:
    """Devuelve el nombre de la regional SIN el prefijo "R-" (ej. "Mendoza"), o None
    si el grupo no es una regional."""
    if not nombre:
        return None
    m = _REGIONAL_RE.match(nombre.strip())
    return m.group(1).strip() if m else None


def resolver_grupos_alumno(grupos: list[str]) -> tuple[str, str]:
    """Dada la lista de nombres de grupo de un alumno, resuelve (regional, comisión).

    Toma el PRIMER grupo que matchea cada patrón e ignora el resto (grupos de trabajo,
    de estado, cohortes...). Si falta alguno, usa los fallbacks SIN_REGIONAL / SIN_COMISION.
    """
    regional = SIN_REGIONAL
    comision = SIN_COMISION
    regional_set = False
    comision_set = False

    for g in grupos:
        if not regional_set:
            r = parse_regional(g)
            if r is not None:
                regional = r
                regional_set = True
        if not comision_set:
            c = parse_comision(g)
            if c is not None:
                comision = c
                comision_set = True
        if regional_set and comision_set:
            break

    return regional, comision
