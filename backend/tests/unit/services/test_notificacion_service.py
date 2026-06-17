"""
Tests del NotificacionService (T6 — orquestación de la corrida semanal).

Repos y EmailService mockeados; el render (HTML/PDF/Excel) y la agregación corren
de verdad. Cubre: arma+envía las 3 tandas, refresca (o no) snapshots, idempotencia.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.notificacion_service import NotificacionService


def _u(nums):
    return {"deudas": [{"unidad": n, "tipo": "CIERRE", "estado": "pendiente"} for n in nums]}


def _alumno():
    return SimpleNamespace(
        moodle_user_id=10, nombre="Ana", apellido="Gómez", email="ana@x.com",
        comision="M26 C1-09", regional="Mendoza", actividades_faltantes=_u([4, 5]),
    )


def _make_service() -> NotificacionService:
    service = NotificacionService(db=MagicMock())
    service.materia_repo = AsyncMock()
    service.avance_repo = AsyncMock()
    service.comision_repo = AsyncMock()
    service.usuario_repo = AsyncMock()
    service.nexo_repo = AsyncMock()
    service.notif_repo = AsyncMock()
    service.email_service = AsyncMock()
    service.snapshot_service = AsyncMock()
    service.config_service = AsyncMock()
    service.config_service.get_config.return_value = MagicMock(remitente=None)

    # Datos de prueba: 1 materia, 1 alumno (Mendoza, comisión M26 C1-09, con faltantes)
    service.materia_repo.get_configuradas_dashboard.return_value = [
        MagicMock(id=1, nombre="Programación 1", etiqueta_unidad="Unidad", unidad_actual=8)
    ]
    service.avance_repo.get_ultimo_snapshot.return_value = MagicMock(id=100)
    service.avance_repo.get_alumnos_de_snapshot.return_value = [_alumno()]
    # 1 tutor académico con la comisión del alumno
    service.usuario_repo.get_tutores.return_value = [
        MagicMock(id=1, email="juan@x.com", nombre="Juan")
    ]
    # El alumno tiene comisión "M26 C1-09" (número 9) → la comisión del tutor es COMI-9.
    service.comision_repo.get_by_tutor.return_value = [
        MagicMock(materia_id=1, nombre="COMI-9")
    ]
    # 1 tutor nexo de Mendoza
    service.nexo_repo.get_activos.return_value = [
        MagicMock(email="nexo.mza@x.com", nombre="Nexo Mza", regional="Mendoza")
    ]
    service.notif_repo.refs_enviados.return_value = set()
    return service


@pytest.mark.asyncio
async def test_corrida_envia_las_tres_tandas():
    service = _make_service()

    resumen = await service.ejecutar_corrida_semanal(usuario_id=1)

    assert resumen["alumnos"] == 1
    assert resumen["tutores"] == 1
    assert resumen["nexos"] == 1
    assert "tanda_id" in resumen
    # 3 lotes enviados (alumnos, tutores, nexos)
    assert service.email_service.enviar_lote.await_count == 3
    # refresca snapshots con las credenciales del usuario de servicio
    service.snapshot_service.generar_todas_para_usuario.assert_awaited_once()


@pytest.mark.asyncio
async def test_corrida_sin_refrescar_no_genera_snapshots():
    service = _make_service()

    await service.ejecutar_corrida_semanal(usuario_id=1, refrescar=False)

    service.snapshot_service.generar_todas_para_usuario.assert_not_awaited()


@pytest.mark.asyncio
async def test_corrida_idempotente_omite_alumno_ya_enviado():
    service = _make_service()
    # El alumno (ref "10") ya figura como ENVIADO en esta tanda → se omite.
    service.notif_repo.refs_enviados.return_value = {"10"}

    resumen = await service.ejecutar_corrida_semanal(usuario_id=1, tanda_id="t-fija")

    assert resumen["alumnos"] == 0  # omitido por idempotencia
    # tutores y nexos no comparten ese ref → siguen enviándose
    assert resumen["tutores"] == 1
    assert resumen["nexos"] == 1


@pytest.mark.asyncio
async def test_corrida_usa_remitente_del_config():
    service = _make_service()
    service.config_service.get_config.return_value = MagicMock(
        remitente="notificaciones@active-ia.com"
    )

    await service.ejecutar_corrida_semanal(usuario_id=1)

    # El remitente configurado viaja en los items de cada lote enviado.
    for call in service.email_service.enviar_lote.call_args_list:
        items = call.args[0]
        assert all(it["remitente"] == "notificaciones@active-ia.com" for it in items)


@pytest.mark.asyncio
async def test_corrida_sin_destinatarios_no_envia():
    service = _make_service()
    service.avance_repo.get_alumnos_de_snapshot.return_value = []  # nadie con faltantes
    service.usuario_repo.get_tutores.return_value = []
    service.nexo_repo.get_activos.return_value = []

    resumen = await service.ejecutar_corrida_semanal(usuario_id=1)

    assert resumen == {"tanda_id": resumen["tanda_id"], "alumnos": 0, "tutores": 0, "nexos": 0}
    service.email_service.enviar_lote.assert_not_awaited()
