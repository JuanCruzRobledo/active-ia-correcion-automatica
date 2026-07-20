"""
Tests de autorizacion por pertenencia en el router de entregas (SEC-002).

Antes de este change los 8 endpoints usaban SOLO `require_any_authenticated`,
que es literalmente `return user`: cualquier usuario autenticado leia el codigo
fuente de cualquier alumno y borraba entregas de cualquier comision.

Cubre los 5 endpoints de recurso unico y de creacion. El listado (`GET /`)
y los 2 de lote van en sus propios archivos por tener semantica distinta
(scoping y particion en vez de 403).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.routers.entregas import (
    archivar_entregas,
    crear_entrega,
    crear_entregas_masivas,
    eliminar_entrega,
    eliminar_entregas_masivo,
    listar_entregas,
    obtener_contenido_entrega,
    obtener_entrega,
)
from app.schemas.entrega import EntregaAccionMasivaResponse

ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)
TUTOR = SimpleNamespace(id=5, rol=RolEnum.TUTOR)
COORD = SimpleNamespace(id=7, rol=RolEnum.COORDINADOR)
GESTOR = SimpleNamespace(id=9, rol=RolEnum.GESTOR)

# Filas del LEFT JOIN de pertenencia: (comision_id, comision_tutor_id, coord_materia_id)
_ES_TUTOR = (10, 555, None)
_ES_COORDINADOR = (10, None, 777)
_SIN_PERTENENCIA = (10, None, None)

# Fila de resolucion de entrega: (entrega_id, comision_id)
_ENTREGA_42 = (42, 10)


def _db(*rows):
    """db async cuyo execute().first() devuelve rows[i] en la i-esima llamada."""
    db = AsyncMock()
    resultados = []
    for r in rows:
        res = MagicMock()
        res.first.return_value = r
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


# ===================== GET /entregas/{id} =====================


@pytest.mark.asyncio
async def test_obtener_entrega_tutor_propio_ok():
    db = _db(_ENTREGA_42, _ES_TUTOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.obtener_entrega = AsyncMock(return_value="ENTREGA")
        assert await obtener_entrega(42, current_user=TUTOR, db=db) == "ENTREGA"


@pytest.mark.asyncio
async def test_obtener_entrega_tutor_ajeno_403_sin_llamar_al_service():
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await obtener_entrega(42, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.obtener_entrega.assert_not_called()


@pytest.mark.asyncio
async def test_obtener_entrega_coordinador_de_la_materia_ok():
    db = _db(_ENTREGA_42, _ES_COORDINADOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.obtener_entrega = AsyncMock(return_value="ENTREGA")
        assert await obtener_entrega(42, current_user=COORD, db=db) == "ENTREGA"


@pytest.mark.asyncio
async def test_obtener_entrega_gestor_403():
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await obtener_entrega(42, current_user=GESTOR, db=db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_obtener_entrega_admin_ok_sin_consultar_permisos():
    db = AsyncMock()
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.obtener_entrega = AsyncMock(return_value="ENTREGA")
        assert await obtener_entrega(42, current_user=ADMIN, db=db) == "ENTREGA"
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_obtener_entrega_inexistente_404():
    db = _db(None)
    with pytest.raises(HTTPException) as exc:
        await obtener_entrega(404404, current_user=TUTOR, db=db)
    assert exc.value.status_code == 404


# ===================== GET /entregas/{id}/contenido =====================


@pytest.mark.asyncio
async def test_contenido_tutor_propio_ok():
    db = _db(_ENTREGA_42, _ES_TUTOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.obtener_contenido = AsyncMock(return_value="CODIGO")
        assert await obtener_contenido_entrega(42, current_user=TUTOR, db=db) == "CODIGO"


@pytest.mark.asyncio
async def test_contenido_ajeno_403_no_devuelve_el_codigo_del_alumno():
    """El caso mas grave de SEC-002: el codigo fuente no puede filtrarse."""
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await obtener_contenido_entrega(42, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.obtener_contenido.assert_not_called()


@pytest.mark.asyncio
async def test_contenido_coordinador_de_la_materia_ok():
    db = _db(_ENTREGA_42, _ES_COORDINADOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.obtener_contenido = AsyncMock(return_value="CODIGO")
        assert await obtener_contenido_entrega(42, current_user=COORD, db=db) == "CODIGO"


# ===================== DELETE /entregas/{id} =====================


@pytest.mark.asyncio
async def test_eliminar_entrega_propia_ok():
    db = _db(_ENTREGA_42, _ES_TUTOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.eliminar_entrega = AsyncMock(return_value=None)
        await eliminar_entrega(42, current_user=TUTOR, db=db)
        MockSvc.return_value.eliminar_entrega.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_eliminar_entrega_ajena_403_sin_borrar_nada():
    """El borrado es fisico e irreversible (CRUD-001): el service NO debe correr."""
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await eliminar_entrega(42, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.eliminar_entrega.assert_not_called()


@pytest.mark.asyncio
async def test_eliminar_entrega_gestor_403():
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await eliminar_entrega(42, current_user=GESTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.eliminar_entrega.assert_not_called()


# ===================== POST /entregas/ =====================


async def _crear(current_user, db, comision_id=10):
    return await crear_entrega(
        comision_id=comision_id,
        rubrica_id=3,
        alumno_nombre="Perez Juan",
        sobrescribir=False,
        modo_consolidacion="solo_codigo",
        extensiones_personalizadas=None,
        moodle_url=None,
        archivo=MagicMock(),
        current_user=current_user,
        db=db,
    )


@pytest.mark.asyncio
async def test_crear_entrega_en_comision_propia_ok():
    db = _db(_ES_TUTOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.crear_entrega_individual = AsyncMock(return_value="CREADA")
        assert await _crear(TUTOR, db) == "CREADA"


@pytest.mark.asyncio
async def test_crear_entrega_en_comision_ajena_403_sin_procesar_el_archivo():
    """El guard va ANTES de leer el upload: una comision ajena no consume recursos."""
    db = _db(_SIN_PERTENENCIA)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await _crear(TUTOR, db)
    assert exc.value.status_code == 403
    MockSvc.return_value.crear_entrega_individual.assert_not_called()


@pytest.mark.asyncio
async def test_crear_entrega_coordinador_de_la_materia_ok():
    db = _db(_ES_COORDINADOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.crear_entrega_individual = AsyncMock(return_value="CREADA")
        assert await _crear(COORD, db) == "CREADA"


@pytest.mark.asyncio
async def test_crear_entrega_comision_inexistente_404():
    db = _db(None)
    with pytest.raises(HTTPException) as exc:
        await _crear(TUTOR, db, comision_id=404404)
    assert exc.value.status_code == 404


# ===================== POST /entregas/masiva =====================


async def _crear_masiva(current_user, db, comision_id=10):
    return await crear_entregas_masivas(
        comision_id=comision_id,
        rubrica_id=3,
        sobrescribir=False,
        modo_consolidacion="solo_codigo",
        extensiones_personalizadas=None,
        archivo_zip=MagicMock(),
        current_user=current_user,
        db=db,
    )


@pytest.mark.asyncio
async def test_carga_masiva_en_comision_propia_ok():
    db = _db(_ES_TUTOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.crear_entrega_masiva = AsyncMock(return_value="RESUMEN")
        assert await _crear_masiva(TUTOR, db) == "RESUMEN"


@pytest.mark.asyncio
async def test_carga_masiva_en_comision_ajena_403_sin_descomprimir_el_zip():
    """Sin este guard, un ZIP-bomb en comision ajena era gratis (SEC-005 + SEC-002)."""
    db = _db(_SIN_PERTENENCIA)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await _crear_masiva(TUTOR, db)
    assert exc.value.status_code == 403
    MockSvc.return_value.crear_entrega_masiva.assert_not_called()


@pytest.mark.asyncio
async def test_carga_masiva_admin_ok_sin_consultar_permisos():
    db = AsyncMock()
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.crear_entrega_masiva = AsyncMock(return_value="RESUMEN")
        assert await _crear_masiva(ADMIN, db) == "RESUMEN"
    db.execute.assert_not_called()


# ===================== GET /entregas/ (scoping, no 403) =====================


async def _listar(current_user, db, comision_id=None):
    return await listar_entregas(
        comision_id=comision_id,
        rubrica_id=None,
        estado=None,
        include_archivadas=False,
        solo_archivadas=False,
        fecha_desde=None,
        fecha_hasta=None,
        search=None,
        page=1,
        per_page=20,
        current_user=current_user,
        db=db,
    )


@pytest.mark.asyncio
async def test_listar_con_comision_propia_no_aplica_scoping():
    """Con comisión explícita el guard ya acotó: el scoping seria redundante."""
    db = _db(_ES_TUTOR)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        MockSvc.return_value.listar_entregas = AsyncMock(return_value="LISTA")
        assert await _listar(TUTOR, db, comision_id=10) == "LISTA"
        kwargs = MockSvc.return_value.listar_entregas.await_args.kwargs
    assert kwargs["comision_id"] == 10
    assert kwargs["comisiones_visibles"] is None


@pytest.mark.asyncio
async def test_listar_con_comision_ajena_403():
    db = _db(_SIN_PERTENENCIA)
    with patch("app.routers.entregas.EntregaService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await _listar(TUTOR, db, comision_id=10)
    assert exc.value.status_code == 403
    MockSvc.return_value.listar_entregas.assert_not_called()


@pytest.mark.asyncio
async def test_listar_sin_comision_aplica_scoping_del_tutor():
    """El caso del bug: sin filtro devolvia entregas de TODAS las comisiones."""
    db = AsyncMock()
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.comisiones_visibles_para",
        AsyncMock(return_value=[10, 11]),
    ):
        MockSvc.return_value.listar_entregas = AsyncMock(return_value="LISTA")
        await _listar(TUTOR, db)
        kwargs = MockSvc.return_value.listar_entregas.await_args.kwargs
    assert kwargs["comisiones_visibles"] == [10, 11]


@pytest.mark.asyncio
async def test_listar_sin_comision_admin_ve_todo():
    db = AsyncMock()
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.comisiones_visibles_para", AsyncMock(return_value=None)
    ):
        MockSvc.return_value.listar_entregas = AsyncMock(return_value="LISTA")
        await _listar(ADMIN, db)
        kwargs = MockSvc.return_value.listar_entregas.await_args.kwargs
    assert kwargs["comisiones_visibles"] is None


@pytest.mark.asyncio
async def test_listar_sin_comision_gestor_no_ve_nada():
    db = AsyncMock()
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.comisiones_visibles_para", AsyncMock(return_value=[])
    ):
        MockSvc.return_value.listar_entregas = AsyncMock(return_value="LISTA")
        await _listar(GESTOR, db)
        kwargs = MockSvc.return_value.listar_entregas.await_args.kwargs
    assert kwargs["comisiones_visibles"] == []


# ===================== PATCH /entregas/archivar (lote: filtrar + informar) =====

# filtrar_entregas_accesibles se parchea directo: su logica ya tiene sus
# propios tests en test_permissions_pertenencia. Aca importa la orquestacion.


def _resp(procesadas, ids):
    return EntregaAccionMasivaResponse(procesadas=procesadas, ids=ids)


@pytest.mark.asyncio
async def test_archivar_lote_mixto_opera_solo_permitidos_e_informa_omitidos():
    db = AsyncMock()
    body = SimpleNamespace(ids=[1, 2, 3, 4], archivado=True)
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, {3, 4})),
    ):
        MockSvc.return_value.archivar_entregas = AsyncMock(return_value=_resp(2, [1, 2]))
        res = await archivar_entregas(body, current_user=TUTOR, db=db)
        # El service recibe SOLO los permitidos, ordenados.
        assert MockSvc.return_value.archivar_entregas.await_args.kwargs["ids"] == [1, 2]
    assert res.procesadas == 2
    assert res.omitidas == 2
    assert res.ids_omitidos == [3, 4]


@pytest.mark.asyncio
async def test_archivar_lote_todo_denegado_403_sin_tocar_el_service():
    db = AsyncMock()
    body = SimpleNamespace(ids=[3, 4], archivado=True)
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.filtrar_entregas_accesibles",
        AsyncMock(return_value=(set(), {3, 4})),
    ):
        with pytest.raises(HTTPException) as exc:
            await archivar_entregas(body, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.archivar_entregas.assert_not_called()


@pytest.mark.asyncio
async def test_archivar_lote_todo_propio_no_reporta_omitidos():
    db = AsyncMock()
    body = SimpleNamespace(ids=[1, 2], archivado=True)
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, set())),
    ):
        MockSvc.return_value.archivar_entregas = AsyncMock(return_value=_resp(2, [1, 2]))
        res = await archivar_entregas(body, current_user=TUTOR, db=db)
    assert res.omitidas == 0
    assert res.ids_omitidos == []


# ===================== DELETE /entregas/masivo (borrado FISICO) ================


@pytest.mark.asyncio
async def test_borrado_masivo_mixto_borra_solo_permitidos_e_informa():
    """El borrado es fisico e irreversible: el service jamas ve un ID ajeno."""
    db = AsyncMock()
    body = SimpleNamespace(ids=[1, 2, 99])
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, {99})),
    ):
        MockSvc.return_value.eliminar_entregas_masivo = AsyncMock(
            return_value=_resp(2, [1, 2])
        )
        res = await eliminar_entregas_masivo(body, current_user=TUTOR, db=db)
        assert MockSvc.return_value.eliminar_entregas_masivo.await_args.kwargs["ids"] == [1, 2]
    assert res.procesadas == 2
    assert res.omitidas == 1
    assert res.ids_omitidos == [99]


@pytest.mark.asyncio
async def test_borrado_masivo_todo_denegado_403_no_borra_nada():
    db = AsyncMock()
    body = SimpleNamespace(ids=[98, 99])
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.filtrar_entregas_accesibles",
        AsyncMock(return_value=(set(), {98, 99})),
    ):
        with pytest.raises(HTTPException) as exc:
            await eliminar_entregas_masivo(body, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.eliminar_entregas_masivo.assert_not_called()


@pytest.mark.asyncio
async def test_borrado_masivo_admin_borra_todo():
    db = AsyncMock()
    body = SimpleNamespace(ids=[1, 2, 3])
    with patch("app.routers.entregas.EntregaService") as MockSvc, patch(
        "app.routers.entregas.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2, 3}, set())),
    ):
        MockSvc.return_value.eliminar_entregas_masivo = AsyncMock(
            return_value=_resp(3, [1, 2, 3])
        )
        res = await eliminar_entregas_masivo(body, current_user=ADMIN, db=db)
    assert res.procesadas == 3
    assert res.omitidas == 0


def test_schema_omitidos_tiene_defaults_contrato_aditivo():
    """El backend se despliega antes que el frontend: los campos nuevos NO son obligatorios."""
    r = EntregaAccionMasivaResponse(procesadas=1, ids=[1])
    assert r.omitidas == 0
    assert r.ids_omitidos == []
