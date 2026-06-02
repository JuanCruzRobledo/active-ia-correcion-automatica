"""Integration tests del router 'Gestión' (T7).

Sin DB real: se mockea GestionService y se sobreescriben get_current_user / get_db.
Cubre los 4 endpoints, el permiso (GESTOR/ADMIN sí, TUTOR no) y la validación 422.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user, get_db
from app.models.enums import RolEnum
from app.services.gestion_service import (
    AlumnoGestion,
    CursoGestion,
    FiltrosDisponibles,
    ResultadoGestion,
)

ASGI = ASGITransport(app=app)


def _override(rol=RolEnum.GESTOR):
    app.dependency_overrides[get_current_user] = lambda: MagicMock(
        id=1, rol=rol, moodle_username="u", moodle_password_encrypted="enc", moodle_host="https://m",
    )
    app.dependency_overrides[get_db] = lambda: AsyncMock()


@pytest.fixture
def auth():
    _override()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_listar_cursos(auth):
    with patch("app.routers.gestion.GestionService") as cls:
        cls.return_value.listar_cursos = AsyncMock(return_value=[
            CursoGestion(materia_id=1, nombre="Prog I", codigo="P1", moodle_course_id=38),
        ])
        async with AsyncClient(transport=ASGI, base_url="http://test") as client:
            resp = await client.get("/api/v1/gestion/cursos")

    assert resp.status_code == 200
    assert resp.json()[0]["materia_id"] == 1


@pytest.mark.asyncio
async def test_opciones_filtros(auth):
    with patch("app.routers.gestion.GestionService") as cls:
        cls.return_value.opciones_filtros = AsyncMock(return_value=FiltrosDisponibles(
            regionales=["Mendoza", "Rosario"], comisiones=["M26 C1-01"],
            roles=[{"value": "student", "label": "Estudiante"}],
            estatus=[{"value": "activo", "label": "Activo"}],
            inactividad=[{"value": "1_mes", "label": "1 mes"}],
        ))
        async with AsyncClient(transport=ASGI, base_url="http://test") as client:
            resp = await client.get("/api/v1/gestion/cursos/1/filtros")

    assert resp.status_code == 200
    body = resp.json()
    assert body["regionales"] == ["Mendoza", "Rosario"]
    assert body["roles"][0]["value"] == "student"


@pytest.mark.asyncio
async def test_consulta(auth):
    with patch("app.routers.gestion.GestionService") as cls:
        cls.return_value.consultar = AsyncMock(return_value=ResultadoGestion(
            items=[AlumnoGestion("Ana", "Lopez", "a@x", "Mendoza", "M26 C1-01", 45, "45 días", False)],
            total=1,
        ))
        async with AsyncClient(transport=ASGI, base_url="http://test") as client:
            resp = await client.post("/api/v1/gestion/cursos/1/consulta", json={"rol": "student"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "a@x"
    assert body["items"][0]["tiempo_inactividad"] == "45 días"


@pytest.mark.asyncio
async def test_exportar_excel(auth):
    with patch("app.routers.gestion.GestionService") as cls:
        cls.return_value.exportar_excel = AsyncMock(
            return_value=(b"PK\x03\x04xlsxbytes", "gestion_Prog_I_20260602.xlsx")
        )
        async with AsyncClient(transport=ASGI, base_url="http://test") as client:
            resp = await client.post("/api/v1/gestion/cursos/1/excel", json={})

    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content == b"PK\x03\x04xlsxbytes"


@pytest.mark.asyncio
async def test_consulta_inactividad_invalida_es_422(auth):
    with patch("app.routers.gestion.GestionService"):
        async with AsyncClient(transport=ASGI, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/gestion/cursos/1/consulta", json={"inactividad_tipo": "no_existe"}
            )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tutor_no_accede_es_403():
    _override(rol=RolEnum.TUTOR)
    try:
        with patch("app.routers.gestion.GestionService"):
            async with AsyncClient(transport=ASGI, base_url="http://test") as client:
                resp = await client.get("/api/v1/gestion/cursos")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_si_accede():
    _override(rol=RolEnum.ADMIN)
    try:
        with patch("app.routers.gestion.GestionService") as cls:
            cls.return_value.listar_cursos = AsyncMock(return_value=[])
            async with AsyncClient(transport=ASGI, base_url="http://test") as client:
                resp = await client.get("/api/v1/gestion/cursos")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
