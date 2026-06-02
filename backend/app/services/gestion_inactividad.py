"""Bandas de inactividad para la pantalla "Gestión".

Modelo (definido con el usuario): bandas CERRADAS, NO acumulativas. Seleccionar
"1 mes" trae SOLO 30-59 días — no los de 2 meses ni los que nunca entraron.
"2 meses" es el ÚNICO catch-all (60 días o más, pero que SÍ entró alguna vez).
"Nunca" (lastcourseaccess == 0) es una categoría aparte que jamás se mezcla.

La inactividad se mide sobre `lastcourseaccess` (último acceso AL CURSO), que es
lo que usa el filtro de Participantes de Moodle. Funciones puras: `now` se pasa
explícito (no se lee el reloj acá).
"""

SECONDS_PER_DAY = 86_400

# Tipos especiales (no son bandas de días).
NUNCA = "nunca"
RANGO = "rango"

# Presets → banda [low, high) en días. high=None → catch-all (sin tope superior).
BANDAS: dict[str, tuple[int, int | None]] = {
    "1_dia": (1, 2),
    "2_dias": (2, 7),
    "1_semana": (7, 14),
    "2_semanas": (14, 21),
    "3_semanas": (21, 30),
    "1_mes": (30, 60),
    "2_meses": (60, None),  # catch-all
}

# Todos los valores de inactividad aceptados por la API.
TIPOS_VALIDOS = frozenset(BANDAS) | {NUNCA, RANGO}


def dias_inactividad(lastcourseaccess: int | None, now: int) -> int | None:
    """Días enteros desde el último acceso al curso. None si nunca entró
    (lastcourseaccess 0/None), que es un caso aparte de las bandas de días."""
    if not lastcourseaccess or lastcourseaccess <= 0:
        return None
    return (now - lastcourseaccess) // SECONDS_PER_DAY


def coincide_inactividad(
    lastcourseaccess: int | None,
    now: int,
    tipo: str,
    *,
    desde: int | None = None,
    hasta: int | None = None,
) -> bool:
    """¿El alumno cae en la banda de inactividad seleccionada?

    - `NUNCA`: sólo los que nunca entraron (lastcourseaccess == 0).
    - `RANGO`: días en [desde, hasta] inclusive (excluye a los que nunca entraron).
    - presets de `BANDAS`: días en [low, high); "2_meses" es catch-all (high=None).
      Los que nunca entraron NO caen en ninguna banda de días.
    """
    if tipo == NUNCA:
        return not lastcourseaccess or lastcourseaccess <= 0

    dias = dias_inactividad(lastcourseaccess, now)
    if dias is None:
        return False  # nunca entró → no pertenece a ninguna banda de días

    if tipo == RANGO:
        if desde is None or hasta is None:
            return False
        return desde <= dias <= hasta

    banda = BANDAS.get(tipo)
    if banda is None:
        return False
    low, high = banda
    return low <= dias and (high is None or dias < high)
