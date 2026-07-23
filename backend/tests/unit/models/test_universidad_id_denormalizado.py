"""
Fase 0 multi-tenant: columna `universidad_id` denormalizada en las 9 tablas del
árbol de Materia, y unicidad de `materias.codigo` scopeada por universidad.

Fase 4 (multi-tenant-scoping-queries, OQ4-D7 estricto): la columna se endureció a
NOT NULL en la DB real vía la migración R7 (Fase 0) y el modelo SQLAlchemy se
alinea acá a `Mapped[int]` (ya no `Mapped[int | None]`), cerrando la divergencia
modelo/DB que dejaba pasar filas sin universidad en el motor de test (SQLite
in-memory generado desde `Base.metadata`, no desde las migraciones Alembic).

Ref: openspec/changes/multi-tenant-modelo-datos/specs/universidad-id-denormalizado/spec.md
Ref: openspec/changes/multi-tenant-scoping-queries/design.md (D7, OQ4)
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
def test_tabla_tiene_universidad_id_fk(module_path, class_name):
    import importlib

    module = importlib.import_module(module_path)
    model = getattr(module, class_name)

    col = model.__table__.columns["universidad_id"]
    assert any(
        fk.column.table.name == "universidades" for fk in col.foreign_keys
    ), f"{class_name}.universidad_id debe ser FK a universidades.id"


@pytest.mark.parametrize("module_path,class_name", TABLAS_DEL_ARBOL)
def test_tabla_tiene_universidad_id_not_null(module_path, class_name):
    """Fase 4 (D7 estricto, OQ4): NOT NULL en el modelo, alineado a la DB real
    (migración R7 de Fase 0 ya lo exigía; acá se cierra la divergencia)."""
    import importlib

    module = importlib.import_module(module_path)
    model = getattr(module, class_name)

    col = model.__table__.columns["universidad_id"]
    assert col.nullable is False, (
        f"{class_name}.universidad_id debe ser NOT NULL desde Fase 4"
    )


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
