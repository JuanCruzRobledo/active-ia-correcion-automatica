"""
IA-015: sin límite de tamaño del código consolidado que se manda al LLM. Una entrega
enorme (muchos archivos consolidados) podía inflar el payload sin control (costo de
tokens / rechazo del modelo). Se capa el código a un máximo con un marcador de corte.

Nota de mantenimiento (change `motor-anti-falsos-positivos`): `_truncar_codigo` pasó
a devolver `(codigo, fue_truncado, caracteres_originales)`. El texto y el marcador no
cambiaron — lo que se agregó es el ESTADO, que antes solo existía como marcador
embebido dentro del propio blob. El motor no podía distinguir "esto falta porque el
alumno no lo entregó" de "esto falta porque lo cortamos nosotros", y esa confusión es
parte del bug 1 (descontar por archivos presentes). Las aserciones de acá son las
mismas de antes; solo desempaquetan.
"""

from app.services.correccion_service import _truncar_codigo


def test_codigo_corto_no_se_toca():
    codigo, truncado, originales = _truncar_codigo("print(1)", 100)
    assert codigo == "print(1)"
    assert truncado is False
    assert originales == len("print(1)")


def test_codigo_largo_se_trunca_con_marcador():
    codigo = "x" * 500
    out, truncado, originales = _truncar_codigo(codigo, 100)
    assert len(out) <= 100 + 200          # el cuerpo cortado + el marcador
    assert out.startswith("x" * 100)      # conserva el principio
    assert "truncado" in out.lower()      # avisa que se cortó
    assert truncado is True               # y ahora también lo dice aparte
    assert originales == 500


def test_codigo_none_no_rompe():
    codigo, truncado, originales = _truncar_codigo(None, 100)
    assert codigo is None
    assert truncado is False
    assert originales == 0


def test_codigo_justo_en_el_limite_no_se_trunca():
    codigo = "y" * 100
    out, truncado, _ = _truncar_codigo(codigo, 100)
    assert out == codigo
    assert truncado is False
