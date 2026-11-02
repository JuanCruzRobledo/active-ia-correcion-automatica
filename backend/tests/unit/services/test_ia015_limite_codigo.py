"""
IA-015: sin límite de tamaño del código consolidado que se manda al LLM. Una entrega
enorme (muchos archivos consolidados) podía inflar el payload sin control (costo de
tokens / rechazo del modelo). Se capa el código a un máximo con un marcador de corte.
"""

import pytest
from fastapi import HTTPException
from app.services.correccion_service import _truncar_codigo


def test_codigo_corto_no_se_toca():
    assert _truncar_codigo("print(1)", 100) == "print(1)"


def test_codigo_largo_se_rechaza_sin_correccion_parcial():
    codigo = "x" * 500
    with pytest.raises(HTTPException) as error:
        _truncar_codigo(codigo, 100)
    assert error.value.status_code == 413
    assert "código incompleto" in error.value.detail


def test_codigo_none_no_rompe():
    assert _truncar_codigo(None, 100) is None


def test_codigo_justo_en_el_limite_no_se_trunca():
    codigo = "y" * 100
    assert _truncar_codigo(codigo, 100) == codigo
