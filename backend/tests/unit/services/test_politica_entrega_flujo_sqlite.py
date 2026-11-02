"""Flujo de versiones con repositorios reales y SQLite efímero."""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.correccion import Correccion
from app.models.entrega import EntregaHistorial
from app.models.enums import EstadoEntregaEnum, TipoRubricaEnum
from app.models.rubrica import Rubrica
from app.schemas.correccion import CorreccionExternaCreate
from app.services.correccion_service import CorreccionService
from app.services.entrega_service import EntregaService
from tests.unit.repositories.test_ia003_reclamar_atomico import _entrega
from tests.unit.services.test_correccion_service_persistencia_subcriterios import _gemini_result_v1
from tests.unit.services.test_politica_entrega import zip_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize("dirty_again,expected", [(False, 90), (True, 50)])
async def test_sucia_a_nueva_version_requiere_evaluacion_nueva(db_session, dirty_again, expected):
    original = await _entrega(db_session)
    rubric = Rubrica(universidad_id=1, materia_id=original.comision_id,
        tipo=TipoRubricaEnum.TP, anio=2026, titulo="TP", descripcion="Prueba",
        puntaje_maximo=100, metadata_json={}, criterios_json=[{"id": "C1", "peso": 100}],
        penalizaciones_json=[], condiciones_desaprobacion_json=[])
    db_session.add(rubric)
    await db_session.flush()
    original.rubrica_id = rubric.id
    await db_session.delete(original)
    await db_session.commit()
    uploads = EntregaService(db_session)
    grades = CorreccionService(db_session)
    # El ensamblado HTTP no participa de esta comprobación de persistencia.
    grades._build_correccion_response = AsyncMock(side_effect=lambda c: c)
    async def upload(timestamp, dirty):
        files = {"tp/src/main.py": "print(1)"}
        if dirty:
            files["tp/node_modules/lib.js"] = "dependency"
        return await uploads.crear_o_actualizar_desde_bytes(comision_id=1,
            rubrica_id=rubric.id, alumno_nombre="Alumno", archivo_nombre="tp.zip",
            contenido_bytes=zip_bytes(files), subido_por_id=1,
            modo_consolidacion="solo_codigo", moodle_timemodified=timestamp)
    first = await upload(100, True)
    data = CorreccionExternaCreate(**_gemini_result_v1()["correccion"], ia_proveedor="externo")
    correction = await grades.cargar_correccion_externa(first.entrega_id, data, 1)
    assert correction.nota == 50
    assert correction.criterios_json["politica_entrega"]["nota_academica"] == 90
    second = await upload(200, dirty_again)
    assert second.entrega_id == first.entrega_id
    current = await uploads.entrega_repo.get_by_id_with_relations(first.entrega_id, load_contenido=True)
    assert current.estado == EstadoEntregaEnum.SUBIDA
    assert current.correccion is None
    assert await grades.correccion_repo.get_by_entrega_id(first.entrega_id) is None
    history = (await db_session.execute(select(EntregaHistorial))).scalar_one()
    assert history.nota_anterior == 50
    assert history.correccion_json["criterios_json"]["politica_entrega"]["nota_academica"] == 90
    assert history.analisis_archivos["limite_nota"] == 50
    assert current.analisis_archivos["limite_nota"] == (50 if dirty_again else None)
    fresh = await grades.cargar_correccion_externa(first.entrega_id, data, 1)
    assert fresh.nota == expected
    assert len((await db_session.execute(select(Correccion))).scalars().all()) == 1
    assert current.estado == EstadoEntregaEnum.CORREGIDA
