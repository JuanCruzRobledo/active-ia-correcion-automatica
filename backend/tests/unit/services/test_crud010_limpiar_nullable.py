"""
CRUD-010: los updates parciales deben distinguir "campo ausente" (preservar) de
"campo en null explícito" (limpiar).

Con `if data.campo is not None` un cliente que manda {"descripcion": null} para
VACIAR un campo nullable era ignorado en silencio (200 OK, sin cambio). El fix usa
`"campo" in data.model_fields_set` (patrón ya presente en rubrica_service para
moodle_assign_id), aplicado SOLO a los campos nullable.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.cohorte import CohorteUpdate, CuatrimestreUpdate
from app.schemas.comision import ComisionUpdate
from app.schemas.materia import MateriaUpdate
from app.schemas.usuario import UsuarioUpdate
from app.services.cohorte_service import CohorteService
from app.services.comision_service import ComisionService
from app.services.materia_service import MateriaService
from app.services.usuario_service import UsuarioService


# ===================== materia.descripcion / moodle_course_id =====================


@pytest.mark.asyncio
async def test_materia_null_explicito_limpia_descripcion():
    svc = MateriaService.__new__(MateriaService)
    materia = SimpleNamespace(descripcion="algo", moodle_course_id=5, nombre="Prog")
    svc.materia_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=materia), update=AsyncMock()
    )
    svc.obtener_materia = AsyncMock(return_value="OK")

    await svc.actualizar_materia(1, MateriaUpdate(descripcion=None))
    assert materia.descripcion is None  # se limpió


@pytest.mark.asyncio
async def test_materia_campo_ausente_preserva_descripcion():
    svc = MateriaService.__new__(MateriaService)
    materia = SimpleNamespace(descripcion="algo", moodle_course_id=5, nombre="Prog")
    svc.materia_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=materia), update=AsyncMock()
    )
    svc.obtener_materia = AsyncMock(return_value="OK")

    await svc.actualizar_materia(1, MateriaUpdate(nombre="Prog 2"))  # sin descripcion
    assert materia.descripcion == "algo"  # intacto


@pytest.mark.asyncio
async def test_materia_null_explicito_limpia_moodle_course_id():
    svc = MateriaService.__new__(MateriaService)
    materia = SimpleNamespace(descripcion="x", moodle_course_id=5, nombre="Prog")
    svc.materia_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=materia), update=AsyncMock()
    )
    svc.obtener_materia = AsyncMock(return_value="OK")

    await svc.actualizar_materia(1, MateriaUpdate(moodle_course_id=None))
    assert materia.moodle_course_id is None


# ===================== usuario.email =====================


@pytest.mark.asyncio
async def test_usuario_null_explicito_limpia_email():
    svc = UsuarioService.__new__(UsuarioService)
    user = SimpleNamespace(nombre="Juan", rol="TUTOR", email="j@x.com")
    svc.repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=user), update=AsyncMock(return_value=user)
    )
    with patch("app.services.usuario_service.UsuarioResponse") as MockResp:
        MockResp.model_validate.return_value = "OK"
        await svc.actualizar_usuario(1, UsuarioUpdate(email=None))
    assert user.email is None


@pytest.mark.asyncio
async def test_usuario_email_ausente_preserva():
    svc = UsuarioService.__new__(UsuarioService)
    user = SimpleNamespace(nombre="Juan", rol="TUTOR", email="j@x.com")
    svc.repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=user), update=AsyncMock(return_value=user)
    )
    with patch("app.services.usuario_service.UsuarioResponse") as MockResp:
        MockResp.model_validate.return_value = "OK"
        await svc.actualizar_usuario(1, UsuarioUpdate(nombre="Juancho"))
    assert user.email == "j@x.com"


# ===================== comision.moodle_group_code / _id =====================


@pytest.mark.asyncio
async def test_comision_null_explicito_limpia_moodle_group_code():
    svc = ComisionService.__new__(ComisionService)
    comision = SimpleNamespace(
        nombre="C1", materia_id=1, anio=2026, moodle_group_id=7, moodle_group_code="G1"
    )
    svc.comision_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=comision), update=AsyncMock()
    )
    svc.obtener_comision = AsyncMock(return_value="OK")

    await svc.actualizar_comision(1, ComisionUpdate(moodle_group_code=None))
    assert comision.moodle_group_code is None


# ===================== cohorte.nombre / cuatrimestre.nombre =====================


@pytest.mark.asyncio
async def test_cohorte_null_explicito_limpia_nombre():
    svc = CohorteService.__new__(CohorteService)
    cohorte = SimpleNamespace(nombre="2026", activa=True)
    svc._get_cohorte_or_404 = AsyncMock(return_value=cohorte)
    svc.cohorte_repo = SimpleNamespace(
        update=AsyncMock(), get_by_id=AsyncMock(return_value=cohorte)
    )
    with patch("app.services.cohorte_service.CohorteDetailResponse") as MockResp:
        MockResp.model_validate.return_value = "OK"
        await svc.actualizar_cohorte(1, CohorteUpdate(nombre=None))
    assert cohorte.nombre is None


@pytest.mark.asyncio
async def test_cuatrimestre_null_explicito_limpia_nombre():
    svc = CohorteService.__new__(CohorteService)
    cuatri = SimpleNamespace(nombre="C1", numero=1, cohorte_id=1)
    svc._get_cuatrimestre_or_404 = AsyncMock(return_value=cuatri)
    svc.cuatrimestre_repo = SimpleNamespace(update=AsyncMock(return_value=cuatri))
    with patch("app.services.cohorte_service.CuatrimestreResponse") as MockResp:
        MockResp.model_validate.return_value = "OK"
        await svc.actualizar_cuatrimestre(1, CuatrimestreUpdate(nombre=None))
    assert cuatri.nombre is None
