"""
trabajos-practicos-y-external-ref: contrato de escritura y de respuesta del TP.

Dos invariantes que parecen detalles y no lo son:

1. **El peso de los ejercicios NO se valida contra ningún total** (design D7). El
   cliente dijo explícitamente que Active-IA no calcula la nota final del TP: el
   promedio ponderado lo hace él. Exigir que sumen 100 impondría una restricción
   que el consumidor no pidió y rompería publicaciones legítimas.

2. **La respuesta devuelve `rubrica_id` por ejercicio.** Es lo que le permite al
   cliente saber con qué rúbrica se corrige cada uno. Emparejar por orden o por
   título sería adivinar, y elegir mal no da una nota floja: corrige otra cosa.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.ejercicio import (
    CriterioEjercicioInput,
    EjercicioResponse,
    EjercicioWriteRequest,
    RubricaEjercicioInput,
)
from app.schemas.trabajo_practico import (
    TrabajoPracticoResponse,
    TrabajoPracticoWriteRequest,
)


def _rubrica() -> RubricaEjercicioInput:
    return RubricaEjercicioInput(
        criterios=[
            CriterioEjercicioInput(nombre="C", descripcion="D", puntaje_max=10)
        ]
    )


def _ejercicio(ref: str, orden: int, peso: str = "1") -> EjercicioWriteRequest:
    return EjercicioWriteRequest(
        external_ref=ref,
        orden=orden,
        titulo=f"E{orden}",
        enunciado_md="...",
        peso=Decimal(peso),
        rubrica=_rubrica(),
    )


class TestTrabajoPracticoWriteRequest:
    def test_alta_con_cuatro_ejercicios(self):
        tp = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp",
            materia_external_ref="uuid-materia",
            titulo="TP 2 JAVA",
            ejercicios=[_ejercicio(f"uuid-ej-{i}", i) for i in range(1, 5)],
        )
        assert len(tp.ejercicios) == 4
        assert tp.materia_external_ref == "uuid-materia"

    def test_external_ref_del_tp_es_obligatorio(self):
        with pytest.raises(ValidationError):
            TrabajoPracticoWriteRequest(
                materia_external_ref="uuid-materia", titulo="TP", ejercicios=[]
            )

    def test_materia_external_ref_es_obligatorio(self):
        """Un id numérico ajeno obligaría al cliente a mantener un mapeo que vence."""
        with pytest.raises(ValidationError):
            TrabajoPracticoWriteRequest(
                external_ref="uuid-tp", titulo="TP", ejercicios=[]
            )

    def test_tp_sin_ejercicios_es_valido(self):
        """Estado intermedio legítimo durante la creación."""
        tp = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[],
        )
        assert tp.ejercicios == []

    def test_los_pesos_no_se_validan_contra_ningun_total(self):
        """Cuatro ejercicios de peso 1 es válido; también 3.5 + 0.5."""
        tp = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[_ejercicio(f"uuid-ej-{i}", i) for i in range(1, 5)],
        )
        assert sum(e.peso for e in tp.ejercicios) == Decimal("4")

        tp2 = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp2",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[
                _ejercicio("uuid-a", 1, peso="3.5"),
                _ejercicio("uuid-b", 2, peso="0.5"),
            ],
        )
        assert sum(e.peso for e in tp2.ejercicios) == Decimal("4.0")


class TestRespuesta:
    def test_la_respuesta_del_ejercicio_trae_rubrica_id(self):
        r = EjercicioResponse(
            id=10,
            external_ref="uuid-ej-1",
            orden=1,
            titulo="E1",
            peso=Decimal("1.00"),
            rubrica_id=99,
            enunciado_md="...",
            test_cases=[],
        )
        assert r.rubrica_id == 99
        assert r.external_ref == "uuid-ej-1"

    def test_la_respuesta_del_tp_trae_sus_ejercicios(self):
        tp = TrabajoPracticoResponse(
            id=1,
            external_ref="uuid-tp",
            materia_id=7,
            titulo="TP 2 JAVA",
            descripcion=None,
            ejercicios=[
                EjercicioResponse(
                    id=10 + i,
                    external_ref=f"uuid-ej-{i}",
                    orden=i,
                    titulo=f"E{i}",
                    peso=Decimal("1.00"),
                    rubrica_id=100 + i,
                    enunciado_md=None,
                    test_cases=[],
                )
                for i in range(1, 5)
            ],
        )
        assert len(tp.ejercicios) == 4
        # Cada ejercicio identificable por SU referencia, con SU rúbrica.
        assert {e.external_ref: e.rubrica_id for e in tp.ejercicios} == {
            "uuid-ej-1": 101,
            "uuid-ej-2": 102,
            "uuid-ej-3": 103,
            "uuid-ej-4": 104,
        }


class TestInvariantesDelPush:
    """Lo que se rechaza dentro de un mismo cuerpo, antes de tocar la base."""

    def test_dos_ejercicios_con_el_mismo_external_ref_se_rechazan(self):
        """La reconciliacion empareja por external_ref: dos iguales la vuelven
        ambigua, y el indice unico parcial los rechazaria despues igual. Mejor
        fallar aca, con el identificador nombrado."""
        with pytest.raises(ValidationError) as exc:
            TrabajoPracticoWriteRequest(
                external_ref="uuid-tp",
                materia_external_ref="uuid-materia",
                titulo="TP",
                ejercicios=[_ejercicio("uuid-repetido", 1), _ejercicio("uuid-repetido", 2)],
            )
        assert "uuid-repetido" in str(exc.value)

    def test_demasiados_ejercicios_en_un_tp_se_rechazan(self):
        """Limite explicito en vez de un timeout o un payload que revienta."""
        with pytest.raises(ValidationError):
            TrabajoPracticoWriteRequest(
                external_ref="uuid-tp",
                materia_external_ref="uuid-materia",
                titulo="TP",
                ejercicios=[_ejercicio(f"uuid-{i}", i) for i in range(1, 60)],
            )

    def test_un_tp_con_muchos_ejercicios_pero_dentro_del_limite_es_valido(self):
        tp = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[_ejercicio(f"uuid-{i}", i) for i in range(1, 21)],
        )
        assert len(tp.ejercicios) == 20
