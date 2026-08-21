"""
api-escritura-trabajos-practicos: reconciliación entre publicaciones sucesivas.

**Este es el punto donde una decisión floja rompe notas**, y por eso tiene su
propio archivo.

El cliente publica el mismo TP muchas veces: el docente edita un enunciado,
agrega un ejercicio, corrige un criterio. Cada publicación es la MISMA llamada
(`PUT .../by-ref/{ref}`), porque el cliente no guarda el id de Active-IA. Sin
idempotencia, cada publicación crearía un TP nuevo y el docente terminaría
eligiendo entre diez copias — y elegir mal no da una nota floja: **corrige otra
cosa**.

La garantía que sostiene todo: **el `rubrica_id` de un ejercicio es estable de
por vida**. Las `Entrega` y las `Correccion` cuelgan de `rubrica_id`. Si un push
lo rotara, las correcciones ya hechas quedarían asociadas a una rúbrica que el
cliente ya no vincula a ese ejercicio, y pediría corregir contra la nueva sin
ver las viejas. Por eso los ejercicios se emparejan por `external_ref` y nunca
por orden ni por título: reordenarlos en la plataforma del cliente no puede
rotar nada.
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ejercicio import Ejercicio
from app.models.entrega import Entrega
from app.models.comision import Comision
from app.models.enums import EstadoEntregaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.trabajo_practico import TrabajoPractico
from app.schemas.ejercicio import (
    CriterioEjercicioInput,
    EjercicioWriteRequest,
    RubricaEjercicioInput,
)
from app.schemas.trabajo_practico import TrabajoPracticoWriteRequest
from app.services.trabajo_practico_service import TrabajoPracticoService

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


def _ej(ref: str, orden: int, titulo: str | None = None, puntaje: str = "10"):
    return EjercicioWriteRequest(
        external_ref=ref,
        orden=orden,
        titulo=titulo or f"E{orden}",
        enunciado_md="Consigna",
        peso=Decimal("1"),
        rubrica=RubricaEjercicioInput(
            criterios=[
                CriterioEjercicioInput(
                    nombre="Criterio", descripcion="Desc", puntaje_max=Decimal(puntaje)
                )
            ]
        ),
    )


def _req(refs_ordenes, titulo="TP 2 JAVA"):
    return TrabajoPracticoWriteRequest(
        external_ref="uuid-tp",
        materia_external_ref="uuid-materia",
        titulo=titulo,
        ejercicios=[_ej(ref, orden) for ref, orden in refs_ordenes],
    )


async def _refs_a_rubrica(db: AsyncSession, tp_id: int) -> dict[str, int]:
    """Mapa external_ref → rubrica_id de los ejercicios vigentes."""
    db.expunge_all()
    ejercicios = (
        (
            await db.execute(
                select(Ejercicio).where(
                    Ejercicio.trabajo_practico_id == tp_id,
                    Ejercicio.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return {e.external_ref: e.rubrica.id for e in ejercicios if e.rubrica}


class TestIdempotencia:
    async def test_primer_push_crea(self, db_session: AsyncSession, materia: Materia):
        service = TrabajoPracticoService(db_session)

        tp, creado, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2)]), materia=materia
        )
        await db_session.commit()

        assert creado is True
        assert len(await _refs_a_rubrica(db_session, tp.id)) == 2

    async def test_republicar_identico_no_duplica_nada(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        req = _req([("uuid-ej-1", 1), ("uuid-ej-2", 2)])

        tp1, creado1, _ = await service.upsert_por_external_ref(req, materia=materia)
        await db_session.commit()
        tp2, creado2, _ = await service.upsert_por_external_ref(req, materia=materia)
        await db_session.commit()

        assert creado1 is True
        assert creado2 is False
        assert tp1.id == tp2.id

        todos_los_tp = (await db_session.execute(select(TrabajoPractico))).scalars().all()
        assert len(todos_los_tp) == 1
        assert len(await _refs_a_rubrica(db_session, tp1.id)) == 2

    async def test_republicar_con_cambios_actualiza_en_su_lugar(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1)], titulo="TP viejo"), materia=materia
        )
        await db_session.commit()

        tp2, creado, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1)], titulo="TP nuevo"), materia=materia
        )
        await db_session.commit()

        assert creado is False
        assert tp2.id == tp.id
        assert tp2.titulo == "TP nuevo"


class TestEstabilidadDelRubricaId:
    """La garantía que sostiene el resto. Si esto se rompe, se rompen notas."""

    async def test_el_rubrica_id_de_cada_ejercicio_no_cambia_entre_pushes(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        req = _req([("uuid-ej-1", 1), ("uuid-ej-2", 2), ("uuid-ej-3", 3)])

        tp, _, _ = await service.upsert_por_external_ref(req, materia=materia)
        await db_session.commit()
        antes = await _refs_a_rubrica(db_session, tp.id)

        await service.upsert_por_external_ref(req, materia=materia)
        await db_session.commit()
        despues = await _refs_a_rubrica(db_session, tp.id)

        assert antes == despues

    async def test_reordenar_los_ejercicios_no_rota_ninguna_rubrica(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Emparejar por orden en vez de por external_ref rompería justo acá."""
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-a", 1), ("uuid-ej-b", 2), ("uuid-ej-c", 3)]),
            materia=materia,
        )
        await db_session.commit()
        antes = await _refs_a_rubrica(db_session, tp.id)

        # Mismos ejercicios, orden invertido.
        await service.upsert_por_external_ref(
            _req([("uuid-ej-c", 1), ("uuid-ej-b", 2), ("uuid-ej-a", 3)]),
            materia=materia,
        )
        await db_session.commit()
        despues = await _refs_a_rubrica(db_session, tp.id)

        assert antes == despues, "el rubrica_id siguió al orden en vez de al external_ref"

    async def test_renombrar_un_ejercicio_no_lo_recrea(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Emparejar por título rompería acá."""
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            TrabajoPracticoWriteRequest(
                external_ref="uuid-tp",
                materia_external_ref="uuid-materia",
                titulo="TP",
                ejercicios=[_ej("uuid-ej-1", 1, titulo="Título viejo")],
            ),
            materia=materia,
        )
        await db_session.commit()
        antes = await _refs_a_rubrica(db_session, tp.id)

        await service.upsert_por_external_ref(
            TrabajoPracticoWriteRequest(
                external_ref="uuid-tp",
                materia_external_ref="uuid-materia",
                titulo="TP",
                ejercicios=[_ej("uuid-ej-1", 1, titulo="Título nuevo")],
            ),
            materia=materia,
        )
        await db_session.commit()
        despues = await _refs_a_rubrica(db_session, tp.id)

        assert antes == despues

    async def test_actualizar_los_criterios_reescribe_la_misma_rubrica(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1)]), materia=materia
        )
        await db_session.commit()
        rubrica_id = (await _refs_a_rubrica(db_session, tp.id))["uuid-ej-1"]

        nuevo = TrabajoPracticoWriteRequest(
            external_ref="uuid-tp",
            materia_external_ref="uuid-materia",
            titulo="TP",
            ejercicios=[
                EjercicioWriteRequest(
                    external_ref="uuid-ej-1",
                    orden=1,
                    titulo="E1",
                    rubrica=RubricaEjercicioInput(
                        criterios=[
                            CriterioEjercicioInput(
                                nombre="Nuevo A", descripcion="D", puntaje_max=Decimal("1")
                            ),
                            CriterioEjercicioInput(
                                nombre="Nuevo B", descripcion="D", puntaje_max=Decimal("1")
                            ),
                        ]
                    ),
                )
            ],
        )
        await service.upsert_por_external_ref(nuevo, materia=materia)
        await db_session.commit()
        db_session.expunge_all()

        rubrica = (
            await db_session.execute(select(Rubrica).where(Rubrica.id == rubrica_id))
        ).scalar_one()
        assert [c["nombre"] for c in rubrica.criterios_json] == ["Nuevo A", "Nuevo B"]
        assert sum(c["peso"] for c in rubrica.criterios_json) == 100


class TestAltasYBajasEnLaReconciliacion:
    async def test_ejercicio_nuevo_se_crea_y_los_viejos_conservan_su_rubrica(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2), ("uuid-ej-3", 3)]),
            materia=materia,
        )
        await db_session.commit()
        antes = await _refs_a_rubrica(db_session, tp.id)

        _, _, conteos = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2), ("uuid-ej-3", 3), ("uuid-ej-4", 4)]),
            materia=materia,
        )
        await db_session.commit()
        despues = await _refs_a_rubrica(db_session, tp.id)

        assert conteos["creados"] == 1
        assert conteos["actualizados"] == 3
        assert len(despues) == 4
        for ref, rubrica_id in antes.items():
            assert despues[ref] == rubrica_id

    async def test_ejercicio_ausente_del_push_queda_de_baja_con_su_rubrica(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2), ("uuid-ej-3", 3), ("uuid-ej-4", 4)]),
            materia=materia,
        )
        await db_session.commit()
        rubrica_del_cuarto = (await _refs_a_rubrica(db_session, tp.id))["uuid-ej-4"]

        _, _, conteos = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2), ("uuid-ej-3", 3)]),
            materia=materia,
        )
        await db_session.commit()
        vigentes = await _refs_a_rubrica(db_session, tp.id)

        assert conteos["dados_de_baja"] == 1
        assert "uuid-ej-4" not in vigentes

        rubrica = (
            await db_session.execute(
                select(Rubrica).where(Rubrica.id == rubrica_del_cuarto)
            )
        ).scalar_one()
        assert rubrica.activa is False

    async def test_la_baja_conserva_las_entregas_y_no_borra_filas(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Un ejercicio con correcciones no puede perderlas por un push."""
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2)]), materia=materia
        )
        await db_session.commit()
        rubrica_id = (await _refs_a_rubrica(db_session, tp.id))["uuid-ej-2"]

        comision = Comision(
            universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1", anio=2026, activa=True
        )
        db_session.add(comision)
        await db_session.flush()
        db_session.add(
            Entrega(
                universidad_id=UNIV_ID,
                comision_id=comision.id,
                rubrica_id=rubrica_id,
                alumno_nombre="pseudonimo-alumno",
                archivo_nombre="e.zip",
                archivo_tipo="zip",
                estado=EstadoEntregaEnum.CORREGIDA,
            )
        )
        await db_session.commit()

        await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1)]), materia=materia
        )
        await db_session.commit()

        entregas = (await db_session.execute(select(Entrega))).scalars().all()
        assert len(entregas) == 1
        assert entregas[0].rubrica_id == rubrica_id
        assert entregas[0].deleted_at is None

        ejercicios = (await db_session.execute(select(Ejercicio))).scalars().all()
        assert len(ejercicios) == 2, "la baja tiene que ser lógica, nunca física"

    async def test_reenviar_un_ejercicio_dado_de_baja_lo_deja_vigente_otra_vez(
        self, db_session: AsyncSession, materia: Materia
    ):
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2)]), materia=materia
        )
        await db_session.commit()

        await service.upsert_por_external_ref(_req([("uuid-ej-1", 1)]), materia=materia)
        await db_session.commit()
        assert "uuid-ej-2" not in await _refs_a_rubrica(db_session, tp.id)

        await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2)]), materia=materia
        )
        await db_session.commit()

        vigentes = await _refs_a_rubrica(db_session, tp.id)
        assert "uuid-ej-2" in vigentes


class TestAtomicidad:
    async def test_un_fallo_deja_el_tp_como_estaba(
        self, db_session: AsyncSession, materia: Materia
    ):
        """El servicio no commitea: el llamador es dueño de la transacción."""
        service = TrabajoPracticoService(db_session)
        tp, _, _ = await service.upsert_por_external_ref(
            _req([("uuid-ej-1", 1), ("uuid-ej-2", 2)], titulo="TP original"),
            materia=materia,
        )
        await db_session.commit()
        antes = await _refs_a_rubrica(db_session, tp.id)

        # Un push que actualiza dos y falla al crear el tercero.
        malo = _req([("uuid-ej-1", 1), ("uuid-ej-2", 2), ("uuid-ej-3", 3)], titulo="TP roto")
        malo.ejercicios[2].rubrica.criterios[0].puntaje_max = Decimal("-0")

        with pytest.raises(Exception):
            await service.upsert_por_external_ref(malo, materia=materia)
            await db_session.commit()
        await db_session.rollback()

        db_session.expunge_all()
        recargado = (
            await db_session.execute(
                select(TrabajoPractico).where(TrabajoPractico.id == tp.id)
            )
        ).scalar_one()
        assert recargado.titulo == "TP original"
        assert await _refs_a_rubrica(db_session, tp.id) == antes
