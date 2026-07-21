# app/repositories/correccion_repository.py
"""
Correccion repository for Active-IA.

Handles database queries for Correccion model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/06-MODELO-DATOS.md seccion 3.8
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 8
"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.models.comision import Comision, ComisionTutor
from app.models.correccion import Correccion
from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum, MoodleSyncEstado
from app.models.materia import Materia
from app.models.moodle_sync import MoodleSync
from app.models.rubrica import Rubrica


class CorreccionRepository:
    """
    Repository for Correccion model.

    Provides CRUD operations and common queries for correcciones.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, correccion_id: int) -> Correccion | None:
        """
        Get correccion by ID.

        Args:
            correccion_id: Correccion's database ID.

        Returns:
            Correccion object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Correccion).where(Correccion.id == correccion_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(
        self, correccion_id: int
    ) -> Correccion | None:
        """
        Get correccion by ID with all relations loaded.

        Loads nested relations needed for PDF generation:
        - entrega (with comision, materia, rubrica)
        - corregido_por

        Args:
            correccion_id: Correccion's database ID.

        Returns:
            Correccion object with relations if found, None otherwise.
        """
        result = await self.db.execute(
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
                selectinload(Correccion.corregido_por),
            )
            .where(Correccion.id == correccion_id)
        )
        return result.scalar_one_or_none()

    async def get_by_entrega_id(
        self, entrega_id: int, *, load_raw: bool = False
    ) -> Correccion | None:
        """
        Get correccion by entrega ID.

        Since Correccion has a 1:1 relationship with Entrega,
        this returns the unique correccion for a given entrega.

        Args:
            entrega_id: ID of the entrega.
            load_raw: CRUD-003: si True, carga raw_response (deferred) con undefer().
                El snapshot de la recorrección lo necesita: hay que leer el crudo
                ANTES del delete o salta DetachedInstanceError (o MissingGreenlet en
                async). Los demás callers no lo tocan (default False).

        Returns:
            Correccion object if found, None otherwise.
        """
        query = select(Correccion).where(Correccion.entrega_id == entrega_id)
        if load_raw:
            query = query.options(undefer(Correccion.raw_response))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_entrega_id_with_relations(
        self, entrega_id: int
    ) -> Correccion | None:
        """
        Get correccion by entrega ID with all relations loaded.

        Loads nested relations needed for PDF generation:
        - entrega (with comision, materia, rubrica)
        - corregido_por

        Args:
            entrega_id: ID of the entrega.

        Returns:
            Correccion object with relations if found, None otherwise.
        """
        result = await self.db.execute(
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
                selectinload(Correccion.corregido_por),
            )
            .where(Correccion.entrega_id == entrega_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        comision_id: int | None = None,
        rubrica_id: int | None = None,
        corregido_por_id: int | None = None,
        editado_manualmente: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Correccion], int]:
        """
        Get all correcciones with optional filters and pagination.

        Args:
            comision_id: Filter by comision ID (via entrega).
            rubrica_id: Filter by rubrica ID (via entrega).
            corregido_por_id: Filter by user who corrected.
            editado_manualmente: Filter by manual edit flag.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of correcciones, total count).
        """
        query = select(Correccion).options(
            selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
            selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
            selectinload(Correccion.corregido_por),
        )

        # Apply filters
        if comision_id is not None:
            query = query.join(Entrega).where(Entrega.comision_id == comision_id)

        if rubrica_id is not None:
            if comision_id is None:
                query = query.join(Entrega)
            query = query.where(Entrega.rubrica_id == rubrica_id)

        if corregido_por_id is not None:
            query = query.where(Correccion.corregido_por_id == corregido_por_id)

        if editado_manualmente is not None:
            query = query.where(
                Correccion.editado_manualmente == editado_manualmente
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Correccion.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        correcciones = list(result.scalars().all())

        return correcciones, total

    async def get_all_for_export(
        self,
        *,
        comision_id: int | None = None,
        rubrica_id: int | None = None,
        batch_size: int = 500,
    ) -> list[Correccion]:
        """PERF-009: devuelve TODAS las correcciones que matchean el filtro, SIN el tope
        de ``per_page`` de ``get_all``.

        El ZIP de devoluciones es un artefacto OFICIAL: debe ser COMPLETO. Con
        ``get_all(per_page=1000)`` cualquier comisión con más de 1000 correcciones salía
        truncada en silencio. Acá iteramos en lotes reutilizando ``get_all`` (mismos
        filtros y eager loads ya testeados) hasta agotar el conjunto, así el resultado
        refleja el total real (si hay 1500, trae 1500).

        Args:
            comision_id: Filtra por comisión (vía entrega).
            rubrica_id: Filtra por rúbrica (vía entrega).
            batch_size: Tamaño de lote por página. Parametrizable para poder ejercitar la
                iteración multi-página en tests sin sembrar miles de filas.

        Returns:
            Lista COMPLETA de correcciones con relaciones eager cargadas.
        """
        todas: list[Correccion] = []
        page = 1
        while True:
            lote, _ = await self.get_all(
                comision_id=comision_id,
                rubrica_id=rubrica_id,
                page=page,
                per_page=batch_size,
            )
            if not lote:
                break
            todas.extend(lote)
            if len(lote) < batch_size:
                break
            page += 1
        return todas

    async def exists_by_entrega_id(self, entrega_id: int) -> bool:
        """
        Check if a correccion exists for a given entrega.

        Args:
            entrega_id: Entrega ID.

        Returns:
            True if correccion exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Correccion)
            .where(Correccion.entrega_id == entrega_id)
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, correccion: Correccion) -> Correccion:
        """
        Create a new correccion.

        Args:
            correccion: Correccion object to create.

        Returns:
            Created Correccion object with ID assigned.
        """
        self.db.add(correccion)
        await self.db.commit()
        await self.db.refresh(correccion)
        return correccion

    async def update(self, correccion: Correccion) -> Correccion:
        """
        Update an existing correccion.

        Args:
            correccion: Correccion object with updated fields.

        Returns:
            Updated Correccion object.
        """
        correccion.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(correccion)
        return correccion

    async def delete(self, correccion: Correccion) -> None:
        """
        Hard delete a correccion.

        Note: Correcciones do not use soft delete.
        This is typically used when re-correcting an entrega.

        Args:
            correccion: Correccion object to delete.
        """
        await self.db.delete(correccion)
        await self.db.commit()

    async def get_statistics_by_rubrica(
        self, rubrica_id: int
    ) -> dict[str, float]:
        """
        Get statistics for correcciones of a specific rubrica.

        Args:
            rubrica_id: Rubrica ID.

        Returns:
            Dictionary with statistics (avg_nota, min_nota, max_nota, count).
        """
        result = await self.db.execute(
            select(
                func.avg(Correccion.nota).label("avg_nota"),
                func.min(Correccion.nota).label("min_nota"),
                func.max(Correccion.nota).label("max_nota"),
                func.count(Correccion.id).label("count"),
            )
            .select_from(Correccion)
            .join(Entrega)
            .where(Entrega.rubrica_id == rubrica_id)
        )

        row = result.one()

        return {
            "avg_nota": float(row.avg_nota) if row.avg_nota else 0.0,
            "min_nota": float(row.min_nota) if row.min_nota else 0.0,
            "max_nota": float(row.max_nota) if row.max_nota else 0.0,
            "count": int(row.count) if row.count else 0,
        }

    async def get_by_ids(self, correccion_ids: list[int]) -> list[Correccion]:
        """
        Get multiple correcciones by their IDs.

        Loads nested relations needed for PDF generation:
        - entrega (with comision, materia, rubrica)
        - corregido_por

        Args:
            correccion_ids: List of correccion IDs.

        Returns:
            List of Correccion objects.
        """
        result = await self.db.execute(
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
                selectinload(Correccion.corregido_por),
            )
            .where(Correccion.id.in_(correccion_ids))
        )
        return list(result.scalars().all())

    async def get_pendientes_subida_moodle(
        self, tutor_id: int, es_admin: bool
    ) -> list[Correccion]:
        """Correcciones listas para subir a Moodle pero aún NO enviadas.

        Una corrección es "pendiente de entregar" si:
          - su entrega está CORREGIDA y no archivada;
          - la entrega vino de Moodle (moodle_user_id poblado);
          - la rúbrica y la materia tienen sus IDs de Moodle configurados; y
          - NO existe un MoodleSync ENVIADO para esa corrección.

        Es una consulta 100% local (sin tocar Moodle): el listado es instantáneo.

        Args:
            tutor_id: ID del tutor solicitante.
            es_admin: si es True, ve correcciones de todas las comisiones.

        Returns:
            Lista de Correccion con entrega/comision/materia/rubrica cargadas,
            ordenada por materia, rúbrica y alumno.
        """
        enviado_exists = (
            select(MoodleSync.id)
            .where(
                MoodleSync.correccion_id == Correccion.id,
                MoodleSync.estado == MoodleSyncEstado.ENVIADO,
            )
            .exists()
        )

        query = (
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
            )
            .join(Entrega, Entrega.id == Correccion.entrega_id)
            .join(Comision, Comision.id == Entrega.comision_id)
            .join(Rubrica, Rubrica.id == Entrega.rubrica_id)
            .join(Materia, Materia.id == Comision.materia_id)
            .where(
                Entrega.estado == EstadoEntregaEnum.CORREGIDA,
                Entrega.archivado == False,  # noqa: E712
                Entrega.moodle_user_id.isnot(None),
                Rubrica.moodle_assign_id.isnot(None),
                Materia.moodle_course_id.isnot(None),
                ~enviado_exists,
            )
            .order_by(Materia.nombre, Rubrica.titulo, Entrega.alumno_nombre)
        )

        if not es_admin:
            tutor_exists = (
                select(ComisionTutor.id)
                .where(
                    ComisionTutor.comision_id == Comision.id,
                    ComisionTutor.tutor_id == tutor_id,
                )
                .exists()
            )
            query = query.where(tutor_exists)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def contar_no_vinculadas_moodle(
        self, tutor_id: int, es_admin: bool
    ) -> int:
        """Cuenta las correcciones CORREGIDA (no enviadas) que NO se pueden subir a Moodle.

        Son las que faltan algún requisito de subida: entrega sin moodle_user_id
        (cargada a mano), o rúbrica/materia sin IDs de Moodle configurados. Se usan
        sólo para el contador informativo de la vista (no se listan como filas).

        Args:
            tutor_id: ID del tutor solicitante.
            es_admin: si es True, cuenta sobre todas las comisiones.

        Returns:
            Cantidad de correcciones no vinculadas a Moodle.
        """
        enviado_exists = (
            select(MoodleSync.id)
            .where(
                MoodleSync.correccion_id == Correccion.id,
                MoodleSync.estado == MoodleSyncEstado.ENVIADO,
            )
            .exists()
        )

        query = (
            select(func.count(Correccion.id))
            .select_from(Correccion)
            .join(Entrega, Entrega.id == Correccion.entrega_id)
            .join(Comision, Comision.id == Entrega.comision_id)
            .join(Rubrica, Rubrica.id == Entrega.rubrica_id)
            .join(Materia, Materia.id == Comision.materia_id)
            .where(
                Entrega.estado == EstadoEntregaEnum.CORREGIDA,
                Entrega.archivado == False,  # noqa: E712
                ~enviado_exists,
                or_(
                    Entrega.moodle_user_id.is_(None),
                    Rubrica.moodle_assign_id.is_(None),
                    Materia.moodle_course_id.is_(None),
                ),
            )
        )

        if not es_admin:
            tutor_exists = (
                select(ComisionTutor.id)
                .where(
                    ComisionTutor.comision_id == Comision.id,
                    ComisionTutor.tutor_id == tutor_id,
                )
                .exists()
            )
            query = query.where(tutor_exists)

        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def get_by_entrega_ids_corregidas(
        self, entrega_ids: list[int]
    ) -> list[Correccion]:
        """
        Get correcciones for the given entrega IDs, filtering to CORREGIDA state only.

        Args:
            entrega_ids: List of entrega IDs requested by the user.

        Returns:
            List of Correccion objects with relations loaded (only CORREGIDA entregas).
        """
        result = await self.db.execute(
            select(Correccion)
            .options(
                selectinload(Correccion.entrega).selectinload(Entrega.comision).selectinload(Comision.materia),
                selectinload(Correccion.entrega).selectinload(Entrega.rubrica),
                selectinload(Correccion.corregido_por),
            )
            .join(Entrega)
            .where(
                Correccion.entrega_id.in_(entrega_ids),
                Entrega.estado == EstadoEntregaEnum.CORREGIDA,
            )
        )
        return list(result.scalars().all())
