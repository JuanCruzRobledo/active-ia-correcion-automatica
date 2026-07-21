"""
IA-015: sin límite de tamaño del código consolidado que se manda al LLM. Una entrega
enorme (muchos archivos consolidados) podía inflar el payload sin control (costo de
tokens / rechazo del modelo). Se capa el código a un máximo con un marcador de corte.
"""

from app.services.correccion_service import _truncar_codigo


def test_codigo_corto_no_se_toca():
    assert _truncar_codigo("print(1)", 100) == "print(1)"


def test_codigo_largo_se_trunca_con_marcador():
    codigo = "x" * 500
    out = _truncar_codigo(codigo, 100)
    assert len(out) <= 100 + 200          # el cuerpo cortado + el marcador
    assert out.startswith("x" * 100)      # conserva el principio
    assert "truncado" in out.lower()      # avisa que se cortó


def test_codigo_none_no_rompe():
    assert _truncar_codigo(None, 100) is None


def test_codigo_justo_en_el_limite_no_se_trunca():
    codigo = "y" * 100
    assert _truncar_codigo(codigo, 100) == codigo
