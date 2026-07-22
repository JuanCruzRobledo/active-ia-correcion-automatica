"""
Fase 1 multi-tenant (multi-tenant-auth-jwt): schemas del login en dos pasos y
nueva semántica de `UserInfo.rol` (rol en la universidad activa, no el rol
global).

Ref: openspec/changes/multi-tenant-auth-jwt/design.md (D4)
Ref: openspec/changes/multi-tenant-auth-jwt/specs/login-seleccion-universidad/spec.md
Ref: openspec/changes/multi-tenant-auth-jwt/tasks.md (4.1-4.3)
"""

import pytest
from pydantic import ValidationError

from app.models.enums import RolEnum
from app.schemas.auth import (
    SeleccionarUniversidadRequest,
    SeleccionUniversidadRequerida,
    TokenResponse,
    UniversidadDisponible,
    UserInfo,
)


# ==================================== UniversidadDisponible ====================================


class TestUniversidadDisponible:
    def test_construye_con_id_nombre_rol(self):
        u = UniversidadDisponible(id=1, nombre="TUPaD", rol=RolEnum.TUTOR)
        assert u.id == 1
        assert u.nombre == "TUPaD"
        assert u.rol == RolEnum.TUTOR

    def test_falta_rol_es_invalido(self):
        with pytest.raises(ValidationError):
            UniversidadDisponible(id=1, nombre="TUPaD")

    def test_rol_invalido_rechazado(self):
        with pytest.raises(ValidationError):
            UniversidadDisponible(id=1, nombre="TUPaD", rol="NO_EXISTE")


# ================================ SeleccionarUniversidadRequest ================================


class TestSeleccionarUniversidadRequest:
    def test_construye_con_universidad_id(self):
        req = SeleccionarUniversidadRequest(universidad_id=3)
        assert req.universidad_id == 3

    def test_falta_universidad_id_es_invalido(self):
        with pytest.raises(ValidationError):
            SeleccionarUniversidadRequest()


# =================================== Respuesta intermedia de login ===================================


class TestSeleccionUniversidadRequerida:
    def test_requiere_seleccion_true_por_default(self):
        resp = SeleccionUniversidadRequerida(
            universidades=[UniversidadDisponible(id=1, nombre="TUPaD", rol=RolEnum.TUTOR)],
            token_transicion="tok",
        )
        assert resp.requiere_seleccion is True

    def test_lista_universidades_con_dos_o_mas_opciones(self):
        resp = SeleccionUniversidadRequerida(
            universidades=[
                UniversidadDisponible(id=1, nombre="TUPaD", rol=RolEnum.TUTOR),
                UniversidadDisponible(id=2, nombre="Otra Uni", rol=RolEnum.COORDINADOR),
            ],
            token_transicion="tok-transicion",
        )
        assert len(resp.universidades) == 2
        assert resp.universidades[1].rol == RolEnum.COORDINADOR

    def test_no_tiene_access_token(self):
        resp = SeleccionUniversidadRequerida(universidades=[], token_transicion="tok")
        assert not hasattr(resp, "access_token")

    def test_lleva_token_transicion_para_identificar_al_usuario_en_el_paso_2(self):
        """D4/apply: portador de identidad recomendado para POST
        /auth/select-universidad — un token corto de transición, NO el
        access_token final."""
        resp = SeleccionUniversidadRequerida(
            universidades=[UniversidadDisponible(id=1, nombre="TUPaD", rol=RolEnum.TUTOR)],
            token_transicion="tok-transicion",
        )
        assert resp.token_transicion == "tok-transicion"


# ====================================== UserInfo ======================================


class TestUserInfo:
    def _base_kwargs(self, **over):
        kwargs = dict(
            id=1,
            username="tutor1",
            nombre="Tutor Uno",
            rol=RolEnum.TUTOR,
            primer_login=False,
            universidad_activa_id=5,
            es_superadmin=False,
        )
        kwargs.update(over)
        return kwargs

    def test_rol_de_membresia_activa(self):
        """4.3: UserInfo con rol de membresía (no rol global)."""
        info = UserInfo(**self._base_kwargs(rol=RolEnum.COORDINADOR, universidad_activa_id=5))
        assert info.rol == RolEnum.COORDINADOR
        assert info.universidad_activa_id == 5
        assert info.es_superadmin is False

    def test_superadmin_sin_universidad_rol_none(self):
        """4.3: UserInfo de superadmin (rol=None, universidad_activa_id=None)."""
        info = UserInfo(
            **self._base_kwargs(rol=None, universidad_activa_id=None, es_superadmin=True)
        )
        assert info.rol is None
        assert info.universidad_activa_id is None
        assert info.es_superadmin is True

    def test_token_response_model_rebuild_resuelve_forward_ref(self):
        """El model_rebuild() de TokenResponse debe seguir resolviendo el forward
        ref 'UserInfo' aunque UserInfo haya ganado campos nuevos."""
        info = UserInfo(**self._base_kwargs())
        resp = TokenResponse(access_token="tok", user=info)
        assert resp.user.universidad_activa_id == 5
