"""Integration tests para subir corrección a Moodle + PDF público (Fase 3).

Sin DB real: se mockean el MoodleGradeService / DevolucionLinkService / PDFService
y se sobreescriben las dependencias de auth/db.
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
from app.services.devolucion_link_service import TokenDevolucionInvalido
from app.services.moodle_grade_service import PreviewCorreccion


def _ctx_tutor():
    return ContextoUniversidad(universidad_id=1, rol=RolEnum.TUTOR, es_superadmin=False)


@pytest.fixture
def auth():
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_universidad_activa] = _ctx_tutor
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preview_devuelve_datos(auth):
    preview = PreviewCorreccion(
        nota_a_enviar="Aprobado", nota_activeia=85.0,
        comentario_sugerido="Muy bien Juan!\nTe dejo tu devolución: http://x",
        requiere_comentario_tutor=False, link_devolucion="http://x", ya_enviada=False,
        ya_calificada_en_moodle=False,
    )
    with patch("app.routers.correcciones.MoodleGradeService") as cls:
        cls.return_value.preview_correccion = AsyncMock(return_value=preview)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/correcciones/9/moodle/preview")

    assert resp.status_code == 200
    body = resp.json()
    assert body["nota_a_enviar"] == "Aprobado"
    assert body["requiere_comentario_tutor"] is False
    assert body["ya_enviada"] is False


@pytest.mark.asyncio
async def test_subir_devuelve_estado(auth):
    sync = MagicMock(nota_enviada="Aprobado", intento=1)
    sync.estado = MagicMock(value="ENVIADO")
    with patch("app.routers.correcciones.MoodleGradeService") as cls:
        cls.return_value.subir_correccion = AsyncMock(return_value=sync)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/correcciones/9/moodle", json={"comentario": "Muy bien!"}
            )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "ENVIADO"


@pytest.mark.asyncio
async def test_devolucion_publica_token_valido_sirve_pdf():
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    try:
        with patch(
            "app.routers.public_docs.DevolucionLinkService.validar_token", return_value=5
        ), patch("app.routers.public_docs.PDFService") as cls:
            cls.return_value.generar_pdf_devolucion = AsyncMock(return_value=b"%PDF-1.4 demo")
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/public/devoluciones/sometoken")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content == b"%PDF-1.4 demo"


@pytest.mark.asyncio
async def test_devolucion_publica_token_invalido_404():
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    try:
        with patch(
            "app.routers.public_docs.DevolucionLinkService.validar_token",
            side_effect=TokenDevolucionInvalido("expirado"),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/public/devoluciones/bad")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
