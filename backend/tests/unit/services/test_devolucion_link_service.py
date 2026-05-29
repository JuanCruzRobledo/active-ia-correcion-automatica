"""Tests para DevolucionLinkService (Fase 3 — link público al PDF de devolución).

El token es un JWT firmado con SECRET_KEY que codifica {tipo: 'devolucion', correccion_id, exp}.
No expone datos de otros alumnos: cada token apunta a UNA corrección.
"""

import pytest

from app.services.devolucion_link_service import (
    DevolucionLinkService,
    TokenDevolucionInvalido,
)


def test_generar_y_validar_roundtrip():
    token = DevolucionLinkService.generar_token(correccion_id=42)
    assert DevolucionLinkService.validar_token(token) == 42


def test_token_alterado_es_rechazado():
    token = DevolucionLinkService.generar_token(correccion_id=42)
    with pytest.raises(TokenDevolucionInvalido):
        DevolucionLinkService.validar_token(token + "x")


def test_token_de_otro_tipo_es_rechazado():
    # Un JWT válido pero SIN tipo 'devolucion' (p. ej. un token de sesión) no debe servir.
    from jose import jwt
    from app.core.config import settings

    otro = jwt.encode(
        {"user_id": 1, "rol": "TUTOR"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    with pytest.raises(TokenDevolucionInvalido):
        DevolucionLinkService.validar_token(otro)


def test_token_expirado_es_rechazado():
    token = DevolucionLinkService.generar_token(correccion_id=42, ttl_dias=-1)  # ya expirado
    with pytest.raises(TokenDevolucionInvalido):
        DevolucionLinkService.validar_token(token)


def test_generar_path_incluye_token():
    token = DevolucionLinkService.generar_token(correccion_id=7)
    path = DevolucionLinkService.generar_path(correccion_id=7)
    assert path.startswith("/api/v1/public/devoluciones/")
    # el path debe contener un token válido que resuelva a la misma corrección
    token_en_path = path.rsplit("/", 1)[-1]
    assert DevolucionLinkService.validar_token(token_en_path) == 7
