"""PERF-015: índice en entregas.updated_at.

El polling de novedades (EntregaRepository.version) hace MAX(updated_at)+COUNT(id)
sobre `entregas`. `updated_at` viene del TimestampMixin COMPARTIDO, que no la indexa.
El fix declara el índice SCOPED en Entrega (no en el mixin, para no indexar todas las
tablas). Este test verifica que el índice existe en el metadata del modelo y que apunta
exactamente a la columna updated_at de la tabla entregas.
"""

from app.models.entrega import Entrega


def _indices_por_nombre():
    return {ix.name: ix for ix in Entrega.__table__.indexes}


def test_indice_updated_at_declarado_en_entregas():
    indices = _indices_por_nombre()
    assert "ix_entregas_updated_at" in indices, (
        "PERF-015: falta el índice ix_entregas_updated_at en Entrega.__table_args__"
    )


def test_indice_updated_at_apunta_a_la_columna_correcta():
    ix = _indices_por_nombre()["ix_entregas_updated_at"]
    columnas = [c.name for c in ix.columns]
    assert columnas == ["updated_at"]


def test_updated_at_no_indexado_en_mixin_compartido():
    """El índice es SCOPED: NO debe existir un índice equivalente en otra tabla por
    culpa del mixin (verificamos con Usuario, que también usa TimestampMixin)."""
    from app.models.usuario import Usuario

    nombres_usuario = {ix.name for ix in Usuario.__table__.indexes}
    assert "ix_usuarios_updated_at" not in nombres_usuario
    # y ningún índice de usuarios cubre updated_at aislado
    for ix in Usuario.__table__.indexes:
        cols = [c.name for c in ix.columns]
        assert cols != ["updated_at"], (
            "updated_at quedó indexado en usuarios: el índice PERF-015 no debe estar en el mixin"
        )
