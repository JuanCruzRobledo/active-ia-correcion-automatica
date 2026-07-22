# app/repositories/usuario_repository.py
"""
Usuario repository for Active-IA.

Handles database queries for Usuario model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
"""

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.models import Usuario
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario_universidad import UsuarioUniversidad


class UsuarioRepository:
    """
    Repository for Usuario model.

    Provides CRUD operations and common queries for users.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_by_id(self, user_id: int) -> Usuario | None:
        """
        Get user by ID.

        Args:
            user_id: User's database ID.

        Returns:
            Usuario object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Usuario).where(Usuario.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_light(self, user_id: int) -> Usuario | None:
        """
        Get user by ID without loading relationships.

        Optimized for authentication checks where only user
        attributes are needed (no entregas, correcciones, etc.).
        """
        result = await self.db.execute(
            select(Usuario)
            .where(Usuario.id == user_id)
            .options(noload("*"))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Usuario | None:
        """
        Get user by username.

        Args:
            username: User's username.

        Returns:
            Usuario object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Usuario).where(Usuario.username == username)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        activo: bool | None = None,
        rol: RolEnum | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Usuario], int]:
        """
        Get all users with optional filters and pagination.

        Args:
            activo: Filter by active status. None = all, True = active only, False = inactive only.
            rol: Filter by role.
            search: Search term for username or nombre.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of users, total count).
        """
        # Base query
        query = select(Usuario)

        # Apply filters
        if activo is not None:
            query = query.where(Usuario.activo == activo)  # noqa: E712

        if rol is not None:
            query = query.where(Usuario.rol == rol)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Usuario.username.ilike(search_term))
                | (Usuario.nombre.ilike(search_term))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Usuario.nombre.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def get_active_by_id(self, user_id: int) -> Usuario | None:
        """
        Get active user by ID (not soft-deleted).

        Args:
            user_id: User's database ID.

        Returns:
            Usuario object if found and active, None otherwise.
        """
        result = await self.db.execute(
            select(Usuario).where(
                Usuario.id == user_id,
                Usuario.activo == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def exists_username(self, username: str) -> bool:
        """
        Check if a username already exists.

        Args:
            username: Username to check.

        Returns:
            True if username exists, False otherwise.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.username == username)
        )
        count = result.scalar() or 0
        return count > 0

    async def create(self, user: Usuario) -> Usuario:
        """
        Create a new user.

        Args:
            user: Usuario object to create.

        Returns:
            Created Usuario object with ID assigned.
        """
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: Usuario) -> Usuario:
        """
        Update an existing user.

        Args:
            user: Usuario object with updated fields.

        Returns:
            Updated Usuario object.
        """
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def save(self, user: Usuario) -> Usuario:
        """Persiste cambios ya aplicados sobre un Usuario cargado SIN tocar updated_at.

        Para estado de login (contadores de intentos, lockout, last_login) que NO
        debe contar como 'modificación' del registro. Para cambios de datos usar
        update() (que sí bumpea updated_at).
        """
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def soft_delete(self, user: Usuario) -> Usuario:
        """
        Soft delete a user (set activo=False).

        Args:
            user: Usuario object to delete.

        Returns:
            Updated Usuario object.
        """
        user.activo = False
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def restore(self, user: Usuario) -> Usuario:
        """
        Restore a soft-deleted user (set activo=True).

        Args:
            user: Usuario object to restore.

        Returns:
            Updated Usuario object.
        """
        user.activo = True
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_coordinadores(self) -> list[Usuario]:
        """
        Get all active coordinators.

        Returns:
            List of active users with COORDINADOR role.
        """
        result = await self.db.execute(
            select(Usuario)
            .where(
                Usuario.rol == RolEnum.COORDINADOR,
                Usuario.activo == True,  # noqa: E712
            )
            .order_by(Usuario.nombre.asc())
        )
        return list(result.scalars().all())

    async def get_tutores(self) -> list[Usuario]:
        """
        Get all active tutors.

        Returns:
            List of active users with TUTOR role.
        """
        result = await self.db.execute(
            select(Usuario)
            .where(
                Usuario.rol == RolEnum.TUTOR,
                Usuario.activo == True,  # noqa: E712
            )
            .order_by(Usuario.nombre.asc())
        )
        return list(result.scalars().all())

    async def update_moodle_credentials(
        self,
        user_id: int,
        username: str,
        password_encrypted: str,
        host: str,
    ) -> Usuario | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.moodle_username = username
        user.moodle_password_encrypted = password_encrypted
        user.moodle_host = host
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_membresias_activas(self, usuario_id: int) -> list[UsuarioUniversidad]:
        """
        Membresías ACTIVAS de un usuario, con la `Universidad` ya cargada.

        Fase 1 multi-tenant (multi-tenant-auth-jwt, D7): consumido por
        `AuthService` para ramificar el login (0/1/2+ universidades). Filtra
        `usuario_universidad.activo = true` Y `universidades.activa = true`.

        `Usuario.universidades` es `lazy="raise"`: se usa `select(...)` +
        `selectinload(...)` explícito acá, nunca se navega el objeto `Usuario`.

        Args:
            usuario_id: ID del usuario.

        Returns:
            Lista de `UsuarioUniversidad` activas, con `.universidad` precargada.
        """
        result = await self.db.execute(
            select(UsuarioUniversidad)
            .join(Universidad, UsuarioUniversidad.universidad_id == Universidad.id)
            .where(
                UsuarioUniversidad.usuario_id == usuario_id,
                UsuarioUniversidad.activo == True,  # noqa: E712
                Universidad.activa == True,  # noqa: E712
            )
            .options(selectinload(UsuarioUniversidad.universidad))
        )
        return list(result.scalars().all())

    async def get_membresia(
        self, usuario_id: int, universidad_id: int
    ) -> UsuarioUniversidad | None:
        """
        Membresía ACTIVA puntual de un usuario en una universidad, o `None`.

        Usado por `select-universidad`/`switch-universidad`/`get_universidad_activa`
        para validar pertenencia. Requiere `usuario_universidad.activo = true` Y
        `universidades.activa = true` (mismo criterio que `get_membresias_activas`).

        Args:
            usuario_id: ID del usuario.
            universidad_id: ID de la universidad.

        Returns:
            `UsuarioUniversidad` con `.universidad` precargada, o `None` si no
            existe el par, la membresía está inactiva o la universidad lo está.
        """
        result = await self.db.execute(
            select(UsuarioUniversidad)
            .join(Universidad, UsuarioUniversidad.universidad_id == Universidad.id)
            .where(
                UsuarioUniversidad.usuario_id == usuario_id,
                UsuarioUniversidad.universidad_id == universidad_id,
                UsuarioUniversidad.activo == True,  # noqa: E712
                Universidad.activa == True,  # noqa: E712
            )
            .options(selectinload(UsuarioUniversidad.universidad))
        )
        return result.scalar_one_or_none()

    async def hard_delete(self, user: Usuario) -> None:
        """
        Hard delete: elimina físicamente el usuario de la DB.

        Orden de operaciones para respetar FK constraints:
        1. SET NULL en Entrega.subido_por_id  (columna ahora nullable)
        2. SET NULL en Correccion.corregido_por_id  (columna ahora nullable)
        3. DELETE CoordinadorMateria del usuario
        4. DELETE ComisionTutor del usuario
        5. DELETE Actividades del usuario
        6. DELETE Usuario

        Las entregas y correcciones se conservan (SET NULL),
        ya que pertenecen al alumno/materia, no al usuario eliminado.

        Args:
            user: Usuario object to hard-delete.

        Raises:
            Exception: Si falla alguna operación de DB.
        """
        from app.models.actividad import Actividad
        from app.models.comision import ComisionTutor
        from app.models.correccion import Correccion
        from app.models.entrega import Entrega
        from app.models.materia import CoordinadorMateria

        user_id = user.id

        # 1. Desvincular entregas subidas por este usuario (SET NULL)
        await self.db.execute(
            update(Entrega)
            .where(Entrega.subido_por_id == user_id)
            .values(subido_por_id=None)
        )

        # 2. Desvincular correcciones realizadas por este usuario (SET NULL)
        await self.db.execute(
            update(Correccion)
            .where(Correccion.corregido_por_id == user_id)
            .values(corregido_por_id=None)
        )

        # 3. Eliminar asignaciones como coordinador de materias
        await self.db.execute(
            delete(CoordinadorMateria).where(CoordinadorMateria.coordinador_id == user_id)
        )

        # 4. Eliminar asignaciones como tutor de comisiones
        await self.db.execute(
            delete(ComisionTutor).where(ComisionTutor.tutor_id == user_id)
        )

        # 5. Eliminar historial de actividades del usuario
        await self.db.execute(
            delete(Actividad).where(Actividad.usuario_id == user_id)
        )

        # 6. Eliminar el usuario
        await self.db.delete(user)
        await self.db.commit()
