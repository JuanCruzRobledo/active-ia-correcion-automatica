"""
Tests for RubricaService.

Tests cover:
- Creating rubricas with validation
- Duplicating rubricas to new years
- Updating rubricas
- Listing and filtering rubricas
- Soft deleting and restoring rubricas
- Criterios validation (sum must be 100)

Nota de mantenimiento: este archivo venía del commit inicial del repo y nunca
llegó a ejecutarse — importaba `CriteriosSchema`, un símbolo que jamás existió,
así que pytest cortaba en la colección. Se reescribió contra la API real
conservando la intención de los 10 tests originales. La API había derivado en:
`RubricaCreate` se aplanó (`nombre` -> `titulo`, y `criterios_json` pasó a ser
`list[dict]` en vez de un `CriteriosStructure` anidado), los métodos del
service reciben `current_user`, y `universidad_id` entró con
multi-tenant-scoping-queries (Fase 4).
"""

from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.materia import Materia
from app.models.rubrica import TipoRubricaEnum, FuenteRubricaEnum
from app.models.enums import RolEnum
from app.models.usuario import Usuario
from app.schemas.rubrica import (
    CriteriosStructure,
    RubricaCreate,
    RubricaDuplicar,
    RubricaUpdate,
)
from app.services.rubrica_service import RubricaService

# multi-tenant-scoping-queries (Fase 4): universidad_id es NOT NULL en Materia
# y las firmas del service reciben el scope de la universidad activa.
UNIV_ID = 1


def _criterio(id_: str, nombre: str, peso: int) -> dict[str, Any]:
    """Criterio como dict, con el subcriterio mínimo que exige el schema."""
    descripcion = f"Descripción de {nombre}"
    return {
        "id": id_,
        "nombre": nombre,
        "descripcion": descripcion,
        "peso": peso,
        "subcriterios": [
            {
                "id": f"{id_}.1",
                "descripcion": descripcion,
                "evidencias": [f"Se verifica {nombre.lower()}"],
            }
        ],
    }


@pytest.fixture
def criterios_validos() -> list[dict[str, Any]]:
    """Criterios cuyos pesos suman exactamente 100."""
    return [
        _criterio("C1", "Funcionalidad", 40),
        _criterio("C2", "Buenas prácticas", 30),
        _criterio("C3", "Documentación", 30),
    ]


def _rubrica_create(
    materia_id: int,
    criterios: list[dict[str, Any]],
    *,
    tipo: TipoRubricaEnum = TipoRubricaEnum.TP,
    titulo: str = "TP1 - Listas",
    numero: int = 1,
    anio: int = 2026,
    **overrides: Any,
) -> RubricaCreate:
    kwargs: dict[str, Any] = {
        "materia_id": materia_id,
        "tipo": tipo,
        "numero": numero,
        "anio": anio,
        "titulo": titulo,
        "descripcion": "Evalúa el manejo de listas y buenas prácticas.",
        "criterios_json": criterios,
    }
    kwargs.update(overrides)
    return RubricaCreate(**kwargs)


@pytest_asyncio.fixture
async def materia(db_session: AsyncSession) -> Materia:
    """Create a test materia."""
    materia = Materia(
        universidad_id=UNIV_ID,
        codigo="PROG1",
        nombre="Programación 1",
        descripcion="Materia de programación inicial",
        activa=True,
    )
    db_session.add(materia)
    await db_session.commit()
    await db_session.refresh(materia)
    return materia


@pytest_asyncio.fixture
async def admin(db_session: AsyncSession) -> Usuario:
    """Admin user: `_validar_acceso_materia` le da acceso a toda materia.

    `password_hash` se setea literal a propósito: `hash_password()` depende de
    passlib+bcrypt y estos tests no ejercitan autenticación.
    """
    usuario = Usuario(
        username="admin_test",
        nombre="Admin Test",
        password_hash="no-usado-en-estos-tests",
    )
    db_session.add(usuario)
    await db_session.commit()
    await db_session.refresh(usuario)
    return usuario


@pytest.mark.asyncio
class TestRubricaService:
    """Tests for RubricaService."""

    async def test_crear_rubrica_success(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test creating a rubrica successfully."""
        service = RubricaService(db_session)

        data = _rubrica_create(
            materia.id,
            criterios_validos,
            fuente=FuenteRubricaEnum.MANUAL,
        )

        rubrica = await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        assert rubrica.id is not None
        assert rubrica.titulo == "TP1 - Listas"
        assert rubrica.tipo == TipoRubricaEnum.TP
        assert rubrica.numero == 1
        assert rubrica.anio == 2026
        assert rubrica.activa is True
        assert rubrica.puntaje_maximo == 100
        assert len(rubrica.criterios_json) == 3

    async def test_crear_rubrica_materia_not_found(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test creating rubrica with non-existent materia fails."""
        service = RubricaService(db_session)

        data = _rubrica_create(9999, criterios_validos, titulo="TP1")

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        assert exc_info.value.status_code == 404
        assert "no encontrada" in exc_info.value.detail.lower()

    async def test_crear_rubrica_duplicada(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test creating duplicate rubrica fails."""
        service = RubricaService(db_session)

        data = _rubrica_create(
            materia.id,
            criterios_validos,
            tipo=TipoRubricaEnum.PARCIAL_1,
            titulo="Parcial 1",
        )
        await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        # Mismo tipo, numero, anio y materia -> conflicto
        with pytest.raises(HTTPException) as exc_info:
            await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        assert exc_info.value.status_code == 409
        assert "ya existe" in exc_info.value.detail.lower()

    async def test_crear_rubrica_criterios_invalidos_suma(self):
        """Una rúbrica cuyos pesos no suman 100 es rechazada.

        El chequeo dejó de vivir en el service: hoy es el `model_validator`
        `CriteriosStructure.validar_suma_pesos`, así que corta al construir el
        schema y nunca llega a `crear_rubrica`. La intención del test original
        se mantiene: pesos que no suman 100 no se pueden persistir.
        """
        with pytest.raises(ValidationError) as exc_info:
            CriteriosStructure(
                titulo="TP1",
                descripcion="Rúbrica con pesos que no suman 100.",
                puntaje_maximo=100,
                criterios=[
                    _criterio("C1", "Criterio 1", 50),
                    _criterio("C2", "Criterio 2", 40),  # 50 + 40 = 90
                ],
            )

        assert "suma" in str(exc_info.value).lower()

    async def test_duplicar_rubrica_success(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test duplicating rubrica to new year."""
        service = RubricaService(db_session)

        original_data = _rubrica_create(
            materia.id,
            criterios_validos,
            titulo="TP1 - Listas (2025)",
            anio=2025,
        )
        original = await service.crear_rubrica(
            original_data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN
        )

        duplicate_data = RubricaDuplicar(
            nuevo_anio=2026,
            nuevo_titulo="TP1 - Listas (2026)",
        )
        duplicated = await service.duplicar_rubrica(
            original.id, duplicate_data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN
        )

        assert duplicated.id != original.id
        assert duplicated.anio == 2026
        assert duplicated.titulo == "TP1 - Listas (2026)"
        assert duplicated.tipo == original.tipo
        assert duplicated.numero == original.numero
        assert duplicated.materia_id == original.materia_id
        assert duplicated.puntaje_maximo == 100

    async def test_duplicar_rubrica_already_exists(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test duplicating rubrica fails if already exists for new year."""
        service = RubricaService(db_session)

        data_2025 = _rubrica_create(
            materia.id,
            criterios_validos,
            tipo=TipoRubricaEnum.PARCIAL_1,
            titulo="Parcial 1 (2025)",
            anio=2025,
        )
        original = await service.crear_rubrica(
            data_2025, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN
        )

        data_2026 = _rubrica_create(
            materia.id,
            criterios_validos,
            tipo=TipoRubricaEnum.PARCIAL_1,
            titulo="Parcial 1 (2026)",
            anio=2026,
        )
        await service.crear_rubrica(data_2026, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        # Duplicar de 2025 a 2026 debe fallar: ya existe
        duplicate_data = RubricaDuplicar(nuevo_anio=2026)

        with pytest.raises(HTTPException) as exc_info:
            await service.duplicar_rubrica(
                original.id, duplicate_data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN
            )

        assert exc_info.value.status_code == 409
        assert "ya existe" in exc_info.value.detail.lower()

    async def test_actualizar_rubrica_success(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test updating rubrica successfully."""
        service = RubricaService(db_session)

        data = _rubrica_create(materia.id, criterios_validos, titulo="TP1 Original")
        rubrica = await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        update_data = RubricaUpdate(titulo="TP1 Actualizado")
        updated = await service.actualizar_rubrica(
            rubrica.id, update_data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN
        )

        assert updated.id == rubrica.id
        assert updated.titulo == "TP1 Actualizado"

    async def test_listar_rubricas_filtros(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test listing rubricas with filters."""
        service = RubricaService(db_session)

        for i in range(3):
            data = _rubrica_create(
                materia.id,
                criterios_validos,
                titulo=f"TP{i + 1}",
                numero=i + 1,
            )
            await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        result = await service.listar_rubricas(
            materia_id=materia.id, universidad_id=UNIV_ID
        )
        assert result.total == 3
        assert len(result.items) == 3

        result_tp = await service.listar_rubricas(
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP.value,
            universidad_id=UNIV_ID,
        )
        assert result_tp.total == 3

    async def test_eliminar_rubrica_soft_delete(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test soft deleting rubrica."""
        service = RubricaService(db_session)

        data = _rubrica_create(materia.id, criterios_validos, titulo="TP1")
        rubrica = await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        await service.eliminar_rubrica(rubrica.id, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        # Ya no aparece entre las activas
        result = await service.listar_rubricas(
            materia_id=materia.id,
            include_inactive=False,
            universidad_id=UNIV_ID,
        )
        assert result.total == 0

        # Pero sigue existiendo: es baja lógica, no física
        result_with_inactive = await service.listar_rubricas(
            materia_id=materia.id,
            include_inactive=True,
            universidad_id=UNIV_ID,
        )
        assert result_with_inactive.total == 1
        assert result_with_inactive.items[0].activa is False

    async def test_restaurar_rubrica(
        self,
        db_session: AsyncSession,
        admin: Usuario,
        materia: Materia,
        criterios_validos: list[dict[str, Any]],
    ):
        """Test restoring a soft-deleted rubrica."""
        service = RubricaService(db_session)

        data = _rubrica_create(materia.id, criterios_validos, titulo="TP1")
        rubrica = await service.crear_rubrica(data, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)
        await service.eliminar_rubrica(rubrica.id, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN)

        restored = await service.restaurar_rubrica(
            rubrica.id, admin, universidad_id=UNIV_ID, rol=RolEnum.ADMIN
        )

        assert restored.id == rubrica.id
        assert restored.activa is True

        result = await service.listar_rubricas(
            materia_id=materia.id, universidad_id=UNIV_ID
        )
        assert result.total == 1
