"""
nota-deterministica-penalizaciones: el cálculo de la nota, como funciones puras.

Este módulo NO está cableado al flujo de corrección todavía. Existe primero para
que el script de diagnóstico (`scripts/diagnostico_nota_deterministica.py`)
calcule con código verificado y no con una fórmula reescrita a mano — si el
diagnóstico y la implementación futura divergen, el número que ve el coordinador
miente.

Qué arregla, cuando se cablee (bugs 2 y 3 del pedido de AI-Native):

- **Bug 2**: hoy las penalizaciones NO bajan la nota. `_nota_deterministica`
  (`correccion_service.py:162-193`) suma criterios y solo aplica el techo por
  condición de desaprobación; `_penalizaciones_validas` declara en su docstring
  que las penalizaciones "no alteran la nota, son solo auditoría/display". La
  aplicación del descuento vivía únicamente en el texto del prompt. Caso medido
  el 2026-08-17: 48+14+15+10+0 = 87, cuando con el 30% declarado daba ~61.
- **Bug 3**: el criterio no cierra con sus subcriterios. C5 figuraba 0/10 con
  subcriterios que sumaban 5. La invariante estaba declarada como instrucción de
  prompt y nunca se imponía en el backend.

Supuestos que el gate de gobernanza tiene que confirmar (design D1 y Open
Questions): los descuentos se calculan todos sobre la MISMA BASE (la suma de
criterios), no en cascada, y la nota se acota inferiormente en 0.
"""

from decimal import Decimal

import pytest

from app.services.correccion_nota import (
    calcular_nota,
    descuento_por_penalizaciones,
    recomputar_criterio_por_subcriterios,
)


def _pen(id_: str, pct: int, descripcion: str = "Penalización de prueba") -> dict:
    return {"id": id_, "descripcion": descripcion, "descuento_porcentaje": pct}


def _cd(id_: str, nota_maxima: int) -> dict:
    return {"id": id_, "descripcion": "Condición de prueba", "nota_maxima": nota_maxima}


def _crit(id_: str, obtenido, maximo, subcriterios=None) -> dict:
    c = {
        "id": id_,
        "nombre": f"Criterio {id_}",
        "puntaje_obtenido": Decimal(str(obtenido)),
        "puntaje_maximo": Decimal(str(maximo)),
        "estado": "OK",
        "feedback": "ok",
    }
    if subcriterios is not None:
        c["subcriterios_evaluados"] = subcriterios
    return c


def _sub(id_: str, obtenido, maximo) -> dict:
    return {
        "id": id_,
        "puntaje_obtenido": Decimal(str(obtenido)),
        "puntaje_maximo": Decimal(str(maximo)),
        "estado": "OK",
        "feedback": "ok",
    }


class TestDescuentoPorPenalizaciones:
    """El descuento sale de la RÚBRICA, no de lo que informe el modelo."""

    def test_penalizacion_del_30_por_ciento_sobre_el_total(self):
        """El caso medido el 2026-08-17: 87 con P1 al 30% tiene que dar 60.90."""
        descuento, detalle = descuento_por_penalizaciones(
            penalizaciones_rubrica=[_pen("P1", 30, "No entregó el informe")],
            ids_declarados=["P1"],
            suma=Decimal("87"),
        )

        assert descuento == Decimal("26.10")
        assert len(detalle) == 1
        assert detalle[0]["id"] == "P1"
        assert detalle[0]["descripcion"] == "No entregó el informe"
        assert detalle[0]["porcentaje"] == 30
        assert detalle[0]["puntos_descontados"] == Decimal("26.10")

    def test_dos_penalizaciones_sobre_la_misma_base_no_en_cascada(self):
        """20% + 30% sobre 100 da 50 de descuento, no 44 (que sería cascada)."""
        descuento, detalle = descuento_por_penalizaciones(
            penalizaciones_rubrica=[_pen("P1", 20), _pen("P2", 30)],
            ids_declarados=["P1", "P2"],
            suma=Decimal("100"),
        )

        assert descuento == Decimal("50.00")
        assert len(detalle) == 2

    def test_id_declarado_que_no_existe_en_la_rubrica_no_descuenta(self):
        """Defensa contra ids alucinados: el descuento sale de la rúbrica."""
        descuento, detalle = descuento_por_penalizaciones(
            penalizaciones_rubrica=[_pen("P1", 30)],
            ids_declarados=["P9"],
            suma=Decimal("87"),
        )

        assert descuento == Decimal("0")
        assert detalle == []

    def test_porcentaje_de_la_rubrica_manda_sobre_lo_que_informe_el_modelo(self):
        """El modelo declara QUÉ se incumplió; CUÁNTO descuenta lo dice la rúbrica."""
        descuento, _ = descuento_por_penalizaciones(
            penalizaciones_rubrica=[_pen("P1", 30)],
            # el modelo manda solo ids; si alguna vez mandara un porcentaje, se ignora
            ids_declarados=["P1"],
            suma=Decimal("100"),
        )

        assert descuento == Decimal("30.00")

    def test_sin_penalizaciones_declaradas_no_hay_descuento(self):
        descuento, detalle = descuento_por_penalizaciones(
            penalizaciones_rubrica=[_pen("P1", 30)],
            ids_declarados=[],
            suma=Decimal("87"),
        )

        assert descuento == Decimal("0")
        assert detalle == []

    def test_ids_declarados_none_no_rompe(self):
        """El modelo puede omitir el campo entero."""
        descuento, detalle = descuento_por_penalizaciones(
            penalizaciones_rubrica=[_pen("P1", 30)],
            ids_declarados=None,
            suma=Decimal("87"),
        )

        assert descuento == Decimal("0")
        assert detalle == []


class TestRecomputoPorSubcriterios:
    """Bug 3: el criterio tiene que cerrar con sus subcriterios en rúbricas v2."""

    def test_criterio_en_cero_con_subcriterios_que_suman_cinco(self):
        """El caso C5 del 2026-08-17: figuraba 0/10 con subcriterios que sumaban 5."""
        criterio = _crit(
            "C5", 0, 10, subcriterios=[_sub("C5.1", 3, 6), _sub("C5.2", 2, 4)]
        )

        obtenido, hubo_discrepancia = recomputar_criterio_por_subcriterios(
            criterio, peso_criterio=Decimal("10")
        )

        assert obtenido == Decimal("5")
        assert hubo_discrepancia is True

    def test_criterio_que_ya_cierra_no_marca_discrepancia(self):
        criterio = _crit(
            "C1", 5, 10, subcriterios=[_sub("C1.1", 3, 6), _sub("C1.2", 2, 4)]
        )

        obtenido, hubo_discrepancia = recomputar_criterio_por_subcriterios(
            criterio, peso_criterio=Decimal("10")
        )

        assert obtenido == Decimal("5")
        assert hubo_discrepancia is False

    def test_subcriterio_por_encima_de_su_maximo_se_acota(self):
        criterio = _crit("C1", 7, 10, subcriterios=[_sub("C1.1", 7, 4)])

        obtenido, _ = recomputar_criterio_por_subcriterios(
            criterio, peso_criterio=Decimal("10")
        )

        assert obtenido == Decimal("4")

    def test_suma_de_subcriterios_por_encima_del_peso_se_acota_al_peso(self):
        """Un subcriterio alucinado de más no puede inflar el criterio."""
        criterio = _crit(
            "C1",
            13,
            10,
            subcriterios=[_sub("C1.1", 6, 6), _sub("C1.2", 4, 4), _sub("C1.3", 3, 3)],
        )

        obtenido, _ = recomputar_criterio_por_subcriterios(
            criterio, peso_criterio=Decimal("10")
        )

        assert obtenido == Decimal("10")

    def test_criterio_sin_desglose_devuelve_su_puntaje_tal_cual(self):
        criterio = _crit("C1", 7, 10)

        obtenido, hubo_discrepancia = recomputar_criterio_por_subcriterios(
            criterio, peso_criterio=Decimal("10")
        )

        assert obtenido == Decimal("7")
        assert hubo_discrepancia is False

    def test_criterio_con_desglose_vacio_devuelve_su_puntaje_tal_cual(self):
        criterio = _crit("C1", 7, 10, subcriterios=[])

        obtenido, hubo_discrepancia = recomputar_criterio_por_subcriterios(
            criterio, peso_criterio=Decimal("10")
        )

        assert obtenido == Decimal("7")
        assert hubo_discrepancia is False


class TestCalcularNota:
    """La cadena completa: suma → descuento → piso en 0 → techo por condición."""

    def test_caso_medido_2026_08_17(self):
        """48+14+15+10+0 = 87 con una penalización del 30% declarada → ~61."""
        criterios = [
            _crit("C1", 48, 50),
            _crit("C2", 14, 15),
            _crit("C3", 15, 15),
            _crit("C4", 10, 10),
            _crit("C5", 0, 10),
        ]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[_pen("P1", 30, "Reducción del 30% del total")],
            condiciones_rubrica=[],
            ids_penalizaciones_declaradas=["P1"],
            id_condicion_declarada=None,
            schema_version=1,
            pesos_por_criterio={},
        )

        assert r.suma_criterios == Decimal("87.00")
        assert r.nota_antes_penalizaciones == Decimal("87.00")
        assert r.nota_final == Decimal("60.90")

    def test_sin_penalizaciones_ni_condicion_la_nota_es_la_suma(self):
        """Caracterización: el camino que hoy anda bien no cambia."""
        criterios = [_crit("C1", 40, 50), _crit("C2", 30, 50)]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[],
            condiciones_rubrica=[],
            ids_penalizaciones_declaradas=[],
            id_condicion_declarada=None,
            schema_version=1,
            pesos_por_criterio={},
        )

        assert r.nota_final == Decimal("70.00")
        assert r.nota_antes_penalizaciones is None
        assert r.descuento_total == Decimal("0")

    def test_descuento_que_excederia_el_piso_deja_la_nota_en_cero(self):
        criterios = [_crit("C1", 20, 100)]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[_pen("P1", 100), _pen("P2", 50)],
            condiciones_rubrica=[],
            ids_penalizaciones_declaradas=["P1", "P2"],
            id_condicion_declarada=None,
            schema_version=1,
            pesos_por_criterio={},
        )

        assert r.nota_final == Decimal("0.00")

    def test_penalizacion_y_condicion_de_desaprobacion_manda_el_techo(self):
        """80 con 25% de descuento da 60; el techo de 40 lo baja a 40."""
        criterios = [_crit("C1", 80, 100)]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[_pen("P1", 25)],
            condiciones_rubrica=[_cd("CD1", 40)],
            ids_penalizaciones_declaradas=["P1"],
            id_condicion_declarada="CD1",
            schema_version=1,
            pesos_por_criterio={},
        )

        assert r.suma_criterios == Decimal("80.00")
        assert r.descuento_total == Decimal("20.00")
        assert r.nota_final == Decimal("40.00")
        assert r.condicion_aplicada == "CD1"

    def test_techo_por_encima_de_la_nota_penada_no_se_aplica(self):
        """80 con 50% da 40, que ya está por debajo del techo de 60."""
        criterios = [_crit("C1", 80, 100)]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[_pen("P1", 50)],
            condiciones_rubrica=[_cd("CD1", 60)],
            ids_penalizaciones_declaradas=["P1"],
            id_condicion_declarada="CD1",
            schema_version=1,
            pesos_por_criterio={},
        )

        assert r.nota_final == Decimal("40.00")

    def test_condicion_declarada_inexistente_se_ignora(self):
        """Caracterización del comportamiento actual: id alucinado no aplica techo."""
        criterios = [_crit("C1", 80, 100)]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[],
            condiciones_rubrica=[_cd("CD1", 40)],
            ids_penalizaciones_declaradas=[],
            id_condicion_declarada="CD9",
            schema_version=1,
            pesos_por_criterio={},
        )

        assert r.nota_final == Decimal("80.00")
        assert r.condicion_aplicada is None

    def test_v2_recomputa_los_criterios_antes_de_sumar(self):
        """Bug 3 + bug 2 juntos: el desglose corrige la suma y después descuenta."""
        criterios = [
            _crit("C1", 40, 50, subcriterios=[_sub("C1.1", 25, 30), _sub("C1.2", 15, 20)]),
            _crit("C5", 0, 10, subcriterios=[_sub("C5.1", 3, 6), _sub("C5.2", 2, 4)]),
        ]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[],
            condiciones_rubrica=[],
            ids_penalizaciones_declaradas=[],
            id_condicion_declarada=None,
            schema_version=2,
            pesos_por_criterio={"C1": Decimal("50"), "C5": Decimal("10")},
        )

        # C1 cierra en 40, C5 pasa de 0 a 5 → 45, no 40
        assert r.suma_criterios == Decimal("45.00")
        assert r.nota_final == Decimal("45.00")
        assert "C5" in r.criterios_con_discrepancia

    def test_v1_no_recomputa_aunque_venga_desglose(self):
        """Caracterización: v1 corrige exactamente igual que antes del change."""
        criterios = [
            _crit("C5", 0, 10, subcriterios=[_sub("C5.1", 3, 6), _sub("C5.2", 2, 4)])
        ]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[],
            condiciones_rubrica=[],
            ids_penalizaciones_declaradas=[],
            id_condicion_declarada=None,
            schema_version=1,
            pesos_por_criterio={"C5": Decimal("10")},
        )

        assert r.suma_criterios == Decimal("0.00")
        assert r.criterios_con_discrepancia == []

    def test_la_nota_se_cuantiza_una_sola_vez_al_final(self):
        """Cuantizar en cada paso arrastra error; el redondeo va al final."""
        criterios = [_crit("C1", "33.333", 50), _crit("C2", "33.333", 50)]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[_pen("P1", 33)],
            condiciones_rubrica=[],
            ids_penalizaciones_declaradas=["P1"],
            id_condicion_declarada=None,
            schema_version=1,
            pesos_por_criterio={},
        )

        # 66.666 - (66.666 * 0.33 = 21.99978) = 44.66622 → 44.67
        assert r.nota_final == Decimal("44.67")

    def test_resultado_expone_el_detalle_para_auditoria(self):
        criterios = [_crit("C1", 87, 100)]

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=[_pen("P1", 30, "Repositorio inaccesible")],
            condiciones_rubrica=[],
            ids_penalizaciones_declaradas=["P1"],
            id_condicion_declarada=None,
            schema_version=1,
            pesos_por_criterio={},
        )

        assert r.penalizaciones_aplicadas == ["P1"]
        assert r.detalle_descuentos[0]["descripcion"] == "Repositorio inaccesible"
        assert r.detalle_descuentos[0]["puntos_descontados"] == Decimal("26.10")


class TestComportamientoActualParaElDiagnostico:
    """La fórmula VIEJA, para que el script pueda comparar contra ella.

    Es la que hoy vive en `_nota_deterministica`: suma de criterios, techo por
    condición, penalizaciones ignoradas.
    """

    def test_nota_actual_ignora_las_penalizaciones(self):
        from app.services.correccion_nota import calcular_nota_actual

        criterios = [_crit("C1", 87, 100)]

        nota = calcular_nota_actual(
            criterios_evaluados=criterios,
            condiciones_rubrica=[_pen("P1", 30)],
            id_condicion_declarada=None,
        )

        assert nota == Decimal("87.00")

    def test_nota_actual_aplica_el_techo_por_condicion(self):
        from app.services.correccion_nota import calcular_nota_actual

        criterios = [_crit("C1", 87, 100)]

        nota = calcular_nota_actual(
            criterios_evaluados=criterios,
            condiciones_rubrica=[_cd("CD1", 40)],
            id_condicion_declarada="CD1",
        )

        assert nota == Decimal("40.00")
