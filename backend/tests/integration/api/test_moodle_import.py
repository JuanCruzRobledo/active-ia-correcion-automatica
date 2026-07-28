"""Integration tests para POST /api/v1/moodle/importar.

No usa DB real (el conftest SQLite no soporta JSONB/ARRAY/enums PG): se mockea
el MoodleImportService y se sobreescriben las dependencias de auth/db.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.models.enums import RolEnum
from app.services.moodle_import_service import ResumenImportacion


@pytest.fixture
def override_deps():
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_universidad_activa] = lambda: ContextoUniversidad(
        universidad_id=1, rol=RolEnum.TUTOR, es_superadmin=False
    )
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_importar_moodle_devuelve_resumen(override_deps):
    resumen = ResumenImportacion(
        cargadas=3, duplicadas=1, omitidas_ya_corregidas=2, reentregas=1, sin_archivos=0,
        errores=[{"alumno": "Ana Gomez", "motivo": "Descarga falló"}],
        detalle_por_rubrica=[{"rubrica_id": 2, "titulo": "TP3", "comision_id": 5, "cargadas": 3}],
    )
    with patch("app.routers.moodle_import.MoodleImportService") as cls:
        cls.return_value.importar = AsyncMock(return_value=resumen)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/moodle/importar", json={"scope": "tutor"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["cargadas"] == 3
    assert body["reentregas"] == 1
    assert body["omitidas_ya_corregidas"] == 2
    assert body["errores"][0]["alumno"] == "Ana Gomez"
    assert body["detalle_por_rubrica"][0]["titulo"] == "TP3"


@pytest.mark.asyncio
async def test_importar_moodle_scope_invalido_devuelve_422(override_deps):
    # scope fuera del Literal permitido → 422 de validación de Pydantic
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/moodle/importar", json={"scope": "todo_el_universo"})
    assert resp.status_code == 422
