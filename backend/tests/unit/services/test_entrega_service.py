"""
Tests for EntregaService.

Tests cover:
- Creating individual entregas
- Creating entregas from ZIP (masiva)
- Handling duplicates (overwrite vs error)
- Soft deleting entregas
- Validation of required fields

Nota de mantenimiento: este archivo venía del commit inicial del repo y nunca
llegó a ejecutarse — importaba `CargaMasivaRequest`, un símbolo que jamás
existió, así que pytest cortaba en la colección. Se reescribió contra la API
real conservando la intención de los 11 tests originales. La API había
derivado en: `EntregaCreate` se redujo a `alumno_nombre`/`comision_id`/
`rubrica_id` y el archivo pasó a viajar como `UploadFile` aparte;
`crear_entrega_masiva` recibe argumentos planos en vez de un schema;
`eliminar_entrega` pide `actor_id`; y `universidad_id` entró con
multi-tenant-scoping-queries (Fase 4), donde el service lo propaga desde el
padre ya cargado.

Es el único lugar de la suite que ejercita `crear_entrega_individual` y
`crear_entrega_masiva` de verdad: el resto de los tests los mockea.
"""

import io
import zipfile
from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comision import Comision
from app.models.materia import Materia
from app.models.rubrica import Rubrica, TipoRubricaEnum
from app.models.enums import RolEnum
from app.models.usuario import Usuario
from app.schemas.entrega import EntregaCreate
from app.services.entrega_service import EntregaService

# multi-tenant-scoping-queries (Fase 4): universidad_id es NOT NULL en toda la
# rama Materia -> Comision -> Rubrica -> Entrega.
UNIV_ID = 1


def crear_zip_simple(contenido: str = "print('hello')") -> bytes:
    """Create a simple ZIP file with one Python file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", contenido)
    return buffer.getvalue()


def _upload(contenido: bytes, filename: str) -> UploadFile:
    """UploadFile en memoria: el service usa .size, .filename y await .read()."""
    return UploadFile(
        file=io.BytesIO(contenido),
        filename=filename,
        size=len(contenido),
    )


@pytest_asyncio.fixture
async def materia(db_session: AsyncSession) -> Materia:
    """Create a test materia."""
    materia = Materia(
        universidad_id=UNIV_ID,
        codigo="PROG1",
        nombre="Programación 1",
        activa=True,
    )
    db_session.add(materia)
    await db_session.commit()
    await db_session.refresh(materia)
    return materia


@pytest_asyncio.fixture
async def comision(db_session: AsyncSession, materia: Materia) -> Comision:
    """Create a test comision."""
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
    """Create a test rubrica."""
    criterios: list[dict[str, Any]] = [
        {
            "id": "C1",
            "nombre": "Funcionalidad",
            "descripcion": "Código funciona",
            "peso": 100,
            "subcriterios": [
                {
                    "id": "C1.1",
                    "descripcion": "El código corre sin errores",
                    "evidencias": ["Se ejecuta sin excepciones"],
                }
            ],
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
    """Usuario que sube las entregas y actúa de actor en el borrado.

    `password_hash` se setea literal a propósito: `hash_password()` depende de
    passlib+bcrypt y estos tests no ejercitan autenticación.
    """
    usuario = Usuario(
        username="subidor_test",
        nombre="Subidor Test",
        password_hash="no-usado-en-estos-tests",
    )
    db_session.add(usuario)
    await db_session.commit()
    await db_session.refresh(usuario)
    return usuario


@pytest.mark.asyncio
class TestEntregaService:
    """Tests for EntregaService."""

    async def test_crear_entrega_individual_success(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating individual entrega successfully."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )

        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple("print('hello world')"), "tp1.zip"),
            subido_por_id=subidor.id,
        )

        assert entrega.id is not None
        assert entrega.alumno_nombre == "Pérez, Juan"
        assert entrega.comision_id == comision.id
        assert entrega.rubrica_id == rubrica.id
        assert entrega.archivo_nombre == "tp1.zip"
        assert entrega.archivado is False

    async def test_crear_entrega_individual_comision_not_found(
        self,
        db_session: AsyncSession,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating entrega with non-existent comision fails."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=9999,  # Non-existent
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), "test.zip"),
                subido_por_id=subidor.id,
            )

        assert exc_info.value.status_code == 404

    async def test_crear_entrega_individual_rubrica_not_found(
        self,
        db_session: AsyncSession,
        comision: Comision,
        subidor: Usuario,
    ):
        """Test creating entrega with non-existent rubrica fails."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=9999,  # Non-existent
            alumno_nombre="Test Student",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), "test.zip"),
                subido_por_id=subidor.id,
            )

        assert exc_info.value.status_code == 404

    async def test_crear_entrega_individual_pdf(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating an individual PDF entrega."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )

        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(b"%PDF-1.4 mock pdf content", "documento.pdf"),
            subido_por_id=subidor.id,
            modo_consolidacion="solo_codigo",  # se ignora para PDF
        )

        # `contenido_consolidado` no viaja en EntregaResponse (PERF-006: es una
        # columna deferred); el marcador de PDF se ve en el preview.
        assert entrega.id is not None
        assert entrega.archivo_tipo == "pdf"
        assert "[Entrega en formato PDF]" in entrega.contenido_preview

    async def test_crear_entrega_duplicada_sin_sobrescribir(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating duplicate entrega without overwrite fails."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )
        await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple(), "tp1_v1.zip"),
            subido_por_id=subidor.id,
        )

        # Mismo alumno + misma rúbrica, sin sobrescribir -> conflicto
        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), "tp1_v2.zip"),
                subido_por_id=subidor.id,
            )

        assert exc_info.value.status_code == 409
        assert "ya existe" in exc_info.value.detail.lower()

    async def test_crear_entrega_duplicada_con_sobrescribir(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating duplicate entrega with overwrite succeeds."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )

        entrega_v1 = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple("print('version 1')"), "tp1_v1.zip"),
            subido_por_id=subidor.id,
        )

        entrega_v2 = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple("print('version 2')"), "tp1_v2.zip"),
            subido_por_id=subidor.id,
            sobrescribir=True,
        )

        # Se pisa la misma fila, no se crea una nueva
        assert entrega_v2.id == entrega_v1.id
        assert entrega_v2.archivo_nombre == "tp1_v2.zip"

    async def test_crear_entrega_masiva_pdf(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Masiva con dos alumnos: uno entrega código y el otro un PDF."""
        service = EntregaService(db_session)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("García, Ana/main.py", "print('codigo')")
            zf.writestr("Pérez, Juan/documento.pdf", b"%PDF-1.4 mock pdf")

        resultado = await service.crear_entrega_masiva(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            archivo_zip=_upload(buffer.getvalue(), "entregas.zip"),
            subido_por_id=subidor.id,
        )

        assert resultado.total_procesadas == 2
        assert resultado.total_exitosas == 2

        resultado_db = await service.listar_entregas(comision_id=comision.id)
        assert resultado_db.total == 2

        entregas_pdf = [
            e for e in resultado_db.items if e.alumno_nombre == "Pérez, Juan"
        ]
        entregas_codigo = [
            e for e in resultado_db.items if e.alumno_nombre == "García, Ana"
        ]

        assert len(entregas_pdf) == 1
        assert len(entregas_codigo) == 1
        assert entregas_pdf[0].archivo_tipo == "pdf"

    async def test_listar_entregas_por_comision(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test listing entregas by comision."""
        service = EntregaService(db_session)

        for i in range(3):
            data = EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=f"Alumno {i}",
            )
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(f"print('student {i}')"), f"tp{i}.zip"),
                subido_por_id=subidor.id,
            )

        result = await service.listar_entregas(comision_id=comision.id)

        assert result.total == 3
        assert len(result.items) == 3

    async def test_listar_entregas_por_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test listing entregas by rubrica."""
        service = EntregaService(db_session)

        for i in range(2):
            data = EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=f"Alumno {i}",
            )
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), f"tp{i}.zip"),
                subido_por_id=subidor.id,
            )

        result = await service.listar_entregas(rubrica_id=rubrica.id)

        assert result.total == 2

    async def test_eliminar_entrega_soft_delete(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test soft deleting entrega."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
        )
        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple(), "test.zip"),
            subido_por_id=subidor.id,
        )

        await service.eliminar_entrega(entrega.id, actor_id=subidor.id)

        # Baja lógica: desaparece del listado activo
        result = await service.listar_entregas(comision_id=comision.id)
        assert result.total == 0

    async def test_obtener_entrega_con_correccion(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test getting entrega with correction included."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
        )
        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple(), "test.zip"),
            subido_por_id=subidor.id,
        )

        detail = await service.obtener_entrega(entrega.id)

        assert detail.id == entrega.id
        assert detail.alumno_nombre == "Test Student"
        assert detail.tiene_correccion is False  # todavía no se corrigió
        # Regresión: `obtener_entrega` arma un HistorialResponse para contar
        # versiones. Construirlo con los nombres de campo equivocados hacía
        # explotar el endpoint entero con 500.
        assert detail.num_versiones_anteriores == 0
