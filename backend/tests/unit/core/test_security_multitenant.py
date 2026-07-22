"""
Fase 1 multi-tenant (multi-tenant-auth-jwt): nuevo payload del JWT.

`create_access_token` deja de recibir el rol global del usuario y pasa a
recibir la universidad activa, el rol de la membresía activa y el flag
superadmin, los 3 keyword-only para que ningún caller viejo compile en
silencio con el argumento equivocado.

Ref: openspec/changes/multi-tenant-auth-jwt/design.md (D1, D2)
Ref: openspec/changes/multi-tenant-auth-jwt/specs/jwt-universidad-activa/spec.md
Ref: openspec/changes/multi-tenant-auth-jwt/tasks.md (3.1-3.5)
"""

import pytest

from app.core.security import create_access_token, create_transitional_token, decode_token


# ====================== 3.1 / 3.4: payload nuevo + triangulación ======================


def test_create_access_token_payload_incluye_los_campos_multitenant():
    token = create_access_token(
        1, "admin", rol="TUTOR", universidad_activa_id=7, es_superadmin=False
    )
    payload = decode_token(token)

    assert payload["user_id"] == 1
    assert payload["username"] == "admin"
    assert payload["universidad_activa_id"] == 7
    assert payload["rol"] == "TUTOR"
    assert payload["es_superadmin"] is False


def test_create_access_token_caso_superadmin_sin_universidad():
    """Triangulación: caso superadmin (universidad_activa_id/rol = None)."""
    token = create_access_token(
        2, "root", rol=None, universidad_activa_id=None, es_superadmin=True
    )
    payload = decode_token(token)

    assert payload["universidad_activa_id"] is None
    assert payload["rol"] is None
    assert payload["es_superadmin"] is True


def test_create_access_token_caso_normal_todos_los_campos_poblados():
    """Triangulación: caso normal (todos los campos multi-tenant poblados)."""
    token = create_access_token(
        3, "coordi", rol="COORDINADOR", universidad_activa_id=5, es_superadmin=False
    )
    payload = decode_token(token)

    assert payload["user_id"] == 3
    assert payload["rol"] == "COORDINADOR"
    assert payload["universidad_activa_id"] == 5
    assert payload["es_superadmin"] is False


# ====================== 3.2: keyword-only fuerza fallo ruidoso ======================


def test_create_access_token_rechaza_llamada_posicional_estilo_viejo():
    """Estilo viejo: create_access_token(user_id, username, rol) posicional.

    La firma nueva solo acepta user_id/username posicionales; rol y el resto
    son keyword-only, así que un caller desactualizado debe fallar con
    TypeError (ruidoso), no colar el rol en el lugar equivocado.
    """
    with pytest.raises(TypeError):
        create_access_token(1, "admin", "ADMIN")  # type: ignore[misc]


def test_create_access_token_rechaza_universidad_activa_id_posicional():
    with pytest.raises(TypeError):
        create_access_token(1, "admin", "ADMIN", 7)  # type: ignore[misc]


# ====================== 3.4: retrocompat de decode_token ======================


def test_decode_token_acepta_payload_de_token_viejo_sin_claims_nuevos(monkeypatch):
    """Un token viejo (emitido antes de este change) no trae universidad_activa_id
    ni es_superadmin. decode_token no debe romperse por su ausencia — sigue
    devolviendo el dict crudo tal cual lo decodifica jose."""
    from datetime import datetime, timedelta

    from jose import jwt

    from app.core.config import settings

    payload_viejo = {
        "user_id": 9,
        "username": "viejo",
        "rol": "TUTOR",
        "exp": datetime.utcnow() + timedelta(days=1),
        "iat": datetime.utcnow(),
    }
    token_viejo = jwt.encode(payload_viejo, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    decoded = decode_token(token_viejo)

    assert decoded["user_id"] == 9
    assert "universidad_activa_id" not in decoded
    assert "es_superadmin" not in decoded


# ================== token de transición para POST /auth/select-universidad ==================


def test_create_transitional_token_lleva_scope_seleccion():
    token = create_transitional_token(4, "multiuni")
    payload = decode_token(token)

    assert payload["user_id"] == 4
    assert payload["username"] == "multiuni"
    assert payload["scope"] == "seleccion"


def test_create_transitional_token_no_lleva_claims_multitenant():
    """No es un token de acceso: no debe llevar universidad_activa_id/rol/
    es_superadmin (para no poder usarse como si fuera un token final)."""
    token = create_transitional_token(4, "multiuni")
    payload = decode_token(token)

    assert "universidad_activa_id" not in payload
    assert "es_superadmin" not in payload


def test_create_transitional_token_expira_mas_rapido_que_el_normal():
    from datetime import timedelta

    token_transicion = create_transitional_token(4, "multiuni")
    token_normal = create_access_token(
        4, "multiuni", rol="TUTOR", universidad_activa_id=1, es_superadmin=False
    )

    exp_transicion = decode_token(token_transicion)["exp"]
    exp_normal = decode_token(token_normal)["exp"]

    assert exp_transicion < exp_normal
