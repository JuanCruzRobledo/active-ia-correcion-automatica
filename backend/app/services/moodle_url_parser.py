# app/services/moodle_url_parser.py
"""
Parser/armador de URLs de entrega de Moodle (items #4 y #5).

#4 (corrección manual): de la URL que pega el tutor (la de calificar en Moodle)
   extraemos el cmid (param `id`) y el userid, para poblar entrega.moodle_user_id y
   habilitar "Subir a Moodle" en entregas cargadas a mano.
#5 (link a la entrega): armamos la URL de la submission del alumno para mostrarla
   cuando entregó sin archivos válidos.

Lógica PURA (sin I/O). Formato típico:
   https://<host>/mod/assign/view.php?id=<cmid>&userid=<userid>&action=grade
"""

from urllib.parse import parse_qs, urlparse

from app.models.enums import TipoActividadMoodleEnum


def _int_o_none(valores: list[str] | None) -> int | None:
    if not valores:
        return None
    try:
        return int(valores[0])
    except (TypeError, ValueError):
        return None


def parsear_url_entrega(url: str | None) -> dict[str, int | None]:
    """URL de Moodle → {'cmid': int|None, 'userid': int|None}.

    Tolera params extra, falta de params y valores no numéricos (→ None).
    """
    if not url or not isinstance(url, str):
        return {"cmid": None, "userid": None}
    try:
        query = parse_qs(urlparse(url).query)
    except (ValueError, TypeError):
        return {"cmid": None, "userid": None}
    return {
        "cmid": _int_o_none(query.get("id")),
        "userid": _int_o_none(query.get("userid")),
    }


def construir_url_entrega(host: str | None, cmid: int | None, userid: int | None) -> str | None:
    """(host, cmid, userid) → URL de la entrega del alumno en Moodle. None si falta algo."""
    if not host or cmid is None or userid is None:
        return None
    return f"{host.rstrip('/')}/mod/assign/view.php?id={cmid}&userid={userid}"


def construir_url_actividad(
    host: str | None,
    cmid: int | None,
    tipo_actividad: TipoActividadMoodleEnum | str | None,
) -> str | None:
    """(host, cmid, tipo_actividad) → URL de la actividad de Moodle según su tipo.

    Resuelve el recurso correcto por tipo de actividad:
    - `quiz`  → ``/mod/quiz/view.php?id={cmid}``
    - `assign`→ ``/mod/assign/view.php?id={cmid}``

    Acepta `tipo_actividad` como str ("quiz"/"assign") o como
    `TipoActividadMoodleEnum`. Cualquier valor distinto de `quiz` se resuelve
    como `assign` (comportamiento histórico por defecto). Devuelve None si falta
    el host o el cmid. Lógica PURA (sin I/O).
    """
    if not host or cmid is None:
        return None
    tipo = getattr(tipo_actividad, "value", tipo_actividad)
    modulo = "quiz" if tipo == TipoActividadMoodleEnum.QUIZ.value else "assign"
    return f"{host.rstrip('/')}/mod/{modulo}/view.php?id={cmid}"
