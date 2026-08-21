"""
api-escritura-trabajos-practicos: contrato HTTP de los tres endpoints.

El cliente ya tiene su lado implementado contra este contrato y corre contra un
mock hasta que exista. Los códigos importan: su doble HTTP cubre el camino feliz,
el 409, el motor saturado, la credencial inválida y la respuesta sin id.

La distinción 201/200 en el `PUT` no es cosmética: es lo que le permite al
cliente saber si su publicación creó algo o actualizó lo que ya estaba, sin
tener que consultar antes.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Response

from app.core.dependencies import ContextoUniversidad
from app.models.enums import RolEnum
from app.routers.trabajos_practicos import (
    crear_trabajo_practico,
    obtener_trabajo_practico_por_ref,
    upsert_trabajo_practico_por_ref,
)

pytestmark = pytest.mark.asyncio

ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)
COORD = SimpleNamespace(id=7, rol=RolEnum.COORDINADOR)
TUTOR = SimpleNamespace(id=5, rol=RolEnum.TUTOR)

CTX_ADMIN = ContextoUniversidad(universidad_id=1, rol=RolEnum.ADMIN, es_superadmin=False)
CTX_COORD = ContextoUniversidad(
    universidad_id=1, rol=RolEnum.COORDINADOR, es_superadmin=False
)
CTX_TUTOR = ContextoUniversidad(universidad_id=1, rol=RolEnum.TUTOR, es_superadmin=False)

_RUTA = "app.routers.trabajos_practicos"


def _db():
    """Sesión mockeada cuyos métodos de transacción SÍ se pueden await."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _cuerpo():
    from decimal import Decimal

    from app.schemas.ejercicio import (
        CriterioEjercicioInput,
        EjercicioWriteRequest,
        RubricaEjercicioInput,
    )
    from app.schemas.trabajo_practico import TrabajoPracticoWriteRequest

    return TrabajoPracticoWriteRequest(
        external_ref="uuid-tp",
        materia_external_ref="uuid-materia",
        titulo="TP 2 JAVA",
        ejercicios=[
            EjercicioWriteRequest(
                external_ref="uuid-ej-1",
                orden=1,
                titulo="E1",
                peso=Decimal("1"),
                rubrica=RubricaEjercicioInput(
                    criterios=[
                        CriterioEjercicioInput(
                            nombre="C", descripcion="D", puntaje_max=Decimal("10")
                        )
                    ]
                ),
            )
        ],
    )


class TestPermisos:
    async def test_crear_con_rol_tutor_da_403(self):
        with patch(f"{_RUTA}.TrabajoPracticoService"):
            with pytest.raises(HTTPException) as exc:
                await crear_trabajo_practico(
                    _cuerpo(), current_user=TUTOR, db=MagicMock(), ctx=CTX_TUTOR
                )
        assert exc.value.status_code == 403

    async def test_upsert_con_rol_tutor_da_403(self):
        with patch(f"{_RUTA}.TrabajoPracticoService"):
            with pytest.raises(HTTPException) as exc:
                await upsert_trabajo_practico_por_ref(
                    "uuid-tp",
                    _cuerpo(),
                    response=Response(),
                    current_user=TUTOR,
                    db=MagicMock(),
                    ctx=CTX_TUTOR,
                )
        assert exc.value.status_code == 403

    async def test_consulta_con_rol_tutor_es_permitida(self):
        """El tutor puede leer: lo que no puede es escribir."""
        with patch(f"{_RUTA}._resolver_materia", new=AsyncMock(return_value=MagicMock(id=3))), patch(
            f"{_RUTA}.verificar_acceso_materia", new=AsyncMock()
        ), patch(f"{_RUTA}.TrabajoPracticoRepository") as Repo:
            Repo.return_value.get_by_external_ref = AsyncMock(
                return_value=SimpleNamespace(
                    id=1,
                    external_ref="uuid-tp",
                    materia_id=3,
                    titulo="TP",
                    descripcion=None,
                    ejercicios=[],
                )
            )
            with patch(f"{_RUTA}._a_response", return_value="RESP"):
                salida = await obtener_trabajo_practico_por_ref(
                    "uuid-tp",
                    materia_external_ref="uuid-materia",
                    current_user=TUTOR,
                    db=MagicMock(),
                    ctx=CTX_TUTOR,
                )
        assert salida == "RESP"


class TestCodigosDeRespuesta:
    async def test_upsert_que_crea_responde_201(self):
        response = Response()
        with patch(f"{_RUTA}._resolver_materia", new=AsyncMock(return_value=MagicMock(id=3))), patch(
            f"{_RUTA}.verificar_acceso_materia", new=AsyncMock()
        ), patch(f"{_RUTA}.TrabajoPracticoService") as Svc, patch(
            f"{_RUTA}._a_response", return_value="RESP"
        ), patch(
            f"{_RUTA}.ActividadService"
        ) as Act:
            Act.return_value.registrar_actividad = AsyncMock()
            Svc.return_value.upsert_por_external_ref = AsyncMock(
                return_value=(MagicMock(id=1, titulo="TP"), True, {"creados": 1, "actualizados": 0, "dados_de_baja": 0})
            )
            await upsert_trabajo_practico_por_ref(
                "uuid-tp",
                _cuerpo(),
                response=response,
                current_user=COORD,
                db=_db(),
                ctx=CTX_COORD,
            )
        assert response.status_code == 201

    async def test_upsert_que_actualiza_responde_200(self):
        response = Response()
        with patch(f"{_RUTA}._resolver_materia", new=AsyncMock(return_value=MagicMock(id=3))), patch(
            f"{_RUTA}.verificar_acceso_materia", new=AsyncMock()
        ), patch(f"{_RUTA}.TrabajoPracticoService") as Svc, patch(
            f"{_RUTA}._a_response", return_value="RESP"
        ), patch(
            f"{_RUTA}.ActividadService"
        ) as Act:
            Act.return_value.registrar_actividad = AsyncMock()
            Svc.return_value.upsert_por_external_ref = AsyncMock(
                return_value=(MagicMock(id=1, titulo="TP"), False, {"creados": 0, "actualizados": 1, "dados_de_baja": 0})
            )
            await upsert_trabajo_practico_por_ref(
                "uuid-tp",
                _cuerpo(),
                response=response,
                current_user=COORD,
                db=_db(),
                ctx=CTX_COORD,
            )
        assert response.status_code == 200

    async def test_consulta_de_tp_inexistente_da_404(self):
        with patch(f"{_RUTA}._resolver_materia", new=AsyncMock(return_value=MagicMock(id=3))), patch(
            f"{_RUTA}.verificar_acceso_materia", new=AsyncMock()
        ), patch(f"{_RUTA}.TrabajoPracticoRepository") as Repo:
            Repo.return_value.get_by_external_ref = AsyncMock(return_value=None)
            with pytest.raises(HTTPException) as exc:
                await obtener_trabajo_practico_por_ref(
                    "uuid-inexistente",
                    materia_external_ref="uuid-materia",
                    current_user=ADMIN,
                    db=MagicMock(),
                    ctx=CTX_ADMIN,
                )
        assert exc.value.status_code == 404


class TestResolucionDeMateria:
    async def test_materia_inexistente_da_404_nombrando_el_identificador(self):
        from app.routers.trabajos_practicos import _resolver_materia

        repo = MagicMock()
        repo.get_by_external_ref = AsyncMock(return_value=None)
        with patch(f"{_RUTA}.MateriaRepository", return_value=repo):
            with pytest.raises(HTTPException) as exc:
                await _resolver_materia(MagicMock(), "uuid-que-no-existe", CTX_ADMIN)

        assert exc.value.status_code == 404
        # El cliente publica desde una interfaz de docente: tiene que saber CUÁL
        # identificador no resolvió.
        assert "uuid-que-no-existe" in exc.value.detail

    async def test_no_crea_la_materia_implicitamente(self):
        """Crear entidades por efecto colateral es la magia que nadie explica."""
        from app.routers.trabajos_practicos import _resolver_materia

        repo = MagicMock()
        repo.get_by_external_ref = AsyncMock(return_value=None)
        repo.create = AsyncMock()
        with patch(f"{_RUTA}.MateriaRepository", return_value=repo):
            with pytest.raises(HTTPException):
                await _resolver_materia(MagicMock(), "uuid-x", CTX_ADMIN)

        repo.create.assert_not_called()


class TestAuditoria:
    async def test_el_upsert_registra_los_tres_conteos(self):
        registrar = AsyncMock()
        with patch(f"{_RUTA}._resolver_materia", new=AsyncMock(return_value=MagicMock(id=3))), patch(
            f"{_RUTA}.verificar_acceso_materia", new=AsyncMock()
        ), patch(f"{_RUTA}.TrabajoPracticoService") as Svc, patch(
            f"{_RUTA}._a_response", return_value="RESP"
        ), patch(
            f"{_RUTA}.ActividadService"
        ) as Act:
            Svc.return_value.upsert_por_external_ref = AsyncMock(
                return_value=(
                    MagicMock(id=1, titulo="TP 2 JAVA"),
                    False,
                    {"creados": 1, "actualizados": 2, "dados_de_baja": 1},
                )
            )
            Act.return_value.registrar_actividad = registrar
            await upsert_trabajo_practico_por_ref(
                "uuid-tp",
                _cuerpo(),
                response=Response(),
                current_user=COORD,
                db=_db(),
                ctx=CTX_COORD,
            )

        registrar.assert_awaited_once()
        metadatos = registrar.await_args.kwargs["metadatos"]
        assert '"creados": 1' in metadatos
        assert '"actualizados": 2' in metadatos
        assert '"dados_de_baja": 1' in metadatos
