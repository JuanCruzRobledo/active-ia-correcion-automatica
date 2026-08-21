"""
trabajos-practicos-y-external-ref: modelo del nivel de ejercicio.

AI-Native corrige un TP compuesto por N ejercicios, y necesita corregir **de a
uno**. Con el modelo actual los cuatro ejercicios de un TP tendrían que
compartir una sola rúbrica, lo que activa un modo de fallo ya medido del motor
(distingue presencia, no vínculo): una pieza del ejercicio 3 puede contar como
cumplimiento de un criterio del 1.

Decisión de arquitectura (design D1): **un ejercicio es dueño de una `Rubrica`
existente**, no de un modelo de rúbrica paralelo. La `Rubrica` de Active-IA ya
tiene criterios jerárquicos, subcriterios con peso, penalizaciones y
condiciones de desaprobación — es estrictamente más expresiva que el
`{criterios: [{nombre, descripcion, puntaje_max}]}` que manda el cliente. Así
el motor de corrección, el PDF, el historial y el frontend no se tocan.

El punto no obvio (design D3): `uq_rubrica_materia_tipo_numero_anio` **impide**
hoy que cuatro ejercicios del mismo TP tengan cuatro rúbricas, porque las
cuatro comparten `(materia_id, tipo, numero, anio)`. Pasa a ser un índice único
**parcial** sobre `ejercicio_id IS NULL`, replicando el patrón que el repo ya
usa en `uq_entrega_rubrica_alumno`. Las rúbricas de Moodle conservan
exactamente la unicidad que tienen hoy.
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comision import Comision
from app.models.ejercicio import Ejercicio
from app.models.enums import TipoRubricaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.trabajo_practico import TrabajoPractico

UNIV_ID = 1

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def materia(db_session: AsyncSession) -> Materia:
    m = Materia(
        universidad_id=UNIV_ID, codigo="PROG2", nombre="Programación 2", activa=True
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


@pytest_asyncio.fixture
async def tp(db_session: AsyncSession, materia: Materia) -> TrabajoPractico:
    t = TrabajoPractico(
        universidad_id=UNIV_ID,
        materia_id=materia.id,
        external_ref="uuid-tp-2-java",
        titulo="TP 2 JAVA",
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


def _rubrica_de_ejercicio(materia_id: int, ejercicio_id: int, titulo: str) -> Rubrica:
    """Rúbrica que pertenece a un ejercicio: misma clave que sus hermanas."""
    return Rubrica(
        universidad_id=UNIV_ID,
        materia_id=materia_id,
        tipo=TipoRubricaEnum.TP,
        titulo=titulo,
        descripcion="Rúbrica del ejercicio",
        puntaje_maximo=100,
        numero=2,
        anio=2026,
        criterios_json=[],
        activa=True,
        ejercicio_id=ejercicio_id,
    )


class TestTrabajoPractico:
    async def test_alta_con_materia_y_referencia_externa(
        self, db_session: AsyncSession, materia: Materia
    ):
        t = TrabajoPractico(
            universidad_id=UNIV_ID,
            materia_id=materia.id,
            external_ref="uuid-tp-1",
            titulo="TP 1",
        )
        db_session.add(t)
        await db_session.commit()
        await db_session.refresh(t)

        assert t.id is not None
        assert t.universidad_id == UNIV_ID
        assert t.materia_id == materia.id
        assert t.deleted_at is None

    async def test_puede_existir_sin_ejercicios(self, tp: TrabajoPractico):
        """Estado intermedio legítimo durante la creación."""
        assert tp.ejercicios == []

    async def test_baja_logica_no_elimina_la_fila(
        self, db_session: AsyncSession, tp: TrabajoPractico
    ):
        from datetime import datetime

        tp.deleted_at = datetime.utcnow()
        await db_session.commit()

        vivo = (
            await db_session.execute(
                select(TrabajoPractico).where(TrabajoPractico.id == tp.id)
            )
        ).scalar_one()
        assert vivo is not None
        assert vivo.is_deleted is True


class TestEjercicio:
    async def test_alta_dentro_de_un_trabajo_practico(
        self, db_session: AsyncSession, materia: Materia, tp: TrabajoPractico
    ):
        e = Ejercicio(
            universidad_id=UNIV_ID,
            materia_id=materia.id,
            trabajo_practico_id=tp.id,
            external_ref="uuid-ej-1",
            orden=1,
            titulo="TP2 E1 - Cupo excedido",
            enunciado_md="Implementar la excepción...",
            peso=Decimal("1.0"),
        )
        db_session.add(e)
        await db_session.commit()
        await db_session.refresh(e)

        assert e.id is not None
        assert e.materia_id == materia.id
        assert e.trabajo_practico_id == tp.id
        assert e.deleted_at is None

    async def test_peso_por_defecto_es_uno(
        self, db_session: AsyncSession, materia: Materia, tp: TrabajoPractico
    ):
        e = Ejercicio(
            universidad_id=UNIV_ID,
            materia_id=materia.id,
            trabajo_practico_id=tp.id,
            external_ref="uuid-ej-sin-peso",
            orden=1,
            titulo="E1",
            enunciado_md="...",
        )
        db_session.add(e)
        await db_session.commit()
        await db_session.refresh(e)

        assert Decimal(str(e.peso)) == Decimal("1.00")

    async def test_los_ejercicios_del_tp_vienen_ordenados_por_orden(
        self, db_session: AsyncSession, materia: Materia, tp: TrabajoPractico
    ):
        for orden in (3, 1, 2):
            db_session.add(
                Ejercicio(
                    universidad_id=UNIV_ID,
                    materia_id=materia.id,
                    trabajo_practico_id=tp.id,
                    external_ref=f"uuid-ej-{orden}",
                    orden=orden,
                    titulo=f"E{orden}",
                    enunciado_md="...",
                )
            )
        await db_session.commit()
        # El TP ya está en el identity map con su colección (vacía) cargada, así
        # que un select devolvería la foto vieja. `expunge_all` lo saca de la
        # sesión para que el select siguiente lo reconstruya con su selectin —
        # `expire_all` no sirve acá: dispara una carga lazy fuera del greenlet.
        db_session.expunge_all()

        recargado = (
            await db_session.execute(
                select(TrabajoPractico).where(TrabajoPractico.id == tp.id)
            )
        ).scalar_one()
        assert [e.orden for e in recargado.ejercicios] == [1, 2, 3]

    async def test_test_cases_se_persisten(
        self, db_session: AsyncSession, materia: Materia, tp: TrabajoPractico
    ):
        casos = [
            {
                "id": "t1",
                "nombre": "cupo alcanza",
                "tipo": "stdin_stdout",
                "entrada": "EVT-1\n",
                "salida_esperada": "Inscripto: Ana\n",
                "es_publico": True,
            },
            {
                "id": "t3",
                "nombre": "cupo 1 admite dos",
                "tipo": "stdin_stdout",
                "es_publico": False,
            },
        ]
        e = Ejercicio(
            universidad_id=UNIV_ID,
            materia_id=materia.id,
            trabajo_practico_id=tp.id,
            external_ref="uuid-ej-casos",
            orden=1,
            titulo="E1",
            enunciado_md="...",
            test_cases=casos,
        )
        db_session.add(e)
        await db_session.commit()
        await db_session.refresh(e)

        assert len(e.test_cases) == 2
        # El caso oculto no guarda salida esperada: lo que el motor nunca recibe
        # no lo puede citar en una devolución que el alumno lee.
        assert "salida_esperada" not in e.test_cases[1]


class TestVinculoEjercicioRubrica:
    async def test_un_ejercicio_es_duenio_de_una_rubrica(
        self, db_session: AsyncSession, materia: Materia, tp: TrabajoPractico
    ):
        e = Ejercicio(
            universidad_id=UNIV_ID,
            materia_id=materia.id,
            trabajo_practico_id=tp.id,
            external_ref="uuid-ej-r",
            orden=1,
            titulo="E1",
            enunciado_md="...",
        )
        db_session.add(e)
        await db_session.commit()
        await db_session.refresh(e)

        r = _rubrica_de_ejercicio(materia.id, e.id, "E1 - rúbrica")
        db_session.add(r)
        await db_session.commit()
        await db_session.refresh(e)

        assert e.rubrica is not None
        assert e.rubrica.id == r.id
        assert r.ejercicio_id == e.id

    async def test_rubrica_de_moodle_no_tiene_ejercicio(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Caracterización: el flujo de Moodle no cambia."""
        r = Rubrica(
            universidad_id=UNIV_ID,
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            titulo="TP1 Moodle",
            descripcion="...",
            puntaje_maximo=100,
            numero=1,
            anio=2026,
            criterios_json=[],
            activa=True,
            moodle_assign_id=17703,
        )
        db_session.add(r)
        await db_session.commit()
        await db_session.refresh(r)

        assert r.ejercicio_id is None
        assert r.moodle_assign_id == 17703

    async def test_cuatro_ejercicios_del_mismo_tp_tienen_cuatro_rubricas(
        self, db_session: AsyncSession, materia: Materia, tp: TrabajoPractico
    ):
        """El caso que HOY rechaza `uq_rubrica_materia_tipo_numero_anio`.

        Las cuatro rúbricas comparten `(materia_id, tipo=TP, numero=2, anio=2026)`
        y solo se distinguen por su ejercicio.
        """
        for i in range(1, 5):
            e = Ejercicio(
                universidad_id=UNIV_ID,
                materia_id=materia.id,
                trabajo_practico_id=tp.id,
                external_ref=f"uuid-ej-{i}",
                orden=i,
                titulo=f"E{i}",
                enunciado_md="...",
            )
            db_session.add(e)
            await db_session.flush()
            db_session.add(_rubrica_de_ejercicio(materia.id, e.id, f"E{i} - rúbrica"))

        await db_session.commit()

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
        assert {r.numero for r in rubricas} == {2}

    async def test_dos_rubricas_de_moodle_con_la_misma_clave_siguen_rechazandose(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Caracterización: la unicidad del flujo existente NO se aflojó.

        El índice sigue aplicando sobre las rúbricas sin ejercicio, que son las
        de Moodle. Si este test pasara a permitir el duplicado, el índice parcial
        habría desactivado una garantía que el proyecto tenía.
        """

        def _rubrica_moodle(titulo: str) -> Rubrica:
            return Rubrica(
                universidad_id=UNIV_ID,
                materia_id=materia.id,
                tipo=TipoRubricaEnum.TP,
                titulo=titulo,
                descripcion="...",
                puntaje_maximo=100,
                numero=7,
                anio=2026,
                criterios_json=[],
                activa=True,
            )

        db_session.add(_rubrica_moodle("Primera"))
        await db_session.commit()

        db_session.add(_rubrica_moodle("Duplicada"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_dos_rubricas_no_pueden_apuntar_al_mismo_ejercicio(
        self, db_session: AsyncSession, materia: Materia, tp: TrabajoPractico
    ):
        """El 1:1 lo fuerza la unicidad de `rubricas.ejercicio_id`."""
        e = Ejercicio(
            universidad_id=UNIV_ID,
            materia_id=materia.id,
            trabajo_practico_id=tp.id,
            external_ref="uuid-ej-1a1",
            orden=1,
            titulo="E1",
            enunciado_md="...",
        )
        db_session.add(e)
        await db_session.commit()
        await db_session.refresh(e)

        db_session.add(_rubrica_de_ejercicio(materia.id, e.id, "Primera"))
        await db_session.commit()

        db_session.add(_rubrica_de_ejercicio(materia.id, e.id, "Segunda"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestIndiceParcialDeRubricas:
    """La unicidad de Moodle se conserva; las rúbricas de ejercicio quedan exentas."""

    def test_el_unique_constraint_fue_reemplazado_por_un_indice_parcial(self):
        """El constraint total ya no puede existir: rechazaría los 4 ejercicios."""
        constraints = {c.name for c in Rubrica.__table__.constraints}
        assert "uq_rubrica_materia_tipo_numero_anio" not in constraints

        indices = {i.name: i for i in Rubrica.__table__.indexes}
        assert "uq_rubrica_materia_tipo_numero_anio" in indices

        indice = indices["uq_rubrica_materia_tipo_numero_anio"]
        assert indice.unique is True
        assert [c.name for c in indice.columns] == [
            "materia_id",
            "tipo",
            "numero",
            "anio",
        ]
        # La condición parcial es lo que exime a las rúbricas de ejercicio.
        assert "ejercicio_id" in str(
            indice.dialect_options["postgresql"]["where"]
        )

    def test_la_rubrica_tiene_ejercicio_id_unico(self):
        """El 1:1 lo fuerza la unicidad de la FK."""
        columnas = {c.name: c for c in Rubrica.__table__.columns}
        assert "ejercicio_id" in columnas
        assert columnas["ejercicio_id"].nullable is True


class TestReferenciaExternaEnMateria:
    def test_materia_acepta_referencia_externa_opcional(
        self, db_session: AsyncSession
    ):
        columnas = {c.name: c for c in Materia.__table__.columns}
        assert "external_ref" in columnas
        assert columnas["external_ref"].nullable is True

    async def test_materia_existente_sin_referencia_externa_sigue_siendo_valida(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Caracterización: las materias de Moodle no tienen ninguna."""
        assert materia.external_ref is None
