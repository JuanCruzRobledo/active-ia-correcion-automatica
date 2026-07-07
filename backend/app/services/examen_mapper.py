# app/services/examen_mapper.py
"""
Lógica PURA del seguimiento de exámenes (parciales/recuperatorios/extensiones/
extraordinarias/globales) — gemela conceptual de avance_mapper, pero para evaluaciones
sumativas (aprobó/desaprobó/ausente), NO para el avance de contenido.

Sin I/O: opera sobre las notas YA descargadas por el snapshot (el export del calificador
trae TODAS las notas, así que los exámenes no cuestan requests extra a Moodle).

Reglas:
  - interpretar_resultado: escala "Aprobado/Desaprobado" o nota NUMÉRICA con umbral.
    Sin nota → "ausente" (no "desaprobado": no rendir ≠ reprobar).
  - RESCATE: un PARCIAL queda aprobado si lo aprobó O si aprobó alguno de sus
    recuperatorios/extensiones/extraordinarias (los que lo apuntan con recupera_examen_id).
    Precedencia: aprobado > desaprobado > ausente.
  - Solo PARCIAL y GLOBAL son "principales" (filas del reporte); los que rescatan se
    pliegan dentro de su parcial.

Config de examen (lo arma el service desde ExamenMateria):
  {"id", "tipo", "moodle_cmid", "modo_aprobacion", "nota_minima", "recupera_examen_id", "orden"}
"""

# Tipos que se muestran como fila principal en el reporte.
TIPOS_PRINCIPALES = ("PARCIAL", "GLOBAL")
# Precedencia para combinar el parcial con sus rescates (mayor gana). 'sin_corregir'
# (entregado, esperando nota) pisa a desaprobado: el rescate todavía puede aprobar, así
# que el alumno está PENDIENTE, no reprobado. aprobado > sin_corregir > desaprobado > ausente.
_PRECEDENCIA = {"ausente": 0, "desaprobado": 1, "sin_corregir": 2, "aprobado": 3}
# Etiqueta visible por tipo (se concatena con el número derivado: "Parcial 2").
ETIQUETA_TIPO = {
    "PARCIAL": "Parcial",
    "RECUPERATORIO": "Recuperatorio",
    "EXTENSION": "Extensión",
    "EXTRAORDINARIA": "Extraordinaria",
    "GLOBAL": "Global",
}


def etiqueta_examen(tipo: str, numero: int) -> str:
    """'Parcial 2' a partir del tipo y el número derivado."""
    return f"{ETIQUETA_TIPO.get(tipo, tipo)} {numero}"


def parsear_nota_numerica(texto: str | None) -> float | None:
    """Nota numérica de Moodle (es-AR, coma decimal) → float, o None si no hay/parsea.

    "7,00" → 7.0 · "7.5" → 7.5 · "10" → 10.0 · "" / "-" / "abc" / None → None.
    """
    t = (texto or "").strip()
    if not t or t == "-":
        return None
    try:
        return float(t.replace(",", "."))
    except ValueError:
        return None


def interpretar_resultado(
    nota: str | None, modo: str, nota_minima: float | None
) -> str:
    """Nota de un examen → 'aprobado' | 'desaprobado' | 'ausente'.

    - modo ESCALA: "Desaprobado" → desaprobado; vacío/"-" → ausente; otra cosa → aprobado.
    - modo NUMERICO: parsea la nota; sin nota → ausente; nota >= nota_minima → aprobado.
    """
    if modo == "NUMERICO":
        valor = parsear_nota_numerica(nota)
        if valor is None:
            return "ausente"
        minimo = nota_minima if nota_minima is not None else 0.0
        return "aprobado" if valor >= minimo else "desaprobado"
    # ESCALA (default).
    t = (nota or "").strip().lower()
    if not t or t == "-":
        return "ausente"
    if "desaprob" in t:  # chequear antes que "aprob"
        return "desaprobado"
    return "aprobado"


def clasificar_grade_estructural(entry: dict | None) -> str:
    """Grade estructural de un assign (mod_assign_get_grades) → 'calificado' | 'sin_corregir'
    | 'ausente'. NO decide aprobado/desaprobado: eso lo resuelve el texto cuando 'calificado'.

    entry: {'timemodified': int, 'grade': str|None} del grade más reciente, o None si el
    alumno no tiene registro (no entregó). Moodle crea el registro al ENTREGAR con
    grade=-1 (placeholder) hasta que alguien corrige; grade>=0 = nota puesta. Esta señal
    es la única que distingue 'entregó pero falta corregir' de 'no entregó' — el texto del
    calificador muestra '-' en ambos casos.
    """
    if not entry:
        return "ausente"
    grade = entry.get("grade")
    try:
        valor = float(grade)
    except (TypeError, ValueError):
        valor = None
    if valor is not None and valor >= 0:
        return "calificado"  # hay nota real → el texto la interpreta (NUMERICO o ESCALA)
    # grade -1 / None: existe registro. Si entregó (timemodified>0) está sin corregir.
    return "sin_corregir" if (entry.get("timemodified") or 0) > 0 else "ausente"


def _mejor(*resultados: str) -> str:
    """Combina resultados por precedencia aprobado > desaprobado > sin_corregir > ausente."""
    return max(resultados, key=lambda r: _PRECEDENCIA.get(r, 0))


def _valor_numerico(ex: dict, notas_uid: dict[int, str]) -> float | None:
    """Nota numérica de un examen (base o rescate), o None si el examen es modo ESCALA o
    no tiene nota parseable. Sólo tiene sentido en modo NUMERICO (ESCALA no tiene escala
    numérica: el cierre lo evalúa por `resultado`, no por `valor_real`)."""
    if ex.get("modo_aprobacion") != "NUMERICO":
        return None
    return parsear_nota_numerica(notas_uid.get(ex.get("moodle_cmid")))


def _mejor_valor_real(*valores: float | None) -> float | None:
    """Mejor (mayor) valor numérico entre varios, ignorando los None. None si todos None."""
    numericos = [v for v in valores if v is not None]
    return max(numericos) if numericos else None


def numeros_por_tipo(examenes: list[dict]) -> dict[int, int]:
    """{examen_id: número visible} derivado del orden entre exámenes del mismo tipo."""
    numeros: dict[int, int] = {}
    por_tipo: dict[str, list[dict]] = {}
    for ex in examenes:
        por_tipo.setdefault(ex.get("tipo"), []).append(ex)
    for grupo in por_tipo.values():
        for i, ex in enumerate(
            sorted(grupo, key=lambda e: (e.get("orden") or 0, e.get("id") or 0)), 1
        ):
            numeros[ex["id"]] = i
    return numeros


# Jerarquía del "corte": Global manda sobre los parciales; entre el mismo tipo, mayor número.
_PRIORIDAD_CORTE = {"PARCIAL": 1, "GLOBAL": 2}


def examen_corte(examenes: list[dict] | None) -> str | None:
    """Etiqueta del examen MÁS ALTO (corte): Global > Parcial de mayor número.

    examenes: [{"id", "tipo", "orden"}] (tal como vienen del modelo ExamenMateria; el
    número/etiqueta se derivan). Recuperatorios/extensiones no son corte. None si no hay
    parciales ni globales.
    """
    principales = [e for e in (examenes or []) if e.get("tipo") in _PRIORIDAD_CORTE]
    if not principales:
        return None
    numeros = numeros_por_tipo(examenes or [])
    top = max(
        principales,
        key=lambda e: (_PRIORIDAD_CORTE[e["tipo"]], numeros.get(e.get("id"), 1)),
    )
    return etiqueta_examen(top["tipo"], numeros.get(top.get("id"), 1))


def calcular_resultados_examenes(
    notas_uid: dict[int, str],
    examenes_config: list[dict],
    estructural_uid: dict[int, dict | None] | None = None,
) -> list[dict]:
    """Resultados de los exámenes PRINCIPALES de un alumno, con rescate aplicado.

    notas_uid: {cmid: gradeformatted} del alumno (subset del export del calificador).
    estructural_uid: {cmid: entry} del grade estructural (mod_assign_get_grades), SOLO para
    los exámenes cuya fuente es Tarea (assign). La PRESENCIA de la clave cmid marca "usar
    fuente estructural": detecta 'sin_corregir' (entregó, grade=-1) y 'ausente' (sin
    registro), que el texto no distingue; cuando hay nota real, se interpreta el texto
    (sirve para NUMERICO y ESCALA). Los exámenes sin clave (quiz/sin fuente) usan el texto.
    Devuelve [{examen_id, tipo, numero, etiqueta, resultado, rescatado, valor_real,
    modo_aprobacion, nota_minima}] para cada PARCIAL/GLOBAL. `valor_real` es el mejor valor
    NUMÉRICO (mayor) entre la instancia base y sus rescates —vía `parsear_nota_numerica`
    sobre `notas_uid`—, o `None` si el principal está en modo ESCALA o no tiene nota
    numérica parseable. `modo_aprobacion`/`nota_minima` son los del examen principal (los
    consume el service para armar la entrada de `calcular_estado_cierre`).
    """
    numeros = numeros_por_tipo(examenes_config)
    estructural = estructural_uid or {}

    def por_texto(ex: dict) -> str:
        return interpretar_resultado(
            notas_uid.get(ex.get("moodle_cmid")),
            ex.get("modo_aprobacion"),
            ex.get("nota_minima"),
        )

    def resultado_de(ex: dict) -> str:
        cmid = ex.get("moodle_cmid")
        if cmid in estructural:  # fuente estructural (assign)
            estado = clasificar_grade_estructural(estructural[cmid])
            return por_texto(ex) if estado == "calificado" else estado
        return por_texto(ex)  # quiz / sin fuente estructural

    # Recuperatorios/extensiones/extraordinarias agrupados por el parcial que rescatan.
    rescates: dict[int, list[dict]] = {}
    for ex in examenes_config:
        rid = ex.get("recupera_examen_id")
        if rid is not None:
            rescates.setdefault(rid, []).append(ex)

    out: list[dict] = []
    for ex in examenes_config:
        if ex.get("tipo") not in TIPOS_PRINCIPALES:
            continue
        base = resultado_de(ex)
        recs_ex = rescates.get(ex["id"], [])
        recs = [resultado_de(r) for r in recs_ex]
        efectivo = _mejor(base, *recs) if recs else base
        rescatado = base != "aprobado" and efectivo == "aprobado"
        numero = numeros.get(ex["id"])
        valor_real = _mejor_valor_real(
            _valor_numerico(ex, notas_uid),
            *[_valor_numerico(r, notas_uid) for r in recs_ex],
        )
        out.append(
            {
                "examen_id": ex["id"],
                "tipo": ex.get("tipo"),
                "numero": numero,
                "etiqueta": etiqueta_examen(ex.get("tipo"), numero),
                "resultado": efectivo,
                "rescatado": rescatado,
                "valor_real": valor_real,
                "modo_aprobacion": ex.get("modo_aprobacion"),
                "nota_minima": ex.get("nota_minima"),
            }
        )
    return out
