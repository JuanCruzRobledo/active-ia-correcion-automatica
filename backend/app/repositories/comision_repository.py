# app/repositories/comision_repository.py
"""
Comision repository for Active-IA.

Handles database queries for Comision and ComisionTutor models.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 5
"""

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.models.comision import Comision, ComisionTutor
from app.models.entrega import Entrega
from app.models.materia import CoordinadorMateria
from app.models.usuario import Usuario
from app.utils.orden_natural import orden_natural_sql


class ComisionRepository:
    """
    Repository for Comision model.

    Provides CRUD operations and common queries for comisiones.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, comision_id: int) -> Comision | None:
        """
        Get comision by ID.

        Args:
            comision_id: Comision's database ID.

        Returns:
            Comision object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Comision).where(Comision.id == comision_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, comision_id: int) -> Comision | None:
        """
        Get comision by ID with materia and tutores loaded.

        Args:
            comision_id: Comision's database ID.

        Returns:
            Comision object with relations if found, None otherwise.
        """
        # PERF-012: se eager-loadea también el usuario de cada tutor (con load_only de
        # las columnas que usa la respuesta), para que el service NO haga un
        # get_by_id(tutor_id) por tutor en loop.
        result = await self.db.execute(
            select(Comision)
            .options(
                selectinload(Comision.materia),
                selectinload(Comision.tutores)
                .selectinload(ComisionTutor.tutor)
                .load_only(Usuario.id, Usuario.username, Usuario.nombre),
            )
            .where(Comision.id == comision_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        materia_id: int | None = None,
        tutor_id: int | None = None,
        coordinador_id: int | None = None,
        anio: int | None = None,
        include_inactive: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Comision], int]:
        """
        Get all comisiones with optional filters and pagination.

        Args:
            materia_id: Filter by materia ID.
            tutor_id: Filter to comisiones assigned to this tutor.
            coordinador_id: Filter to comisiones of materias assigned to this coordinator.
            anio: Filter by academic year.
            include_inactive: Include soft-deleted comisiones.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of comisiones, total count).
        """
        # Base query
        query = select(Comision).options(selectinload(Comision.materia))

        # Apply filters
        if not include_inactive:
            query = query.where(Comision.activa == True)  # noqa: E712

        if materia_id is not None:
            query = query.where(Comision.materia_id == materia_id)

        if tutor_id is not None:
            query = query.join(ComisionTutor).where(ComisionTutor.tutor_id == tutor_id)

        if coordinador_id is not None:
            query = query.join(
                CoordinadorMateria,
                Comision.materia_id == CoordinadorMateria.materia_id,
            ).where(CoordinadorMateria.coordinador_id == coordinador_id)

        if anio is not None:
            query = query.where(Comision.anio == anio)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Comision.anio.desc(), *orden_natural_sql(Comision.nombre))
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        comisiones = list(result.scalars().all())

        return comisiones, total

    async def contar_tutores_entregas(
        self, comision_ids: list[int]
    ) -> dict[int, tuple[int, int]]:
        """(num_tutores, num_entregas) por comisión en UNA sola query agregada.

        Reemplaza el N+1 de ``listar_comisiones`` (una query de tutores + la
        materialización de la colección ``entregas`` selectin por cada comisión).

        Se hacen dos ``outerjoin`` (a comision_tutor y a entregas) y se cuenta con
        ``COUNT(DISTINCT ...)`` para que la multiplicación cartesiana de ambos joins
        NO infle los conteos: el resultado es idéntico al del loop viejo
        (``len(get_tutores_for_comision(id))`` y ``len(comision.entregas)``). Las
        comisiones sin tutores ni entregas quedan en (0, 0).

        Args:
            comision_ids: IDs de las comisiones a contar.

        Returns:
            dict {comision_id: (num_tutores, num_entregas)}.
        """
        if not comision_ids:
            return {}

        result = await self.db.execute(
            select(
                Comision.id,
                func.count(func.distinct(ComisionTutor.id)),
                func.count(func.distinct(Entrega.id)),
            )
            .select_from(Comision)
            .outerjoin(ComisionTutor, ComisionTutor.comision_id == Comision.id)
            .outerjoin(Entrega, Entrega.comision_id == Comision.id)
            .where(Comision.id.in_(comision_ids))
            .group_by(Comision.id)
        )
        return {cid: (int(nt), int(ne)) for cid, nt, ne in result.all()}

    async def contar_comisiones_activas_por_materia(
        self, materia_ids: list[int]
    ) -> dict[int, int]:
        """CRUD-016: Nº de comisiones ACTIVAS por materia en UNA query agregada.

        Reemplaza el conteo en Python sobre materia.comisiones (lazy=selectin), que
        materializaba la colección entera de cada materia del listado solo para
        contar. Las materias sin comisiones activas no aparecen (se interpretan 0).
        """
        if not materia_ids:
            return {}
        result = await self.db.execute(
            select(Comision.materia_id, func.count(Comision.id))
            .where(
                Comision.materia_id.in_(materia_ids),
                Comision.activa == True,  # noqa: E712
            )
            .group_by(Comision.materia_id)
        )
        return {mid: int(n) for mid, n in result.all()}

    async def get_by_materia(self, materia_id: int) -> list[Comision]:
        """
        Get all active comisiones for a materia.

        Args:
            materia_id: ID of the materia.

        Returns:
            List of active comisiones for the materia.
        """
        result = await self.db.execute(
            select(Comision)
            .where(
                Comision.materia_id == materia_id,
                Comision.activa == True,  # noqa: E712
            )
            .order_by(Comision.anio.desc(), *orden_natural_sql(Comision.nombre))
        )
        return list(result.scalars().all())

    async def get_by_materia_con_tutores(self, materia_id: int) -> list[Comision]:
        """Comisiones activas de una materia con sus tutores (y el usuario) eager-loaded.

        Una sola query: evita N+1 al mapear comisión → tutor (pantalla Gestión).
        """
        result = await self.db.execute(
            select(Comision)
            .where(
                Comision.materia_id == materia_id,
                Comision.activa == True,  # noqa: E712
            )
            .options(selectinload(Comision.tutores).selectinload(ComisionTutor.tutor))
            .order_by(*orden_natural_sql(Comision.nombre))
        )
        return list(result.scalars().all())

    async def get_by_tutor(self, tutor_id: int) -> list[Comision]:
        """
        Get all active comisiones assigned to a tutor.

        Args:
            tutor_id: ID of the tutor user.

        Returns:
            List of active comisiones for the tutor.
        """
        result = await self.db.execute(
            select(Comision)
            .join(ComisionTutor)
            .where(
                ComisionTutor.tutor_id == tutor_id,
                Comision.activa == True,  # noqa: E712
            )
            .order_by(Comision.anio.desc(), *orden_natural_sql(Comision.nombre))
        )
        return list(result.scalars().all())

    async def get_moodle_habilitadas_de_tutor(
        self,
        tutor_id: int,
        *,
        comision_id: int | None = None,
        materia_id: int | None = None,
    ) -> list[Comision]:
        """Comisiones ACTIVAS del tutor con moodle_group_id configurado (con la
        materia eager-loaded), para los flujos de Moodle (pendientes / import).

        Filtros de scope opcionales: comision_id acota a una sola comisión;
        materia_id acota a las de una materia (usados por el import con scope).
        """
        stmt = (
            select(Comision)
            .join(ComisionTutor, ComisionTutor.comision_id == Comision.id)
            .where(
                ComisionTutor.tutor_id == tutor_id,
                Comision.activa == True,  # noqa: E712
                Comision.moodle_group_id.isnot(None),
            )
            .options(selectinload(Comision.materia))
        )
        if comision_id is not None:
            stmt = stmt.where(Comision.id == comision_id)
        if materia_id is not None:
            stmt = stmt.where(Comision.materia_id == materia_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_id(self, comision_id: int) -> Comision | None:
        """
        Get active comision by ID (not soft-deleted).

        Args:
            comision_id: Comision's database ID.

        Returns:
            Comision object if found and active, None otherwise.
        """
        result = await self.db.execute(
            select(Comision).where(
                Comision.id == comision_id,
                Comision.activa == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def exists(
        self,
        materia_id: int,
        nombre: str,
        anio: int,
    ) -> bool:
        """
        Check if a comision with same materia, nombre, and anio exists.

        Args:
            materia_id: Materia ID.
            nombre: Comision name.
            anio: Academic year.

        Returns:
            True if comision exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Comision)
            .where(
                Comision.materia_id == materia_id,
                Comision.nombre == nombre,
                Comision.anio == anio,
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def desactivar_por_materia(self, materia_id: int) -> int:
        """
        CRUD-006: desactiva las comisiones ACTIVAS de una materia (propagación del
        soft delete). Solo toca las activas para que el restore reactive el mismo
        conjunto. Devuelve cuántas se desactivaron.
        """
        result = await self.db.execute(
            update(Comision)
            .where(Comision.materia_id == materia_id, Comision.activa == True)  # noqa: E712
            .values(activa=False)
        )
        await self.db.commit()
        return result.rowcount

    async def reactivar_por_materia(self, materia_id: int) -> int:
        """CRUD-006: reactiva las comisiones inactivas de una materia (restore).

        Nota: reactiva TODAS las inactivas de la materia. Si una comisión se había
        desactivado por su cuenta antes de borrar la materia, el restore también la
        reactivará (edge case documentado, poco frecuente).
        """
        result = await self.db.execute(
            update(Comision)
            .where(Comision.materia_id == materia_id, Comision.activa == False)  # noqa: E712
            .values(activa=True)
        )
        await self.db.commit()
        return result.rowcount

    async def get_by_materia_nombre_anio(
        self,
        materia_id: int,
        nombre: str,
        anio: int,
    ) -> Comision | None:
        """
        CRUD-011: devuelve la comisión que ocupa la clave única (materia+nombre+anio),
        SIN filtrar por `activa`, para poder distinguir un conflicto contra un
        registro eliminado y ofrecer restaurarlo.
        """
        result = await self.db.execute(
            select(Comision).where(
                Comision.materia_id == materia_id,
                Comision.nombre == nombre,
                Comision.anio == anio,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, comision: Comision) -> Comision:
        """
        Create a new comision.

        Args:
            comision: Comision object to create.

        Returns:
            Created Comision object with ID assigned.
        """
        self.db.add(comision)
        await self.db.commit()
        await self.db.refresh(comision)
        return comision

    async def update(self, comision: Comision) -> Comision:
        """
        Update an existing comision.

        Args:
            comision: Comision object with updated fields.

        Returns:
            Updated Comision object.
        """
        comision.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(comision)
        return comision

    async def soft_delete(self, comision: Comision) -> Comision:
        """
        Soft delete a comision (set activa=False).

        Args:
            comision: Comision object to delete.

        Returns:
            Updated Comision object.
        """
        comision.activa = False
        comision.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(comision)
        return comision

    async def restore(self, comision: Comision) -> Comision:
        """
        Restore a soft-deleted comision (set activa=True).

        Args:
            comision: Comision object to restore.

        Returns:
            Updated Comision object.
        """
        comision.activa = True
        comision.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(comision)
        return comision

    async def hard_delete_with_cascade(self, comision: Comision) -> None:
        """
        Hard delete: elimina físicamente la comisión y toda su cascada.

        Orden de operaciones:
        1. Por cada Entrega de la comision:
           a. Elimina archivos físicos del disco
           b. DELETE Entrega (cascade ORM elimina Correccion y EntregaHistorial)
        2. DELETE ComisionTutor (asignaciones de tutores)
        3. DELETE Comision

        Args:
            comision: Comision object to hard-delete.

        Raises:
            Exception: Si falla alguna operación de DB o de disco.
        """

        from sqlalchemy import select

        from app.models.entrega import Entrega

        comision_id = comision.id

        # 1. Cargar y eliminar todas las entregas de la comision
        result = await self.db.execute(
            select(Entrega).where(Entrega.comision_id == comision_id)
        )
        entregas = result.scalars().all()

        for entrega in entregas:

            # Eliminar la entrega (cascade ORM elimina Correccion y EntregaHistorial)
            await self.db.delete(entrega)

        # Flush para que se procesen los deletes de entregas antes de eliminar la comision
        await self.db.flush()

        # 2. Eliminar asignaciones de tutores a esta comision
        await self.db.execute(
            delete(ComisionTutor).where(ComisionTutor.comision_id == comision_id)
        )

        # 3. Eliminar la comision
        await self.db.delete(comision)
        await self.db.commit()


class ComisionTutorRepository:
    """
    Repository for ComisionTutor model.

    Manages the N:M relationship between comisiones and tutors.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_tutores_for_comision(
        self,
        comision_id: int,
    ) -> list[ComisionTutor]:
        """
        Get all tutor assignments for a comision.

        Args:
            comision_id: ID of the comision.

        Returns:
            List of ComisionTutor records.
        """
        result = await self.db.execute(
            select(ComisionTutor)
            .where(ComisionTutor.comision_id == comision_id)
            .order_by(ComisionTutor.asignado_en.desc())
        )
        return list(result.scalars().all())

    async def exists(self, tutor_id: int, comision_id: int) -> bool:
        """
        Check if a tutor is already assigned to a comision.

        Args:
            tutor_id: ID of the tutor.
            comision_id: ID of the comision.

        Returns:
            True if assignment exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(ComisionTutor)
            .where(
                ComisionTutor.tutor_id == tutor_id,
                ComisionTutor.comision_id == comision_id,
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def create(
        self,
        tutor_id: int,
        comision_id: int,
    ) -> ComisionTutor:
        """
        Create a tutor-comision assignment.

        Args:
            tutor_id: ID of the tutor.
            comision_id: ID of the comision.

        Returns:
            Created ComisionTutor record.
        """
        assignment = ComisionTutor(
            tutor_id=tutor_id,
            comision_id=comision_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def delete_all_for_comision(self, comision_id: int) -> int:
        """
        Delete all tutor assignments for a comision.

        Args:
            comision_id: ID of the comision.

        Returns:
            Number of records deleted.
        """
        result = await self.db.execute(
            select(ComisionTutor).where(
                ComisionTutor.comision_id == comision_id
            )
        )
        assignments = result.scalars().all()
        count = len(assignments)

        for assignment in assignments:
            await self.db.delete(assignment)

        await self.db.commit()
        return count

    async def delete_all_for_tutor(self, tutor_id: int) -> int:
        """
        CRUD-013: borra todas las asignaciones de tutoría de un usuario.

        Se usa al cambiar su rol AWAY de TUTOR, para no dejar filas huérfanas.
        """
        result = await self.db.execute(
            delete(ComisionTutor).where(ComisionTutor.tutor_id == tutor_id)
        )
        await self.db.commit()
        return result.rowcount

    async def delete(self, tutor_id: int, comision_id: int) -> bool:
        """
        Delete a specific tutor-comision assignment.

        Args:
            tutor_id: ID of the tutor.
            comision_id: ID of the comision.

        Returns:
            True if deleted, False if not found.
        """
        result = await self.db.execute(
            select(ComisionTutor).where(
                ComisionTutor.tutor_id == tutor_id,
                ComisionTutor.comision_id == comision_id,
            )
        )
        assignment = result.scalar_one_or_none()

        if assignment:
            await self.db.delete(assignment)
            await self.db.commit()
            return True

        return False
