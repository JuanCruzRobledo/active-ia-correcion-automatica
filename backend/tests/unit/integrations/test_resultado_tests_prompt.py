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


def _caso(cid="t1", paso=True, nombre="Caso base", salida_obtenida="out",
          es_publico=True):
    """Las cinco claves que el cliente emite de verdad (verificado 2026-08-27)."""
    return {
        "id": cid,
        "nombre": nombre,
        "paso": paso,
        "salida_obtenida": salida_obtenida,
        "es_publico": es_publico,
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


class TestCorridaSinEvidencia:
    """`total: 0` y `casos: []` no es una medición: es la AUSENCIA de una.

    Lo destapó un bug del cliente (informado el 2026-08-28): su `_mapear` leía
    cuatro claves que su propio sandbox no emitía, así que TODA corrección de
    producción nos mandó el mismo objeto vacío —
    `{"compila": true, "error_compilacion": null, "total": 0, "pasados": 0,
    "casos": []}`— y un alumno cuyo Java no compilaba viajaba como
    `compila: true`. Ellos ya lo corrigieron.

    Pero lo que hacíamos NOSOTROS con ese payload era un defecto propio, y
    sobrevive a su arreglo: rendereábamos «Casos superados: 0 de 0» bajo un
    encabezado que dice HECHO ESTABLECIDO, junto con «no vuelvas a deducir si el
    programa funciona: ya está respondido».

    Las dos cosas juntas son lo peor posible: un «0 de 0» que se lee como que no
    pasó nada, y una orden de apagar el juicio propio sobre una corrida que no
    responde nada. Si el cliente no midió el comportamiento, la pregunta sigue
    abierta y el motor tiene que contestarla leyendo el código, como cuando no
    hay sección.
    """

    def _sin_evidencia(self):
        return _resultado(compila=True, total=0, pasados=0, casos=[])

    def test_no_muestra_un_cero_de_cero(self):
        """Ese número se lee como fracaso y no mide nada."""
        texto = _build_resultado_tests_texto(self._sin_evidencia())

        assert "0 de 0" not in texto

    def test_no_le_ordena_dejar_de_deducir_el_comportamiento(self):
        """Sin evidencia, apagarle el juicio propio no lo reemplaza por nada."""
        texto = _build_resultado_tests_texto(self._sin_evidencia()).lower()

        assert "no vuelvas a deducir" not in texto
        assert "ya está respondido" not in texto

    def test_dice_explicitamente_que_no_se_ejecutaron_casos(self):
        texto = _build_resultado_tests_texto(self._sin_evidencia()).lower()

        assert "no se ejecut" in texto

    def test_conserva_el_hecho_de_que_compila(self):
        """Compilar es un dato aparte que el cliente sí puede saber sin tests."""
        texto = _build_resultado_tests_texto(self._sin_evidencia()).lower()

        assert "compila" in texto

    def test_le_pide_que_juzgue_el_comportamiento_leyendo_el_codigo(self):
        texto = _build_resultado_tests_texto(self._sin_evidencia()).lower()

        assert "leyendo el código" in texto or "leyendo el codigo" in texto

    def test_no_compila_sin_casos_SIGUE_siendo_evidencia(self):
        """La simetría que no hay que romper.

        Que no compile es un hecho completo por sí solo: no necesita casos para
        respaldarlo, y el cierre determinístico de criterios depende de él.
        """
        texto = _build_resultado_tests_texto(
            _resultado(compila=False, total=0, pasados=0, casos=[],
                       error_compilacion="Main.java:12: error: ';' expected")
        )

        assert "NO COMPILA" in texto
        assert "';' expected" in texto

    def test_con_un_solo_caso_vuelve_a_ser_una_medicion(self):
        """Triangulación: la frontera está en si hubo corrida, no en el conteo."""
        texto = _build_resultado_tests_texto(
            _resultado(compila=True, total=1, pasados=0, casos=[_caso("t1", False)])
        ).lower()

        assert "no vuelvas a deducir" in texto
        assert "no se ejecut" not in texto


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

    def test_nombra_el_caso_fallado(self):
        """Un id opaco no le sirve al motor para redactar la devolución."""
        texto = _build_resultado_tests_texto(
            _resultado(total=1, pasados=0,
                       casos=[_caso("t7", False, nombre="Rechaza inscripción sin cupo")])
        )

        assert "Rechaza inscripción sin cupo" in texto

    def test_muestra_la_salida_obtenida_del_caso_fallado(self):
        """El único dato que el sandbox agrega y que nadie más puede saber.

        Antes del 2026-08-27 este campo se llamaba `obtenido` de nuestro lado y
        `salida_obtenida` del suyo, así que llegaba vacío SIEMPRE y el motor
        constataba el fallo sin poder explicarlo.
        """
        texto = _build_resultado_tests_texto(
            _resultado(total=1, pasados=0,
                       casos=[_caso("t7", False, salida_obtenida="Cupo lleno")])
        )

        assert "Cupo lleno" in texto


class TestCasosOcultos:
    """Un caso oculto CUENTA para la nota pero no se puede citar.

    Es la razón de ser de un test oculto: si la devolución dice "fallaste
    'Rechaza inscripción sin cupo' devolviendo 'Inscripto: Ana'", el alumno ya
    tiene el caso y el próximo intento lo aprueba sin arreglar nada. Filtrar acá
    y no en el prompt: pedirle al motor que no mencione algo que le mostramos
    es confiar en que obedezca, y de este motor ya está medido que no siempre lo
    hace (bug 2).
    """

    def test_el_veredicto_del_caso_oculto_sigue_estando(self):
        texto = _build_resultado_tests_texto(
            _resultado(total=1, pasados=0,
                       casos=[_caso("t9", False, es_publico=False)])
        )

        assert "t9" in texto

    def test_no_filtra_el_nombre_del_caso_oculto(self):
        texto = _build_resultado_tests_texto(
            _resultado(total=1, pasados=0,
                       casos=[_caso("t9", False, nombre="Cupo negativo",
                                    es_publico=False)])
        )

        assert "Cupo negativo" not in texto

    def test_no_filtra_la_salida_del_caso_oculto(self):
        texto = _build_resultado_tests_texto(
            _resultado(total=1, pasados=0,
                       casos=[_caso("t9", False, salida_obtenida="Inscripto: Ana",
                                    es_publico=False)])
        )

        assert "Inscripto: Ana" not in texto

    def test_le_avisa_al_motor_que_no_lo_mencione(self):
        """El filtrado ya lo protege; esto evita que INVENTE el contenido."""
        texto = _build_resultado_tests_texto(
            _resultado(total=1, pasados=0,
                       casos=[_caso("t9", False, es_publico=False)])
        ).lower()

        assert "oculto" in texto

    def test_un_caso_publico_del_mismo_lote_no_se_censura(self):
        """El filtro es por caso, no por lote."""
        texto = _build_resultado_tests_texto(
            _resultado(total=2, pasados=0, casos=[
                _caso("t1", False, nombre="Visible", salida_obtenida="salida visible"),
                _caso("t9", False, nombre="Secreto", salida_obtenida="salida secreta",
                      es_publico=False),
            ])
        )

        assert "Visible" in texto and "salida visible" in texto
        assert "Secreto" not in texto and "salida secreta" not in texto


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
            _caso(f"c{i}", i % 2 == 0, nombre="n" * 150, salida_obtenida="y" * 300)
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
        casos = [_caso(f"c{i}", False, salida_obtenida="x" * 500) for i in range(50)]
        texto = _build_resultado_tests_texto(
            _resultado(total=50, pasados=0, casos=casos), max_caracteres=1500
        )

        # `max_caracteres` acota la SECCION ENTERA, no solo la lista de casos:
        # el que la llama quiere saber cuanto le cuesta esto en el prompt, y un
        # presupuesto que deja afuera el texto fijo no responde esa pregunta.
        assert len(texto) <= 1500

    def test_respeta_el_presupuesto_tambien_con_casos_ocultos(self):
        """El aviso de ocultos es texto fijo nuevo: tiene que entrar en la cuenta.

        Si se olvidara de reservarlo, la seccion se pasaria del presupuesto justo
        en el caso mas caro, que es el que tiene mas casos.
        """
        casos = [
            _caso(f"c{i}", False, salida_obtenida="x" * 500, es_publico=i % 2 == 0)
            for i in range(50)
        ]
        texto = _build_resultado_tests_texto(
            _resultado(total=50, pasados=0, casos=casos), max_caracteres=1500
        )

        assert "oculto" in texto.lower()
        assert len(texto) <= 1500


class TestElContratoRealDeExtremoAExtremo:
    """El test que habría cazado el bug: el payload REAL cruzando toda la cadena.

    Hasta el 2026-08-27, cada capa se probaba con su propio diccionario inventado
    y las dos estaban de acuerdo entre ellas — y equivocadas respecto del cliente.
    Acá se parte del dict tal como sale de su `_mapear`, se lo hace pasar por el
    schema (que es donde se perdía) y recién después por el prompt.
    """

    def _payload_del_cliente(self):
        # Copiado de `correccion_pre_ejecucion.py::_mapear`, no de su documento.
        return {
            "compila": True,
            "error_compilacion": None,
            "total": 2,
            "pasados": 1,
            "casos": [
                {
                    "id": "t1",
                    "nombre": "Inscribe con cupo disponible",
                    "paso": True,
                    "salida_obtenida": "Inscripto: Ana\n",
                    "es_publico": True,
                },
                {
                    "id": "t2",
                    "nombre": "Rechaza inscripción sin cupo",
                    "paso": False,
                    "salida_obtenida": "Inscripto: Beto\n",
                    "es_publico": True,
                },
            ],
        }

    def test_la_salida_real_sobrevive_al_schema(self):
        from app.schemas.correccion import ResultadoTests

        r = ResultadoTests(**self._payload_del_cliente())

        assert r.casos[1].salida_obtenida == "Inscripto: Beto\n"

    def test_la_salida_real_llega_al_prompt(self):
        from app.schemas.correccion import ResultadoTests

        r = ResultadoTests(**self._payload_del_cliente())
        texto = _build_resultado_tests_texto(r.model_dump())

        assert "Inscripto: Beto" in texto
        assert "Rechaza inscripción sin cupo" in texto


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
