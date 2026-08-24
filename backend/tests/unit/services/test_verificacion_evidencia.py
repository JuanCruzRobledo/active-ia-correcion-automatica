"""
motor-anti-falsos-positivos, bloque 3: la evidencia se verifica de verdad.

El bloque 2 le pidió al motor que cite. Éste comprueba que la cita EXISTA en el
código que se le mandó. Sin esta parte, pedir evidencia sería otra regla
declarada que el motor puede no honrar — el mismo error del bug 2.

**Degrada, no anula.** Un criterio con cita inexistente baja a la mitad de su
peso y queda en WARNING; no se pone en 0. La verificación es una heurística
textual, no un analizador: puede dar falso negativo (el modelo cita código real
pero reformateado por él). Anular por un falso negativo desaprobaría a alguien
por un error NUESTRO, que es peor que el problema que venimos a resolver.

Tres exenciones, cada una con su motivo:

- **Criterio cerrado en 0**: no hay nada que citar. Degradarlo sería castigar dos
  veces lo mismo.
- **Corrección de PDF**: no hay código consolidado contra el cual comparar. Se
  pide la evidencia igual (sirve al tutor), pero no se verifica.
- **Código truncado**: la cita puede estar en la parte que no le llegó al modelo.
  Se registra en el log, pero no se degrada: el corte lo hicimos nosotros.
"""

from decimal import Decimal

import pytest

from app.services.correccion_evidencia import (
    evaluar_evidencias,
    normalizar_para_comparar,
    verificar_evidencia,
)

CODIGO = """public class Evento {
    private int cupo;

    public void inscribir(Persona p) throws CupoExcedidoException {
        if (inscriptos.size() >= cupo) {
            throw new CupoExcedidoException("Cupo lleno");
        }
        inscriptos.add(p);
    }
}"""


def _criterio(cid="C1", puntaje=20, maximo=20, evidencia=None, estado="OK"):
    return {
        "id": cid,
        "nombre": f"Criterio {cid}",
        "puntaje_obtenido": Decimal(str(puntaje)),
        "puntaje_maximo": Decimal(str(maximo)),
        "estado": estado,
        "feedback": "Cumple correctamente.",
        "evidencia": evidencia,
    }


class TestNormalizador:
    def test_colapsa_espacios_y_tabs(self):
        assert normalizar_para_comparar("if  (a\t==\tb)") == normalizar_para_comparar(
            "if (a == b)"
        )

    def test_ignora_saltos_de_linea(self):
        assert normalizar_para_comparar("a\nb") == normalizar_para_comparar("a b")

    def test_no_toca_las_mayusculas(self):
        assert normalizar_para_comparar("Foo") != normalizar_para_comparar("foo")

    def test_tolera_none(self):
        assert normalizar_para_comparar(None) == ""


class TestVerificacion:
    def test_cita_literal_se_encuentra(self):
        assert verificar_evidencia('throw new CupoExcedidoException("Cupo lleno");', CODIGO)

    def test_cita_con_distinto_espaciado_se_encuentra(self):
        """El modelo reindenta al copiar; eso no lo hace una cita falsa."""
        assert verificar_evidencia("if (inscriptos.size()   >=   cupo) {", CODIGO)

    def test_cita_partida_en_varias_lineas_se_encuentra(self):
        cita = "public void inscribir(Persona p)\nthrows CupoExcedidoException {"
        assert verificar_evidencia(cita, CODIGO)

    def test_cita_con_distinta_capitalizacion_NO_se_encuentra(self):
        """`Cupo` y `cupo` son identificadores distintos en Java."""
        assert not verificar_evidencia("private int Cupo;", CODIGO)

    def test_cita_inventada_no_se_encuentra(self):
        assert not verificar_evidencia("categoria.agregarProducto(p);", CODIGO)

    def test_cita_vacia_no_se_verifica(self):
        assert not verificar_evidencia("", CODIGO)
        assert not verificar_evidencia(None, CODIGO)

    def test_sin_codigo_no_se_verifica(self):
        assert not verificar_evidencia("cualquier cosa", None)


class TestDegradacion:
    def test_criterio_cerrado_con_cita_inexistente_baja_a_la_mitad_del_peso(self):
        criterios = [_criterio(puntaje=20, maximo=20, evidencia="lo que no está")]

        r = evaluar_evidencias(
            criterios, codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert r.criterios[0]["puntaje_obtenido"] == Decimal("10")
        assert r.criterios[0]["estado"] == "WARNING"
        assert r.degradados == ["C1"]

    def test_el_feedback_dice_por_que_bajo(self):
        criterios = [_criterio(puntaje=20, evidencia="lo que no está")]

        r = evaluar_evidencias(
            criterios, codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert "evidencia" in r.criterios[0]["feedback"].lower()
        assert "Cumple correctamente." in r.criterios[0]["feedback"]

    def test_criterio_ya_por_debajo_del_techo_conserva_su_puntaje(self):
        """Degradar no puede SUBIR una nota."""
        criterios = [_criterio(puntaje=6, maximo=20, evidencia="lo que no está")]

        r = evaluar_evidencias(
            criterios, codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert r.criterios[0]["puntaje_obtenido"] == Decimal("6")
        assert r.criterios[0]["estado"] == "WARNING"

    def test_criterio_con_cita_valida_no_se_toca(self):
        criterios = [
            _criterio(puntaje=20, evidencia='throw new CupoExcedidoException("Cupo lleno");')
        ]

        r = evaluar_evidencias(
            criterios, codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert r.criterios[0]["puntaje_obtenido"] == Decimal("20")
        assert r.criterios[0]["estado"] == "OK"
        assert r.degradados == []

    def test_sin_peso_en_la_rubrica_cae_al_puntaje_maximo_del_criterio(self):
        criterios = [_criterio(puntaje=20, maximo=20, evidencia="lo que no está")]

        r = evaluar_evidencias(criterios, codigo=CODIGO, pesos_por_criterio={})

        assert r.criterios[0]["puntaje_obtenido"] == Decimal("10")


class TestExenciones:
    def test_criterio_cerrado_en_cero_no_se_degrada(self):
        """No hay nada que citar; degradarlo castiga dos veces lo mismo."""
        criterios = [_criterio(puntaje=0, estado="ERROR", evidencia=None)]

        r = evaluar_evidencias(
            criterios, codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert r.criterios[0]["puntaje_obtenido"] == Decimal("0")
        assert r.criterios[0]["estado"] == "ERROR"
        assert r.degradados == []

    def test_con_degradar_apagado_se_registra_pero_no_se_baja(self):
        """El caso de PDF y el de código truncado."""
        criterios = [_criterio(puntaje=20, evidencia="lo que no está")]

        r = evaluar_evidencias(
            criterios,
            codigo=CODIGO,
            pesos_por_criterio={"C1": Decimal("20")},
            degradar=False,
        )

        assert r.criterios[0]["puntaje_obtenido"] == Decimal("20")
        assert r.criterios[0]["estado"] == "OK"
        assert r.degradados == []
        # pero queda la señal para el log
        assert r.no_verificados == ["C1"]

    def test_criterio_sin_evidencia_se_MIDE_pero_NO_se_degrada(self):
        """La decision mas importante de este bloque.

        Si degradaramos por omision, un modelo que deje de emitir `evidencia`
        —por un cambio de version, por un prompt mas largo, por lo que sea—
        cortaria TODAS las notas a la mitad, en silencio y de golpe. Un desastre
        causado por nosotros, no por los alumnos.

        Degradar solo la cita FALSA deja un hueco (el motor puede evitar la
        verificacion omitiendo el campo), pero ese hueco es MEDIBLE y se arregla
        en el prompt. Entre un agujero medible y un desastre silencioso, el
        agujero medible."""
        criterios = [_criterio(puntaje=20, evidencia=None)]

        r = evaluar_evidencias(
            criterios, codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert r.sin_cita == ["C1"]
        assert r.degradados == []
        assert r.criterios[0]["puntaje_obtenido"] == Decimal("20")
        assert r.criterios[0]["estado"] == "OK"
        # pero SI cuenta para la metrica de salud del motor
        assert r.no_verificados == ["C1"]

    def test_cita_falsa_si_se_degrada(self):
        """El contraste con el test de arriba: citar algo que no existe es una
        afirmacion falsa y comprobable, no una omision."""
        criterios = [_criterio(puntaje=20, evidencia="categoria.agregar(p);")]

        r = evaluar_evidencias(
            criterios, codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert r.cita_no_verificada == ["C1"]
        assert r.degradados == ["C1"]
        assert r.criterios[0]["puntaje_obtenido"] == Decimal("10")


class TestObservabilidad:
    def test_informa_la_tasa_de_citas_no_verificadas(self):
        criterios = [
            _criterio("C1", puntaje=20, evidencia='throw new CupoExcedidoException("Cupo lleno");'),
            _criterio("C2", puntaje=20, evidencia="inventado"),
            _criterio("C3", puntaje=20, evidencia="tambien inventado"),
            _criterio("C4", puntaje=0, estado="ERROR"),
        ]

        r = evaluar_evidencias(criterios, codigo=CODIGO, pesos_por_criterio={})

        # C4 esta exento, asi que no cuenta en el denominador.
        assert r.total_verificables == 3
        assert len(r.no_verificados) == 2

    def test_sin_criterios_verificables_no_divide_por_cero(self):
        criterios = [_criterio(puntaje=0, estado="ERROR")]

        r = evaluar_evidencias(criterios, codigo=CODIGO, pesos_por_criterio={})

        assert r.total_verificables == 0
        assert r.no_verificados == []


class TestNoRompeLoViejo:
    def test_correccion_sin_el_campo_evidencia_no_estalla(self):
        """Criterios de antes del change: la clave ni siquiera existe."""
        criterio = _criterio(puntaje=20)
        del criterio["evidencia"]

        r = evaluar_evidencias(
            [criterio], codigo=CODIGO, pesos_por_criterio={"C1": Decimal("20")}
        )

        assert r.criterios[0]["id"] == "C1"

    def test_lista_vacia_de_criterios(self):
        r = evaluar_evidencias([], codigo=CODIGO, pesos_por_criterio={})

        assert r.criterios == []
        assert r.total_verificables == 0


class TestCableadoEnElFlujo:
    """`_verificar_evidencias` decide degradar segun el TIPO de entrega."""

    @staticmethod
    def _entrega(codigo=CODIGO, pdf=None):
        from types import SimpleNamespace

        return SimpleNamespace(
            contenido_consolidado=codigo,
            contenido_preview=None,
            pdf_contenido_b64=pdf,
        )

    @staticmethod
    def _rubrica(peso=20):
        from types import SimpleNamespace

        return SimpleNamespace(
            criterios_json=[{"id": "C1", "nombre": "C1", "peso": peso}]
        )

    @staticmethod
    def _criterio_evaluado(puntaje, evidencia):
        from app.schemas.correccion import CriterioEvaluado

        return CriterioEvaluado(
            id="C1", nombre="C1",
            puntaje_obtenido=Decimal(str(puntaje)), puntaje_maximo=Decimal("20"),
            estado="OK", feedback="ok", evidencia=evidencia,
        )

    def test_entrega_de_codigo_con_cita_falsa_degrada(self):
        from app.services.correccion_service import CorreccionService

        salida = CorreccionService._verificar_evidencias(
            [self._criterio_evaluado(20, "inventado")],
            entrega=self._entrega(),
            rubrica=self._rubrica(),
        )

        assert salida[0].puntaje_obtenido == Decimal("10")
        assert salida[0].estado == "WARNING"

    def test_entrega_de_codigo_con_cita_real_no_degrada(self):
        from app.services.correccion_service import CorreccionService

        salida = CorreccionService._verificar_evidencias(
            [self._criterio_evaluado(20, 'throw new CupoExcedidoException("Cupo lleno");')],
            entrega=self._entrega(),
            rubrica=self._rubrica(),
        )

        assert salida[0].puntaje_obtenido == Decimal("20")
        assert salida[0].estado == "OK"

    def test_entrega_pdf_no_degrada_nunca(self):
        """No hay codigo consolidado contra el cual comparar."""
        from app.services.correccion_service import CorreccionService

        salida = CorreccionService._verificar_evidencias(
            [self._criterio_evaluado(20, "inventado")],
            entrega=self._entrega(codigo=None, pdf="JVBERi0="),
            rubrica=self._rubrica(),
        )

        assert salida[0].puntaje_obtenido == Decimal("20")

    def test_codigo_truncado_no_degrada(self):
        """La cita puede estar en la parte que no le llego al modelo."""
        from app.services.correccion_service import CorreccionService

        salida = CorreccionService._verificar_evidencias(
            [self._criterio_evaluado(20, "inventado")],
            entrega=self._entrega(codigo="x" * 250_000),
            rubrica=self._rubrica(),
        )

        assert salida[0].puntaje_obtenido == Decimal("20")

    def test_el_peso_sale_de_la_rubrica_no_del_puntaje_maximo(self):
        """Si la rubrica dice 10, el techo es 5 aunque el criterio diga max 20."""
        from app.services.correccion_service import CorreccionService

        salida = CorreccionService._verificar_evidencias(
            [self._criterio_evaluado(20, "inventado")],
            entrega=self._entrega(),
            rubrica=self._rubrica(peso=10),
        )

        assert salida[0].puntaje_obtenido == Decimal("5")
