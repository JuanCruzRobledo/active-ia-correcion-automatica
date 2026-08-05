"""CRUD-011 (entregas): el único de (rubrica, alumno) tiene que ser PARCIAL.

El índice `uq_entrega_rubrica_alumno` nació parcial (`postgresql_where activo = true`,
migración 001). La migración 002 lo volvió TOTAL a propósito, porque en ese momento el
borrado de entregas pasó a ser físico. CRUD-001 (julio 2026) reintrodujo el borrado
lógico con `deleted_at` pero no volvió a hacerlo parcial, y ahí quedó el agujero: la
fila borrada sigue ocupando el slot, así que el alumno no puede volver a entregar y
nadie puede ver qué lo está bloqueando.

Filtrar en la query del repositorio no alcanza: sin índice parcial el INSERT igual
choca contra la base y sale un IntegrityError 500 en vez del 409.

`postgresql_where` es no-op en SQLite, así que el efecto real solo se ve contra
Postgres. Por eso acá se verifica el metadata del modelo, que es lo que la migración
tiene que reflejar.
"""

from app.models.entrega import Entrega

NOMBRE = "uq_entrega_rubrica_alumno"


def _indices_por_nombre():
    return {ix.name: ix for ix in Entrega.__table__.indexes}


def test_indice_unico_declarado_sobre_rubrica_y_alumno():
    indices = _indices_por_nombre()
    assert NOMBRE in indices, f"falta el índice {NOMBRE} en Entrega.__table_args__"
    ix = indices[NOMBRE]
    assert ix.unique is True
    assert [c.name for c in ix.columns] == ["rubrica_id", "alumno_nombre"]


def test_indice_unico_es_parcial():
    ix = _indices_por_nombre()[NOMBRE]
    where = ix.dialect_kwargs.get("postgresql_where")
    assert where is not None, (
        "CRUD-011: el único de entregas es TOTAL. Una entrega borrada sigue ocupando "
        "el par (rubrica_id, alumno_nombre) y bloquea al alumno para siempre."
    )


def test_el_predicado_del_indice_excluye_las_borradas():
    ix = _indices_por_nombre()[NOMBRE]
    # sin `or ""`: un TextClause no admite evaluación booleana.
    crudo = ix.dialect_kwargs.get("postgresql_where")
    where = str(crudo).lower() if crudo is not None else ""
    assert "deleted_at" in where, (
        f"el predicado del índice debe mirar deleted_at; hoy dice: {where!r}"
    )
    assert "null" in where, (
        f"el índice solo debe cubrir las filas vivas (deleted_at IS NULL); "
        f"hoy dice: {where!r}"
    )
