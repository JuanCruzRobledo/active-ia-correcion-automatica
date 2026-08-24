"""
correccion-por-ejercicio-con-tests, bloque 5: la corrida entra al prompt.

**El cliente lo llamó "la parte más importante del pedido", y tiene razón.**

AI-Native ejecuta el código en un sandbox real (Docker sin privilegios, Java 21,
sin red, 10s de límite). Sabe con CERTEZA qué casos pasan y cuáles no. Active-IA,
en cambio, lee el código con un LLM — y los tres modos de fallo documentados del
motor salen todos de eso:

- 100/100 a una entrega donde nada estaba vinculado (*vio* las piezas).
- Puntaje completo a una "búsqueda" que era `if puntajes[i] == 990` (*leyó* una
  búsqueda).

Un test ejecutado no se deja engañar por ninguna de esas dos cosas. Por eso el
resultado entra como **HECHO ESTABLECIDO** y no como sugerencia: si los tests
pasan, el código funciona, y el motor no tiene que deducirlo. Que se concentre en
lo que un test NO puede medir y que es lo que la rúbrica evalúa — si la excepción
es verificada o de runtime, si usó la interfaz o enumeró los tipos concretos, si
el encapsulamiento es real.

El acotamiento prioriza los casos FALLADOS: si hay que recortar, lo que explica
la nota es lo que falló, no lo que anduvo.
"""

import pytest

from app.integrations.gemini_correction_client import _build_resultado_tests_texto


def _caso(cid="t1", paso=True, entrada="in", esperado="out", obtenido="out"):
    return {
        "id": cid,
        "paso": paso,
        "entrada": entrada,
        "esperado": esperado,
        "obtenido": obtenido,
    }


def _resultado(**over):
    base = {
        "compila": True,
        "error_compilacion": None,
        "total": 4,
        "pasados": 4,
        "casos": [_caso()],
    }
    base.update(over)
    return base


class TestSeccionPresente:
    def test_informa_el_conteo(self):
        texto = _build_resultado_tests_texto(_resultado(total=6, pasados=4))

        assert "4" in texto and "6" in texto

    def test_declara_que_es_un_hecho_establecido(self):
        """La instrucción central: no volver a deducir si el programa funciona."""
        texto = _build_resultado_tests_texto(_resultado()).lower()

        assert "hecho establecido" in texto
        assert "no vuelvas a deducir" in texto or "no deduzcas" in texto

    def test_redirige_la_atencion_a_lo_que_el_test_no_mide(self):
        texto = _build_resultado_tests_texto(_resultado()).lower()

        assert "no puede medir" in texto or "no mide" in texto

    def test_lista_los_casos_con_su_veredicto(self):
        texto = _build_resultado_tests_texto(
            _resultado(total=2, pasados=1, casos=[_caso("t1", True), _caso("t2", False)])
        )

        assert "t1" in texto
        assert "t2" in texto


class TestNoCompila:
    def test_lo_dice_explicito_y_cita_el_error(self):
        texto = _build_resultado_tests_texto(
            _resultado(
                compila=False,
                error_compilacion="Main.java:12: error: ';' expected",
                total=6,
                pasados=0,
                casos=[],
            )
        )

        assert "NO COMPILA" in texto.upper()
        assert "';' expected" in texto

    def test_instruye_a_no_cerrar_criterios_de_funcionamiento(self):
        texto = _build_resultado_tests_texto(
            _resultado(compila=False, total=6, pasados=0, casos=[])
        ).lower()

        assert "no cierres" in texto or "no cierre" in texto

    def test_aclara_que_el_juicio_sobre_diseno_sigue_valiendo(self):
        """Es la razón por la que el cliente manda el código aunque no compile."""
        texto = _build_resultado_tests_texto(
            _resultado(compila=False, total=6, pasados=0, casos=[])
        ).lower()

        assert "diseño" in texto or "diseno" in texto


class TestCompilaYFallaTodo:
    def test_NO_dice_que_no_compila(self):
        """La distinción del 2026-08-19: mismo 0/6, situación distinta."""
        texto = _build_resultado_tests_texto(
            _resultado(compila=True, total=6, pasados=0, casos=[])
        )

        assert "NO COMPILA" not in texto.upper()

    def test_dice_que_corre_y_hace_otra_cosa(self):
        texto = _build_resultado_tests_texto(
            _resultado(compila=True, total=6, pasados=0, casos=[])
        ).lower()

        assert "compila" in texto


class TestAcotamiento:
    def test_los_casos_fallados_van_primero(self):
        """Si hay que recortar, lo que explica la nota es lo que falló."""
        casos = [_caso(f"ok{i}", True) for i in range(5)] + [_caso("falla1", False)]
        texto = _build_resultado_tests_texto(
            _resultado(total=6, pasados=5, casos=casos), max_caracteres=400
        )

        assert "falla1" in texto

    def test_avisa_cuando_recorta(self):
        casos = [
            _caso(f"c{i}", i % 2 == 0, entrada="x" * 300, esperado="y" * 300)
            for i in range(20)
        ]
        texto = _build_resultado_tests_texto(
            _resultado(total=20, pasados=10, casos=casos), max_caracteres=800
        )

        assert "recort" in texto.lower()

    def test_sin_recorte_no_avisa(self):
        texto = _build_resultado_tests_texto(_resultado())

        assert "recort" not in texto.lower()

    def test_respeta_el_presupuesto(self):
        casos = [_caso(f"c{i}", False, entrada="x" * 500) for i in range(50)]
        texto = _build_resultado_tests_texto(
            _resultado(total=50, pasados=0, casos=casos), max_caracteres=1500
        )

        # `max_caracteres` acota la SECCION ENTERA, no solo la lista de casos:
        # el que la llama quiere saber cuanto le cuesta esto en el prompt, y un
        # presupuesto que deja afuera el texto fijo no responde esa pregunta.
        assert len(texto) <= 1500


class TestAusencia:
    def test_sin_resultado_no_hay_seccion(self):
        assert _build_resultado_tests_texto(None) == ""

    def test_dict_vacio_tampoco(self):
        assert _build_resultado_tests_texto({}) == ""


class TestLlegaATodosLosCaminos:
    def test_el_prompt_de_codigo_lo_usa(self):
        import inspect

        from app.integrations.gemini_correction_client import GeminiCorrectionClient

        fuente = inspect.getsource(GeminiCorrectionClient.corregir_codigo)
        assert "_build_resultado_tests_texto(" in fuente

    def test_openrouter_lo_usa(self):
        import inspect

        from app.integrations import openrouter_client

        assert "_build_resultado_tests_texto(" in inspect.getsource(openrouter_client)
