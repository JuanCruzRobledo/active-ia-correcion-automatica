"""
correccion-por-ejercicio-con-tests, bloques 3 y 4: criterios que dependen de que
el programa corra.

**Lo que pidió el cliente, textual**: "con `compila: false`, no cierren criterios
del tipo 'el programa funciona'. Ninguna corrida los respalda."

Y acá está la decisión que define este change: **eso NO puede vivir en el
prompt.** Ponerlo ahí sería repetir exactamente el bug 2, donde la rúbrica pedía
una penalización del 30% y el motor aplicó 0%. De este motor ya está medido que
no honra reglas declaradas en su propia rúbrica.

Así que la garantía es determinística en el backend. Pero para eso hace falta un
dato que SOLO la rúbrica tiene: cuál de sus criterios necesita que el programa
corra. El backend no puede adivinarlo — "usó la interfaz o enumeró los tipos
concretos" no depende de la ejecución; "el programa produce la salida esperada",
sí.

De ahí `Criterio.depende_de_ejecucion`, con default `false` para que ninguna
rúbrica existente cambie de comportamiento.

Y la simetría que importa: **compilar y fallar todo NO fuerza nada**. Es la
distinción que el cliente agregó el 19/08. Forzar los dos casos en cero borraría
la diferencia que motivó el pedido.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.correccion import CriterioEvaluado, ResultadoTests
from app.schemas.rubrica import Criterio
from app.services.correccion_ejecucion import forzar_criterios_de_ejecucion


def _criterio_rubrica(depende: bool | None = None) -> dict:
    base = {
        "id": "C1",
        "nombre": "El programa produce la salida esperada",
        "descripcion": "Corre y produce la salida pedida",
        "peso": 40,
        "subcriterios": [
            {"id": "C1.1", "descripcion": "Corre", "evidencias": ["Se ejecuta"]}
        ],
    }
    if depende is not None:
        base["depende_de_ejecucion"] = depende
    return base


def _evaluado(cid="C1", puntaje=40, maximo=40, estado="OK"):
    return CriterioEvaluado(
        id=cid,
        nombre=f"Criterio {cid}",
        puntaje_obtenido=Decimal(str(puntaje)),
        puntaje_maximo=Decimal(str(maximo)),
        estado=estado,
        feedback="El programa funciona correctamente.",
    )


def _resultado(compila=True, pasados=4, total=4, error=None):
    return ResultadoTests(
        compila=compila, error_compilacion=error, total=total, pasados=pasados, casos=[]
    )


class TestCampoEnLaRubrica:
    def test_el_criterio_acepta_la_marca(self):
        c = Criterio(**_criterio_rubrica(depende=True))
        assert c.depende_de_ejecucion is True

    def test_por_defecto_es_falso(self):
        """Ninguna rúbrica existente cambia de comportamiento."""
        c = Criterio(**_criterio_rubrica())
        assert c.depende_de_ejecucion is False

    def test_no_acepta_cualquier_cosa(self):
        with pytest.raises(ValidationError):
            Criterio(**{**_criterio_rubrica(), "depende_de_ejecucion": "quizás"})


class TestForzadoPorNoCompilar:
    def test_criterio_marcado_se_cierra_en_cero(self):
        forzados, ids = forzar_criterios_de_ejecucion(
            [_evaluado()],
            resultado_tests=_resultado(compila=False, pasados=0, total=6,
                                       error="Main.java:12: error: ';' expected"),
            criterios_rubrica=[_criterio_rubrica(depende=True)],
        )

        assert forzados[0].puntaje_obtenido == Decimal("0")
        assert forzados[0].estado == "ERROR"
        assert ids == ["C1"]

    def test_el_feedback_cita_el_error_del_compilador(self):
        """Que el alumno sepa QUÉ arreglar, no solo que no compiló."""
        forzados, _ = forzar_criterios_de_ejecucion(
            [_evaluado()],
            resultado_tests=_resultado(compila=False, pasados=0, total=6,
                                       error="Main.java:12: error: ';' expected"),
            criterios_rubrica=[_criterio_rubrica(depende=True)],
        )

        assert "';' expected" in forzados[0].feedback

    def test_descarta_el_puntaje_que_haya_puesto_el_modelo(self):
        """El motor puede haber cerrado el criterio igual; no importa."""
        forzados, _ = forzar_criterios_de_ejecucion(
            [_evaluado(puntaje=40)],
            resultado_tests=_resultado(compila=False, pasados=0, total=6),
            criterios_rubrica=[_criterio_rubrica(depende=True)],
        )

        assert forzados[0].puntaje_obtenido == Decimal("0")

    def test_los_criterios_de_diseno_conservan_su_puntaje(self):
        """El juicio sobre diseño sigue siendo útil y es lo que un compilador no da.

        Es la razón por la que el cliente manda el código aunque no compile."""
        criterios_rubrica = [
            _criterio_rubrica(depende=True),
            {**_criterio_rubrica(depende=False), "id": "C2",
             "nombre": "La excepción es verificada"},
        ]
        forzados, ids = forzar_criterios_de_ejecucion(
            [_evaluado("C1", 40), _evaluado("C2", 30, 30)],
            resultado_tests=_resultado(compila=False, pasados=0, total=6),
            criterios_rubrica=criterios_rubrica,
        )

        por_id = {c.id: c for c in forzados}
        assert por_id["C1"].puntaje_obtenido == Decimal("0")
        assert por_id["C2"].puntaje_obtenido == Decimal("30")
        assert ids == ["C1"]


class TestLoQueNoSeFuerza:
    def test_compila_y_falla_todo_NO_fuerza_nada(self):
        """La distinción del 2026-08-19.

        Mismo 0/6 que el caso de arriba, situación distinta: el programa corre y
        hace otra cosa. Forzar los dos borraría la diferencia que motivó el
        pedido."""
        forzados, ids = forzar_criterios_de_ejecucion(
            [_evaluado(puntaje=40)],
            resultado_tests=_resultado(compila=True, pasados=0, total=6),
            criterios_rubrica=[_criterio_rubrica(depende=True)],
        )

        assert forzados[0].puntaje_obtenido == Decimal("40")
        assert ids == []

    def test_sin_resultado_de_tests_no_fuerza_nada(self):
        """Un cliente que no ejecute código no puede ser penalizado por eso."""
        forzados, ids = forzar_criterios_de_ejecucion(
            [_evaluado(puntaje=40)],
            resultado_tests=None,
            criterios_rubrica=[_criterio_rubrica(depende=True)],
        )

        assert forzados[0].puntaje_obtenido == Decimal("40")
        assert ids == []

    def test_rubrica_sin_criterios_marcados_no_fuerza_nada(self):
        """Si nadie marcó nada, la garantía no aplica — y no puede aplicar."""
        forzados, ids = forzar_criterios_de_ejecucion(
            [_evaluado(puntaje=40)],
            resultado_tests=_resultado(compila=False, pasados=0, total=6),
            criterios_rubrica=[_criterio_rubrica(depende=False)],
        )

        assert forzados[0].puntaje_obtenido == Decimal("40")
        assert ids == []

    def test_criterio_que_no_esta_en_la_rubrica_no_se_toca(self):
        """Defensa contra un id alucinado por el modelo."""
        forzados, ids = forzar_criterios_de_ejecucion(
            [_evaluado("C9", 40)],
            resultado_tests=_resultado(compila=False, pasados=0, total=6),
            criterios_rubrica=[_criterio_rubrica(depende=True)],
        )

        assert forzados[0].puntaje_obtenido == Decimal("40")
        assert ids == []


class TestNoRompeLoViejo:
    def test_lista_vacia(self):
        forzados, ids = forzar_criterios_de_ejecucion(
            [], resultado_tests=_resultado(compila=False), criterios_rubrica=[]
        )
        assert forzados == []
        assert ids == []

    def test_rubrica_sin_la_clave_en_sus_criterios(self):
        """Rúbricas anteriores al change: la clave ni siquiera existe."""
        forzados, ids = forzar_criterios_de_ejecucion(
            [_evaluado(puntaje=40)],
            resultado_tests=_resultado(compila=False, pasados=0, total=6),
            criterios_rubrica=[_criterio_rubrica()],
        )

        assert forzados[0].puntaje_obtenido == Decimal("40")
        assert ids == []


class TestTrazabilidadPersistida:
    """5.7 — la corrida con la que se corrigio queda GUARDADA junto a la correccion.

    Sin esto, dentro de tres meses una nota rara no se puede auditar: no habria
    forma de saber si el motor tenia los tests a la vista ni que decian.

    Va como clave hermana de `criterios` dentro del JSONB que ya existe, sin
    migracion, y los consumidores que leen `criterios_json["criterios"]` no se
    enteran del campo nuevo.
    """

    def test_el_response_expone_los_criterios_forzados(self):
        from app.schemas.correccion import CorreccionResponse

        assert "criterios_sin_ejecucion" in CorreccionResponse.model_fields

    def test_se_leen_de_la_clave_hermana_en_criterios_json(self):
        from datetime import datetime
        from types import SimpleNamespace

        from app.schemas.correccion import CorreccionResponse

        fila = SimpleNamespace(
            id=1, entrega_id=1, nota=Decimal("40"), nota_antes_penalizaciones=None,
            condicion_desaprobacion_aplicada=None, penalizaciones_aplicadas=[],
            criterios_json={
                "criterios": [],
                "resultado_tests": {"compila": False, "total": 6, "pasados": 0},
                "criterios_sin_ejecucion": ["C1", "C3"],
            },
            fortalezas=[], recomendaciones=[], comentario_general="ok",
            editado_manualmente=False, corregido_por_id=1,
            created_at=datetime(2026, 8, 24), updated_at=datetime(2026, 8, 24),
        )

        r = CorreccionResponse.model_validate(fila)

        assert r.criterios_sin_ejecucion == ["C1", "C3"]

    def test_correccion_vieja_sin_la_clave_no_rompe(self):
        """Todo lo anterior al change: la clave ni siquiera existe."""
        from datetime import datetime
        from types import SimpleNamespace

        from app.schemas.correccion import CorreccionResponse

        fila = SimpleNamespace(
            id=1, entrega_id=1, nota=Decimal("90"), nota_antes_penalizaciones=None,
            condicion_desaprobacion_aplicada=None, penalizaciones_aplicadas=[],
            criterios_json={"criterios": []},
            fortalezas=[], recomendaciones=[], comentario_general="ok",
            editado_manualmente=False, corregido_por_id=1,
            created_at=datetime(2026, 7, 1), updated_at=datetime(2026, 7, 1),
        )

        r = CorreccionResponse.model_validate(fila)

        assert r.criterios_sin_ejecucion == []
