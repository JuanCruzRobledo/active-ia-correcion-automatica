"""Tests para PorEntregarService.listar (vista 'Por entregar').

Mockea correccion_repo y moodle_sync_repo: valida el armado de items
(etiqueta de nota, requiere_comentario_tutor, estado del último intento) y los
contadores, sin DB ni red.
"""

from decimal import Decimal

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.enums import MoodleSyncEstado, RolEnum
from app.services.por_entregar_service import PorEntregarService


def _correccion(correccion_id, *, nota=85, tipo="TP", alumno="Selene Miño"):
    materia = MagicMock(id=38, nombre="Programación I", moodle_course_id=38)
    comision = MagicMock(id=5, nombre="K1051", materia=materia)
    rubrica = MagicMock(id=11, titulo="TP3 - API REST", moodle_assign_id=478)
    rubrica.tipo = MagicMock(value=tipo)
    entrega = MagicMock(
        id=correccion_id * 10,
        alumno_nombre=alumno,
        moodle_user_id=101,
        comision=comision,
        rubrica=rubrica,
    )
    correccion = MagicMock(id=correccion_id, nota=Decimal(str(nota)), entrega=entrega)
    correccion.created_at = None
    return correccion


def _service(correcciones, estados=None, no_vinculadas=0):
    svc = PorEntregarService(AsyncMock())
    svc.correccion_repo = AsyncMock()
    svc.correccion_repo.get_pendientes_subida_moodle = AsyncMock(return_value=correcciones)
    svc.correccion_repo.contar_no_vinculadas_moodle = AsyncMock(return_value=no_vinculadas)
    svc.moodle_sync_repo = AsyncMock()
    svc.moodle_sync_repo.get_ultimo_estado_por_correcciones = AsyncMock(
        return_value=estados or {}
    )
    return svc


def _tutor():
    return MagicMock(id=7, rol=RolEnum.TUTOR)


@pytest.mark.asyncio
async def test_tp_aprobado_etiqueta_y_automatico():
    svc = _service([_correccion(1, nota=85, tipo="TP")])
    res = await svc.listar(_tutor(), rol=RolEnum.TUTOR)

    assert len(res.items) == 1
    item = res.items[0]
    assert item.tipo_rubrica == "TP"
    assert item.etiqueta_nota == "Aprobado"
    assert item.requiere_comentario_tutor is False
    assert item.estado_ultimo_intento == "none"
    assert item.alumno_nombre == "Selene Miño"
    assert item.materia_nombre == "Programación I"


@pytest.mark.asyncio
async def test_tp_desaprobado_por_umbral():
    svc = _service([_correccion(1, nota=55, tipo="TP")])
    res = await svc.listar(_tutor(), rol=RolEnum.TUTOR)
    assert res.items[0].etiqueta_nota == "Desaprobado"


@pytest.mark.asyncio
async def test_no_tp_requiere_comentario_y_etiqueta_numerica():
    svc = _service([_correccion(1, nota=90, tipo="PARCIAL_1")])
    res = await svc.listar(_tutor(), rol=RolEnum.TUTOR)

    item = res.items[0]
    assert item.requiere_comentario_tutor is True
    assert item.etiqueta_nota == "90"


@pytest.mark.asyncio
async def test_ultimo_intento_error_se_etiqueta():
    estados = {1: (MoodleSyncEstado.ERROR, "Moodle 502")}
    svc = _service([_correccion(1, tipo="TP")], estados=estados)
    res = await svc.listar(_tutor(), rol=RolEnum.TUTOR)

    item = res.items[0]
    assert item.estado_ultimo_intento == "error"
    assert item.mensaje_error == "Moodle 502"


@pytest.mark.asyncio
async def test_contadores_automaticas_y_requieren():
    correcciones = [
        _correccion(1, tipo="TP"),
        _correccion(2, tipo="TP"),
        _correccion(3, tipo="FINAL"),
    ]
    svc = _service(correcciones, no_vinculadas=4)
    res = await svc.listar(_tutor(), rol=RolEnum.TUTOR)

    assert res.total_pendientes == 3
    assert res.total_automaticas == 2  # los dos TP
    assert res.total_requieren_comentario == 1  # el FINAL
    assert res.no_vinculadas == 4


@pytest.mark.asyncio
async def test_admin_consulta_todas_las_comisiones():
    admin = MagicMock(id=1, rol=RolEnum.ADMIN)
    svc = _service([_correccion(1)])
    await svc.listar(admin, rol=RolEnum.ADMIN)

    # es_admin=True debe propagarse a los repos
    svc.correccion_repo.get_pendientes_subida_moodle.assert_awaited_once_with(1, True)
    svc.correccion_repo.contar_no_vinculadas_moodle.assert_awaited_once_with(1, True)


@pytest.mark.asyncio
async def test_tutor_solo_sus_comisiones():
    svc = _service([])
    await svc.listar(_tutor(), rol=RolEnum.TUTOR)
    svc.correccion_repo.get_pendientes_subida_moodle.assert_awaited_once_with(7, False)
