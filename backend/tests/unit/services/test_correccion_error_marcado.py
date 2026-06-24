"""
Tests del marcado/limpieza de error en la entrega (item #1).

Cuando una corrección falla, la entrega debe quedar con estado ERROR + el detalle
traducido (code, mensaje, timestamp). Al corregir con éxito, ese detalle se limpia.
"""

from types import SimpleNamespace

from app.core.error_catalog import ERROR_RATE_LIMIT, mensaje_error
from app.models.enums import EstadoEntregaEnum
from app.services.correccion_service import (
    _limpiar_entrega_error,
    _marcar_entrega_error,
)


def test_marcar_error_setea_estado_y_detalle():
    entrega = SimpleNamespace(
        estado=EstadoEntregaEnum.PENDIENTE,
        error_code=None,
        error_mensaje=None,
        error_at=None,
    )

    _marcar_entrega_error(entrega, ERROR_RATE_LIMIT)

    assert entrega.estado == EstadoEntregaEnum.ERROR
    assert entrega.error_code == ERROR_RATE_LIMIT
    assert entrega.error_mensaje == mensaje_error(ERROR_RATE_LIMIT)
    assert entrega.error_at is not None


def test_limpiar_error_borra_el_detalle():
    entrega = SimpleNamespace(
        estado=EstadoEntregaEnum.CORREGIDA,
        error_code=ERROR_RATE_LIMIT,
        error_mensaje="algo",
        error_at="2026-06-24",
    )

    _limpiar_entrega_error(entrega)

    assert entrega.error_code is None
    assert entrega.error_mensaje is None
    assert entrega.error_at is None
