"""Integration tests para el router 'Por entregar'.

Sin DB real: se mockea PorEntregarService y se sobreescriben las dependencias
de auth/db.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import (
    ContextoUniversidad,
    get_current_user,
    get_db,
    get_universidad_activa,
)
from app.models.enums import RolEnum
from app.services.por_entregar_service import (
    CorreccionPorEntregaItem,
    PorEntregarResultado,
)


def _ctx_tutor():
    return ContextoUniversidad(universidad_id=1, rol=RolEnum.TUTOR, es_superadmin=False)


@pytest.fixture
def auth():
    app.dependency_overrides[get_current_user] = lambda: MagicMock(
        id=1, moodle_username="tutor", moodle_password_encrypted="enc"
    )
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_universidad_activa] = _ctx_tutor
    yield
    app.dependency_overrides.clear()


def _item():
    return CorreccionPorEntregaItem(
        correccion_id=9, entrega_id=90, alumno_nombre="Selene Miño",
        materia_id=1, materia_nombre="Prog I", comision_id=5, comision_nombre="K1051",
        rubrica_id=11, rubrica_titulo="TP3", tipo_rubrica="TP", nota=85.0,
        etiqueta_nota="Aprobado", requiere_comentario_tutor=False,
        estado_ultimo_intento="none", mensaje_error=None, corregido_at=None,
    )


@pytest.mark.asyncio
async def test_listar_devuelve_items_y_contadores(auth):
    resultado = PorEntregarResultado(
        items=[_item()], total_pendientes=1, total_automaticas=1,
        total_requieren_comentario=0, no_vinculadas=3,
    )
    with patch("app.routers.por_entregar.PorEntregarService") as cls:
        cls.return_value.listar = AsyncMock(return_value=resultado)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/por-entregar")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_pendientes"] == 1
    assert body["no_vinculadas"] == 3
    assert body["items"][0]["alumno_nombre"] == "Selene Miño"
    assert body["items"][0]["etiqueta_nota"] == "Aprobado"


@pytest.mark.asyncio
async def test_entregar_stream_emite_eventos(auth):
    async def _fake_stream(usuario, base_url, ctx=None):
        yield {"tipo": "inicio", "total": 1}
        yield {"tipo": "progreso", "procesadas": 1, "total": 1}
        yield {"tipo": "resumen", "enviadas": 1, "ya_enviadas": 0,
               "omitidas_requieren_comentario": 0, "errores": []}

    with patch("app.routers.por_entregar.PorEntregarService") as cls:
        cls.return_value.entregar_masivo_stream = _fake_stream
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/por-entregar/entregar/stream")
            texto = resp.text

    assert resp.status_code == 200
    assert '"tipo": "inicio"' in texto
    assert '"tipo": "resumen"' in texto
    assert '"enviadas": 1' in texto


@pytest.mark.asyncio
async def test_entregar_stream_sin_credenciales_es_424():
    app.dependency_overrides[get_current_user] = lambda: MagicMock(
        id=1, moodle_username=None, moodle_password_encrypted=None
    )
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_universidad_activa] = _ctx_tutor
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/por-entregar/entregar/stream")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 424
