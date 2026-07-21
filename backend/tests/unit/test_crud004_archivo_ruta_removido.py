"""
CRUD-004: archivo_ruta era una ruta FANTASMA — se fabricaba como
`/uploads/entregas/{hash}_{filename}` pero el archivo NUNCA se escribía a disco.
Era un dato mentiroso en la DB y en la API, y el `os.remove(archivo_ruta)` de las
cascadas de hard delete era código muerto (la ruta jamás existía). Se elimina.
"""


def test_entrega_no_tiene_archivo_ruta():
    from app.models.entrega import Entrega, EntregaHistorial

    assert "archivo_ruta" not in Entrega.__table__.columns
    assert "archivo_ruta" not in EntregaHistorial.__table__.columns


def test_response_no_expone_archivo_ruta():
    from app.schemas.entrega import EntregaResponse

    assert "archivo_ruta" not in EntregaResponse.model_fields


def test_cascadas_de_hard_delete_no_referencian_archivo_ruta():
    """El os.remove(archivo_ruta) era código muerto (la ruta no existía)."""
    import inspect

    from app.repositories import (
        comision_repository,
        materia_repository,
        rubrica_repository,
    )

    for mod in (comision_repository, materia_repository, rubrica_repository):
        assert "archivo_ruta" not in inspect.getsource(mod)
