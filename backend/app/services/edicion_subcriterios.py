"""Reglas de edición manual del snapshot de subcriterios de una corrección."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException


def _invalid(detalle: str) -> None:
    raise HTTPException(status_code=400, detail=detalle)


def _decimal(value: object, etiqueta: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        _invalid(f"{etiqueta}: el puntaje debe ser un número finito")
    if not result.is_finite():
        _invalid(f"{etiqueta}: el puntaje debe ser un número finito")
    return result


def _por_id(elementos: list[dict]) -> dict[str, dict]:
    resultado = {elemento["id"]: elemento for elemento in elementos}
    if len(resultado) != len(elementos):
        _invalid("No se permiten identificadores duplicados en el desglose")
    return resultado


def preparar_criterios_editados(editados: list[dict], originales: list[dict]) -> list[dict]:
    """Copiar los criterios y derivar su total al cambiar un puntaje del desglose."""
    resultado = deepcopy(editados)
    por_id = _por_id(originales)
    actuales = _por_id(resultado)
    # Clientes históricos sin snapshot todavía pueden enviar sus criterios.
    if por_id and actuales.keys() != por_id.keys():
        _invalid("No se permite agregar o eliminar criterios al editar el desglose")
    for criterio in resultado:
        previo = por_id.get(criterio["id"], {})
        anteriores = previo.get("subcriterios_evaluados") or []
        if "subcriterios_evaluados" not in criterio:
            if anteriores:
                criterio["subcriterios_evaluados"] = deepcopy(anteriores)
                criterio["puntaje_obtenido"] = previo["puntaje_obtenido"]
            continue
        subs = criterio["subcriterios_evaluados"] or []
        if not anteriores:
            if subs:
                _invalid("No se permite agregar subcriterios a una corrección sin desglose")
            continue
        anteriores_por_id = _por_id(anteriores)
        if _por_id(subs).keys() != anteriores_por_id.keys():
            _invalid(f"{criterio['id']}: no se permite modificar la composición del desglose")
        if _decimal(criterio["puntaje_maximo"], criterio["id"]) != _decimal(previo["puntaje_maximo"], criterio["id"]):
            _invalid(f"{criterio['id']}: no se permite modificar el máximo")
        puntaje_cambiado = False
        total = Decimal(0)
        for sub in subs:
            original = anteriores_por_id[sub["id"]]
            etiqueta = sub["id"]
            maximo = _decimal(original["puntaje_maximo"], etiqueta)
            if _decimal(sub["puntaje_maximo"], etiqueta) != maximo or sub["estado"] != original["estado"]:
                _invalid(f"{etiqueta}: no se permite modificar máximo ni estado")
            puntaje = _decimal(sub["puntaje_obtenido"], etiqueta)
            cambio_puntaje = puntaje != _decimal(original["puntaje_obtenido"], etiqueta)
            if cambio_puntaje or sub["feedback"] != original["feedback"]:
                if not Decimal(0) <= puntaje <= maximo:
                    _invalid(f"{etiqueta}: el puntaje debe estar entre 0 y {maximo}")
                if not sub["feedback"].strip():
                    _invalid(f"{etiqueta}: el comentario es obligatorio")
            puntaje_cambiado |= cambio_puntaje
            total += puntaje
        if puntaje_cambiado:
            if total > _decimal(previo["puntaje_maximo"], criterio["id"]):
                _invalid(f"{criterio['id']}: la suma de subcriterios supera el máximo")
            criterio["puntaje_obtenido"] = total
        else:
            criterio["puntaje_obtenido"] = previo["puntaje_obtenido"]
    return resultado
