"""
Tests for EntregaService.

Tests cover:
- Creating individual entregas
- Creating entregas from ZIP (masiva)
- Handling duplicates (overwrite vs error)
- Soft deleting entregas
- Validation of required fields
"""

import io
import zipfile
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comision import Comision
from app.models.materia import Materia
from app.models.rubrica import Rubrica, TipoRubricaEnum
from app.schemas.entrega import EntregaCreate, CargaMasivaRequest
from app.services.entrega_service import EntregaService


@pytest.fixture
async def materia(db_session: AsyncSession) -> Materia:
    """Create a test materia."""
    materia = Materia(
        codigo="PROG1",
        nombre="Programación 1",
        activa=True,
    )
    db_session.add(materia)
    await db_session.commit()
    await db_session.refresh(materia)
    return materia


@pytest.fixture
async def comision(db_session: AsyncSession, materia: Materia) -> Comision:
    """Create a test comision."""
    comision = Comision(
        materia_id=materia.id,
        nombre="Comisión A",
        anio=2026,
        activa=True,
    )
    db_session.add(comision)
    await db_session.commit()
    await db_session.refresh(comision)
    return comision


@pytest.fixture
async def rubrica(db_session: AsyncSession, materia: Materia) -> Rubrica:
    """Create a test rubrica."""
    rubrica = Rubrica(
        materia_id=materia.id,
        tipo=TipoRubricaEnum.TP,
        nombre="TP1 - Listas",
        numero=1,
        anio=2026,
        criterios_json={
            "puntaje_maximo": 100,
            "criterios": [
                {
                    "id": "c1",
                    "nombre": "Funcionalidad",
                    "descripcion": "Código funciona",
                    "puntaje_maximo": 100,
                }
            ],
        },
        activa=True,
    )
    db_session.add(rubrica)
    await db_session.commit()
    await db_session.refresh(rubrica)
    return rubrica


def crear_zip_simple(contenido: str = "print('hello')") -> bytes:
    """Create a simple ZIP file with one Python file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", contenido)
    return buffer.getvalue()


@pytest.mark.asyncio
class TestEntregaService:
    """Tests for EntregaService."""

    async def test_crear_entrega_individual_success(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test creating individual entrega successfully."""
        service = EntregaService(db_session)

        zip_bytes = crear_zip_simple("print('hello world')")

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
            archivo_bytes=zip_bytes,
            archivo_nombre="tp1.zip",
            modo_consolidacion="solo_codigo",
        )

        entrega = await service.crear_entrega_individual(
            data=data,
            subido_por_id=1,
        )

        assert entrega.id is not None
        assert entrega.alumno_nombre == "Pérez, Juan"
        assert entrega.comision_id == comision.id
        assert entrega.rubrica_id == rubrica.id
        assert entrega.archivo_nombre == "tp1.zip"
        assert entrega.activa is True
        assert "print('hello world')" in entrega.contenido_consolidado

    async def test_crear_entrega_individual_comision_not_found(
        self,
        db_session: AsyncSession,
        rubrica: Rubrica,
    ):
        """Test creating entrega with non-existent comision fails."""
        service = EntregaService(db_session)

        zip_bytes = crear_zip_simple()

        data = EntregaCreate(
            comision_id=9999,  # Non-existent
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
            archivo_bytes=zip_bytes,
            archivo_nombre="test.zip",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(data, subido_por_id=1)

        assert exc_info.value.status_code == 404

    async def test_crear_entrega_individual_rubrica_not_found(
        self,
        db_session: AsyncSession,
        comision: Comision,
    ):
        """Test creating entrega with non-existent rubrica fails."""
        service = EntregaService(db_session)

        zip_bytes = crear_zip_simple()

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=9999,  # Non-existent
            alumno_nombre="Test Student",
            archivo_bytes=zip_bytes,
            archivo_nombre="test.zip",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(data, subido_por_id=1)

        assert exc_info.value.status_code == 404

    async def test_crear_entrega_individual_pdf(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test creating an individual PDF entrega."""
        service = EntregaService(db_session)

        pdf_bytes = b"%PDF-1.4 mock pdf content"

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
            archivo_bytes=pdf_bytes,
            archivo_nombre="documento.pdf",
            modo_consolidacion="solo_codigo", # Should be ignored
        )

        entrega = await service.crear_entrega_individual(
            data=data,
            subido_por_id=1,
        )

        assert entrega.id is not None
        assert entrega.archivo_tipo == "pdf"
        assert entrega.contenido_consolidado is None
        assert entrega.pdf_contenido_b64 is not None
        assert "[Entrega en formato PDF]" in entrega.contenido_preview

    async def test_crear_entrega_duplicada_sin_sobrescribir(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test creating duplicate entrega without overwrite fails."""
        service = EntregaService(db_session)

        zip_bytes = crear_zip_simple()

        # Create first entrega
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
            archivo_bytes=zip_bytes,
            archivo_nombre="tp1_v1.zip",
        )
        await service.crear_entrega_individual(data, subido_por_id=1)

        # Try to create duplicate (same alumno + rubrica)
        data2 = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
            archivo_bytes=zip_bytes,
            archivo_nombre="tp1_v2.zip",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(data2, subido_por_id=1)

        assert exc_info.value.status_code == 409
        assert "ya existe" in exc_info.value.detail.lower()

    async def test_crear_entrega_duplicada_con_sobrescribir(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test creating duplicate entrega with overwrite succeeds."""
        service = EntregaService(db_session)

        zip_bytes_v1 = crear_zip_simple("print('version 1')")
        zip_bytes_v2 = crear_zip_simple("print('version 2')")

        # Create first entrega
        data_v1 = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
            archivo_bytes=zip_bytes_v1,
            archivo_nombre="tp1_v1.zip",
        )
        entrega_v1 = await service.crear_entrega_individual(data_v1, subido_por_id=1)

        # Create duplicate with overwrite
        data_v2 = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
            archivo_bytes=zip_bytes_v2,
            archivo_nombre="tp1_v2.zip",
            sobrescribir=True,
        )
        entrega_v2 = await service.crear_entrega_individual(data_v2, subido_por_id=1)

        # Should have same ID (overwritten)
        assert entrega_v2.id == entrega_v1.id
        assert "version 2" in entrega_v2.contenido_consolidado
        assert "version 1" not in entrega_v2.contenido_consolidado

    async def test_crear_entrega_masiva_pdf(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test creating masiva containing both a PDF and a normal code submission."""
        service = EntregaService(db_session)

        # Build a ZIP file containing 2 students: one with python code, one with PDF
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("García, Ana/main.py", "print('codigo')")
            zf.writestr("Pérez, Juan/documento.pdf", b"%PDF-1.4 mock pdf")

        data = CargaMasivaRequest(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            archivo_bytes=buffer.getvalue(),
            modo_consolidacion="solo_codigo",
        )

        resultado = await service.crear_entrega_masiva(
            data=data,
            subido_por_id=1,
        )

        assert resultado.total_procesadas == 2
        assert resultado.total_exitosas == 2
        
        # Verify db entries
        resultado_db = await service.listar_entregas(comision_id=comision.id)
        assert resultado_db.total == 2
        
        # Check specific types
        entregas_pdf = [e for e in resultado_db.items if e.alumno_nombre == "Pérez, Juan"]
        entregas_codigo = [e for e in resultado_db.items if e.alumno_nombre == "García, Ana"]

        assert len(entregas_pdf) == 1
        assert len(entregas_codigo) == 1
        
        assert entregas_pdf[0].archivo_tipo == 'pdf'
        assert entregas_codigo[0].archivo_tipo == 'zip'

    async def test_listar_entregas_por_comision(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test listing entregas by comision."""
        service = EntregaService(db_session)

        # Create multiple entregas
        for i in range(3):
            zip_bytes = crear_zip_simple(f"print('student {i}')")
            data = EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=f"Alumno {i}",
                archivo_bytes=zip_bytes,
                archivo_nombre=f"tp{i}.zip",
            )
            await service.crear_entrega_individual(data, subido_por_id=1)

        # List entregas
        result = await service.listar_entregas(comision_id=comision.id)

        assert result.total == 3
        assert len(result.items) == 3

    async def test_listar_entregas_por_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test listing entregas by rubrica."""
        service = EntregaService(db_session)

        # Create entregas for this rubrica
        for i in range(2):
            zip_bytes = crear_zip_simple()
            data = EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=f"Alumno {i}",
                archivo_bytes=zip_bytes,
                archivo_nombre=f"tp{i}.zip",
            )
            await service.crear_entrega_individual(data, subido_por_id=1)

        # List by rubrica
        result = await service.listar_entregas(rubrica_id=rubrica.id)

        assert result.total == 2

    async def test_eliminar_entrega_soft_delete(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test soft deleting entrega."""
        service = EntregaService(db_session)

        # Create entrega
        zip_bytes = crear_zip_simple()
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
            archivo_bytes=zip_bytes,
            archivo_nombre="test.zip",
        )
        entrega = await service.crear_entrega_individual(data, subido_por_id=1)

        # Delete entrega
        await service.eliminar_entrega(entrega.id)

        # Verify soft deleted
        result = await service.listar_entregas(comision_id=comision.id)
        assert result.total == 0  # Should not appear in active list

    async def test_obtener_entrega_con_correccion(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
    ):
        """Test getting entrega with correction included."""
        service = EntregaService(db_session)

        # Create entrega
        zip_bytes = crear_zip_simple()
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
            archivo_bytes=zip_bytes,
            archivo_nombre="test.zip",
        )
        entrega = await service.crear_entrega_individual(data, subido_por_id=1)

        # Get entrega
        detail = await service.obtener_entrega(entrega.id)

        assert detail.id == entrega.id
        assert detail.alumno_nombre == "Test Student"
        assert detail.correccion is None  # No correction yet
