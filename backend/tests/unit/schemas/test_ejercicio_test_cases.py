"""
trabajos-practicos-y-external-ref: validación de los casos de prueba.

Los `test_cases` **no son para que Active-IA los ejecute** — Active-IA no ejecuta
código, nunca. Viajan porque son parte del enunciado: que un caso espere que
pidiendo cupo 1 entren 2 personas le dice al motor cuál es la regla de negocio.
Sin eso, juzga el código sin saber qué se le pidió.

La regla dura (§3.3.1 del pedido, design D6): **los casos ocultos se almacenan
SIN su salida esperada ni su aserción**. No es desconfianza, es diseño — el PDF
de devolución se le entrega al alumno, y lo que el motor nunca recibió no lo
puede citar. Pedirle por escrito que no lo cite sería depender de que honre una
regla declarada, y de este motor ya está medido que no lo hace (el 2026-08-17 la
rúbrica pedía una penalización del 30% y aplicó 0%). Un caso oculto que aparezca
en una devolución deja de estar oculto para toda la cohorte.

Y se **rechaza** en vez de descartar en silencio: falla cuando el docente publica
el TP, que es barato, y no con un alumno esperando su corrección. Descartar en
silencio dejaría al cliente creyendo que su contrato se respeta mientras se le
limpia el payload.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.ejercicio import (
    CriterioEjercicioInput,
    EjercicioWriteRequest,
    RubricaEjercicioInput,
    TestCase,
)


def _caso(**over) -> dict:
    base = {
        "id": "t1",
        "nombre": "cupo alcanza para todos menos uno",
        "tipo": "stdin_stdout",
        "es_publico": True,
        "entrada": "EVT-1\nJornadas\n2\n",
        "salida_esperada": "Inscripto: Ana\n",
    }
    base.update(over)
    return base


def _rubrica_minima() -> RubricaEjercicioInput:
    return RubricaEjercicioInput(
        criterios=[
            CriterioEjercicioInput(
                nombre="Excepcion propia verificada",
                descripcion="CupoExcedidoException extiende Exception",
                puntaje_max=2,
            )
        ]
    )


class TestFormaBasicaDelCaso:
    def test_caso_publico_valido(self):
        c = TestCase(**_caso())
        assert c.id == "t1"
        assert c.tipo == "stdin_stdout"
        assert c.es_publico is True

    def test_tipo_desconocido_falla(self):
        with pytest.raises(ValidationError):
            TestCase(**_caso(tipo="doctest"))

    def test_caso_sin_id_falla(self):
        datos = _caso()
        del datos["id"]
        with pytest.raises(ValidationError):
            TestCase(**datos)

    def test_caso_sin_nombre_falla(self):
        datos = _caso()
        del datos["nombre"]
        with pytest.raises(ValidationError):
            TestCase(**datos)

    def test_id_vacio_falla(self):
        with pytest.raises(ValidationError):
            TestCase(**_caso(id="   "))


class TestCasosOcultos:
    """La regla que protege al caso oculto de aparecer en una devolución."""

    def test_caso_oculto_correcto_solo_guarda_lo_minimo(self):
        c = TestCase(
            id="t3",
            nombre="cupo 1 admite dos personas",
            tipo="stdin_stdout",
            es_publico=False,
        )
        assert c.salida_esperada is None
        assert c.asercion is None

    def test_caso_oculto_con_salida_esperada_se_rechaza(self):
        with pytest.raises(ValidationError) as exc:
            TestCase(
                id="t3",
                nombre="cupo 1 admite dos",
                tipo="stdin_stdout",
                es_publico=False,
                salida_esperada="Inscripto: Ana\n",
            )
        # El mensaje tiene que nombrar el caso: el docente publica desde una
        # interfaz y puede tener veinte ejercicios.
        assert "t3" in str(exc.value)

    def test_caso_oculto_con_asercion_se_rechaza(self):
        with pytest.raises(ValidationError) as exc:
            TestCase(
                id="t7",
                nombre="suma correcta",
                tipo="pytest_assert",
                es_publico=False,
                asercion="assert suma(2,3) == 5",
            )
        assert "t7" in str(exc.value)

    def test_caso_oculto_puede_traer_entrada(self):
        """La entrada no revela la regla; la salida esperada sí."""
        c = TestCase(
            id="t3",
            nombre="cupo 1",
            tipo="stdin_stdout",
            es_publico=False,
            entrada="EVT-1\n1\n",
        )
        assert c.entrada is not None
        assert c.salida_esperada is None


class TestTipoVersusCampos:
    """En los asserts el código ES el criterio; no va como entrada/salida."""

    def test_caso_de_asercion_publico_valido(self):
        c = TestCase(
            id="t9",
            nombre="suma",
            tipo="pytest_assert",
            es_publico=True,
            asercion="assert suma(2,3) == 5",
        )
        assert c.asercion == "assert suma(2,3) == 5"
        assert c.entrada is None
        assert c.salida_esperada is None

    def test_junit_assert_con_entrada_y_salida_se_rechaza(self):
        with pytest.raises(ValidationError) as exc:
            TestCase(
                id="t4",
                nombre="suma",
                tipo="junit_assert",
                es_publico=True,
                entrada="2 3",
                salida_esperada="5",
            )
        assert "t4" in str(exc.value)

    def test_pytest_assert_con_entrada_se_rechaza(self):
        with pytest.raises(ValidationError):
            TestCase(
                id="t5",
                nombre="suma",
                tipo="pytest_assert",
                es_publico=True,
                entrada="2 3",
                asercion="assert suma(2,3) == 5",
            )

    def test_stdin_stdout_con_asercion_se_rechaza(self):
        with pytest.raises(ValidationError) as exc:
            TestCase(
                id="t6",
                nombre="caso mixto",
                tipo="stdin_stdout",
                es_publico=True,
                entrada="2 3",
                asercion="assert True",
            )
        assert "t6" in str(exc.value)


class TestEjercicioWriteRequest:
    def test_ejercicio_valido(self):
        e = EjercicioWriteRequest(
            external_ref="uuid-ej-1",
            orden=1,
            titulo="TP2 E1 - Cupo excedido",
            enunciado_md="Implementar...",
            peso=Decimal("1.0"),
            rubrica=_rubrica_minima(),
            test_cases=[TestCase(**_caso())],
        )
        assert e.external_ref == "uuid-ej-1"
        assert len(e.test_cases) == 1

    def test_ids_de_caso_duplicados_dentro_del_ejercicio_se_rechazan(self):
        with pytest.raises(ValidationError) as exc:
            EjercicioWriteRequest(
                external_ref="uuid-ej-dup",
                orden=1,
                titulo="E1",
                rubrica=_rubrica_minima(),
                test_cases=[TestCase(**_caso(id="t1")), TestCase(**_caso(id="t1"))],
            )
        assert "t1" in str(exc.value)

    def test_external_ref_es_obligatorio(self):
        with pytest.raises(ValidationError):
            EjercicioWriteRequest(
                orden=1, titulo="E1", rubrica=_rubrica_minima()
            )

    def test_peso_debe_ser_mayor_que_cero(self):
        with pytest.raises(ValidationError):
            EjercicioWriteRequest(
                external_ref="uuid-ej-0",
                orden=1,
                titulo="E1",
                peso=Decimal("0"),
                rubrica=_rubrica_minima(),
            )

    def test_peso_por_defecto_es_uno(self):
        e = EjercicioWriteRequest(
            external_ref="uuid-ej-def",
            orden=1,
            titulo="E1",
            rubrica=_rubrica_minima(),
        )
        assert e.peso == Decimal("1")

    def test_ejercicio_sin_casos_de_prueba_es_valido(self):
        e = EjercicioWriteRequest(
            external_ref="uuid-ej-sin-casos",
            orden=1,
            titulo="E1",
            rubrica=_rubrica_minima(),
        )
        assert e.test_cases == []

    def test_rubrica_es_obligatoria(self):
        """Un ejercicio sin rúbrica no se puede corregir: no tiene sentido."""
        with pytest.raises(ValidationError):
            EjercicioWriteRequest(external_ref="uuid-x", orden=1, titulo="E1")


class TestRubricaDelCliente:
    def test_criterio_del_cliente_es_plano(self):
        """El cliente manda nombre + descripcion + puntaje_max, sin subcriterios."""
        c = CriterioEjercicioInput(
            nombre="Excepcion propia verificada",
            descripcion="CupoExcedidoException extiende Exception, no RuntimeException",
            puntaje_max=2,
        )
        assert c.puntaje_max == Decimal("2")

    def test_puntaje_max_debe_ser_mayor_que_cero(self):
        with pytest.raises(ValidationError):
            CriterioEjercicioInput(nombre="X", descripcion="Y", puntaje_max=0)

    def test_rubrica_sin_criterios_se_rechaza(self):
        with pytest.raises(ValidationError):
            RubricaEjercicioInput(criterios=[])
