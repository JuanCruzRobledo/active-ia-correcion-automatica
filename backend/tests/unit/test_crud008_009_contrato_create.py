"""
CRUD-008 / CRUD-009: robustez del contrato de creacion.

CRUD-009: el username se canonicaliza a minuscula en el schema, asi el chequeo de
duplicados, el insert y el login operan sobre el MISMO valor. Antes, crear "JPerez"
teniendo "jperez" esquivaba el exists() y reventaba contra el unique (500).

CRUD-008: un handler global traduce las violaciones de UNIQUE (SQLSTATE 23505) a
409 en vez del 500 generico que dejaba la carrera check-then-insert.
"""

from types import SimpleNamespace

import pytest
from fastapi import status

from app.models.enums import RolEnum
from app.schemas.auth import LoginRequest
from app.schemas.usuario import UsuarioCreate


# ===================== CRUD-009: normalizacion del username =====================


def test_usuario_create_baja_el_username_a_minuscula():
    u = UsuarioCreate(username="JPerez", nombre="Juan Perez", rol=RolEnum.TUTOR)
    assert u.username == "jperez"


def test_usuario_create_username_ya_minuscula_no_cambia():
    u = UsuarioCreate(username="jperez", nombre="Juan Perez", rol=RolEnum.TUTOR)
    assert u.username == "jperez"


def test_login_request_baja_el_username_a_minuscula():
    """Login case-insensitive: quien tipea 'Admin' matchea el 'admin' guardado."""
    lr = LoginRequest(username="Admin", password="secret123")
    assert lr.username == "admin"


def test_login_request_username_mixto_se_normaliza():
    lr = LoginRequest(username="JuanPerez", password="secret123")
    assert lr.username == "juanperez"


# ===================== CRUD-008: handler de IntegrityError =====================


def _integrity_error(sqlstate: str):
    """IntegrityError falso con el SQLSTATE dado en .orig (como asyncpg)."""
    from sqlalchemy.exc import IntegrityError

    orig = SimpleNamespace(sqlstate=sqlstate)
    return IntegrityError("stmt", {}, orig)


@pytest.mark.asyncio
async def test_handler_traduce_unique_violation_a_409():
    from app.main import integrity_error_handler

    resp = await integrity_error_handler(SimpleNamespace(), _integrity_error("23505"))
    assert resp.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_handler_otras_integrity_errors_van_a_500():
    """Una FK rota o un NOT NULL (23503 / 23502) son bugs reales, no 409."""
    from app.main import integrity_error_handler

    resp = await integrity_error_handler(SimpleNamespace(), _integrity_error("23503"))
    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
async def test_handler_registrado_en_la_app():
    from sqlalchemy.exc import IntegrityError

    from app.main import create_application

    app = create_application()
    assert IntegrityError in app.exception_handlers
