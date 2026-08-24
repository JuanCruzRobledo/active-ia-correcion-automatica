"""
correccion-por-ejercicio-con-tests, bloque 1: resolución de la comisión.

**El hueco que el pedido de AI-Native no podía ver.** Su documento describe el
endpoint de corrección como `{alumno_ref, codigo, resultado_tests}` y nada más,
porque no ve nuestro modelo de datos. Pero `entregas.comision_id` es `NOT NULL`
y AI-Native no tiene comisiones: sin resolver esto, el endpoint no puede
persistir absolutamente nada.

Dos vías, en orden de precedencia:

1. `comision_external_ref` en el cuerpo → habilita cohortes cuando el cliente
   quiera modelarlas.
2. `Materia.comision_integracion_id` → la comisión que un admin configura UNA
   VEZ por materia al dar de alta la integración.

Si ninguna resuelve, se responde 409 diciendo qué falta configurar. **Nunca se
crea una comisión implícitamente**: dar de alta entidades por efecto colateral de
una corrección es la clase de magia que después nadie puede explicar.

El contrato que el cliente ya implementó NO cambia: el campo nuevo es opcional.

Alternativa descartada: hacer `entregas.comision_id` nullable. Es una tabla
caliente, con índices, scoping multi-tenant y consultas en medio proyecto que
asumen la comisión. Esa nullabilidad se paga para siempre; una FK de
configuración se paga una vez.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comision import Comision
from app.models.materia import Materia

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


async def _comision(db: AsyncSession, materia: Materia, nombre: str, ref: str | None = None):
    c = Comision(
        universidad_id=materia.universidad_id,
        materia_id=materia.id,
        nombre=nombre,
        anio=2026,
        activa=True,
        external_ref=ref,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


class TestReferenciaExternaEnComision:
    def test_la_columna_existe_y_es_opcional(self):
        columnas = {c.name: c for c in Comision.__table__.columns}
        assert "external_ref" in columnas
        assert columnas["external_ref"].nullable is True

    async def test_comision_del_flujo_de_moodle_sigue_sin_referencia(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Caracterización: las comisiones existentes no tienen ninguna."""
        c = await _comision(db_session, materia, "C1")
        assert c.external_ref is None

    async def test_dos_comisiones_de_la_misma_materia_no_repiten_referencia(
        self, db_session: AsyncSession, materia: Materia
    ):
        await _comision(db_session, materia, "C1", ref="uuid-cohorte-a")

        db_session.add(
            Comision(
                universidad_id=UNIV_ID, materia_id=materia.id, nombre="C2",
                anio=2026, activa=True, external_ref="uuid-cohorte-a",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_varias_comisiones_sin_referencia_no_colisionan(
        self, db_session: AsyncSession, materia: Materia
    ):
        """El índice es parcial sobre no nulos: la mayoría no tiene ninguna."""
        await _comision(db_session, materia, "C1")
        await _comision(db_session, materia, "C2")
        await _comision(db_session, materia, "C3")

        total = len((await db_session.execute(select(Comision))).scalars().all())
        assert total == 3

    async def test_misma_referencia_en_materias_distintas_es_valida(
        self, db_session: AsyncSession, materia: Materia
    ):
        otra = Materia(
            universidad_id=UNIV_ID, codigo="PROG3", nombre="Programación 3", activa=True
        )
        db_session.add(otra)
        await db_session.commit()
        await db_session.refresh(otra)

        await _comision(db_session, materia, "C1", ref="uuid-compartido")
        await _comision(db_session, otra, "C1", ref="uuid-compartido")

        total = len((await db_session.execute(select(Comision))).scalars().all())
        assert total == 2


class TestComisionDeIntegracionEnMateria:
    def test_la_columna_existe_y_es_opcional(self):
        columnas = {c.name: c for c in Materia.__table__.columns}
        assert "comision_integracion_id" in columnas
        assert columnas["comision_integracion_id"].nullable is True

    async def test_materia_sin_integracion_no_tiene_comision_configurada(
        self, db_session: AsyncSession, materia: Materia
    ):
        """Caracterización: las materias de Moodle no la necesitan."""
        assert materia.comision_integracion_id is None

    async def test_se_puede_configurar_y_navegar(
        self, db_session: AsyncSession, materia: Materia
    ):
        comision = await _comision(db_session, materia, "Integración AI-Native")

        materia.comision_integracion_id = comision.id
        await db_session.commit()
        db_session.expunge_all()

        recargada = (
            await db_session.execute(select(Materia).where(Materia.id == materia.id))
        ).scalar_one()
        assert recargada.comision_integracion_id == comision.id
