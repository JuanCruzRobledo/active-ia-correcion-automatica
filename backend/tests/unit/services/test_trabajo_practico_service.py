"""
trabajos-practicos-y-external-ref: servicio de TPs y ejercicios.

Dos cosas no triviales acá.

**1. La traducción de rúbrica.** El cliente manda criterios planos con su propia
escala de puntaje (`{nombre, descripcion, puntaje_max}`), y la `Rubrica` de
Active-IA exige criterios con `peso` entero de 1 a 100 **que sumen exactamente
100**, cada uno con al menos un subcriterio con al menos una evidencia. La
normalización usa el método del resto mayor: repartir por redondeo simple no
garantiza que la suma cierre, y una rúbrica cuyos pesos no suman 100 la rechaza
el propio schema de Active-IA.

**2. La baja lógica en cascada.** Un ejercicio es dueño de su rúbrica (1:1). Dar
de baja el ejercicio sin dar de baja la rúbrica dejaría una rúbrica huérfana,
visible en los listados de la materia y sin ejercicio que la explique.
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ejercicio import Ejercicio
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.trabajo_practico import TrabajoPractico
from app.schemas.ejercicio import (
    CriterioEjercicioInput,
    EjercicioWriteRequest,
    RubricaEjercicioInput,
    TestCase,
)
from app.schemas.trabajo_practico import TrabajoPracticoWriteRequest
from app.services.trabajo_practico_service import (
    TrabajoPracticoService,
    normalizar_pesos,
    traducir_rubrica_del_cliente,
)

UNIV_ID = 1

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def materia(db_session: AsyncSession) -> Materia:
    m = Materia(
        universidad_id=UNIV_ID,
        codigo="PROG2",
        nombre="Programación 2",
        activa=True,
        external_ref="uuid-materia",
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


def _crit(nombre: str, puntaje: str) -> CriterioEjercicioInput:
    return CriterioEjercicioInput(
        nombre=nombre, descripcion=f"Descripción de {nombre}", puntaje_max=Decimal(puntaje)
    )


def _ejercicio(ref: str, orden: int, criterios=None) -> EjercicioWriteRequest:
    return EjercicioWriteRequest(
        external_ref=ref,
        orden=orden,
        titulo=f"E{orden}",
        enunciado_md="Consigna...",
        peso=Decimal("1"),
        rubrica=RubricaEjercicioInput(criterios=criterios or [_crit("C", "10")]),
    )


class TestNormalizacionDePesos:
    """Los pesos tienen que sumar EXACTAMENTE 100, o el schema rechaza la rúbrica."""

    def test_escala_simple(self):
        assert normalizar_pesos([Decimal("2"), Decimal("3"), Decimal("5")]) == [20, 30, 50]

    def test_un_solo_criterio_se_lleva_todo(self):
        assert normalizar_pesos([Decimal("7")]) == [100]

    def test_reparto_que_no_es_exacto_cierra_igual_en_cien(self):
        """1/3 cada uno da 33.33: el resto mayor decide quién se lleva el punto."""
        pesos = normalizar_pesos([Decimal("1"), Decimal("1"), Decimal("1")])
        assert sum(pesos) == 100
        assert sorted(pesos) == [33, 33, 34]

    def test_siete_criterios_iguales_cierran_en_cien(self):
        pesos = normalizar_pesos([Decimal("1")] * 7)
        assert sum(pesos) == 100

    def test_escala_grande_cierra_en_cien(self):
        pesos = normalizar_pesos([Decimal("17"), Decimal("23"), Decimal("41"), Decimal("19")])
        assert sum(pesos) == 100

    def test_todos_los_pesos_son_al_menos_uno(self):
        pesos = normalizar_pesos([Decimal("1"), Decimal("99")])
        assert min(pesos) >= 1
        assert sum(pesos) == 100

    def test_demasiados_criterios_para_la_escala_falla_claro(self):
        """Con más de 100 criterios no hay reparto entero posible que cierre."""
        with pytest.raises(ValueError) as exc:
            normalizar_pesos([Decimal("1")] * 101)
        assert "101" in str(exc.value)


class TestTraduccionDeRubrica:
    def test_los_criterios_reciben_id_por_orden(self):
        criterios = traducir_rubrica_del_cliente(
            [_crit("Excepción propia", "2"), _crit("Encapsulamiento", "3")]
        )
        assert [c["id"] for c in criterios] == ["C1", "C2"]

    def test_nombre_y_descripcion_pasan_tal_cual(self):
        criterios = traducir_rubrica_del_cliente([_crit("Excepción propia", "2")])
        assert criterios[0]["nombre"] == "Excepción propia"
        assert criterios[0]["descripcion"] == "Descripción de Excepción propia"

    def test_cada_criterio_recibe_un_subcriterio_con_evidencia(self):
        """`Criterio` exige subcriterios (min 1) y cada uno evidencias (min 1)."""
        criterios = traducir_rubrica_del_cliente([_crit("Excepción propia", "2")])
        subs = criterios[0]["subcriterios"]
        assert len(subs) == 1
        assert subs[0]["id"] == "C1.1"
        assert len(subs[0]["evidencias"]) >= 1

    def test_el_resultado_valida_contra_el_schema_de_rubrica_de_active_ia(self):
        """La prueba que importa: que Active-IA acepte lo traducido."""
        from app.schemas.rubrica import CriteriosStructure

        criterios = traducir_rubrica_del_cliente(
            [_crit("A", "2"), _crit("B", "3"), _crit("C", "5")]
        )
        estructura = CriteriosStructure(
            titulo="TP 2 JAVA - E1",
            descripcion="Rúbrica traducida desde el contrato del cliente",
            criterios=criterios,
        )
        assert sum(c.peso for c in estructura.criterios) == 100


class TestAltaDeTrabajoPractico:
    async def test_alta_con_cuatro_ejercicios_crea_tp_ejercicios_y_rubricas(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        req = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp-2",
            materia_external_ref="uuid-materia",
            titulo="TP 2 JAVA",
            ejercicios=[_ejercicio(f"uuid-ej-{i}", i) for i in range(1, 5)],
        )

        tp = await service.crear(req, materia=materia)
        await db_session.commit()

        assert tp.id is not None
        ejercicios = (
            (
                await db_session.execute(
                    select(Ejercicio).where(Ejercicio.trabajo_practico_id == tp.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(ejercicios) == 4

        rubricas = (
            (
                await db_session.execute(
                    select(Rubrica).where(Rubrica.materia_id == materia.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rubricas) == 4
        # Cada rúbrica pertenece a un ejercicio distinto: el 1:1.
        assert len({r.ejercicio_id for r in rubricas}) == 4

    async def test_los_test_cases_se_persisten_en_el_ejercicio(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        ej = _ejercicio("uuid-ej-casos", 1)
        ej.test_cases = [
            TestCase(
                id="t1", nombre="caso público", tipo="stdin_stdout",
                es_publico=True, entrada="a", salida_esperada="b",
            ),
            TestCase(id="t3", nombre="caso oculto", tipo="stdin_stdout", es_publico=False),
        ]
        req = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp-casos",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[ej],
        )

        tp = await service.crear(req, materia=materia)
        await db_session.commit()
        db_session.expunge_all()

        ejercicio = (
            (
                await db_session.execute(
                    select(Ejercicio).where(Ejercicio.trabajo_practico_id == tp.id)
                )
            )
            .scalars()
            .one()
        )
        assert len(ejercicio.test_cases) == 2
        oculto = next(c for c in ejercicio.test_cases if c["id"] == "t3")
        assert "salida_esperada" not in oculto

    async def test_la_rubrica_del_ejercicio_hereda_titulo_y_metadata_del_tp(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        req = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp-meta",
            materia_external_ref="uuid-materia",
            titulo="TP 2 JAVA",
            ejercicios=[_ejercicio("uuid-ej-meta", 1)],
        )

        await service.crear(req, materia=materia)
        await db_session.commit()

        rubrica = (
            (await db_session.execute(select(Rubrica).where(Rubrica.materia_id == materia.id)))
            .scalars()
            .one()
        )
        assert rubrica.universidad_id == UNIV_ID
        assert rubrica.puntaje_maximo == 100
        assert rubrica.ejercicio_id is not None
        # El vínculo con Moodle no se usa en este camino.
        assert rubrica.moodle_assign_id is None


class TestBajaLogicaEnCascada:
    async def test_dar_de_baja_un_ejercicio_da_de_baja_su_rubrica(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        req = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp-baja",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[_ejercicio("uuid-ej-baja", 1)],
        )
        tp = await service.crear(req, materia=materia)
        await db_session.commit()

        ejercicio = (
            (await db_session.execute(select(Ejercicio).where(Ejercicio.trabajo_practico_id == tp.id)))
            .scalars()
            .one()
        )
        rubrica_id = ejercicio.rubrica.id

        await service.dar_de_baja_ejercicio(ejercicio)
        await db_session.commit()
        db_session.expunge_all()

        ej_recargado = (
            await db_session.execute(select(Ejercicio).where(Ejercicio.id == ejercicio.id))
        ).scalar_one()
        rub_recargada = (
            await db_session.execute(select(Rubrica).where(Rubrica.id == rubrica_id))
        ).scalar_one()

        assert ej_recargado.deleted_at is not None
        # `Rubrica` NO hereda SoftDeleteMixin: su baja lógica es `activa = False`
        # (ver RubricaRepository.soft_delete). Son dos convenciones distintas
        # conviviendo, y la cascada usa la de cada entidad.
        assert rub_recargada.activa is False

    async def test_la_baja_no_elimina_filas_fisicamente(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        req = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp-fisico",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[_ejercicio("uuid-ej-fisico", 1)],
        )
        tp = await service.crear(req, materia=materia)
        await db_session.commit()

        ejercicio = (
            (await db_session.execute(select(Ejercicio).where(Ejercicio.trabajo_practico_id == tp.id)))
            .scalars()
            .one()
        )
        await service.dar_de_baja_ejercicio(ejercicio)
        await db_session.commit()

        total = len(
            (await db_session.execute(select(Ejercicio))).scalars().all()
        )
        assert total == 1, "la baja tiene que ser lógica, nunca física"

    async def test_reutilizar_el_external_ref_de_un_tp_dado_de_baja_es_valido(
        self, db_session: AsyncSession, materia: Materia
    ):
        """El índice parcial sobre `deleted_at IS NULL` es lo que lo permite."""
        service = TrabajoPracticoService(db_session)
        req = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp-reuso",
            materia_external_ref="uuid-materia",
            titulo="TP viejo",
            ejercicios=[],
        )
        tp_viejo = await service.crear(req, materia=materia)
        await db_session.commit()

        await service.dar_de_baja_trabajo_practico(tp_viejo)
        await db_session.commit()

        tp_nuevo = await service.crear(
            TrabajoPracticoWriteRequest(
                external_ref="uuid-tp-reuso",
                materia_external_ref="uuid-materia",
                titulo="TP nuevo",
                ejercicios=[],
            ),
            materia=materia,
        )
        await db_session.commit()

        assert tp_nuevo.id != tp_viejo.id
        assert tp_nuevo.titulo == "TP nuevo"
