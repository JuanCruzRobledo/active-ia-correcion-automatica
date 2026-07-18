"""Tests de `Subcriterio.peso` y validación condicional por `schema_version`.

Change: peso-por-subcriterio (openspec/changes/peso-por-subcriterio, D1-D3).

- v1 (schema_version=1, default): subcriterios sin peso siguen validando
  exactamente igual que antes (comportamiento actual, sin exigir peso).
- v2 (schema_version=2): cada subcriterio DEBE tener `peso` (1-100) y la suma
  de `peso` de los subcriterios de un criterio debe ser exactamente igual al
  `peso` de ese criterio.
"""

import pytest
from pydantic import ValidationError

from app.models.enums import TipoRubricaEnum
from app.schemas.rubrica import RubricaCreate, RubricaUpdate, Subcriterio


def _sub(**overrides) -> dict:
    base = {
        "id": "C1.1",
        "descripcion": "Descripción del subcriterio",
        "evidencias": ["Evidencia 1"],
    }
    base.update(overrides)
    return base


def _criterio(peso=100, subcriterios=None, **overrides) -> dict:
    base = {
        "id": "C1",
        "nombre": "Criterio 1",
        "descripcion": "Descripción del criterio",
        "peso": peso,
        "subcriterios": subcriterios or [_sub()],
    }
    base.update(overrides)
    return base


def _rubrica_create_kwargs(schema_version=None, criterios_json=None) -> dict:
    kwargs = dict(
        materia_id=1,
        tipo=TipoRubricaEnum.TP,
        numero=1,
        anio=2026,
        titulo="TP1 - Test",
        descripcion="Descripción de prueba",
        criterios_json=criterios_json or [_criterio()],
    )
    if schema_version is not None:
        kwargs["schema_version"] = schema_version
    return kwargs


# ---------------------------------------------------------------------------
# 2.1 — Subcriterio.peso opcional a nivel modelo
# ---------------------------------------------------------------------------


def test_subcriterio_sin_peso_parsea_ok_v1():
    """v1: un dict sin `peso` sigue parseando (comportamiento actual intacto)."""
    sub = Subcriterio(**_sub())
    assert sub.peso is None


def test_subcriterio_con_peso_valido_parsea_ok():
    sub = Subcriterio(**_sub(peso=10))
    assert sub.peso == 10


@pytest.mark.parametrize("peso_invalido", [0, 101, -5])
def test_subcriterio_peso_fuera_de_rango_falla(peso_invalido):
    with pytest.raises(ValidationError):
        Subcriterio(**_sub(peso=peso_invalido))


# ---------------------------------------------------------------------------
# 2.3 — Helper de validación v2 (sum(sub.peso) == criterio.peso)
# ---------------------------------------------------------------------------


def test_rubrica_v2_subcriterios_suman_peso_criterio_pasa():
    criterios = [
        _criterio(
            peso=100,
            subcriterios=[_sub(id="C1.1", peso=60), _sub(id="C1.2", peso=40)],
        )
    ]
    data = RubricaCreate(**_rubrica_create_kwargs(schema_version=2, criterios_json=criterios))
    assert data.schema_version == 2


def test_rubrica_v2_subcriterios_no_suman_peso_criterio_falla():
    criterios = [
        _criterio(
            peso=100,
            subcriterios=[_sub(id="C1.1", peso=60), _sub(id="C1.2", peso=30)],
        )
    ]
    with pytest.raises(ValidationError):
        RubricaCreate(**_rubrica_create_kwargs(schema_version=2, criterios_json=criterios))


def test_rubrica_v2_subcriterio_sin_peso_falla():
    criterios = [
        _criterio(
            peso=100,
            subcriterios=[_sub(id="C1.1"), _sub(id="C1.2", peso=100)],
        )
    ]
    with pytest.raises(ValidationError):
        RubricaCreate(**_rubrica_create_kwargs(schema_version=2, criterios_json=criterios))


def test_rubrica_v1_sin_peso_en_subcriterios_pasa_sin_exigir_peso():
    """v1: ningún subcriterio tiene peso — NO se exige (reparto implícito, igual que hoy)."""
    criterios = [
        _criterio(
            peso=100,
            subcriterios=[_sub(id="C1.1"), _sub(id="C1.2")],
        )
    ]
    data = RubricaCreate(**_rubrica_create_kwargs(schema_version=1, criterios_json=criterios))
    assert data.schema_version == 1


def test_rubrica_update_v2_subcriterios_no_suman_falla():
    criterios = [
        _criterio(
            peso=100,
            subcriterios=[_sub(id="C1.1", peso=50), _sub(id="C1.2", peso=10)],
        )
    ]
    with pytest.raises(ValidationError):
        RubricaUpdate(schema_version=2, criterios_json=criterios)


def test_rubrica_update_v2_subcriterios_suman_pasa():
    criterios = [
        _criterio(
            peso=100,
            subcriterios=[_sub(id="C1.1", peso=50), _sub(id="C1.2", peso=50)],
        )
    ]
    update = RubricaUpdate(schema_version=2, criterios_json=criterios)
    assert update.schema_version == 2


def test_rubrica_update_v1_sin_peso_pasa():
    criterios = [_criterio(peso=100, subcriterios=[_sub(id="C1.1"), _sub(id="C1.2")])]
    update = RubricaUpdate(criterios_json=criterios)
    assert update.schema_version is None


# ---------------------------------------------------------------------------
# 2.5 — `schema_version` en los schemas (defaults)
# ---------------------------------------------------------------------------


def test_rubrica_create_schema_version_default_es_1():
    """Un cliente que no manda schema_version preserva el comportamiento previo (v1)."""
    data = RubricaCreate(**_rubrica_create_kwargs())
    assert data.schema_version == 1


def test_rubrica_update_schema_version_default_es_none():
    """RubricaUpdate no fuerza versión si no se manda (no pisa la existente)."""
    update = RubricaUpdate(titulo="Nuevo título")
    assert update.schema_version is None


# ---------------------------------------------------------------------------
# 2.6 — Caracterización v1: la validación general no cambió
# ---------------------------------------------------------------------------


def test_rubrica_v1_suma_pesos_criterios_sigue_validando_100():
    """Camino v1 intacto: la suma de pesos de CRITERIOS sigue exigiendo 100."""
    criterios = [_criterio(id="C1", peso=60), _criterio(id="C2", peso=30)]
    with pytest.raises(ValidationError):
        RubricaCreate(**_rubrica_create_kwargs(schema_version=1, criterios_json=criterios))


def test_rubrica_v1_ids_subcriterios_unicos_sigue_validando():
    """Camino v1 intacto: subcriterio IDs duplicados dentro de un criterio siguen fallando."""
    criterios = [
        _criterio(
            peso=100,
            subcriterios=[_sub(id="C1.1"), _sub(id="C1.1")],
        )
    ]
    with pytest.raises(ValidationError):
        RubricaCreate(**_rubrica_create_kwargs(schema_version=1, criterios_json=criterios))
