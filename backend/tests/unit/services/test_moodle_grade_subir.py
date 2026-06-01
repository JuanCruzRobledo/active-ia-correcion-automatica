"""Tests para MoodleGradeService.subir_correccion (Fase 3 — orquestación).

Mockea correccion_repo, moodle_sync_repo, MoodleService y ComentarioTemplateService/Link
para validar la orquestación sin DB ni red.
"""

from decimal import Decimal

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.services.moodle_grade_service import MoodleGradeService
from app.services.moodle_service import AssignmentGradeConfig


def _correccion(nota=85, tipo="TP", moodle_user_id=101):
    materia = MagicMock(moodle_course_id=38)
    comision = MagicMock(id=5, moodle_group_id=4165, materia=materia)
    rubrica = MagicMock(moodle_assign_id=11237)
    rubrica.tipo = MagicMock(value=tipo)
    entrega = MagicMock(
        alumno_nombre="Carlos Brittos", moodle_user_id=moodle_user_id,
        comision=comision, rubrica=rubrica,
    )
    correccion = MagicMock(id=9, nota=Decimal(str(nota)), entrega=entrega)
    return correccion


def _usuario():
    return MagicMock(
        id=7, moodle_username="tutor", moodle_password_encrypted="enc",
        moodle_host="https://m",
    )


@pytest.fixture
def service():
    # La verificación de permisos por comisión se testea aparte (test del helper);
    # acá la neutralizamos para enfocar los tests en la orquestación.
    with patch(
        "app.services.moodle_grade_service.verificar_acceso_comision", AsyncMock()
    ):
        svc = MoodleGradeService(AsyncMock())
        svc.correccion_repo = AsyncMock()
        svc.moodle_sync_repo = AsyncMock()
        svc.moodle_sync_repo.get_ultimo_enviado = AsyncMock(return_value=None)  # no enviado aún
        svc.moodle_sync_repo.contar_por_correccion = AsyncMock(return_value=0)
        svc.moodle_sync_repo.create = AsyncMock(side_effect=lambda s: s)
        svc.moodle = AsyncMock()
        svc.moodle.get_token = AsyncMock(return_value="tok")
        svc.moodle.save_grade = AsyncMock(return_value=None)
        # Por defecto, nadie está calificado en Moodle (el chequeo anti-pisado no dispara).
        svc.moodle.get_grades_full = AsyncMock(return_value={})
        yield svc


@pytest.mark.asyncio
async def test_subir_tp_aprobado_envia_indice_correcto(service):
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion(nota=85, tipo="TP"))
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=478, tipo="escala", scale_id=5)
    )

    await service.subir_correccion(
        correccion_id=9, comentario_final="Muy bien!", usuario=_usuario(), base_url="http://test",
    )

    # nota 85 (>=60) → índice 1 (Aprobado) en scale 5
    kwargs = service.moodle.save_grade.call_args.kwargs
    assert kwargs["grade"] == 1.0
    assert kwargs["moodle_user_id"] == 101
    assert kwargs["assignment_instance_id"] == 478
    assert "Muy bien!" in kwargs["feedback_comment"]
    assert '<a href=' in kwargs["feedback_comment"]
    assert "devolución</a>" in kwargs["feedback_comment"]
    service.moodle_sync_repo.create.assert_awaited()


@pytest.mark.asyncio
async def test_subir_no_tp_escala_numerica(service):
    service.correccion_repo.get_by_id_with_relations = AsyncMock(
        return_value=_correccion(nota=90, tipo="PARCIAL_1")
    )
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=487, tipo="numerica", grade_max=100)
    )

    await service.subir_correccion(correccion_id=9, comentario_final="Bien", usuario=_usuario(), base_url="http://test")

    assert service.moodle.save_grade.call_args.kwargs["grade"] == 90.0


@pytest.mark.asyncio
async def test_subir_idempotente_bloquea_doble_envio(service):
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion())
    service.moodle_sync_repo.get_ultimo_enviado = AsyncMock(return_value=MagicMock(id=1))  # ya enviado

    with pytest.raises(HTTPException) as exc:
        await service.subir_correccion(correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test")
    assert exc.value.status_code == 409
    service.moodle.save_grade.assert_not_called()


@pytest.mark.asyncio
async def test_subir_forzar_reenvia(service):
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion(tipo="TP"))
    service.moodle_sync_repo.get_ultimo_enviado = AsyncMock(return_value=MagicMock(id=1))
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=478, tipo="escala", scale_id=5)
    )

    await service.subir_correccion(
        correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test", forzar=True
    )
    service.moodle.save_grade.assert_awaited()


@pytest.mark.asyncio
async def test_subir_sin_moodle_user_id_es_400(service):
    service.correccion_repo.get_by_id_with_relations = AsyncMock(
        return_value=_correccion(moodle_user_id=None)
    )
    with pytest.raises(HTTPException) as exc:
        await service.subir_correccion(correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_subir_discordancia_escala_es_422(service):
    # Rúbrica TP pero assignment numérico → no se envía
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion(tipo="TP"))
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=1, tipo="numerica", grade_max=100)
    )
    with pytest.raises(HTTPException) as exc:
        await service.subir_correccion(correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test")
    assert exc.value.status_code == 422
    service.moodle.save_grade.assert_not_called()


@pytest.mark.asyncio
async def test_subir_correccion_inexistente_es_404(service):
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await service.subir_correccion(correccion_id=999, comentario_final="x", usuario=_usuario(), base_url="http://test")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_subir_bloquea_si_ya_calificada_en_moodle(service):
    # La entrega (moodle_user_id=101) ya tiene nota en Moodle → 409, sin pisar.
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion(tipo="TP"))
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=478, tipo="escala", scale_id=5)
    )
    service.moodle.get_grades_full = AsyncMock(
        return_value={101: {"timemodified": 99999, "grade": "1.0"}}
    )
    with pytest.raises(HTTPException) as exc:
        await service.subir_correccion(correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test")
    assert exc.value.status_code == 409
    service.moodle.save_grade.assert_not_called()


@pytest.mark.asyncio
async def test_subir_no_bloquea_si_entregada_sin_calificar(service):
    # "Enviado para calificar" sin nota: Moodle deja un grade con grade=-1 y timemodified>0.
    # NO debe contar como calificada → se sube normalmente.
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion(tipo="TP"))
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=478, tipo="escala", scale_id=5)
    )
    service.moodle.get_grades_full = AsyncMock(
        return_value={101: {"timemodified": 99999, "grade": "-1.00000"}}
    )
    await service.subir_correccion(correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test")
    service.moodle.save_grade.assert_awaited()


@pytest.mark.asyncio
async def test_subir_forzar_pisa_aunque_este_calificada_en_moodle(service):
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion(tipo="TP"))
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=478, tipo="escala", scale_id=5)
    )
    service.moodle.get_grades_full = AsyncMock(
        return_value={101: {"timemodified": 99999, "grade": "1.0"}}
    )
    await service.subir_correccion(
        correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test", forzar=True
    )
    service.moodle.save_grade.assert_awaited()


@pytest.mark.asyncio
async def test_subir_verificar_moodle_false_no_chequea(service):
    # El masivo usa verificar_moodle=False: no debe consultar grades ni bloquear.
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=_correccion(tipo="TP"))
    service.moodle.get_assignment_grade_config = AsyncMock(
        return_value=AssignmentGradeConfig(instance_id=478, tipo="escala", scale_id=5)
    )
    await service.subir_correccion(
        correccion_id=9, comentario_final="x", usuario=_usuario(), base_url="http://test",
        verificar_moodle=False,
    )
    service.moodle.save_grade.assert_awaited()
    service.moodle.get_grades_full.assert_not_called()
