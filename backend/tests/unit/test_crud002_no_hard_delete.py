"""
CRUD-002: se eliminó el flag ALLOW_HARD_DELETE. Los DELETE son SIEMPRE soft, nunca
físico — regla dura del proyecto (auditoría). El flag sobrecargaba el mismo verbo
DELETE con dos semánticas opuestas según config: un solo cambio de env degradaba
todo el sistema a borrado destructivo (incluido el audit log).
"""


def test_settings_no_tiene_allow_hard_delete():
    from app.core.config import settings

    assert not hasattr(settings, "ALLOW_HARD_DELETE")


def test_ningun_service_consulta_allow_hard_delete():
    import inspect

    from app.services import (
        comision_service,
        entrega_service,
        materia_service,
        rubrica_service,
        usuario_service,
    )

    for mod in (materia_service, comision_service, rubrica_service,
                usuario_service, entrega_service):
        src = inspect.getsource(mod)
        assert "settings.ALLOW_HARD_DELETE" not in src
