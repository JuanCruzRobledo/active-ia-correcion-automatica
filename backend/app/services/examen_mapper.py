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
# Precedencia para combinar el parcial con sus rescates (mayor gana).
_PRECEDENCIA = {"ausente": 0, "desaprobado": 1, "aprobado": 2}
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


def _mejor(*resultados: str) -> str:
    """Combina resultados por precedencia aprobado > desaprobado > ausente."""
    return max(resultados, key=lambda r: _PRECEDENCIA.get(r, 0))


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


def calcular_resultados_examenes(
    notas_uid: dict[int, str], examenes_config: list[dict]
) -> list[dict]:
    """Resultados de los exámenes PRINCIPALES de un alumno, con rescate aplicado.

    notas_uid: {cmid: gradeformatted} del alumno (subset del export del calificador).
    Devuelve [{examen_id, tipo, numero, resultado, rescatado}] para cada PARCIAL/GLOBAL.
    """
    numeros = numeros_por_tipo(examenes_config)

    def resultado_de(ex: dict) -> str:
        return interpretar_resultado(
            notas_uid.get(ex.get("moodle_cmid")),
            ex.get("modo_aprobacion"),
            ex.get("nota_minima"),
        )

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
        recs = [resultado_de(r) for r in rescates.get(ex["id"], [])]
        efectivo = _mejor(base, *recs) if recs else base
        rescatado = base != "aprobado" and efectivo == "aprobado"
        numero = numeros.get(ex["id"])
        out.append(
            {
                "examen_id": ex["id"],
                "tipo": ex.get("tipo"),
                "numero": numero,
                "etiqueta": etiqueta_examen(ex.get("tipo"), numero),
                "resultado": efectivo,
                "rescatado": rescatado,
            }
        )
    return out
