# app/services/correccion_nota.py
"""
Cálculo determinístico de la nota de una corrección — funciones puras.

Change: `nota-deterministica-penalizaciones` (bugs 2 y 3 del pedido de AI-Native).

**Este módulo todavía NO está cableado al flujo de corrección.** Existe primero
para que el script de diagnóstico (`scripts/diagnostico_nota_deterministica.py`)
calcule el impacto con código verificado por tests, y no con una fórmula
reescrita a mano: si el diagnóstico y la implementación futura divergen, el
número que ve el coordinador miente. Cuando el gate de gobernanza dé el OK,
`correccion_service._nota_deterministica` pasa a delegar acá.

Qué corrige respecto del comportamiento actual:

- **Bug 2 — las penalizaciones no bajaban la nota.** Hoy `_nota_deterministica`
  (`correccion_service.py:162-193`) suma criterios y solo aplica el techo por
  condición de desaprobación. `_penalizaciones_validas` declara en su docstring
  que las penalizaciones "no alteran la nota, son solo auditoría/display": la
  aplicación del descuento vivía únicamente en el texto del prompt, delegada a
  que el modelo la ejecutara. Cuando no lo hacía, nadie lo corregía.
- **Bug 3 — el criterio no cerraba con sus subcriterios.** La invariante estaba
  declarada como instrucción de prompt y nunca se imponía en el backend.

El principio es el mismo en los dos: **ninguna regla aritmética que la rúbrica
declara puede depender de que un LLM la ejecute.** El proyecto ya lo resolvió
bien una vez con las condiciones de desaprobación, que sí son determinísticas.

Supuestos pendientes de confirmación en el gate (design D1 y Open Questions):
los descuentos se calculan todos sobre la MISMA BASE (la suma de criterios) y
no en cascada, y la nota se acota inferiormente en 0.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# La nota es Numeric(5,2) en la base (`Correccion.nota`). Se cuantiza UNA SOLA
# VEZ al final de la cadena: redondear en cada paso arrastra error.
_DOS_DECIMALES = Decimal("0.01")


def _a_decimal(valor: Any) -> Decimal:
    """Normaliza a Decimal sin pasar por float (que introduce error binario)."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or 0))


def _cuantizar(valor: Decimal) -> Decimal:
    return valor.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


def _campo(obj: Any, nombre: str, default: Any = None) -> Any:
    """Lee un campo tanto de un dict como de un objeto con atributos.

    Los criterios evaluados llegan como schemas Pydantic desde el flujo de
    corrección y como dicts crudos desde `criterios_json` cuando el script de
    diagnóstico los lee de la base.
    """
    if isinstance(obj, dict):
        return obj.get(nombre, default)
    return getattr(obj, nombre, default)


@dataclass
class ResultadoNota:
    """Desglose completo del cálculo, para poder auditarlo sin rehacerlo."""

    nota_final: Decimal
    suma_criterios: Decimal
    descuento_total: Decimal
    # Se puebla solo si hubo descuento o techo; None cuando la nota es la suma
    # limpia (mismo criterio con el que hoy se usa la columna homónima).
    nota_antes_penalizaciones: Decimal | None
    condicion_aplicada: str | None
    penalizaciones_aplicadas: list[str] = field(default_factory=list)
    detalle_descuentos: list[dict[str, Any]] = field(default_factory=list)
    # Criterios cuyo puntaje devuelto por el modelo no coincidía con la suma de
    # sus subcriterios. Señal de observabilidad, no afecta el cálculo.
    criterios_con_discrepancia: list[str] = field(default_factory=list)
    puntajes_recomputados: dict[str, Decimal] = field(default_factory=dict)


def descuento_por_penalizaciones(
    penalizaciones_rubrica: list[dict[str, Any]] | None,
    ids_declarados: list[str] | None,
    suma: Decimal,
) -> tuple[Decimal, list[dict[str, Any]]]:
    """Descuento total y su detalle, con el porcentaje tomado de la RÚBRICA.

    El modelo declara QUÉ penalización se incumplió (los ids); CUÁNTO descuenta
    lo decide la rúbrica. Los ids que no existen en la rúbrica se descartan —
    es la misma defensa contra alucinaciones que ya hacía
    `_penalizaciones_validas`, que se conserva como filtro de entrada.

    Todos los descuentos se calculan sobre `suma` (la misma base), no en
    cascada: dos penalizaciones del 30% descuentan 60%, no 51%.
    """
    if not ids_declarados or not penalizaciones_rubrica:
        return Decimal("0"), []

    por_id = {p.get("id"): p for p in penalizaciones_rubrica if p.get("id")}

    descuento_total = Decimal("0")
    detalle: list[dict[str, Any]] = []

    for pen_id in ids_declarados:
        penalizacion = por_id.get(pen_id)
        if penalizacion is None:
            continue  # id alucinado: el llamador lo loguea

        porcentaje = int(penalizacion.get("descuento_porcentaje", 0) or 0)
        puntos = _cuantizar(suma * Decimal(porcentaje) / Decimal(100))

        descuento_total += puntos
        detalle.append(
            {
                "id": pen_id,
                "descripcion": penalizacion.get("descripcion", ""),
                "porcentaje": porcentaje,
                "puntos_descontados": puntos,
            }
        )

    return descuento_total, detalle


def recomputar_criterio_por_subcriterios(
    criterio: Any,
    peso_criterio: Decimal | None,
) -> tuple[Decimal, bool]:
    """Puntaje del criterio como suma de sus subcriterios (rúbricas v2).

    Devuelve `(puntaje, hubo_discrepancia)`. Si el criterio no trae desglose,
    devuelve su puntaje tal cual y `False` — el camino v1 queda intacto.

    Cada subcriterio se acota a su propio máximo antes de sumar, y la suma se
    acota al peso que la rúbrica define para el criterio: sin eso, un
    subcriterio alucinado de más inflaría el criterio por encima de su peso.
    """
    declarado = _a_decimal(_campo(criterio, "puntaje_obtenido", 0))
    subcriterios = _campo(criterio, "subcriterios_evaluados") or []

    if not subcriterios:
        return declarado, False

    suma = Decimal("0")
    for sub in subcriterios:
        obtenido = _a_decimal(_campo(sub, "puntaje_obtenido", 0))
        maximo = _a_decimal(_campo(sub, "puntaje_maximo", 0))
        if maximo > 0:
            obtenido = min(obtenido, maximo)
        suma += max(Decimal("0"), obtenido)

    techo = peso_criterio if peso_criterio is not None else None
    if techo is None:
        techo = _a_decimal(_campo(criterio, "puntaje_maximo", 0)) or None
    if techo is not None and techo > 0:
        suma = min(suma, techo)

    return suma, suma != declarado


def _techo_de_condicion(
    condiciones_rubrica: list[dict[str, Any]] | None, cd_id: str | None
) -> Decimal | None:
    """Techo de una condición de desaprobación, tomado de la RÚBRICA.

    None si no hay id o si el id no existe en la rúbrica (el modelo pudo
    alucinarlo). Réplica exacta de `_techo_de_condicion` del service actual.
    """
    if not cd_id:
        return None
    for cd in condiciones_rubrica or []:
        if cd.get("id") == cd_id:
            nota_maxima = cd.get("nota_maxima")
            return None if nota_maxima is None else _a_decimal(nota_maxima)
    return None


def calcular_nota(
    criterios_evaluados: list[Any],
    penalizaciones_rubrica: list[dict[str, Any]] | None,
    condiciones_rubrica: list[dict[str, Any]] | None,
    ids_penalizaciones_declaradas: list[str] | None,
    id_condicion_declarada: str | None,
    schema_version: int,
    pesos_por_criterio: dict[str, Decimal] | None = None,
) -> ResultadoNota:
    """Nota final y su desglose completo.

    Cadena de cálculo:

        criterios (recomputados por subcriterios si v2)
          → suma
          → menos descuentos por penalización (todos sobre la misma base)
          → acotado inferiormente en 0
          → acotado superiormente por el techo de la condición de desaprobación
    """
    pesos = pesos_por_criterio or {}
    recomputar = schema_version >= 2

    suma = Decimal("0")
    discrepancias: list[str] = []
    recomputados: dict[str, Decimal] = {}

    for criterio in criterios_evaluados:
        crit_id = _campo(criterio, "id") or ""
        if recomputar:
            puntaje, hubo_discrepancia = recomputar_criterio_por_subcriterios(
                criterio, pesos.get(crit_id)
            )
            if hubo_discrepancia:
                discrepancias.append(crit_id)
            recomputados[crit_id] = puntaje
        else:
            puntaje = _a_decimal(_campo(criterio, "puntaje_obtenido", 0))
        suma += puntaje

    descuento, detalle = descuento_por_penalizaciones(
        penalizaciones_rubrica, ids_penalizaciones_declaradas, suma
    )

    nota_penada = max(Decimal("0"), suma - descuento)

    techo = _techo_de_condicion(condiciones_rubrica, id_condicion_declarada)
    if techo is not None:
        condicion_aplicada = id_condicion_declarada
        nota_final = min(nota_penada, techo)
    else:
        condicion_aplicada = None
        nota_final = nota_penada

    hubo_ajuste = descuento > 0 or techo is not None

    return ResultadoNota(
        nota_final=_cuantizar(nota_final),
        suma_criterios=_cuantizar(suma),
        descuento_total=_cuantizar(descuento) if descuento else Decimal("0"),
        nota_antes_penalizaciones=_cuantizar(suma) if hubo_ajuste else None,
        condicion_aplicada=condicion_aplicada,
        penalizaciones_aplicadas=[d["id"] for d in detalle],
        detalle_descuentos=detalle,
        criterios_con_discrepancia=discrepancias,
        puntajes_recomputados=recomputados,
    )


def calcular_nota_actual(
    criterios_evaluados: list[Any],
    condiciones_rubrica: list[dict[str, Any]] | None,
    id_condicion_declarada: str | None,
) -> Decimal:
    """La fórmula VIEJA, para que el diagnóstico pueda comparar contra ella.

    Réplica del `_nota_deterministica` actual: suma de criterios y techo por
    condición de desaprobación. Las penalizaciones se ignoran, que es
    exactamente el bug 2.

    No se usa en producción: existe para que el script de diagnóstico calcule
    el "antes" con la misma normalización de tipos que el "después", en vez de
    confiar en la nota persistida (que puede haber sido editada a mano).
    """
    suma = sum(
        (_a_decimal(_campo(c, "puntaje_obtenido", 0)) for c in criterios_evaluados),
        Decimal("0"),
    )
    techo = _techo_de_condicion(condiciones_rubrica, id_condicion_declarada)
    nota = min(suma, techo) if techo is not None else suma
    return _cuantizar(nota)
