"""Tests del validador de email del perfil (UpdateEmailRequest)."""

import pytest

from app.schemas.perfil import UpdateEmailRequest


def test_email_valido_se_acepta():
    assert UpdateEmailRequest(email="tutor@utn.edu.ar").email == "tutor@utn.edu.ar"


def test_email_se_normaliza_trim():
    assert UpdateEmailRequest(email="  tutor@utn.edu.ar  ").email == "tutor@utn.edu.ar"


def test_email_vacio_o_none_queda_none():
    # Permite QUITAR el email (no recibir notificaciones).
    assert UpdateEmailRequest(email="").email is None
    assert UpdateEmailRequest(email="   ").email is None
    assert UpdateEmailRequest(email=None).email is None


@pytest.mark.parametrize("malo", ["sin-arroba", "a@b", "a@b.", "@x.com", "a b@x.com"])
def test_email_invalido_lanza(malo):
    with pytest.raises(ValueError):
        UpdateEmailRequest(email=malo)
