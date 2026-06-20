"""Configuración de cascada de borrado de Correccion.

Regresión (DELETE /entregas/{id} 500): borrar una entrega corregida cascadeaba
hasta la corrección, pero los registros de `moodle_sync` (auditoría del envío a
Moodle) quedaban colgados → ForeignKeyViolationError sobre
fk_moodle_sync_correccion_id_correcciones.

El harness es SQLite y los modelos con JSONB/ARRAY no crean tabla ahí, así que no
podemos ejercitar el borrado real. Sí podemos pinear la CONFIGURACIÓN del mapper,
que es exactamente lo que estaba mal: la relación con delete-orphan faltaba.
"""

from sqlalchemy.orm import configure_mappers

# Importar ambos modelos asegura que el registry los conozca antes de configurar.
from app.models.correccion import Correccion
from app.models.moodle_sync import MoodleSync  # noqa: F401


def test_correccion_cascada_borra_moodle_sync():
    configure_mappers()
    rel = Correccion.__mapper__.relationships.get("moodle_syncs")
    assert rel is not None, (
        "Correccion debe declarar la relación 'moodle_syncs' para que el ORM "
        "borre los registros de auditoría al borrar la corrección"
    )
    assert rel.cascade.delete is True
    assert rel.cascade.delete_orphan is True


def test_moodle_sync_correccion_back_populates():
    """La relación inversa en MoodleSync debe quedar emparejada (back_populates)."""
    configure_mappers()
    rel = MoodleSync.__mapper__.relationships.get("correccion")
    assert rel is not None
    assert rel.back_populates == "moodle_syncs"
