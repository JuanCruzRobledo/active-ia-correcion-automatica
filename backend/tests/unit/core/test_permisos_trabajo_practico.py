"""
trabajos-practicos-y-external-ref: control de acceso a TPs y ejercicios.

Se resuelve por la materia que los contiene, replicando el patrón de
`verificar_acceso_rubrica`. Dos garantías separadas, y cada una tiene su test
porque se rompen de formas distintas:

- **Aislamiento por universidad**: un usuario de otra universidad no accede.
- **Pertenencia a la materia**: un usuario de la misma universidad pero sin
  acceso a la materia tampoco.

Y una tercera que es de seguridad y no de permisos: el error **no puede revelar
si el recurso existe** en otra universidad. Un 404 distinto de un 403 le dice al
que prueba identificadores si acertó.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad
from app.core.permissions import (
    verificar_acceso_ejercicio,
    verificar_acceso_trabajo_practico,
)
from app.models.ejercicio import Ejercicio
from app.models.enums import RolEnum
from app.models.materia import CoordinadorMateria, Materia
from app.models.trabajo_practico import TrabajoPractico
from app.models.usuario import Usuario

UNIV_A = 1
UNIV_B = 2

pytestmark = pytest.mark.asyncio

CTX_ADMIN_A = ContextoUniversidad(
    universidad_id=UNIV_A, rol=RolEnum.ADMIN, es_superadmin=False
)
CTX_COORD_A = ContextoUniversidad(
    universidad_id=UNIV_A, rol=RolEnum.COORDINADOR, es_superadmin=False
)
CTX_COORD_B = ContextoUniversidad(
    universidad_id=UNIV_B, rol=RolEnum.COORDINADOR, es_superadmin=False
)


@pytest_asyncio.fixture
async def coordinador(db_session: AsyncSession) -> Usuario:
    u = Usuario(
        username="coord_test",
        nombre="Coordinador Test",
        password_hash="no-se-usa",
        activo=True,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def materia(db_session: AsyncSession) -> Materia:
    m = Materia(
        universidad_id=UNIV_A, codigo="PROG2", nombre="Programación 2", activa=True
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


@pytest_asyncio.fixture
async def tp_y_ejercicio(db_session: AsyncSession, materia: Materia):
    tp = TrabajoPractico(
        universidad_id=UNIV_A,
        materia_id=materia.id,
        external_ref="uuid-tp",
        titulo="TP 2",
    )
    db_session.add(tp)
    await db_session.flush()
    ej = Ejercicio(
        universidad_id=UNIV_A,
        materia_id=materia.id,
        trabajo_practico_id=tp.id,
        external_ref="uuid-ej",
        orden=1,
        titulo="E1",
    )
    db_session.add(ej)
    await db_session.commit()
    await db_session.refresh(tp)
    await db_session.refresh(ej)
    return tp, ej


class TestAccesoATrabajoPractico:
    async def test_admin_de_la_universidad_accede(
        self, db_session: AsyncSession, coordinador: Usuario, tp_y_ejercicio
    ):
        tp, _ = tp_y_ejercicio
        await verificar_acceso_trabajo_practico(
            db_session, coordinador, CTX_ADMIN_A, tp.id
        )

    async def test_coordinador_de_la_materia_accede(
        self,
        db_session: AsyncSession,
        coordinador: Usuario,
        materia: Materia,
        tp_y_ejercicio,
    ):
        tp, _ = tp_y_ejercicio
        db_session.add(
            CoordinadorMateria(coordinador_id=coordinador.id, materia_id=materia.id)
        )
        await db_session.commit()

        await verificar_acceso_trabajo_practico(
            db_session, coordinador, CTX_COORD_A, tp.id
        )

    async def test_coordinador_sin_acceso_a_la_materia_es_rechazado(
        self, db_session: AsyncSession, coordinador: Usuario, tp_y_ejercicio
    ):
        tp, _ = tp_y_ejercicio
        with pytest.raises(HTTPException) as exc:
            await verificar_acceso_trabajo_practico(
                db_session, coordinador, CTX_COORD_A, tp.id
            )
        assert exc.value.status_code in (403, 404)

    async def test_usuario_de_otra_universidad_es_rechazado(
        self, db_session: AsyncSession, coordinador: Usuario, tp_y_ejercicio
    ):
        tp, _ = tp_y_ejercicio
        with pytest.raises(HTTPException) as exc:
            await verificar_acceso_trabajo_practico(
                db_session, coordinador, CTX_COORD_B, tp.id
            )
        assert exc.value.status_code in (403, 404)

    async def test_el_error_no_revela_si_el_recurso_existe(
        self, db_session: AsyncSession, coordinador: Usuario, tp_y_ejercicio
    ):
        """Un mensaje distinto para 'existe pero es ajeno' y 'no existe' filtra."""
        tp, _ = tp_y_ejercicio

        with pytest.raises(HTTPException) as ajeno:
            await verificar_acceso_trabajo_practico(
                db_session, coordinador, CTX_COORD_B, tp.id
            )
        with pytest.raises(HTTPException) as inexistente:
            await verificar_acceso_trabajo_practico(
                db_session, coordinador, CTX_COORD_B, 999_999
            )

        assert ajeno.value.status_code == inexistente.value.status_code
        assert ajeno.value.detail == inexistente.value.detail

    async def test_trabajo_practico_dado_de_baja_no_se_resuelve(
        self,
        db_session: AsyncSession,
        coordinador: Usuario,
        materia: Materia,
        tp_y_ejercicio,
    ):
        """Con un rol que SI consulta: el ADMIN sale antes por `_acceso_total`,
        igual que en `verificar_acceso_rubrica`. El 404 del admin lo da el
        servicio despues, no el guard."""
        from datetime import datetime

        tp, _ = tp_y_ejercicio
        db_session.add(
            CoordinadorMateria(coordinador_id=coordinador.id, materia_id=materia.id)
        )
        tp.deleted_at = datetime.utcnow()
        await db_session.commit()

        with pytest.raises(HTTPException) as exc:
            await verificar_acceso_trabajo_practico(
                db_session, coordinador, CTX_COORD_A, tp.id
            )
        assert exc.value.status_code == 404


class TestAccesoAEjercicio:
    async def test_admin_de_la_universidad_accede(
        self, db_session: AsyncSession, coordinador: Usuario, tp_y_ejercicio
    ):
        _, ej = tp_y_ejercicio
        await verificar_acceso_ejercicio(db_session, coordinador, CTX_ADMIN_A, ej.id)

    async def test_usuario_de_otra_universidad_es_rechazado(
        self, db_session: AsyncSession, coordinador: Usuario, tp_y_ejercicio
    ):
        _, ej = tp_y_ejercicio
        with pytest.raises(HTTPException) as exc:
            await verificar_acceso_ejercicio(db_session, coordinador, CTX_COORD_B, ej.id)
        assert exc.value.status_code in (403, 404)

    async def test_ejercicio_inexistente_da_404(
        self, db_session: AsyncSession, coordinador: Usuario
    ):
        with pytest.raises(HTTPException) as exc:
            await verificar_acceso_ejercicio(
                db_session, coordinador, CTX_COORD_A, 999_999
            )
        assert exc.value.status_code == 404

    async def test_admin_no_recibe_404_del_guard(
        self, db_session: AsyncSession, coordinador: Usuario
    ):
        """Caracterizacion de `_acceso_total`: el ADMIN pasa sin consultar, y el
        404 de un recurso inexistente lo produce el servicio, no este guard.
        Mismo comportamiento que `verificar_acceso_rubrica`."""
        await verificar_acceso_ejercicio(
            db_session, coordinador, CTX_ADMIN_A, 999_999
        )
