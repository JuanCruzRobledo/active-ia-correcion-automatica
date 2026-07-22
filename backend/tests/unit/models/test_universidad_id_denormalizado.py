"""
Fase 0 multi-tenant: columna `universidad_id` denormalizada en las 9 tablas del
árbol de Materia (nullable en esta fase), y unicidad de `materias.codigo`
scopeada por universidad.

Ref: openspec/changes/multi-tenant-modelo-datos/specs/universidad-id-denormalizado/spec.md
"""

import pytest

TABLAS_DEL_ARBOL = [
    ("app.models.materia", "Materia"),
    ("app.models.comision", "Comision"),
    ("app.models.entrega", "Entrega"),
    ("app.models.correccion", "Correccion"),
    ("app.models.unidad", "Unidad"),
    ("app.models.rubrica", "Rubrica"),
    ("app.models.examen_materia", "ExamenMateria"),
    ("app.models.cierre_cursada", "CierreCursadaRun"),
    ("app.models.avance", "AvanceSnapshot"),
]


@pytest.mark.parametrize("module_path,class_name", TABLAS_DEL_ARBOL)
def test_tabla_tiene_universidad_id_fk_nullable(module_path, class_name):
    import importlib

    module = importlib.import_module(module_path)
    model = getattr(module, class_name)

    col = model.__table__.columns["universidad_id"]
    assert col.nullable is True, f"{class_name}.universidad_id debe ser nullable en Fase 0"
    assert any(
        fk.column.table.name == "universidades" for fk in col.foreign_keys
    ), f"{class_name}.universidad_id debe ser FK a universidades.id"


@pytest.mark.parametrize("module_path,class_name", TABLAS_DEL_ARBOL)
def test_tabla_no_tiene_universidad_id_not_null_todavia(module_path, class_name):
    """Fase 0 endurece a NOT NULL vía migración (R7), no en el modelo aún."""
    import importlib

    module = importlib.import_module(module_path)
    model = getattr(module, class_name)

    col = model.__table__.columns["universidad_id"]
    assert col.nullable is True


def test_materia_ya_no_tiene_unique_global_en_codigo():
    from app.models.materia import Materia

    codigo_col = Materia.__table__.columns["codigo"]
    assert codigo_col.unique is not True


def test_materia_tiene_unique_constraint_universidad_id_codigo():
    from sqlalchemy import UniqueConstraint

    from app.models.materia import Materia

    uniques = [
        uc for uc in Materia.__table__.constraints if isinstance(uc, UniqueConstraint)
    ]
    assert any(
        set(uc.columns.keys()) == {"universidad_id", "codigo"} for uc in uniques
    )
