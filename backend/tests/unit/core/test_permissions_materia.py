"""
Tests de los guards de acceso a materia (autorización REAL coordinador↔materia).

Cubre el guard que permite a un coordinador configurar SOLO sus materias asignadas:
- ADMIN: pasa sin consultar la DB.
- COORDINADOR propietario: pasa.
- COORDINADOR ajeno: 403.
- Entidad inexistente (unidad/examen): 404.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    verificar_acceso_examen,
    verificar_acceso_materia,
    verificar_acceso_unidad,
)
from app.models.enums import RolEnum

ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)
COORD = SimpleNamespace(id=5, rol=RolEnum.COORDINADOR)


def _db(*rows):
    """db async cuyo execute().first() devuelve rows[i] en la i-ésima llamada."""
    db = AsyncMock()
    resultados = []
    for r in rows:
        res = MagicMock()
        res.first.return_value = r
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


# ===================== verificar_acceso_materia =====================


@pytest.mark.asyncio
async def test_admin_pasa_sin_consultar_db():
    db = AsyncMock()
    await verificar_acceso_materia(db, ADMIN, 99)
    db.execute.assert_not_called()  # el admin no necesita el chequeo


@pytest.mark.asyncio
async def test_coordinador_propietario_ok():
    db = _db((123,))  # existe la fila CoordinadorMateria
    await verificar_acceso_materia(db, COORD, 10)  # no lanza


@pytest.mark.asyncio
async def test_coordinador_ajeno_403():
    db = _db(None)  # no hay fila → no es coordinador de esa materia
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_materia(db, COORD, 10)
    assert exc.value.status_code == 403


# ===================== verificar_acceso_unidad / examen =====================


@pytest.mark.asyncio
async def test_unidad_inexistente_404():
    db = _db(None)  # la unidad no existe
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_unidad(db, COORD, 77)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unidad_de_materia_ajena_403():
    # 1ª query: unidad → materia_id 7. 2ª query: CoordinadorMateria → None (ajena).
    db = _db((7,), None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_unidad(db, COORD, 77)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_examen_propietario_ok():
    # 1ª query: examen → materia_id 7. 2ª query: CoordinadorMateria → fila.
    db = _db((7,), (123,))
    await verificar_acceso_examen(db, COORD, 55)  # no lanza
