# app/repositories/materia_repository.py
"""
Materia repository for Active-IA.

Handles database queries for Materia and CoordinadorMateria models.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 4
"""

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.materia import CoordinadorMateria, Materia


class MateriaRepository:
    """
    Repository for Materia model.

    Provides CRUD operations and common queries for materias.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, materia_id: int) -> Materia | None:
        """
        Get materia by ID.

        Args:
            materia_id: Materia's database ID.

        Returns:
            Materia object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Materia).where(Materia.id == materia_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_coordinadores(self, materia_id: int) -> Materia | None:
        """
        Get materia by ID with coordinadores loaded.

        Args:
            materia_id: Materia's database ID.

        Returns:
            Materia object with coordinadores if found, None otherwise.
        """
        result = await self.db.execute(
            select(Materia)
            .options(selectinload(Materia.coordinadores))
            .where(Materia.id == materia_id)
        )
        return result.scalar_one_or_none()

    async def get_by_codigo(self, codigo: str) -> Materia | None:
        """
        Get materia by codigo.

        Args:
            codigo: Materia's unique code.

        Returns:
            Materia object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Materia).where(Materia.codigo == codigo.upper())
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        include_inactive: bool = False,
        activa: bool | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        coordinador_id: int | None = None,
    ) -> tuple[list[Materia], int]:
        """
        Get all materias with optional filters and pagination.

        Args:
            include_inactive: Include soft-deleted materias.
            activa: If provided, filter by exact active status (useful with include_inactive=True
                    to retrieve only inactivas). Ignored when include_inactive=False (always activa=True).
            search: Search term for codigo or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.
            coordinador_id: If set, filter to materias assigned to this coordinator.

        Returns:
            Tuple of (list of materias, total count).
        """
        # Base query
        query = select(Materia)

        # Filter by coordinator assignment
        if coordinador_id is not None:
            query = query.join(CoordinadorMateria).where(
                CoordinadorMateria.coordinador_id == coordinador_id
            )

        # Apply active/inactive filter
        if not include_inactive:
            # Default: solo activas
            query = query.where(Materia.activa == True)  # noqa: E712
        elif activa is not None:
            # include_inactive=True + activa especificado → filtrar por ese valor exacto
            query = query.where(Materia.activa == activa)  # noqa: E712
        # else: include_inactive=True sin activa → devolver todas (activas e inactivas)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Materia.codigo.ilike(search_term))
                | (Materia.nombre.ilike(search_term))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Materia.nombre.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        materias = list(result.scalars().all())

        return materias, total

    async def get_active_by_id(self, materia_id: int) -> Materia | None:
        """
        Get active materia by ID (not soft-deleted).

        Args:
            materia_id: Materia's database ID.

        Returns:
            Materia object if found and active, None otherwise.
        """
        result = await self.db.execute(
            select(Materia).where(
                Materia.id == materia_id,
                Materia.activa == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_con_moodle(self) -> list[Materia]:
        """Materias activas vinculadas a un curso de Moodle (moodle_course_id no nulo).

        Son los cursos que el Gestor puede elegir en la pantalla "Gestión".
        """
        result = await self.db.execute(
            select(Materia)
            .where(
                Materia.activa == True,  # noqa: E712
                Materia.moodle_course_id.isnot(None),
            )
            .order_by(Materia.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_by_cuatrimestre(self, cuatrimestre_id: int) -> list[Materia]:
        """Materias activas de un cuatrimestre (para los selectores del dashboard)."""
        result = await self.db.execute(
            select(Materia)
            .where(
                Materia.cuatrimestre_id == cuatrimestre_id,
                Materia.activa == True,  # noqa: E712
            )
            .order_by(Materia.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_by_cuatrimestres(
        self, cuatrimestre_ids: list[int]
    ) -> list[Materia]:
        """Materias activas de VARIOS cuatrimestres en UNA query (árbol del dashboard).

        Reemplaza el N+1 de ``get_by_cuatrimestre(id)`` por cuatrimestre en el loop
        de ``obtener_arbol``. Mismo orden (nombre asc) que ``get_by_cuatrimestre``, de
        modo que al reagrupar por ``cuatrimestre_id`` cada cuatrimestre conserva el
        orden idéntico al del loop viejo.

        Args:
            cuatrimestre_ids: IDs de cuatrimestres.

        Returns:
            Lista de materias activas de esos cuatrimestres, ordenadas por nombre.
        """
        if not cuatrimestre_ids:
            return []
        result = await self.db.execute(
            select(Materia)
            .where(
                Materia.cuatrimestre_id.in_(cuatrimestre_ids),
                Materia.activa == True,  # noqa: E712
            )
            .order_by(Materia.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_configuradas_dashboard(self) -> list[Materia]:
        """Materias listas para el snapshot de avance (Dashboard de Gestores).

        Activas + con moodle_course_id + cuatrimestre + unidad_actual. (La existencia
        de unidades la valida el SnapshotService al generar.)
        """
        result = await self.db.execute(
            select(Materia)
            .where(
                Materia.activa == True,  # noqa: E712
                Materia.moodle_course_id.isnot(None),
                Materia.cuatrimestre_id.isnot(None),
                Materia.unidad_actual.isnot(None),
            )
            .order_by(Materia.id.asc())
        )
        return list(result.scalars().all())

    async def exists_codigo(self, codigo: str) -> bool:
        """
        Check if a codigo already exists.

        Args:
            codigo: Codigo to check.

        Returns:
            True if codigo exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Materia)
            .where(Materia.codigo == codigo.upper())
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, materia: Materia) -> Materia:
        """
        Create a new materia.

        Args:
            materia: Materia object to create.

        Returns:
            Created Materia object with ID assigned.
        """
        self.db.add(materia)
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def update(self, materia: Materia) -> Materia:
        """
        Update an existing materia.

        Args:
            materia: Materia object with updated fields.

        Returns:
            Updated Materia object.
        """
        materia.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def soft_delete(self, materia: Materia) -> Materia:
        """
        Soft delete a materia (set activa=False).

        Args:
            materia: Materia object to delete.

        Returns:
            Updated Materia object.
        """
        materia.activa = False
        materia.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def restore(self, materia: Materia) -> Materia:
        """
        Restore a soft-deleted materia (set activa=True).

        Args:
            materia: Materia object to restore.

        Returns:
            Updated Materia object.
        """
        materia.activa = True
        materia.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(materia)
        return materia

    async def get_by_coordinador(self, coordinador_id: int) -> list[Materia]:
        """
        Get all active materias assigned to a coordinator.

        Args:
            coordinador_id: ID of the coordinator user.

        Returns:
            List of active materias for the coordinator.
        """
        result = await self.db.execute(
            select(Materia)
            .join(CoordinadorMateria)
            .where(
                CoordinadorMateria.coordinador_id == coordinador_id,
                Materia.activa == True,  # noqa: E712
            )
            .order_by(Materia.nombre.asc())
        )
        return list(result.scalars().all())

    async def hard_delete_with_cascade(self, materia: Materia) -> None:
        """
        Hard delete: elimina físicamente la materia y toda su cascada.

        Dado que las rúbricas son exclusivas de una materia, se eliminan
        todas las comisiones (con sus entregas) y todas las rúbricas.

        Orden de operaciones:
        1. Por cada Comision de la materia:
           a. Por cada Entrega de esa comision:
              - Elimina archivos físicos
              - DELETE Entrega (cascade ORM: Correccion + EntregaHistorial)
           b. DELETE ComisionTutor
           c. DELETE Comision
        2. Por cada Rubrica de la materia:
           - Safety: eliminar entregas remanentes con esta rubrica
             (en flujo normal ya están eliminadas en paso 1)
           - DELETE Rubrica
        3. DELETE CoordinadorMateria
        4. DELETE Materia

        Args:
            materia: Materia object to hard-delete.

        Raises:
            Exception: Si falla alguna operación de DB o de disco.
        """
        import os

        from app.models.comision import Comision, ComisionTutor
        from app.models.entrega import Entrega
        from app.models.rubrica import Rubrica

        materia_id = materia.id

        # 1. Eliminar todas las comisiones de la materia con su cascada
        result_c = await self.db.execute(
            select(Comision).where(Comision.materia_id == materia_id)
        )
        comisiones = result_c.scalars().all()

        for comision in comisiones:
            # 1a. Eliminar entregas de esta comision
            result_e = await self.db.execute(
                select(Entrega).where(Entrega.comision_id == comision.id)
            )
            entregas = result_e.scalars().all()

            for entrega in entregas:
                # Eliminar archivo físico del disco
                if entrega.archivo_ruta and os.path.exists(entrega.archivo_ruta):
                    try:
                        os.remove(entrega.archivo_ruta)
                    except OSError:
                        pass  # Si el archivo ya no existe, continuar

                # Eliminar entrega (cascade ORM elimina Correccion y EntregaHistorial)
                await self.db.delete(entrega)

            # Flush las entregas antes de continuar con la comision
            await self.db.flush()

            # 1b. Eliminar asignaciones de tutores
            await self.db.execute(
                delete(ComisionTutor).where(ComisionTutor.comision_id == comision.id)
            )

            # 1c. Eliminar comision
            await self.db.delete(comision)

        # Flush todas las comisiones eliminadas
        await self.db.flush()

        # 2. Eliminar todas las rúbricas de la materia
        #    (Las entregas ya fueron eliminadas en paso 1 por comision_id;
        #     este select es safety-check por si quedara alguna huérfana)
        result_r = await self.db.execute(
            select(Rubrica).where(Rubrica.materia_id == materia_id)
        )
        rubricas = result_r.scalars().all()

        for rubrica in rubricas:
            # Safety: eliminar entregas remanentes con esta rubrica_id
            result_e2 = await self.db.execute(
                select(Entrega).where(Entrega.rubrica_id == rubrica.id)
            )
            entregas_remanentes = result_e2.scalars().all()

            for entrega in entregas_remanentes:
                if entrega.archivo_ruta and os.path.exists(entrega.archivo_ruta):
                    try:
                        os.remove(entrega.archivo_ruta)
                    except OSError:
                        pass
                await self.db.delete(entrega)

            await self.db.flush()

            # Eliminar la rubrica
            await self.db.delete(rubrica)

        # Flush las rubricas
        await self.db.flush()

        # 3. Eliminar asignaciones de coordinadores
        await self.db.execute(
            delete(CoordinadorMateria).where(CoordinadorMateria.materia_id == materia_id)
        )

        # 4. Eliminar la materia
        await self.db.delete(materia)
        await self.db.commit()


class CoordinadorMateriaRepository:
    """
    Repository for CoordinadorMateria model.

    Manages the N:M relationship between coordinators and materias.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def contar_por_materias(self, materia_ids: list[int]) -> dict[int, int]:
        """Nº de coordinadores por materia en UNA query agregada (GROUP BY).

        Reemplaza el N+1 de ``listar_materias`` (``get_coordinadores_for_materia``
        por materia sólo para contar). Devuelve el mismo número que
        ``len(get_coordinadores_for_materia(id))``; las materias sin coordinadores
        no aparecen en el dict (se interpretan como 0).

        Args:
            materia_ids: IDs de las materias a contar.

        Returns:
            dict {materia_id: num_coordinadores}.
        """
        if not materia_ids:
            return {}
        result = await self.db.execute(
            select(CoordinadorMateria.materia_id, func.count(CoordinadorMateria.id))
            .where(CoordinadorMateria.materia_id.in_(materia_ids))
            .group_by(CoordinadorMateria.materia_id)
        )
        return {mid: int(n) for mid, n in result.all()}

    async def get_coordinadores_for_materia(
        self,
        materia_id: int,
    ) -> list[CoordinadorMateria]:
        """
        Get all coordinator assignments for a materia.

        Args:
            materia_id: ID of the materia.

        Returns:
            List of CoordinadorMateria records.
        """
        result = await self.db.execute(
            select(CoordinadorMateria)
            .where(CoordinadorMateria.materia_id == materia_id)
            .order_by(CoordinadorMateria.asignado_en.desc())
        )
        return list(result.scalars().all())

    async def exists(self, coordinador_id: int, materia_id: int) -> bool:
        """
        Check if a coordinator is already assigned to a materia.

        Args:
            coordinador_id: ID of the coordinator.
            materia_id: ID of the materia.

        Returns:
            True if assignment exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(CoordinadorMateria)
            .where(
                CoordinadorMateria.coordinador_id == coordinador_id,
                CoordinadorMateria.materia_id == materia_id,
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def create(
        self,
        coordinador_id: int,
        materia_id: int,
    ) -> CoordinadorMateria:
        """
        Create a coordinator-materia assignment.

        Args:
            coordinador_id: ID of the coordinator.
            materia_id: ID of the materia.

        Returns:
            Created CoordinadorMateria record.
        """
        assignment = CoordinadorMateria(
            coordinador_id=coordinador_id,
            materia_id=materia_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def delete_all_for_materia(self, materia_id: int) -> int:
        """
        Delete all coordinator assignments for a materia.

        Args:
            materia_id: ID of the materia.

        Returns:
            Number of records deleted.
        """
        result = await self.db.execute(
            select(CoordinadorMateria).where(
                CoordinadorMateria.materia_id == materia_id
            )
        )
        assignments = result.scalars().all()
        count = len(assignments)

        for assignment in assignments:
            await self.db.delete(assignment)

        await self.db.commit()
        return count

    async def delete_all_for_coordinador(self, coordinador_id: int) -> int:
        """
        CRUD-013: borra todas las asignaciones de coordinación de un usuario.

        Se usa al cambiar su rol AWAY de COORDINADOR, para no dejar filas huérfanas
        (el ex-coordinador seguiría figurando como coordinador de sus materias).
        """
        result = await self.db.execute(
            delete(CoordinadorMateria).where(
                CoordinadorMateria.coordinador_id == coordinador_id
            )
        )
        await self.db.commit()
        return result.rowcount

    async def delete(self, coordinador_id: int, materia_id: int) -> bool:
        """
        Delete a specific coordinator-materia assignment.

        Args:
            coordinador_id: ID of the coordinator.
            materia_id: ID of the materia.

        Returns:
            True if deleted, False if not found.
        """
        result = await self.db.execute(
            select(CoordinadorMateria).where(
                CoordinadorMateria.coordinador_id == coordinador_id,
                CoordinadorMateria.materia_id == materia_id,
            )
        )
        assignment = result.scalar_one_or_none()

        if assignment:
            await self.db.delete(assignment)
            await self.db.commit()
            return True

        return False
