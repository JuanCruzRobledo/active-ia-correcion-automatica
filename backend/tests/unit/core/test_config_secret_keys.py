"""Tests del fail-fast de arranque ante SECRET_KEY/ENCRYPTION_KEY default (SEC-003)."""

import pytest
from pydantic import ValidationError

from app.core.config import (
    _DEFAULT_ENCRYPTION_KEY,
    _DEFAULT_SECRET_KEY,
    Settings,
)

CLAVE_REAL_SECRET = "a" * 64
CLAVE_REAL_ENCRYPTION = "sBw0aQ7t9K3vX1zR5nY8pL2cJ6hF4dG0mT7uV9wE1sA="


def _build(**overrides) -> Settings:
    # _env_file=None aísla el test de cualquier .env presente en la máquina.
    return Settings(_env_file=None, **overrides)


def test_secret_key_default_en_produccion_aborta_el_arranque():
    with pytest.raises(ValidationError):
        _build(
            DEBUG=False,
            SECRET_KEY=_DEFAULT_SECRET_KEY,
            ENCRYPTION_KEY=CLAVE_REAL_ENCRYPTION,
        )


def test_encryption_key_default_en_produccion_aborta_el_arranque():
    with pytest.raises(ValidationError):
        _build(
            DEBUG=False,
            SECRET_KEY=CLAVE_REAL_SECRET,
            ENCRYPTION_KEY=_DEFAULT_ENCRYPTION_KEY,
        )


def test_defaults_permitidos_en_desarrollo():
    settings = _build(
        DEBUG=True,
        SECRET_KEY=_DEFAULT_SECRET_KEY,
        ENCRYPTION_KEY=_DEFAULT_ENCRYPTION_KEY,
    )
    assert settings.SECRET_KEY == _DEFAULT_SECRET_KEY
    assert settings.ENCRYPTION_KEY == _DEFAULT_ENCRYPTION_KEY


def test_claves_reales_en_produccion_arrancan_sin_error():
    settings = _build(
        DEBUG=False,
        SECRET_KEY=CLAVE_REAL_SECRET,
        ENCRYPTION_KEY=CLAVE_REAL_ENCRYPTION,
    )
    assert settings.SECRET_KEY == CLAVE_REAL_SECRET
    assert settings.ENCRYPTION_KEY == CLAVE_REAL_ENCRYPTION


def test_mensaje_de_error_de_secret_key_guia_la_remediacion():
    with pytest.raises(ValidationError) as exc:
        _build(
            DEBUG=False,
            SECRET_KEY=_DEFAULT_SECRET_KEY,
            ENCRYPTION_KEY=CLAVE_REAL_ENCRYPTION,
        )
    mensaje = str(exc.value)
    assert "SECRET_KEY" in mensaje
    assert "openssl rand -hex 32" in mensaje


def test_mensaje_de_error_de_encryption_key_guia_la_remediacion():
    with pytest.raises(ValidationError) as exc:
        _build(
            DEBUG=False,
            SECRET_KEY=CLAVE_REAL_SECRET,
            ENCRYPTION_KEY=_DEFAULT_ENCRYPTION_KEY,
        )
    mensaje = str(exc.value)
    assert "ENCRYPTION_KEY" in mensaje
    assert "Fernet.generate_key()" in mensaje


def test_placeholder_de_env_example_tambien_se_rechaza():
    # .env.example trae "change-me-in-production", que NO es igual al default de
    # config.py. Es el vector real de SEC-003: copiar .env.example y desplegar
    # sin tocar las claves. Se rechaza por prefijo.
    with pytest.raises(ValidationError):
        _build(
            DEBUG=False,
            SECRET_KEY="change-me-in-production",
            ENCRYPTION_KEY=CLAVE_REAL_ENCRYPTION,
        )


def test_ambas_claves_default_se_reportan_juntas():
    # El validador acumula TODAS las claves inseguras, no corta en la primera.
    with pytest.raises(ValidationError) as exc:
        _build(
            DEBUG=False,
            SECRET_KEY=_DEFAULT_SECRET_KEY,
            ENCRYPTION_KEY=_DEFAULT_ENCRYPTION_KEY,
        )
    mensaje = str(exc.value)
    assert "SECRET_KEY" in mensaje
    assert "ENCRYPTION_KEY" in mensaje
