"""
correccion-por-ejercicio-con-tests, bloque 6: el servicio que corrige un ejercicio.

Es la mitad que faltaba de la integración: hasta acá AI-Native podía PUBLICAR un
TP con sus ejercicios y sus rúbricas, pero no podía pedir que se corrija nada.

Lo que este servicio orquesta, en orden:

1. Resuelve el ejercicio por su referencia externa (scopeado por universidad).
2. Resuelve la comisión — el hueco que el pedido no vio, porque
   `entregas.comision_id` es NOT NULL y el cliente no tiene comisiones.
3. Prepara la entrega: la CREA si es la primera vez, la REUSA si el alumno ya
   había entregado ese ejercicio.
4. Delega en el motor de corrección de siempre, pasándole el resultado de tests.

**Reuso, no 409.** El cliente reintenta con la misma llamada en vez de tener que
ramificar por un conflicto. La corrección anterior queda en el historial —
mecanismo que ya existía (CRUD-003), no se inventa nada acá.

**El pseudónimo se guarda literal.** Active-IA no intenta resolverlo a una
persona ni cruzarlo con ningún padrón: es un pseudónimo por diseño del cliente, y
esa propiedad es la que hace posible el procedimiento de anonimización.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import undefer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad
from app.models.comision import Comision
from app.models.ejercicio import Ejercicio
from app.models.entrega import Entrega
from app.models.enums import RolEnum, TipoRubricaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.trabajo_practico import TrabajoPractico
from app.schemas.correccion import CorreccionEjercicioRequest, ResultadoTests
from app.services.correccion_ejercicio_service import CorreccionEjercicioService

UNIV_ID = 1
CTX = ContextoUniversidad(universidad_id=UNIV_ID, rol=RolEnum.ADMIN, es_superadmin=False)
USUARIO = SimpleNamespace(id=7, rol=RolEnum.ADMIN)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def escenario(db_session: AsyncSession):
    """Materia con TP, un ejercicio con rúbrica, y comisión de integración."""
    materia = Materia(
        universidad_id=UNIV_ID, codigo="PROG2", nombre="Programación 2",
        activa=True, external_ref="uuid-materia",
    )
    db_session.add(materia)
    await db_session.flush()

    comision = Comision(
        universidad_id=UNIV_ID, materia_id=materia.id, nombre="Integración",
        anio=2026, activa=True,
    )
    db_session.add(comision)
    await db_session.flush()
    materia.comision_integracion_id = comision.id

    tp = TrabajoPractico(
        universidad_id=UNIV_ID, materia_id=materia.id,
        external_ref="uuid-tp", titulo="TP 2 JAVA",
    )
    db_session.add(tp)
    await db_session.flush()

    ejercicio = Ejercicio(
        universidad_id=UNIV_ID, materia_id=materia.id, trabajo_practico_id=tp.id,
        external_ref="uuid-ej-1", orden=1, titulo="E1", enunciado_md="...",
    )
    db_session.add(ejercicio)
    await db_session.flush()

    rubrica = Rubrica(
        universidad_id=UNIV_ID, materia_id=materia.id, tipo=TipoRubricaEnum.TP,
        titulo="TP2 — E1", descripcion="...", puntaje_maximo=100,
        numero=1, anio=2026, activa=True, ejercicio_id=ejercicio.id,
        criterios_json=[{"id": "C1", "nombre": "C1", "peso": 100, "subcriterios": []}],
    )
    db_session.add(rubrica)
    await db_session.commit()
    await db_session.refresh(ejercicio)

    return SimpleNamespace(
        materia=materia, comision=comision, tp=tp, ejercicio=ejercicio, rubrica=rubrica
    )


def _request(**over) -> CorreccionEjercicioRequest:
    base = {"alumno_ref": "pseudonimo-alumno-42", "codigo": "public class Main {}"}
    base.update(over)
    return CorreccionEjercicioRequest(**base)


def _mock_correccion(nota="85.00"):
    """La respuesta que devuelve el motor de corrección de siempre."""
    return SimpleNamespace(
        id=100, entrega_id=1, nota=Decimal(nota), criterios=[],
        fortalezas=["a"], recomendaciones=["b"], comentario_general="ok",
    )


def _parchear_motor(nota="85.00"):
    """Aísla el motor de IA: acá se prueba la orquestación, no la corrección."""
    return patch(
        "app.services.correccion_ejercicio_service.CorreccionService",
        return_value=MagicMock(corregir_individual=AsyncMock(return_value=_mock_correccion(nota))),
    )


class TestResolucionDelEjercicio:
    async def test_ejercicio_inexistente_da_404(self, db_session, escenario):
        svc = CorreccionEjercicioService(db_session)

        with pytest.raises(HTTPException) as exc:
            await svc.corregir(
                ejercicio_ref="uuid-que-no-existe", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )
        assert exc.value.status_code == 404

    async def test_ejercicio_dado_de_baja_da_404(self, db_session, escenario):
        from datetime import datetime

        escenario.ejercicio.deleted_at = datetime.utcnow()
        await db_session.commit()
        svc = CorreccionEjercicioService(db_session)

        with pytest.raises(HTTPException) as exc:
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )
        assert exc.value.status_code == 404

    async def test_ejercicio_de_otra_universidad_da_404(self, db_session, escenario):
        otra = ContextoUniversidad(universidad_id=99, rol=RolEnum.ADMIN, es_superadmin=False)
        svc = CorreccionEjercicioService(db_session)

        with pytest.raises(HTTPException) as exc:
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(),
                usuario=USUARIO, ctx=otra, api_key_encrypted="k", provider="gemini",
            )
        assert exc.value.status_code == 404


class TestResolucionDeLaComision:
    async def test_usa_la_comision_de_integracion_de_la_materia(self, db_session, escenario):
        svc = CorreccionEjercicioService(db_session)

        with _parchear_motor():
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        entrega = (await db_session.execute(select(Entrega))).scalars().one()
        assert entrega.comision_id == escenario.comision.id

    async def test_la_referencia_del_cuerpo_tiene_precedencia(self, db_session, escenario):
        cohorte = Comision(
            universidad_id=UNIV_ID, materia_id=escenario.materia.id,
            nombre="Cohorte 2026-B", anio=2026, activa=True,
            external_ref="uuid-cohorte-b",
        )
        db_session.add(cohorte)
        await db_session.commit()
        await db_session.refresh(cohorte)

        svc = CorreccionEjercicioService(db_session)
        with _parchear_motor():
            await svc.corregir(
                ejercicio_ref="uuid-ej-1",
                datos=_request(comision_external_ref="uuid-cohorte-b"),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        entrega = (await db_session.execute(select(Entrega))).scalars().one()
        assert entrega.comision_id == cohorte.id

    async def test_sin_comision_resoluble_da_409_diciendo_que_configurar(
        self, db_session, escenario
    ):
        escenario.materia.comision_integracion_id = None
        await db_session.commit()
        svc = CorreccionEjercicioService(db_session)

        with pytest.raises(HTTPException) as exc:
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        assert exc.value.status_code == 409
        assert "comisión de integración" in exc.value.detail.lower()

    async def test_NUNCA_crea_una_comision_implicitamente(self, db_session, escenario):
        """Crear entidades por efecto colateral es la magia que nadie explica."""
        escenario.materia.comision_integracion_id = None
        await db_session.commit()
        antes = len((await db_session.execute(select(Comision))).scalars().all())

        svc = CorreccionEjercicioService(db_session)
        with pytest.raises(HTTPException):
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )
        await db_session.rollback()

        despues = len((await db_session.execute(select(Comision))).scalars().all())
        assert despues == antes

    async def test_referencia_de_comision_de_otra_materia_da_409(self, db_session, escenario):
        otra_materia = Materia(
            universidad_id=UNIV_ID, codigo="PROG3", nombre="Programación 3", activa=True
        )
        db_session.add(otra_materia)
        await db_session.flush()
        db_session.add(
            Comision(
                universidad_id=UNIV_ID, materia_id=otra_materia.id, nombre="C1",
                anio=2026, activa=True, external_ref="uuid-ajena",
            )
        )
        await db_session.commit()

        svc = CorreccionEjercicioService(db_session)
        with pytest.raises(HTTPException) as exc:
            await svc.corregir(
                ejercicio_ref="uuid-ej-1",
                datos=_request(comision_external_ref="uuid-ajena"),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )
        assert exc.value.status_code == 409


class TestPreparacionDeLaEntrega:
    async def test_primera_correccion_crea_la_entrega(self, db_session, escenario):
        svc = CorreccionEjercicioService(db_session)

        with _parchear_motor():
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(codigo="class A {}"),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        entrega = (
            await db_session.execute(
                select(Entrega).options(undefer(Entrega.contenido_consolidado))
            )
        ).scalars().one()
        assert entrega.rubrica_id == escenario.rubrica.id
        assert entrega.contenido_consolidado == "class A {}"

    async def test_el_pseudonimo_se_guarda_LITERAL(self, db_session, escenario):
        """Sin resolución contra padrón ni contra Moodle: es la propiedad que
        hace posible el procedimiento de anonimización."""
        svc = CorreccionEjercicioService(db_session)

        with _parchear_motor():
            await svc.corregir(
                ejercicio_ref="uuid-ej-1",
                datos=_request(alumno_ref="pseudonimo-opaco-xyz"),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        entrega = (await db_session.execute(select(Entrega))).scalars().one()
        assert entrega.alumno_nombre == "pseudonimo-opaco-xyz"
        assert entrega.moodle_user_id is None

    async def test_segunda_correccion_REUSA_la_entrega_y_no_da_409(
        self, db_session, escenario
    ):
        svc = CorreccionEjercicioService(db_session)

        with _parchear_motor():
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(codigo="v1"),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(codigo="v2"),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        entregas = (
            await db_session.execute(
                select(Entrega).options(undefer(Entrega.contenido_consolidado))
            )
        ).scalars().all()
        assert len(entregas) == 1, "reintentar no puede duplicar la entrega"
        assert entregas[0].contenido_consolidado == "v2"

    async def test_dos_ejercicios_del_mismo_alumno_son_dos_entregas(
        self, db_session, escenario
    ):
        """Cada ejercicio tiene su rúbrica: la clave (rubrica, alumno) los separa."""
        ej2 = Ejercicio(
            universidad_id=UNIV_ID, materia_id=escenario.materia.id,
            trabajo_practico_id=escenario.tp.id, external_ref="uuid-ej-2",
            orden=2, titulo="E2",
        )
        db_session.add(ej2)
        await db_session.flush()
        db_session.add(
            Rubrica(
                universidad_id=UNIV_ID, materia_id=escenario.materia.id,
                tipo=TipoRubricaEnum.TP, titulo="TP2 — E2", descripcion="...",
                puntaje_maximo=100, numero=2, anio=2026, activa=True,
                ejercicio_id=ej2.id, criterios_json=[],
            )
        )
        await db_session.commit()

        svc = CorreccionEjercicioService(db_session)
        with _parchear_motor():
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )
            await svc.corregir(
                ejercicio_ref="uuid-ej-2", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        entregas = (await db_session.execute(select(Entrega))).scalars().all()
        assert len(entregas) == 2
        assert len({e.rubrica_id for e in entregas}) == 2


class TestDelegacionAlMotor:
    async def test_le_pasa_el_resultado_de_tests(self, db_session, escenario):
        svc = CorreccionEjercicioService(db_session)
        resultado = ResultadoTests(compila=True, total=4, pasados=4, casos=[])

        with _parchear_motor() as Motor:
            await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(resultado_tests=resultado),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        kwargs = Motor.return_value.corregir_individual.await_args.kwargs
        assert kwargs["resultado_tests"] is resultado

    async def test_la_respuesta_identifica_ejercicio_y_rubrica(self, db_session, escenario):
        svc = CorreccionEjercicioService(db_session)

        with _parchear_motor(nota="72.50"):
            r = await svc.corregir(
                ejercicio_ref="uuid-ej-1", datos=_request(),
                usuario=USUARIO, ctx=CTX, api_key_encrypted="k", provider="gemini",
            )

        assert r.ejercicio_external_ref == "uuid-ej-1"
        assert r.rubrica_id == escenario.rubrica.id
        assert r.nota == Decimal("72.50")
        assert r.alumno_ref == "pseudonimo-alumno-42"
