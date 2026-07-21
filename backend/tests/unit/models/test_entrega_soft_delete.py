"""
CRUD-001: Entrega gana soft delete via deleted_at (SoftDeleteMixin).

Antes, Entrega heredaba solo TimestampMixin y su unico campo de baja era
`archivado` (flag de UI, no borrado). El borrado era db.delete() fisico e
irreversible: se perdia el trabajo y la nota del alumno sin huella de quien borro.
"""

from datetime import datetime

from app.models.entrega import Entrega
from app.models.enums import TipoActividadEnum


def test_entrega_expone_deleted_at_default_none():
    e = Entrega()
    # El default None del mixin es del lado Python (aplica en el INSERT); antes
    # de persistir, el atributo existe y arranca en None.
    assert hasattr(e, "deleted_at")
    assert e.deleted_at is None


def test_entrega_is_deleted_property():
    e = Entrega()
    assert e.is_deleted is False
    e.deleted_at = datetime.utcnow()
    assert e.is_deleted is True


def test_tipos_de_actividad_de_borrado_existen():
    """Son los primeros tipos de auditoria de BORRADO del sistema."""
    assert TipoActividadEnum.ENTREGA_ELIMINADA.value == "ENTREGA_ELIMINADA"
    assert TipoActividadEnum.ENTREGA_RESTAURADA.value == "ENTREGA_RESTAURADA"
