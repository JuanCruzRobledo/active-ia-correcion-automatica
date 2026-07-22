"""
CRUD-015: Usuario ya no arrastra el campo muerto deleted_at.

Usuario heredaba SoftDeleteMixin (deleted_at) pero su soft delete real es `activo`;
ningún código setea Usuario.deleted_at (solo TutorNexo usa el mixin de verdad).
El campo existía en la tabla, siempre NULL, y confundía. Se elimina.
"""


def test_usuario_no_tiene_deleted_at():
    from app.models.usuario import Usuario

    assert "deleted_at" not in Usuario.__table__.columns
    # el soft delete real sigue siendo `activo`
    assert "activo" in Usuario.__table__.columns


def test_tutor_nexo_conserva_deleted_at():
    """TutorNexo SÍ usa el mixin de verdad — no se toca."""
    from app.models.tutor_nexo import TutorNexo

    assert "deleted_at" in TutorNexo.__table__.columns
