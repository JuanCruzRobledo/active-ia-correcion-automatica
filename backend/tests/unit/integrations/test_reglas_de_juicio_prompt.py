"""
motor-anti-falsos-positivos, bloque 4: reglas de vínculo y hardcodeo.

Los bugs 4 y 5 del pedido de AI-Native, que son el mismo mecanismo con dos caras:

- **Bug 4 — cuenta presencia, no vínculo.** 100/100 a una entrega con "3
  categorías OK" y "10 productos OK" donde ningún producto quedaba vinculado a
  ninguna categoría. El motor encontró los sustantivos de la rúbrica en el código
  y cerró los criterios.
- **Bug 5 — elogia código hardcodeado.** Puntaje completo a una "búsqueda" que
  era `if puntajes[i] == 990`.

Estas son reglas de JUICIO: no se pueden verificar mecánicamente como la
evidencia del bloque 3. Van al prompt porque es donde pueden actuar. Lo que les
da diente es la evidencia obligatoria: exigir la línea donde el vínculo ocurre es
mucho más difícil de falsear que afirmar en prosa que existe.

**Honestidad sobre el alcance**: esto REDUCE los bugs 4 y 5, no los elimina. La
eliminación viene con los tests ejecutados del change
`correccion-por-ejercicio-con-tests`. Un test que corre no se deja engañar por
ninguna de las dos cosas.

El test de presupuesto no es decoración: cada instrucción nueva compite por la
atención del modelo con la rúbrica, que es lo que de verdad tiene que leer. Sin
un techo, el prompt se infla de a poco y nadie se entera hasta que la calidad
baja.
"""

import pytest

from app.integrations.gemini_correction_client import _build_reglas_de_juicio_texto

# Techo del bloque de reglas de juicio. Es un presupuesto, no un límite técnico:
# si hace falta pasarse, que sea una decisión consciente y no un goteo.
MAX_CARACTERES_REGLAS = 2200


class TestReglaDeVinculo:
    def test_declara_que_declarar_no_es_cumplir(self):
        texto = _build_reglas_de_juicio_texto().lower()

        assert "declarar" in texto or "declara" in texto
        assert "vínculo" in texto or "vinculo" in texto

    def test_incluye_el_caso_control_de_categorias_y_productos(self):
        """El ejemplo negativo concreto, no una regla abstracta."""
        texto = _build_reglas_de_juicio_texto().lower()

        assert "categor" in texto
        assert "producto" in texto

    def test_pide_la_linea_donde_la_relacion_ocurre(self):
        texto = _build_reglas_de_juicio_texto().lower()

        assert "ocurre" in texto or "sucede" in texto


class TestReglaDeHardcodeo:
    def test_declara_que_el_literal_embebido_no_cumple(self):
        texto = _build_reglas_de_juicio_texto().lower()

        assert "hardcode" in texto or "literal" in texto

    def test_incluye_el_caso_control_de_la_busqueda_falsa(self):
        """`if puntajes[i] == 990` — el caso real documentado."""
        texto = _build_reglas_de_juicio_texto()

        assert "990" in texto

    def test_instruye_a_no_elogiarlo(self):
        texto = _build_reglas_de_juicio_texto().lower()

        assert "no cumple" in texto or "no lo elogies" in texto


class TestPresupuestoDePrompt:
    """Cada instrucción compite por atención con la rúbrica."""

    def test_el_bloque_no_se_pasa_del_presupuesto(self):
        texto = _build_reglas_de_juicio_texto()

        assert len(texto) <= MAX_CARACTERES_REGLAS, (
            f"El bloque de reglas de juicio creció a {len(texto)} caracteres "
            f"(techo {MAX_CARACTERES_REGLAS}). Subir el techo tiene que ser una "
            "decisión consciente: más instrucciones = menos atención en la rúbrica."
        )

    def test_es_deterministico(self):
        """Sin parámetros: el mismo texto en toda corrección, siempre."""
        assert _build_reglas_de_juicio_texto() == _build_reglas_de_juicio_texto()


class TestLlegaATodosLosCaminos:
    @pytest.mark.parametrize("metodo", ["corregir_codigo", "corregir_pdf"])
    def test_el_prompt_de_gemini_usa_las_reglas(self, metodo):
        import inspect

        from app.integrations.gemini_correction_client import GeminiCorrectionClient

        fuente = inspect.getsource(getattr(GeminiCorrectionClient, metodo))
        assert "_build_reglas_de_juicio_texto()" in fuente

    def test_openrouter_tambien_las_usa(self):
        import inspect

        from app.integrations import openrouter_client

        fuente = inspect.getsource(openrouter_client)
        assert "_build_reglas_de_juicio_texto()" in fuente
