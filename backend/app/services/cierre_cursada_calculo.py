# app/services/cierre_cursada_calculo.py
"""
Lógica PURA del cierre de cursada (PROMOCIONA / REGULARIZA / RECURSA) —
dirigida por la configuración de exámenes de la materia (`ExamenMateria`),
fuente de verdad única (reemplaza al sistema paralelo de mapeo manual de
ítems + umbrales fijos).

Sin I/O: opera sobre los resultados por examen PRINCIPAL (PARCIAL/GLOBAL) del
alumno, ya resueltos con cadena de rescate por
`examen_mapper.calcular_resultados_examenes` (valor numérico `valor_real` +
resultado de escala `resultado_escala`).

Árbol de decisión (por alumno, ver diseño "Algoritmo de clasificación"):
  - Promocionado: cumple el mínimo (`nota_minima`, con rescate) en TODOS los
    exámenes principales, incluido el GLOBAL.
  - Regular: no promociona pero cumple la banda (`nota_minima - banda`) en
    TODOS los exámenes EXCEPTO el GLOBAL (opcional para regularizar).
  - Recursante: cualquier otro caso.
  - Exámenes en modo ESCALA no tienen banda numérica: cumplir el mínimo y
    cumplir la banda son lo mismo (`resultado_escala == 'aprobado'`).

La Nota Final ponderada (`calcular_nota_final`) normaliza cada examen a una
escala común 0–10 (`normalizar_a_10`) antes de ponderar los N parciales al
40 % y el GLOBAL al 60 % — evita que mezclar escalas (parciales en escala
100, global en escala 10) produzca un número sin sentido.
"""

import math


class SinExamenesConfigurados(Exception):
    """La materia no tiene exámenes PARCIAL/GLOBAL configurados para clasificar.

    El service la traduce a `HTTPException(400)` (ver diseño, "Convenciones
    de error").
    """


def round_half_up(x: float) -> int:
    """Redondeo estándar (no bankers' rounding) — 6.5 -> 7, no 6."""
    return math.floor(x + 0.5)


def detectar_escala(nota_minima: float | None) -> int | None:
    """Detecta la escala (100 o 10) de un examen a partir de la magnitud de
    su `nota_minima` — config-driven, sin llamadas extra a Moodle.

    `None` si el examen está en modo ESCALA (`nota_minima is None`, se
    evalúa por Aprobado/Desaprobado, no tiene escala numérica). `100` si
    `nota_minima >= 10` (frontera documentada: los valores reales esperados
    son 6 y 60, lejos del corte en 10), si no `10`.
    """
    if nota_minima is None:
        return None
    return 100 if nota_minima >= 10 else 10


def banda_regular(nota_minima: float | None) -> int | None:
    """Relajación relativa al mínimo para clasificar como Regular: `20` en
    escala 100, `2` en escala 10, `None` (sin banda numérica) en modo ESCALA.
    """
    escala = detectar_escala(nota_minima)
    if escala is None:
        return None
    return 20 if escala == 100 else 2


def normalizar_a_10(valor_real: float | None, nota_minima: float | None) -> float | None:
    """Lleva `valor_real` a la escala común 0–10 antes de ponderar la Nota
    Final: escala 100 se divide por 10 (80 -> 8.0), escala 10 (o `None` /
    ESCALA) queda sin cambio. `None` si no hay valor numérico.
    """
    if valor_real is None:
        return None
    escala = detectar_escala(nota_minima)
    if escala == 100:
        return valor_real / 10
    return valor_real


def max_o_none(valores: list[float | None] | None) -> float | None:
    """Nota más alta entre instancias rendidas, o None si ninguna se rindió."""
    limpios = [v for v in (valores or []) if v is not None]
    return max(limpios) if limpios else None


def cumple_minimo(examen: dict) -> bool:
    """Cumple el mínimo de aprobación de un examen principal.

    examen: `{tipo, modo_aprobacion, nota_minima, valor_real,
    resultado_escala}` (ya con rescate aplicado). Modo ESCALA: sin nota
    numérica, se evalúa por `resultado_escala`. Modo NUMERICO: `valor_real
    >= nota_minima` (`>=`, no `>`).
    """
    if examen.get("modo_aprobacion") == "ESCALA":
        return examen.get("resultado_escala") == "aprobado"
    valor_real = examen.get("valor_real")
    nota_minima = examen.get("nota_minima")
    return valor_real is not None and nota_minima is not None and valor_real >= nota_minima


def cumple_banda(examen: dict) -> bool:
    """Cumple la banda relativa para Regular (sólo aplica a exámenes NO
    globales, el caller filtra el GLOBAL antes de usar esta función).

    Modo ESCALA: no tiene banda numérica, exige aprobado (igual que
    `cumple_minimo`). Modo NUMERICO: `valor_real >= (nota_minima - banda)`.
    """
    if examen.get("modo_aprobacion") == "ESCALA":
        return examen.get("resultado_escala") == "aprobado"
    valor_real = examen.get("valor_real")
    nota_minima = examen.get("nota_minima")
    banda = banda_regular(nota_minima)
    if valor_real is None or nota_minima is None or banda is None:
        return False
    return valor_real >= (nota_minima - banda)


def _valor_para_nota_final(examen: dict) -> float:
    """Valor numérico 0-10 de un examen para ponderar la Nota Final —
    SIEMPRE devuelve un número (nunca `None`): un faltante cuenta como 0.

    Modo ESCALA: `10.0` si `resultado_escala == "aprobado"`, si no `0.0`
    (desaprobado, ausente, o sin resultado). Modo NUMERICO: `valor_real`
    normalizado a 0-10 (`normalizar_a_10`); `0.0` si no se rindió (no hay
    `valor_real`).
    """
    if examen.get("modo_aprobacion") == "ESCALA":
        return 10.0 if examen.get("resultado_escala") == "aprobado" else 0.0
    norm = normalizar_a_10(examen.get("valor_real"), examen.get("nota_minima"))
    return norm if norm is not None else 0.0


def calcular_nota_final(examenes: list[dict]) -> int | None:
    """Nota Final ponderada del alumno, con escala normalizada.

    `NF = (promedio de los N exámenes PARCIAL normalizados a 0-10) * 0.4 +
    (GLOBAL normalizado a 0-10) * 0.6`, redondeada con `round_half_up` a
    entero 0-10. Un examen no entregado (o en modo ESCALA no aprobado)
    cuenta como `0` en vez de invalidar el cálculo — ver
    `_valor_para_nota_final`.

    examenes: misma lista de exámenes PRINCIPALES (PARCIAL/GLOBAL) del
    alumno que recibe `calcular_estado_cierre`, cada uno
    `{tipo, modo_aprobacion, nota_minima, valor_real, ...}` (ya con rescate
    resuelto — `valor_real` es el mejor valor numérico entre la instancia
    base y sus rescates).

    Devuelve `None` (`N/E` en el reporte) sólo si la materia no tiene la
    forma PARCIAL+GLOBAL configurada:
      - no hay ningún examen PARCIAL, o
      - no hay exactamente un examen GLOBAL.

    Si hay PARCIAL y GLOBAL, SIEMPRE devuelve un `int` 0-10 (los faltantes
    cuentan como 0).
    """
    parciales = [e for e in examenes if e.get("tipo") == "PARCIAL"]
    globales = [e for e in examenes if e.get("tipo") == "GLOBAL"]

    if len(parciales) == 0 or len(globales) != 1:
        return None

    parciales_vals = [_valor_para_nota_final(e) for e in parciales]
    global_val = _valor_para_nota_final(globales[0])

    promedio_parciales = sum(parciales_vals) / len(parciales_vals)
    nf = promedio_parciales * 0.4 + global_val * 0.6
    return round_half_up(nf)


def calcular_estado_cierre(examenes: list[dict]) -> dict:
    """Veredicto de cierre de un alumno: PROMOCIONA / REGULARIZA / RECURSA.

    examenes: lista de exámenes PRINCIPALES (PARCIAL/GLOBAL) del alumno, cada
    uno `{examen_id, tipo, modo_aprobacion, nota_minima, valor_real,
    resultado_escala}` (ya con rescate resuelto por
    `examen_mapper.calcular_resultados_examenes`).

    Devuelve `{estado, resultados_examenes, global_valor, nota_final}`.
    `nota_final` sólo se informa para el estado PROMOCIONA (entero 0-10,
    resultado de `calcular_nota_final(examenes)`); para REGULARIZA/RECURSA
    es siempre `None` (celda en blanco en el reporte, no "N/E") — la Nota
    Final ponderada sólo tiene sentido para quien promociona.

    Lanza `SinExamenesConfigurados` si `examenes` está vacío.
    """
    if not examenes:
        raise SinExamenesConfigurados(
            "La materia no tiene exámenes PARCIAL/GLOBAL configurados para clasificar"
        )

    no_globales = [e for e in examenes if e.get("tipo") != "GLOBAL"]
    globales = [e for e in examenes if e.get("tipo") == "GLOBAL"]

    promociona = all(cumple_minimo(e) for e in examenes)  # incluye GLOBAL
    regulariza = (not promociona) and all(cumple_banda(e) for e in no_globales)

    if promociona:
        estado = "PROMOCIONA"
    elif regulariza:
        estado = "REGULARIZA"
    else:
        estado = "RECURSA"

    resultados_examenes = []
    for e in examenes:
        resultado = dict(e)
        resultado["cumple_minimo"] = cumple_minimo(e)
        resultado["cumple_banda"] = cumple_banda(e)
        resultados_examenes.append(resultado)

    global_valor = max_o_none([g.get("valor_real") for g in globales])

    return {
        "estado": estado,
        "resultados_examenes": resultados_examenes,
        "global_valor": global_valor,
        "nota_final": calcular_nota_final(examenes) if estado == "PROMOCIONA" else None,
    }
