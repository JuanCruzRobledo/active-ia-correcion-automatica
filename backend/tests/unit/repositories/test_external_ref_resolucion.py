"""
trabajos-practicos-y-external-ref: resolución por identificador externo.

El resolver actual de Active-IA cruza por `cmid` (el `assign_id` de Moodle), y
AI-Native no es Moodle: cero ocurrencias de `cmid` en todo su monorepo. Sin una
vía de cruce propia, el 100% del mapeo queda en un archivo manual del tutor, lo
que no escala cuando los ejercicios los crea el docente y pueden ser decenas.

Las cuatro garantías que tiene que dar la resolución, y las cuatro tienen su
test porque cada una que falte es un agujero distinto:

1. Resuelve el registro vigente.
2. NO resuelve un registro dado de baja (si no, un TP borrado seguiría
   atrapando las publicaciones nuevas).
3. NO cruza universidades (aislamiento multi-tenant).
4. El mismo identificador en dos materias distintas resuelve a cada una.
"""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ejercicio import Ejercicio
from app.models.materia import Materia
from app.models.trabajo_practico import TrabajoPractico
from app.repositories.ejercicio_repository import EjercicioRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.trabajo_practico_repository import TrabajoPracticoRepository

UNIV_A = 1
UNIV_B = 2

pytestmark = pytest.mark.asyncio


async def _materia(db: AsyncSession, universidad_id: int, codigo: str, ref: str | None):
    m = Materia(
        universidad_id=universidad_id,
        codigo=codigo,
        nombre=f"Materia {codigo}",
        activa=True,
        external_ref=ref,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _tp(db: AsyncSession, materia: Materia, ref: str, borrado: bool = False):
    t = TrabajoPractico(
        universidad_id=materia.universidad_id,
        materia_id=materia.id,
        external_ref=ref,
        titulo=f"TP {ref}",
        deleted_at=datetime.utcnow() if borrado else None,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def _ejercicio(db: AsyncSession, tp: TrabajoPractico, ref: str, borrado: bool = False):
    e = Ejercicio(
        universidad_id=tp.universidad_id,
        materia_id=tp.materia_id,
        trabajo_practico_id=tp.id,
        external_ref=ref,
        orden=1,
        titulo=f"E {ref}",
        deleted_at=datetime.utcnow() if borrado else None,
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return e


@pytest_asyncio.fixture
async def materia_a(db_session: AsyncSession) -> Materia:
    return await _materia(db_session, UNIV_A, "PROG1", "uuid-materia-a")


class TestResolucionDeTrabajoPractico:
    async def test_resuelve_el_tp_vigente(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        tp = await _tp(db_session, materia_a, "uuid-tp-1")
        repo = TrabajoPracticoRepository(db_session)

        hallado = await repo.get_by_external_ref(
            "uuid-tp-1", materia_id=materia_a.id, universidad_id=UNIV_A
        )

        assert hallado is not None
        assert hallado.id == tp.id

    async def test_identificador_inexistente_devuelve_none(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        repo = TrabajoPracticoRepository(db_session)
        assert (
            await repo.get_by_external_ref(
                "uuid-que-no-existe", materia_id=materia_a.id, universidad_id=UNIV_A
            )
            is None
        )

    async def test_tp_dado_de_baja_no_se_resuelve(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        """Si no, un TP borrado seguiría atrapando las publicaciones nuevas."""
        await _tp(db_session, materia_a, "uuid-tp-borrado", borrado=True)
        repo = TrabajoPracticoRepository(db_session)

        assert (
            await repo.get_by_external_ref(
                "uuid-tp-borrado", materia_id=materia_a.id, universidad_id=UNIV_A
            )
            is None
        )

    async def test_no_cruza_universidades(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        await _tp(db_session, materia_a, "uuid-tp-univ-a")
        repo = TrabajoPracticoRepository(db_session)

        assert (
            await repo.get_by_external_ref(
                "uuid-tp-univ-a", materia_id=materia_a.id, universidad_id=UNIV_B
            )
            is None
        )

    async def test_mismo_identificador_en_dos_materias_resuelve_a_cada_una(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        materia_b = await _materia(db_session, UNIV_A, "PROG2", "uuid-materia-b")
        tp_a = await _tp(db_session, materia_a, "uuid-tp-compartido")
        tp_b = await _tp(db_session, materia_b, "uuid-tp-compartido")
        repo = TrabajoPracticoRepository(db_session)

        hallado_a = await repo.get_by_external_ref(
            "uuid-tp-compartido", materia_id=materia_a.id, universidad_id=UNIV_A
        )
        hallado_b = await repo.get_by_external_ref(
            "uuid-tp-compartido", materia_id=materia_b.id, universidad_id=UNIV_A
        )

        assert hallado_a.id == tp_a.id
        assert hallado_b.id == tp_b.id
        assert hallado_a.id != hallado_b.id


class TestResolucionDeEjercicio:
    async def test_resuelve_el_ejercicio_vigente(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        tp = await _tp(db_session, materia_a, "uuid-tp-e")
        e = await _ejercicio(db_session, tp, "uuid-ej-1")
        repo = EjercicioRepository(db_session)

        hallado = await repo.get_by_external_ref("uuid-ej-1", universidad_id=UNIV_A)

        assert hallado is not None
        assert hallado.id == e.id

    async def test_ejercicio_dado_de_baja_no_se_resuelve(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        tp = await _tp(db_session, materia_a, "uuid-tp-eb")
        await _ejercicio(db_session, tp, "uuid-ej-borrado", borrado=True)
        repo = EjercicioRepository(db_session)

        assert (
            await repo.get_by_external_ref("uuid-ej-borrado", universidad_id=UNIV_A)
            is None
        )

    async def test_ejercicio_de_otra_universidad_no_se_resuelve(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        tp = await _tp(db_session, materia_a, "uuid-tp-eu")
        await _ejercicio(db_session, tp, "uuid-ej-univ-a")
        repo = EjercicioRepository(db_session)

        assert (
            await repo.get_by_external_ref("uuid-ej-univ-a", universidad_id=UNIV_B)
            is None
        )

    async def test_lista_los_ejercicios_vigentes_del_tp_ordenados(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        tp = await _tp(db_session, materia_a, "uuid-tp-list")
        for orden, ref in ((3, "c"), (1, "a"), (2, "b")):
            e = Ejercicio(
                universidad_id=UNIV_A,
                materia_id=materia_a.id,
                trabajo_practico_id=tp.id,
                external_ref=f"uuid-ej-{ref}",
                orden=orden,
                titulo=f"E{orden}",
            )
            db_session.add(e)
        await _ejercicio(db_session, tp, "uuid-ej-borrado-2", borrado=True)
        repo = EjercicioRepository(db_session)

        vigentes = await repo.listar_vigentes_de_tp(tp.id)

        assert [e.orden for e in vigentes] == [1, 2, 3]
        assert "uuid-ej-borrado-2" not in {e.external_ref for e in vigentes}


class TestResolucionDeMateria:
    async def test_resuelve_la_materia_por_identificador_externo(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        repo = MateriaRepository(db_session)

        hallada = await repo.get_by_external_ref("uuid-materia-a", universidad_id=UNIV_A)

        assert hallada is not None
        assert hallada.id == materia_a.id

    async def test_materia_de_otra_universidad_no_se_resuelve(
        self, db_session: AsyncSession, materia_a: Materia
    ):
        repo = MateriaRepository(db_session)
        assert (
            await repo.get_by_external_ref("uuid-materia-a", universidad_id=UNIV_B)
            is None
        )

    async def test_materia_sin_identificador_externo_no_se_resuelve_por_nulo(
        self, db_session: AsyncSession
    ):
        """Caracterización: buscar por None no debe devolver las de Moodle."""
        await _materia(db_session, UNIV_A, "SIN-REF", None)
        repo = MateriaRepository(db_session)

        assert await repo.get_by_external_ref(None, universidad_id=UNIV_A) is None
