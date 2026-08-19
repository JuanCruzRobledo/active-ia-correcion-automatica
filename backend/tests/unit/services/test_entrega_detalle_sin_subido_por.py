"""
fix-detalle-entrega-500: `GET /entregas/{id}` devolvía 500 para toda entrega
importada desde Moodle.

`Entrega.subido_por_id` es nullable (`app/models/entrega.py:108-111`) — las
entregas que crea la importación no las subió ninguna persona. Pero:

- `EntregaService.obtener_entrega` (`entrega_service.py:716-720`) accedía
  directo a `entrega.subido_por.id`, sin comprobar que la relación existiera.
  Con la relación en `None` eso levanta `AttributeError`, que sale como 500.
- `EntregaResponse.subido_por_id` estaba declarado `int` y
  `EntregaDetailResponse.subido_por` `UsuarioInfo`, ambos obligatorios. Aunque
  el service no explotara, Pydantic rechazaba el `None` después.

Eran DOS defectos encadenados sobre el mismo dato, y por eso el arreglo toca
schema y service: corregir uno solo deja el 500 igual, movido de línea.

El camino de importación es por donde entra la mayoría de las entregas del
sistema, así que esto no era un borde: el detalle de una entrega importada era
inaccesible para todos los usuarios.

Precedente en el mismo schema: el comentario de `UsuarioInfo.email`
(`app/schemas/entrega.py:94-97`) documenta un 500 idéntico en clase — un campo
declarado obligatorio sobre una columna nullable. Es la tercera vez que este
endpoint cae por lo mismo (ver también la nota de `num_versiones_anteriores` en
`test_entrega_service.py`), y de ahí el test de caracterización de abajo.
"""

import io
import zipfile
from typing import Any

import pytest
import pytest_asyncio
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comision import Comision
from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum, TipoRubricaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.usuario import Usuario
from app.schemas.entrega import EntregaCreate
from app.services.entrega_service import EntregaService

UNIV_ID = 1

pytestmark = pytest.mark.asyncio


def _zip_simple(contenido: str = "print('hola')") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", contenido)
    return buffer.getvalue()


def _upload(contenido: bytes, filename: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(contenido), filename=filename, size=len(contenido))


@pytest_asyncio.fixture
async def materia(db_session: AsyncSession) -> Materia:
    materia = Materia(
        universidad_id=UNIV_ID, codigo="PROG1", nombre="Programación 1", activa=True
    )
    db_session.add(materia)
    await db_session.commit()
    await db_session.refresh(materia)
    return materia


@pytest_asyncio.fixture
async def comision(db_session: AsyncSession, materia: Materia) -> Comision:
    comision = Comision(
        universidad_id=UNIV_ID,
        materia_id=materia.id,
        nombre="Comisión A",
        anio=2026,
        activa=True,
    )
    db_session.add(comision)
    await db_session.commit()
    await db_session.refresh(comision)
    return comision


@pytest_asyncio.fixture
async def rubrica(db_session: AsyncSession, materia: Materia) -> Rubrica:
    criterios: list[dict[str, Any]] = [
        {
            "id": "C1",
            "nombre": "Funcionalidad",
            "descripcion": "El código funciona",
            "peso": 100,
            "subcriterios": [],
        }
    ]
    rubrica = Rubrica(
        universidad_id=UNIV_ID,
        materia_id=materia.id,
        tipo=TipoRubricaEnum.TP,
        titulo="TP1 - Listas",
        descripcion="Evalúa el manejo de listas.",
        puntaje_maximo=100,
        numero=1,
        anio=2026,
        criterios_json=criterios,
        activa=True,
    )
    db_session.add(rubrica)
    await db_session.commit()
    await db_session.refresh(rubrica)
    return rubrica


@pytest_asyncio.fixture
async def subidor(db_session: AsyncSession) -> Usuario:
    usuario = Usuario(
        username="subidor_test",
        nombre="Subidor Test",
        email="subidor@test.local",
        password_hash="no-se-usa-en-estos-tests",
        activo=True,
    )
    db_session.add(usuario)
    await db_session.commit()
    await db_session.refresh(usuario)
    return usuario


@pytest_asyncio.fixture
async def entrega_importada(
    db_session: AsyncSession, comision: Comision, rubrica: Rubrica
) -> Entrega:
    """Entrega tal como la deja la importación desde Moodle: sin `subido_por_id`.

    Se construye a mano y no vía `crear_entrega_individual` porque ese camino
    exige un `subido_por_id`; el que no lo tiene es justamente el de importación.
    """
    entrega = Entrega(
        universidad_id=UNIV_ID,
        comision_id=comision.id,
        rubrica_id=rubrica.id,
        alumno_nombre="Alumna Importada",
        archivo_nombre="entrega_moodle.zip",
        archivo_tamanio=128,
        archivo_tipo="zip",
        contenido_preview="print('hola')",
        contenido_consolidado="print('hola')",
        estado=EstadoEntregaEnum.SUBIDA,
        subido_por_id=None,
        moodle_user_id=90210,
    )
    db_session.add(entrega)
    await db_session.commit()
    await db_session.refresh(entrega)
    return entrega


class TestDetalleEntregaSinSubidoPor:
    """El detalle de una entrega sin usuario que la haya subido."""

    async def test_detalle_de_entrega_importada_no_explota(
        self, db_session: AsyncSession, entrega_importada: Entrega
    ):
        """RED: hoy levanta AttributeError sobre `entrega.subido_por.id` → 500."""
        service = EntregaService(db_session)

        detalle = await service.obtener_entrega(entrega_importada.id)

        assert detalle.id == entrega_importada.id
        assert detalle.subido_por is None
        assert detalle.subido_por_id is None

    async def test_detalle_de_entrega_importada_trae_el_resto_integro(
        self,
        db_session: AsyncSession,
        entrega_importada: Entrega,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """El campo nulo no debe amputar el resto del detalle."""
        service = EntregaService(db_session)

        detalle = await service.obtener_entrega(entrega_importada.id)

        assert detalle.alumno_nombre == "Alumna Importada"
        assert detalle.archivo_nombre == "entrega_moodle.zip"
        assert detalle.estado == EstadoEntregaEnum.SUBIDA
        assert detalle.comision.id == comision.id
        assert detalle.comision.materia_nombre == "Programación 1"
        assert detalle.rubrica.id == rubrica.id
        assert detalle.rubrica.nombre == "TP1 - Listas"
        assert detalle.tiene_correccion is False
        assert detalle.num_versiones_anteriores == 0

    async def test_detalle_de_entrega_con_subidor_no_cambia(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Caracterización: el camino que ya andaba tiene que seguir igual."""
        service = EntregaService(db_session)
        entrega = await service.crear_entrega_individual(
            data=EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre="Alumno Con Subidor",
            ),
            archivo=_upload(_zip_simple(), "entrega.zip"),
            subido_por_id=subidor.id,
        )

        detalle = await service.obtener_entrega(entrega.id)

        assert detalle.subido_por is not None
        assert detalle.subido_por.id == subidor.id
        assert detalle.subido_por.nombre == "Subidor Test"
        assert detalle.subido_por.email == "subidor@test.local"
        assert detalle.subido_por_id == subidor.id

    async def test_entrega_inexistente_sigue_dando_404(self, db_session: AsyncSession):
        """Caracterización: el 404 no se convierte en 200 con campos vacíos."""
        from fastapi import HTTPException

        service = EntregaService(db_session)

        with pytest.raises(HTTPException) as exc:
            await service.obtener_entrega(999_999)

        assert exc.value.status_code == 404
