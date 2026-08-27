"""
correccion-por-ejercicio-con-tests, bloque 2: el contrato de la corrección.

**AI-Native ya tiene su cliente escrito contra este contrato** y corre contra un
mock hasta que el endpoint exista. Cualquier cosa que agreguemos tiene que ser
opcional, o les rompemos lo que ya construyeron.

La distinción que el cliente agregó el 2026-08-19 y que este bloque codifica:

    |                     | compila | pasados/total | Qué le pasó al alumno        |
    |---------------------|---------|---------------|------------------------------|
    | No compila          | false   | 0/6           | Un error de sintaxis         |
    | Compila y falla todo| true    | 0/6           | El programa corre y hace otra cosa |

Son dos situaciones distintas y merecen devoluciones distintas. **`compila` NO se
deduce de `pasados == 0`**, y por eso es un campo propio con su test.

El cliente manda el código aunque no compile: antes lo cortaba y lo revirtió,
porque un punto y coma que falta no justifica dejar al alumno sin devolución — el
juicio sobre el DISEÑO sigue siendo útil y es justo lo que un compilador no da.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.correccion import (
    CasoTestResultado,
    CorreccionEjercicioRequest,
    CorreccionEjercicioResponse,
    ResultadoTests,
)


def _caso(**over):
    """Un caso TAL COMO LO MANDA EL CLIENTE.

    Verificado el 2026-08-27 leyendo su código, no su documento: en
    `correccion_pre_ejecucion.py::_mapear` arma exactamente estas cinco claves.

    No manda `entrada` ni `esperado`, y tiene razón: el sandbox corre un caso
    cuya definición se la dimos nosotros en el TP. Devolverla sería que nos
    repita lo que ya sabemos. Lo único que el sandbox agrega, y que nadie más
    puede saber, es qué salió.
    """
    base = {
        "id": "t1",
        "nombre": "Inscribe a un alumno con cupo disponible",
        "paso": True,
        "salida_obtenida": "Inscripto: Ana\n",
        "es_publico": True,
    }
    base.update(over)
    return base


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


class TestCuerpoDeLaSolicitud:
    def test_el_contrato_minimo_del_cliente(self):
        """Exactamente lo que su cliente ya implementó, sin agregados."""
        req = CorreccionEjercicioRequest(
            alumno_ref="pseudonimo-del-alumno",
            codigo="public class Main {}",
            resultado_tests=ResultadoTests(**_resultado()),
        )
        assert req.alumno_ref == "pseudonimo-del-alumno"
        assert req.resultado_tests.pasados == 4

    def test_el_resultado_de_tests_es_opcional(self):
        """Un cliente que no ejecute código tiene que poder corregir igual."""
        req = CorreccionEjercicioRequest(alumno_ref="p", codigo="x")
        assert req.resultado_tests is None

    def test_la_referencia_de_comision_es_opcional(self):
        """El campo nuevo NO puede romper el contrato que ya implementaron."""
        req = CorreccionEjercicioRequest(alumno_ref="p", codigo="x")
        assert req.comision_external_ref is None

        con_cohorte = CorreccionEjercicioRequest(
            alumno_ref="p", codigo="x", comision_external_ref="uuid-cohorte"
        )
        assert con_cohorte.comision_external_ref == "uuid-cohorte"

    def test_alumno_ref_es_obligatorio(self):
        with pytest.raises(ValidationError):
            CorreccionEjercicioRequest(codigo="x")

    def test_codigo_es_obligatorio(self):
        """Se manda aunque no compile: el juicio sobre diseño sigue sirviendo."""
        with pytest.raises(ValidationError):
            CorreccionEjercicioRequest(alumno_ref="p")

    def test_codigo_vacio_se_rechaza(self):
        with pytest.raises(ValidationError):
            CorreccionEjercicioRequest(alumno_ref="p", codigo="   ")


class TestCompilaEsUnCampoPropio:
    """La distinción del 2026-08-19: no se deduce de `pasados == 0`."""

    def test_no_compila_con_cero_pasados(self):
        r = ResultadoTests(
            **_resultado(
                compila=False,
                error_compilacion="Main.java:12: error: ';' expected",
                total=6,
                pasados=0,
                casos=[],
            )
        )
        assert r.compila is False
        assert "';' expected" in r.error_compilacion

    def test_compila_y_falla_todo(self):
        """Mismo 0/6, situación completamente distinta."""
        r = ResultadoTests(**_resultado(compila=True, total=6, pasados=0, casos=[]))
        assert r.compila is True
        assert r.error_compilacion is None

    def test_los_dos_casos_se_distinguen_entre_si(self):
        no_compila = ResultadoTests(**_resultado(compila=False, total=6, pasados=0, casos=[]))
        falla_todo = ResultadoTests(**_resultado(compila=True, total=6, pasados=0, casos=[]))

        assert no_compila.compila != falla_todo.compila
        assert no_compila.pasados == falla_todo.pasados == 0

    def test_compila_es_obligatorio(self):
        datos = _resultado()
        del datos["compila"]
        with pytest.raises(ValidationError):
            ResultadoTests(**datos)


class TestCoherenciaDelResultado:
    def test_pasados_no_puede_superar_el_total(self):
        with pytest.raises(ValidationError):
            ResultadoTests(**_resultado(total=3, pasados=5))

    def test_pasados_no_puede_ser_negativo(self):
        with pytest.raises(ValidationError):
            ResultadoTests(**_resultado(pasados=-1))

    def test_sin_casos_es_valido(self):
        """Un código que no compila no llega a correr ninguno."""
        r = ResultadoTests(**_resultado(compila=False, total=6, pasados=0, casos=[]))
        assert r.casos == []


class TestCasoDePrueba:
    def test_caso_pasado(self):
        c = CasoTestResultado(**_caso(paso=True))
        assert c.paso is True

    def test_caso_fallado_conserva_la_salida_obtenida(self):
        """Lo que salió es lo que le permite al motor explicar el fallo.

        Es el campo por el que existe todo este bloque: sin él, el motor
        constata que falló y no puede decir por qué.
        """
        c = CasoTestResultado(**_caso(paso=False, salida_obtenida="Cupo lleno"))
        assert c.salida_obtenida == "Cupo lleno"

    def test_el_nombre_del_caso_viaja(self):
        """Un id opaco no le dice nada al alumno; el nombre sí."""
        c = CasoTestResultado(**_caso(nombre="Rechaza inscripción sin cupo"))
        assert c.nombre == "Rechaza inscripción sin cupo"

    def test_solo_id_y_paso_son_obligatorios(self):
        c = CasoTestResultado(id="t9", paso=False)
        assert c.nombre is None
        assert c.salida_obtenida is None

    def test_un_caso_es_publico_salvo_que_digan_lo_contrario(self):
        """El default seguro es el que NO crea un caso oculto por omisión.

        Si un cliente omite la clave, tratarlo como oculto silenciaría un caso
        que sí se podía citar. Al revés — tratar un oculto como público — el
        default nunca se aplica, porque el que tiene casos ocultos los marca.
        """
        c = CasoTestResultado(id="t9", paso=False)
        assert c.es_publico is True

    def test_un_caso_oculto_se_marca_como_tal(self):
        c = CasoTestResultado(**_caso(es_publico=False))
        assert c.es_publico is False

    def test_los_campos_que_el_cliente_no_manda_ya_no_existen(self):
        """`entrada` y `esperado` NO son parte del contrato de resultado.

        Estaban acá por un supuesto nuestro que su código desmintió. Un campo
        opcional que nadie llena es peor que ninguno: el próximo que lo lea va
        a creer que hay un dato ahí.
        """
        campos = set(CasoTestResultado.model_fields)
        assert "entrada" not in campos
        assert "esperado" not in campos
        assert "obtenido" not in campos


class TestRespuesta:
    def test_devuelve_nota_y_desglose_del_EJERCICIO(self):
        r = CorreccionEjercicioResponse(
            correccion_id=10,
            entrega_id=5,
            ejercicio_external_ref="uuid-ej-1",
            rubrica_id=99,
            alumno_ref="pseudonimo",
            nota=Decimal("85.00"),
            criterios=[],
            fortalezas=["a"],
            recomendaciones=["b"],
            comentario_general="ok",
        )
        assert r.nota == Decimal("85.00")
        assert r.ejercicio_external_ref == "uuid-ej-1"

    def test_NO_expone_una_nota_agregada_del_trabajo_practico(self):
        """El cliente dijo explícitamente que el promedio ponderado lo hace él."""
        campos = set(CorreccionEjercicioResponse.model_fields)

        assert "nota_tp" not in campos
        assert "nota_trabajo_practico" not in campos
        assert "promedio" not in campos
