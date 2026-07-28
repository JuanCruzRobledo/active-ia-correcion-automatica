"""
Fase 3 multi-tenant (multi-tenant-moodle-services, OQ1): guard defensivo
`verificar_materia_universidad_activa` / `materia_pertenece_a_universidad_activa`.

Red de seguridad LOCAL en los entrypoints de sync Moodle: evita mintear un
token del campus de la universidad activa y pegarle con un course_id/group_id
de una Materia de OTRA universidad. NO es el aislamiento general de queries
(eso es Fase 4) — acá sólo se valida la materia puntual que el entrypoint
recibió.

Ref: openspec/changes/multi-tenant-moodle-services/design.md (OQ1)
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    materia_pertenece_a_universidad_activa,
    verificar_materia_universidad_activa,
)


def _materia(universidad_id):
    return MagicMock(universidad_id=universidad_id)


# ============================== verificar_materia_universidad_activa ==============================


def test_verificar_materia_misma_universidad_no_lanza():
    verificar_materia_universidad_activa(_materia(1), 1)  # no debe lanzar


def test_verificar_materia_otra_universidad_lanza_409():
    with pytest.raises(HTTPException) as exc:
        verificar_materia_universidad_activa(_materia(1), 2)
    assert exc.value.status_code == 409


def test_verificar_materia_sin_universidad_id_no_lanza():
    """Dato legado (Fase 0, backfill): materia.universidad_id NULL no es mismatch."""
    verificar_materia_universidad_activa(_materia(None), 1)


def test_verificar_materia_none_no_lanza():
    verificar_materia_universidad_activa(None, 1)


# ============================== materia_pertenece_a_universidad_activa ==============================


def test_pertenece_misma_universidad_true():
    assert materia_pertenece_a_universidad_activa(_materia(1), 1) is True


def test_pertenece_otra_universidad_false():
    assert materia_pertenece_a_universidad_activa(_materia(1), 2) is False


def test_pertenece_sin_universidad_id_true():
    assert materia_pertenece_a_universidad_activa(_materia(None), 1) is True


def test_pertenece_materia_none_false():
    assert materia_pertenece_a_universidad_activa(None, 1) is False
