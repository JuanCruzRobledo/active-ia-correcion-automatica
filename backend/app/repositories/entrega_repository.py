# app/repositories/entrega_repository.py
"""
Entrega repository for Active-IA.

Handles database queries for Entrega model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.models.comision import Comision
from app.models.entrega import Entrega


class EntregaRepository:
    """
    Repository for Entrega model.

    Provides CRUD operations and common queries for entregas.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def version(self) -> tuple[datetime | None, int]:
        """(MAX(updated_at), COUNT) de todas las entregas — token barato de 'novedades'."""
        result = await self.db.execute(
            select(func.max(Entrega.updated_at), func.count(Entrega.id))
        )
        max_updated_at, count = result.one()
        return max_updated_at, count or 0

    async def get_by_id(
        self,
        entrega_id: int,
        *,
        load_contenido: bool = False,
        include_deleted: bool = False,
    ) -> Entrega | None:
        """
        Get entrega by ID.

        Args:
            entrega_id: Entrega's database ID.
            load_contenido: Si True, carga explícitamente las columnas GIGANTES
                deferidas (contenido_consolidado / pdf_contenido_b64) con undefer().
                PERF-002/PERF-006: por defecto False para no arrastrarlas; los
                flujos que SÍ leen el contenido (obtener_contenido) lo piden en True.
            include_deleted: CRUD-001: por defecto una entrega borrada (soft delete)
                es "no encontrada". El restore la necesita ver -> include_deleted=True.

        Returns:
            Entrega object if found, None otherwise.
        """
        query = select(Entrega).where(Entrega.id == entrega_id)
        if not include_deleted:
            query = query.where(Entrega.deleted_at.is_(None))
        if load_contenido:
            query = query.options(
                undefer(Entrega.contenido_consolidado),
                undefer(Entrega.pdf_contenido_b64),
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(
        self, entrega_id: int, *, load_contenido: bool = False
    ) -> Entrega | None:
        """
        Get entrega by ID with all relations loaded.

        Args:
            entrega_id: Entrega's database ID.
            load_contenido: Si True, carga explícitamente las columnas GIGANTES
                deferidas (contenido_consolidado / pdf_contenido_b64) con undefer().
                PERF-002/PERF-006: la corrección (que arma el payload para la IA con
                el contenido) lo pide en True; el detalle de la entrega no lo necesita.

        Returns:
            Entrega object with relations if found, None otherwise.
        """
        options = [
            selectinload(Entrega.comision).selectinload(Comision.materia),
            selectinload(Entrega.rubrica),
            selectinload(Entrega.subido_por),
            selectinload(Entrega.correccion),
            selectinload(Entrega.historial),
        ]
        if load_contenido:
            options.extend([
                undefer(Entrega.contenido_consolidado),
                undefer(Entrega.pdf_contenido_b64),
            ])
        result = await self.db.execute(
            select(Entrega)
            .options(*options)
            .where(Entrega.id == entrega_id, Entrega.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        comision_id: int | None = None,
        comisiones_visibles: list[int] | None = None,
        rubrica_id: int | None = None,
        estado: str | None = None,
        include_archivadas: bool = False,
        solo_archivadas: bool = False,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Entrega], int]:
        """
        Get all entregas with optional filters and pagination.

        Args:
            comision_id: Filter by comision ID.
            rubrica_id: Filter by rubrica ID.
            estado: Filter by estado.
            include_archivadas: If False (default), exclude archived entregas.
            solo_archivadas: If True, show only archived entregas (overrides include_archivadas).
            fecha_desde: Filter by created_at >= this date (inclusive).
            fecha_hasta: Filter by created_at <= this date (inclusive, end of day).
            search: PERF-013: filtro por nombre del alumno (ILIKE parcial,
                case-insensitive). None o cadena vacía/espacios = sin búsqueda.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of entregas, total count).
        """
        # Build filter conditions once, so the data query and the count query
        # stay in sync from a single source of truth.
        conditions = []

        # CRUD-001: excluir las borradas (soft delete). Va a la lista `conditions`
        # compartida datos+count, así el total paginado tampoco las cuenta.
        conditions.append(Entrega.deleted_at.is_(None))

        if comision_id is not None:
            conditions.append(Entrega.comision_id == comision_id)

        # SEC-002: scoping por pertenencia. None = ADMIN (sin filtro). Lista vacía =
        # el usuario no tiene comisiones y no ve nada, que es el comportamiento correcto.
        # Va a la MISMA lista `conditions` que comparten datos y count, así el total
        # paginado no revela cuántas entregas hay en todo el sistema.
        if comisiones_visibles is not None:
            conditions.append(Entrega.comision_id.in_(comisiones_visibles))

        if rubrica_id is not None:
            conditions.append(Entrega.rubrica_id == rubrica_id)

        if estado is not None:
            conditions.append(Entrega.estado == estado)

        # Archive filter: solo_archivadas takes priority over include_archivadas
        if solo_archivadas:
            conditions.append(Entrega.archivado == True)  # noqa: E712
        elif not include_archivadas:
            conditions.append(Entrega.archivado == False)  # noqa: E712

        # Date range filter
        if fecha_desde:
            start = datetime(fecha_desde.year, fecha_desde.month, fecha_desde.day, 0, 0, 0)
            conditions.append(Entrega.created_at >= start)
        if fecha_hasta:
            end = datetime(fecha_hasta.year, fecha_hasta.month, fecha_hasta.day, 23, 59, 59)
            conditions.append(Entrega.created_at <= end)

        # PERF-013: búsqueda por nombre del alumno (ILIKE parcial, case-insensitive).
        # Se suma a la MISMA lista `conditions` que comparten datos y count, así el
        # total refleja el filtro igual que las filas. Cadena vacía/espacios = sin filtro.
        if search and search.strip():
            conditions.append(Entrega.alumno_nombre.ilike(f"%{search.strip()}%"))

        # Count total (PERF-002): COUNT(id) con los MISMOS filtros, SIN envolver la
        # query de columnas en un subquery — así el count no arrastra las columnas
        # pesadas (contenido_consolidado / pdf_contenido_b64) ni los selectinload.
        count_query = (
            select(func.count(Entrega.id)).select_from(Entrega).where(*conditions)
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Data query: columnas + relaciones eager, mismos filtros.
        query = (
            select(Entrega)
            .options(
                selectinload(Entrega.comision),
                selectinload(Entrega.rubrica),
                selectinload(Entrega.subido_por),
                selectinload(Entrega.correccion),
            )
            .where(*conditions)
        )

        # Apply pagination and ordering
        query = query.order_by(Entrega.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        entregas = list(result.scalars().all())

        return entregas, total

    async def get_all_for_export(
        self,
        *,
        comision_id: int | None = None,
        comisiones_visibles: list[int] | None = None,
        rubrica_id: int | None = None,
        batch_size: int = 500,
    ) -> list[Entrega]:
        """PERF-009: devuelve TODAS las entregas que matchean el filtro, SIN el tope de
        ``per_page`` de ``get_all``.

        El Excel de notas es un acta OFICIAL de calificaciones: debe ser COMPLETO. Con
        ``get_all(per_page=1000)`` una comisión con más de 1000 entregas salía truncada en
        silencio. Acá iteramos en lotes reutilizando ``get_all`` (que ya excluye las
        archivadas por defecto y comparte los filtros/eager loads testeados) hasta agotar
        el conjunto, así el acta refleja el total real (si hay 1500, trae 1500).

        Args:
            comision_id: Filtra por comisión.
            rubrica_id: Filtra por rúbrica.
            batch_size: Tamaño de lote por página. Parametrizable para ejercitar la
                iteración multi-página en tests sin sembrar miles de filas.

        Returns:
            Lista COMPLETA de entregas (no archivadas) con relaciones eager cargadas.
        """
        todas: list[Entrega] = []
        page = 1
        while True:
            lote, _ = await self.get_all(
                comision_id=comision_id,
                # SEC-002: el scoping DEBE propagarse. Este método alimenta el Excel
                # de notas; sin esto sería una puerta trasera para leer entregas
                # ajenas salteando el filtro del listado.
                comisiones_visibles=comisiones_visibles,
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

    async def get_by_rubrica_alumno(
        self,
        rubrica_id: int,
        alumno_nombre: str,
        *,
        load_contenido: bool = False,
    ) -> Entrega | None:
        """
        Get entrega by rubrica and alumno nombre.

        Args:
            rubrica_id: ID of the rubrica.
            alumno_nombre: Nombre del alumno.
            load_contenido: CRUD-005: si True, undefiere contenido_consolidado y
                pdf_contenido_b64 para poder snapshotearlos antes de sobrescribir.

        Returns:
            Entrega object if found, None otherwise.
        """
        options = [selectinload(Entrega.correccion)]
        if load_contenido:
            options.extend([
                undefer(Entrega.contenido_consolidado),
                undefer(Entrega.pdf_contenido_b64),
            ])
        result = await self.db.execute(
            select(Entrega)
            .options(*options)
            .where(
                Entrega.rubrica_id == rubrica_id,
                Entrega.alumno_nombre == alumno_nombre,
            )
        )
        return result.scalar_one_or_none()

    async def exists_by_rubrica_alumno(
        self,
        rubrica_id: int,
        alumno_nombre: str,
    ) -> bool:
        """
        Check if an entrega exists for rubrica and alumno.

        Args:
            rubrica_id: Rubrica ID.
            alumno_nombre: Nombre del alumno.

        Returns:
            True if entrega exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Entrega)
            .where(
                Entrega.rubrica_id == rubrica_id,
                Entrega.alumno_nombre == alumno_nombre,
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, entrega: Entrega) -> Entrega:
        """
        Create a new entrega.

        Args:
            entrega: Entrega object to create.

        Returns:
            Created Entrega object with ID assigned.
        """
        self.db.add(entrega)
        await self.db.commit()
        await self.db.refresh(entrega)
        return entrega

    async def update(self, entrega: Entrega) -> Entrega:
        """
        Update an existing entrega.

        Args:
            entrega: Entrega object with updated fields.

        Returns:
            Updated Entrega object.
        """
        entrega.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(entrega)
        return entrega

    async def delete(self, entrega: Entrega) -> None:
        """
        Physically delete an entrega (hard delete).

        Args:
            entrega: Entrega object to delete.
        """
        await self.db.delete(entrega)
        await self.db.commit()

    async def soft_delete(self, entrega: Entrega) -> Entrega:
        """
        CRUD-001: baja logica de una entrega (setea deleted_at).

        No toca la Correccion 1:1: al no hacer db.delete, la cascada
        all,delete-orphan no dispara y la nota del alumno queda preservada
        colgando de la entrega oculta. Patron calcado de MateriaRepository.soft_delete.
        """
        entrega.deleted_at = datetime.utcnow()
        entrega.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(entrega)
        return entrega

    async def restore(self, entrega: Entrega) -> Entrega:
        """CRUD-001: restaura una entrega borrada (deleted_at = None)."""
        entrega.deleted_at = None
        entrega.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(entrega)
        return entrega

    async def soft_delete_by_ids(self, ids: list[int]) -> int:
        """
        CRUD-001: baja logica masiva. UPDATE en una query (no toca correcciones).

        Solo marca las que aun no estaban borradas, para no pisar el deleted_at
        original de una que ya estaba en la papelera.
        """
        ahora = datetime.utcnow()
        result = await self.db.execute(
            update(Entrega)
            .where(Entrega.id.in_(ids), Entrega.deleted_at.is_(None))
            .values(deleted_at=ahora, updated_at=ahora)
        )
        await self.db.commit()
        return result.rowcount

    async def get_by_ids(self, ids: list[int]) -> list[Entrega]:
        """
        Get multiple entregas by their IDs.

        Args:
            ids: List of entrega IDs.

        Returns:
            List of found Entrega objects.
        """
        result = await self.db.execute(
            select(Entrega).where(Entrega.id.in_(ids))
        )
        return list(result.scalars().all())

    async def archive_by_ids(self, ids: list[int], archivado: bool) -> int:
        """
        Bulk archive or unarchive entregas.

        Args:
            ids: List of entrega IDs.
            archivado: True to archive, False to unarchive.

        Returns:
            Number of rows affected.
        """
        result = await self.db.execute(
            update(Entrega)
            .where(Entrega.id.in_(ids))
            .values(archivado=archivado)
        )
        await self.db.commit()
        return result.rowcount

    async def delete_by_ids(self, ids: list[int]) -> int:
        """
        Bulk hard delete entregas by IDs via ORM to respect cascade rules.

        Uses ORM-level deletion so SQLAlchemy cascades (correccion,
        historial with cascade="all, delete-orphan") are honoured.
        Raw SQL DELETE would bypass those cascades and trigger FK violations.

        Args:
            ids: List of entrega IDs to delete.

        Returns:
            Number of rows deleted.
        """
        result = await self.db.execute(
            select(Entrega)
            .options(
                selectinload(Entrega.correccion),
                selectinload(Entrega.historial),
            )
            .where(Entrega.id.in_(ids))
        )
        entregas = list(result.scalars().all())
        for entrega in entregas:
            await self.db.delete(entrega)
        await self.db.commit()
        return len(entregas)

    async def get_subidas_ids_by_tutor(
        self, tutor_id: int, limite: int | None = None, incluir_errores: bool = True
    ) -> list[int]:
        """IDs de entregas RECORREGIBLES de TODAS las comisiones del tutor (cross-rúbrica).

        Para la corrección masiva global. Excluye archivadas. Por defecto incluye las que
        quedaron en ERROR (item #7: una entrega que falló debe volver a corregirse en la
        masiva, no quedar atrapada). incluir_errores=False vuelve al comportamiento viejo
        (solo SUBIDA).
        """
        from app.models.comision import ComisionTutor
        from app.models.enums import EstadoEntregaEnum

        estados = [EstadoEntregaEnum.SUBIDA]
        if incluir_errores:
            estados.append(EstadoEntregaEnum.ERROR)

        stmt = (
            select(Entrega.id)
            .join(Comision, Comision.id == Entrega.comision_id)
            .join(ComisionTutor, ComisionTutor.comision_id == Comision.id)
            .where(
                ComisionTutor.tutor_id == tutor_id,
                Entrega.estado.in_(estados),
                Entrega.archivado == False,  # noqa: E712
            )
            .order_by(Entrega.id)
        )
        if limite is not None:
            stmt = stmt.limit(limite)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def contar_errores_by_tutor(self, tutor_id: int) -> dict[str, int]:
        """Conteo de entregas en ERROR por error_code, para el resumen de la masiva (item #7)."""
        from app.models.comision import ComisionTutor
        from app.models.enums import EstadoEntregaEnum

        stmt = (
            select(Entrega.error_code, func.count())
            .join(Comision, Comision.id == Entrega.comision_id)
            .join(ComisionTutor, ComisionTutor.comision_id == Comision.id)
            .where(
                ComisionTutor.tutor_id == tutor_id,
                Entrega.estado == EstadoEntregaEnum.ERROR,
                Entrega.archivado == False,  # noqa: E712
            )
            .group_by(Entrega.error_code)
        )
        result = await self.db.execute(stmt)
        return {(code or "DESCONOCIDO"): int(n) for code, n in result.all()}

    async def contar_estados_by_tutor(self, tutor_id: int) -> dict[str, int]:
        """Conteo de entregas por estado para el tutor (para el progreso de 'Corregir todo')."""
        from app.models.comision import ComisionTutor

        stmt = (
            select(Entrega.estado, func.count())
            .join(Comision, Comision.id == Entrega.comision_id)
            .join(ComisionTutor, ComisionTutor.comision_id == Comision.id)
            .where(
                ComisionTutor.tutor_id == tutor_id,
                Entrega.archivado == False,  # noqa: E712
            )
            .group_by(Entrega.estado)
        )
        result = await self.db.execute(stmt)
        counts: dict[str, int] = {}
        for estado, count in result.all():
            key = estado.value if hasattr(estado, "value") else str(estado)
            counts[key] = int(count)
        return counts


