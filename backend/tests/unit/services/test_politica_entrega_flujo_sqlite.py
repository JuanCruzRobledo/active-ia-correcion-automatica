"""Flujo de versiones con repositorios reales y SQLite efímero."""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.correccion import Correccion
from app.models.entrega import EntregaHistorial
from app.models.enums import EstadoEntregaEnum, TipoRubricaEnum
from app.models.rubrica import Rubrica
from app.schemas.correccion import CorreccionExternaCreate, CorreccionUpdate
from app.services.correccion_service import CorreccionService
from app.services.entrega_service import EntregaService
from tests.unit.repositories.test_ia003_reclamar_atomico import _entrega
from tests.unit.services.test_correccion_service_persistencia_subcriterios import _gemini_result_v1
from tests.unit.services.test_politica_entrega import zip_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize("dirty_again", [False, True])
async def test_sucia_a_nueva_version_requiere_evaluacion_nueva(db_session, dirty_again):
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
    assert correction.nota == 90
    assert correction.criterios_json["politica_entrega"]["nota_academica"] == 90
    second = await upload(200, dirty_again)
    assert second.entrega_id == first.entrega_id
    current = await uploads.entrega_repo.get_by_id_with_relations(first.entrega_id, load_contenido=True)
    assert current.estado == EstadoEntregaEnum.SUBIDA
    assert current.correccion is None
    assert await grades.correccion_repo.get_by_entrega_id(first.entrega_id) is None
    history = (await db_session.execute(select(EntregaHistorial))).scalar_one()
    assert history.nota_anterior == 90
    assert history.correccion_json["criterios_json"]["politica_entrega"]["nota_academica"] == 90
    assert history.analisis_archivos["limite_nota"] is None
    assert current.analisis_archivos["limite_nota"] is None
    fresh = await grades.cargar_correccion_externa(first.entrega_id, data, 1)
    assert fresh.nota == 90
    assert len((await db_session.execute(select(Correccion))).scalars().all()) == 1
    assert current.estado == EstadoEntregaEnum.CORREGIDA



@pytest.mark.asyncio
@pytest.mark.parametrize("academic,guardar_rutas", [(90, True), (35, False)])
async def test_reparacion_masiva_previsualiza_y_restaura_sin_duplicar_aviso(db_session, academic, guardar_rutas):
    from decimal import Decimal

    from app.services.politica_entrega import MARCADOR_DEVOLUCION
    from scripts.reparar_tope_entregas import reparar_correcciones

    entrega = await _entrega(db_session)
    analysis = {"version": 1, "rutas_penalizables": ["tp/build/"], "limite_nota": 50}
    entrega.analisis_archivos = {**analysis, "moodle_timemodified": 123}
    correction = Correccion(
        entrega_id=entrega.id, universidad_id=1, nota=Decimal(min(academic, 50)),
        criterios_json={"criterios": [], "politica_entrega": {
            **analysis, "nota_academica": academic,
            "rutas_penalizables": analysis["rutas_penalizables"] if guardar_rutas else [],
        }},
        comentario_general=f"Buen trabajo.\n\n{MARCADOR_DEVOLUCION} máximo 50/100.",
    )
    db_session.add(correction)
    await db_session.commit()

    assert await reparar_correcciones(db_session, universidad_id=2, aplicar=True) == 0
    assert await reparar_correcciones(db_session, universidad_id=1, aplicar=False) == 1
    assert correction.nota == min(academic, 50)
    assert "máximo 50/100" in correction.comentario_general

    assert await reparar_correcciones(db_session, universidad_id=1, aplicar=True) == 1
    await db_session.commit()
    assert correction.nota == academic
    assert correction.comentario_general.startswith("Buen trabajo.")
    assert correction.comentario_general.count(MARCADOR_DEVOLUCION) == 1
    assert "Recomendamos" in correction.comentario_general
    assert "máximo 50/100" not in correction.comentario_general
    assert entrega.analisis_archivos["limite_nota"] is None
    assert entrega.analisis_archivos["moodle_timemodified"] == 123
    assert await reparar_correcciones(db_session, universidad_id=1, aplicar=True) == 0

    service = CorreccionService(db_session)
    service._build_correccion_response = AsyncMock(side_effect=lambda c: c)
    await service.editar_correccion(
        correction.id, CorreccionUpdate(mostrar_recomendacion_archivos=False), 1,
    )
    saved = await service.editar_correccion(
        correction.id, CorreccionUpdate(comentario_general="Devolución revisada."), 1,
    )
    assert saved.nota == academic
    assert saved.comentario_general == "Devolución revisada."
    politica = saved.criterios_json["politica_entrega"]
    assert politica["mostrar_recomendacion_archivos"] is False
    assert politica["rutas_penalizables"] == ["tp/build/"]
