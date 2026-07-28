"""Autorización de POST /comisiones: coordinador puede crear en SU materia.

Bug: el endpoint exigía rol admin (require_admin), así un coordinador no podía
crear una comisión para una materia que tiene asignada. Ahora usa
verificar_acceso_materia (admin total; coordinador solo sus materias; resto 403).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.dependencies import ContextoUniversidad
from app.core.permissions import verificar_acceso_materia_de_comision
from app.models.enums import RolEnum
from app.routers.comisiones import (
    actualizar_comision,
    asignar_tutores,
    crear_comision,
)

ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)
COORD = SimpleNamespace(id=5, rol=RolEnum.COORDINADOR)
TUTOR = SimpleNamespace(id=9, rol=RolEnum.TUTOR)

CTX_ADMIN = ContextoUniversidad(universidad_id=1, rol=RolEnum.ADMIN, es_superadmin=False)
CTX_COORD = ContextoUniversidad(universidad_id=1, rol=RolEnum.COORDINADOR, es_superadmin=False)
CTX_TUTOR = ContextoUniversidad(universidad_id=1, rol=RolEnum.TUTOR, es_superadmin=False)


def _db(row):
    """db async cuyo execute().first() devuelve `row`."""
    db = AsyncMock()
    res = MagicMock()
    res.first.return_value = row
    db.execute.return_value = res
    return db


def _db_rows(*rows):
    """db async cuyo execute().first() devuelve rows[i] en la i-ésima llamada."""
    db = AsyncMock()
    resultados = []
    for r in rows:
        res = MagicMock()
        res.first.return_value = r
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


@pytest.mark.asyncio
async def test_coordinador_propietario_puede_crear():
    db = _db((123,))  # tiene la materia asignada (fila CoordinadorMateria)
    data = SimpleNamespace(materia_id=10)
    with patch("app.routers.comisiones.ComisionService") as MockSvc:
        MockSvc.return_value.crear_comision = AsyncMock(return_value="OK")
        result = await crear_comision(data, current_user=COORD, db=db, ctx=CTX_COORD)
    assert result == "OK"


@pytest.mark.asyncio
async def test_coordinador_ajeno_403():
    db = _db(None)  # no es coordinador de esa materia
    data = SimpleNamespace(materia_id=10)
    with pytest.raises(HTTPException) as exc:
        await crear_comision(data, current_user=COORD, db=db, ctx=CTX_COORD)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_tutor_403():
    db = _db(None)
    data = SimpleNamespace(materia_id=10)
    with pytest.raises(HTTPException) as exc:
        await crear_comision(data, current_user=TUTOR, db=db, ctx=CTX_TUTOR)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_crea_sin_consultar_db():
    db = AsyncMock()
    data = SimpleNamespace(materia_id=10)
    with patch("app.routers.comisiones.ComisionService") as MockSvc:
        MockSvc.return_value.crear_comision = AsyncMock(return_value="OK")
        result = await crear_comision(data, current_user=ADMIN, db=db, ctx=CTX_ADMIN)
    assert result == "OK"
    db.execute.assert_not_called()  # admin no necesita el chequeo de materia


# ===================== verificar_acceso_materia_de_comision =====================


@pytest.mark.asyncio
async def test_helper_comision_inexistente_404():
    db = _db(None)  # la comisión no existe
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_materia_de_comision(db, COORD, CTX_COORD, 77)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_helper_coordinador_de_la_materia_ok():
    # 1ª query: comisión → materia_id 7. 2ª query: CoordinadorMateria → fila.
    db = _db_rows((7,), (123,))
    await verificar_acceso_materia_de_comision(db, COORD, CTX_COORD, 55)  # no lanza


@pytest.mark.asyncio
async def test_helper_coordinador_de_materia_ajena_403():
    # 1ª query: comisión → materia_id 7. 2ª query: CoordinadorMateria → None.
    db = _db_rows((7,), None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_materia_de_comision(db, COORD, CTX_COORD, 55)
    assert exc.value.status_code == 403


# ===================== editar + asignar tutores =====================


@pytest.mark.asyncio
async def test_coordinador_propietario_puede_editar():
    db = _db_rows((7,), (123,))  # comisión→materia 7; coordinador asignado
    data = SimpleNamespace()
    with patch("app.routers.comisiones.ComisionService") as MockSvc:
        MockSvc.return_value.actualizar_comision = AsyncMock(return_value="OK")
        result = await actualizar_comision(55, data, current_user=COORD, db=db, ctx=CTX_COORD)
    assert result == "OK"


@pytest.mark.asyncio
async def test_coordinador_ajeno_no_puede_asignar_tutores_403():
    db = _db_rows((7,), None)  # comisión→materia 7; coordinador NO asignado
    data = SimpleNamespace()
    with pytest.raises(HTTPException) as exc:
        await asignar_tutores(55, data, current_user=COORD, db=db, ctx=CTX_COORD)
    assert exc.value.status_code == 403
