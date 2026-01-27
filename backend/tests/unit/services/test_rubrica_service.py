"""
Tests for RubricaService.

Tests cover:
- Creating rubricas with validation
- Duplicating rubricas to new years
- Updating rubricas
- Listing and filtering rubricas
- Soft deleting and restoring rubricas
- Criterios validation (sum must be 100)
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.materia import Materia
from app.models.rubrica import Rubrica, TipoRubricaEnum, FuenteRubricaEnum
from app.schemas.rubrica import (
    CriteriosStructure,
    CriterioSchema,
    RubricaCreate,
    RubricaUpdate,
    RubricaDuplicar,
)
from app.services.rubrica_service import RubricaService


@pytest.fixture
async def materia(db_session: AsyncSession) -> Materia:
    """Create a test materia."""
    materia = Materia(
        codigo="PROG1",
        nombre="Programación 1",
        descripcion="Materia de programación inicial",
        activa=True,
    )
    db_session.add(materia)
    await db_session.commit()
    await db_session.refresh(materia)
    return materia


@pytest.fixture
def criterios_validos() -> CriteriosStructure:
    """Create valid criterios structure (sum = 100)."""
    return CriteriosStructure(
        puntaje_maximo=100,
        criterios=[
            CriterioSchema(
                id="c1",
                nombre="Funcionalidad",
                descripcion="El código funciona correctamente",
                puntaje_maximo=40,
            ),
            CriterioSchema(
                id="c2",
                nombre="Buenas prácticas",
                descripcion="Código limpio y bien estructurado",
                puntaje_maximo=30,
            ),
            CriterioSchema(
                id="c3",
                nombre="Documentación",
                descripcion="Comentarios y documentación adecuada",
                puntaje_maximo=30,
            ),
        ],
    )


@pytest.mark.asyncio
class TestRubricaService:
    """Tests for RubricaService."""

    async def test_crear_rubrica_success(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test creating a rubrica successfully."""
        service = RubricaService(db_session)

        data = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            nombre="TP1 - Listas",
            numero=1,
            anio=2026,
            criterios_json=criterios_validos,
            fuente=FuenteRubricaEnum.MANUAL,
        )

        rubrica = await service.crear_rubrica(data)

        assert rubrica.id is not None
        assert rubrica.nombre == "TP1 - Listas"
        assert rubrica.tipo == TipoRubricaEnum.TP
        assert rubrica.numero == 1
        assert rubrica.anio == 2026
        assert rubrica.activa is True
        assert rubrica.criterios_json["puntaje_maximo"] == 100

    async def test_crear_rubrica_materia_not_found(
        self,
        db_session: AsyncSession,
        criterios_validos: CriteriosStructure,
    ):
        """Test creating rubrica with non-existent materia fails."""
        service = RubricaService(db_session)

        data = RubricaCreate(
            materia_id=9999,  # Non-existent
            tipo=TipoRubricaEnum.TP,
            nombre="TP1",
            numero=1,
            anio=2026,
            criterios_json=criterios_validos,
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_rubrica(data)

        assert exc_info.value.status_code == 404
        assert "no encontrada" in exc_info.value.detail.lower()

    async def test_crear_rubrica_duplicada(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test creating duplicate rubrica fails."""
        service = RubricaService(db_session)

        # Create first rubrica
        data = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.PARCIAL_1,
            nombre="Parcial 1",
            numero=1,
            anio=2026,
            criterios_json=criterios_validos,
        )
        await service.crear_rubrica(data)

        # Try to create duplicate (same tipo, numero, anio, materia)
        with pytest.raises(HTTPException) as exc_info:
            await service.crear_rubrica(data)

        assert exc_info.value.status_code == 409
        assert "ya existe" in exc_info.value.detail.lower()

    async def test_crear_rubrica_criterios_invalidos_suma(
        self,
        db_session: AsyncSession,
        materia: Materia,
    ):
        """Test creating rubrica with invalid criterios sum fails."""
        service = RubricaService(db_session)

        # Sum = 90, not 100
        criterios_invalidos = CriteriosStructure(
            puntaje_maximo=100,
            criterios=[
                CriterioSchema(
                    id="c1",
                    nombre="Criterio 1",
                    descripcion="Descripción",
                    puntaje_maximo=50,
                ),
                CriterioSchema(
                    id="c2",
                    nombre="Criterio 2",
                    descripcion="Descripción",
                    puntaje_maximo=40,  # 50 + 40 = 90
                ),
            ],
        )

        data = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            nombre="TP1",
            numero=1,
            anio=2026,
            criterios_json=criterios_invalidos,
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_rubrica(data)

        assert exc_info.value.status_code == 400
        assert "suma" in exc_info.value.detail.lower()

    async def test_duplicar_rubrica_success(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test duplicating rubrica to new year."""
        service = RubricaService(db_session)

        # Create original rubrica
        original_data = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            nombre="TP1 - Listas (2025)",
            numero=1,
            anio=2025,
            criterios_json=criterios_validos,
        )
        original = await service.crear_rubrica(original_data)

        # Duplicate to 2026
        duplicate_data = RubricaDuplicar(
            nuevo_anio=2026,
            nuevo_nombre="TP1 - Listas (2026)",
        )
        duplicated = await service.duplicar_rubrica(original.id, duplicate_data)

        assert duplicated.id != original.id
        assert duplicated.anio == 2026
        assert duplicated.nombre == "TP1 - Listas (2026)"
        assert duplicated.tipo == original.tipo
        assert duplicated.numero == original.numero
        assert duplicated.materia_id == original.materia_id
        assert duplicated.criterios_json["puntaje_maximo"] == 100

    async def test_duplicar_rubrica_already_exists(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test duplicating rubrica fails if already exists for new year."""
        service = RubricaService(db_session)

        # Create rubrica for 2025
        data_2025 = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.PARCIAL_1,
            nombre="Parcial 1 (2025)",
            numero=1,
            anio=2025,
            criterios_json=criterios_validos,
        )
        original = await service.crear_rubrica(data_2025)

        # Create rubrica for 2026 (same tipo, numero)
        data_2026 = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.PARCIAL_1,
            nombre="Parcial 1 (2026)",
            numero=1,
            anio=2026,
            criterios_json=criterios_validos,
        )
        await service.crear_rubrica(data_2026)

        # Try to duplicate from 2025 to 2026 (should fail)
        duplicate_data = RubricaDuplicar(nuevo_anio=2026)

        with pytest.raises(HTTPException) as exc_info:
            await service.duplicar_rubrica(original.id, duplicate_data)

        assert exc_info.value.status_code == 409
        assert "ya existe" in exc_info.value.detail.lower()

    async def test_actualizar_rubrica_success(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test updating rubrica successfully."""
        service = RubricaService(db_session)

        # Create rubrica
        data = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            nombre="TP1 Original",
            numero=1,
            anio=2026,
            criterios_json=criterios_validos,
        )
        rubrica = await service.crear_rubrica(data)

        # Update rubrica
        update_data = RubricaUpdate(nombre="TP1 Actualizado")
        updated = await service.actualizar_rubrica(rubrica.id, update_data)

        assert updated.id == rubrica.id
        assert updated.nombre == "TP1 Actualizado"

    async def test_listar_rubricas_filtros(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test listing rubricas with filters."""
        service = RubricaService(db_session)

        # Create multiple rubricas
        for i in range(3):
            data = RubricaCreate(
                materia_id=materia.id,
                tipo=TipoRubricaEnum.TP,
                nombre=f"TP{i+1}",
                numero=i + 1,
                anio=2026,
                criterios_json=criterios_validos,
            )
            await service.crear_rubrica(data)

        # List all
        result = await service.listar_rubricas(materia_id=materia.id)
        assert result.total == 3
        assert len(result.items) == 3

        # Filter by tipo
        result_tp = await service.listar_rubricas(
            materia_id=materia.id, tipo=TipoRubricaEnum.TP.value
        )
        assert result_tp.total == 3

    async def test_eliminar_rubrica_soft_delete(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test soft deleting rubrica."""
        service = RubricaService(db_session)

        # Create rubrica
        data = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            nombre="TP1",
            numero=1,
            anio=2026,
            criterios_json=criterios_validos,
        )
        rubrica = await service.crear_rubrica(data)

        # Delete rubrica
        await service.eliminar_rubrica(rubrica.id)

        # Verify it's soft deleted
        result = await service.listar_rubricas(
            materia_id=materia.id, include_inactive=False
        )
        assert result.total == 0

        # Verify it exists when including inactive
        result_with_inactive = await service.listar_rubricas(
            materia_id=materia.id, include_inactive=True
        )
        assert result_with_inactive.total == 1
        assert result_with_inactive.items[0].activa is False

    async def test_restaurar_rubrica(
        self,
        db_session: AsyncSession,
        materia: Materia,
        criterios_validos: CriteriosStructure,
    ):
        """Test restoring a soft-deleted rubrica."""
        service = RubricaService(db_session)

        # Create and delete rubrica
        data = RubricaCreate(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            nombre="TP1",
            numero=1,
            anio=2026,
            criterios_json=criterios_validos,
        )
        rubrica = await service.crear_rubrica(data)
        await service.eliminar_rubrica(rubrica.id)

        # Restore rubrica
        restored = await service.restaurar_rubrica(rubrica.id)

        assert restored.id == rubrica.id
        assert restored.activa is True

        # Verify it appears in active list
        result = await service.listar_rubricas(materia_id=materia.id)
        assert result.total == 1
