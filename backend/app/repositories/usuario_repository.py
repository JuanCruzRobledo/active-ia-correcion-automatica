# app/repositories/usuario_repository.py
"""
Usuario repository for Active-IA.

Handles database queries for Usuario model.
Follows Repository pattern - only database operations, no business logic.

Ref: .claude/rules/backend.md
Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
"""

from datetime import datetime
from typing import NamedTuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.models import Usuario
from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario_universidad import UsuarioUniversidad


class CredencialesMoodle(NamedTuple):
    """Terna (host, username, password_encrypted) de la membresía activa.

    Fase 3 multi-tenant (multi-tenant-moodle-services, D2): DTO chico que
    devuelve `UsuarioRepository.get_credenciales_moodle` — evita filtrar la
    entidad ORM entera (`UsuarioUniversidad`) a la capa service. Cualquier
    campo puede venir `None` (sin membresía → el método entero devuelve
    `None`; con membresía pero sin host/credenciales → el campo puntual es
    `None`, y el fail-fast lo decide el caller, no el repo).
    """

    host: str | None
    username: str | None
    password_encrypted: str | None


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
        universidad_id: int | None = None,
        activo: bool | None = None,
        rol: RolEnum | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Usuario], int]:
        """
        Get all users with optional filters and pagination.

        Fase 6 multi-tenant (multi-tenant-cleanup-rol-global, D2/D3): antes de
        esta fase este método no filtraba por universidad — un ADMIN de una
        universidad veía los usuarios de todas (agujero heredado de la Fase 4).

        Args:
            universidad_id: Acota a usuarios con membresía ACTIVA en esta
                universidad. `None` = sin filtro (modo superadmin global).
            activo: Filter by active status. None = all, True = active only, False = inactive only.
            rol: Filter by role — se resuelve contra el rol de la membresía en
                `universidad_id` (D3: "TUTOR" significa "tutor EN ESTA
                universidad"), NUNCA contra un rol global. Requiere
                `universidad_id` para tener sentido acotado; si se pasa `rol`
                sin `universidad_id`, el filtro exige una membresía ACTIVA con
                ese rol en CUALQUIER universidad.
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

        # D2: EXISTS y no JOIN — un usuario puede tener varias membresías, un
        # JOIN duplicaría filas y rompería la paginación/los conteos.
        # D3: el filtro por rol va DENTRO del mismo EXISTS de la membresía.
        if universidad_id is not None or rol is not None:
            membresia_conditions = [UsuarioUniversidad.usuario_id == Usuario.id]
            membresia_conditions.append(UsuarioUniversidad.activo == True)  # noqa: E712
            if universidad_id is not None:
                membresia_conditions.append(UsuarioUniversidad.universidad_id == universidad_id)
            if rol is not None:
                membresia_conditions.append(UsuarioUniversidad.rol == rol)
            query = query.where(
                select(UsuarioUniversidad.id).where(*membresia_conditions).exists()
            )

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

    async def create_con_membresia(
        self, user: Usuario, universidad_id: int, rol: RolEnum
    ) -> Usuario:
        """
        Crea el `Usuario` y su `UsuarioUniversidad` (membresía activa) en la
        MISMA transacción (D4, Fase 6 multi-tenant).

        Un usuario sin membresía no puede iniciar sesión (Fase 1 responde 403
        a quien no tiene universidad asignada) — crear el usuario y fallar al
        crear la membresía dejaría una cuenta fantasma. `flush()` (no commit)
        entre ambos `add()` para poder referenciar `user.id` en la membresía;
        un solo `commit()` al final: si algo falla antes de llegar ahí, la
        sesión hace rollback y NO queda ningún usuario creado.

        Args:
            user: Usuario a crear (sin persistir todavía).
            universidad_id: Universidad de la membresía.
            rol: Rol de la membresía (mismo rol que trae `user.rol`).

        Returns:
            El Usuario creado, con `.id` asignado.
        """
        self.db.add(user)
        await self.db.flush()

        membresia = UsuarioUniversidad(
            usuario_id=user.id,
            universidad_id=universidad_id,
            rol=rol,
            activo=True,
        )
        self.db.add(membresia)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_rol_membresia(
        self, usuario_id: int, universidad_id: int, rol: RolEnum
    ) -> UsuarioUniversidad | None:
        """
        Actualiza el rol de la membresía ACTIVA `(usuario, universidad)`.

        Fase 6 multi-tenant (D5, tarea 2.6): el cambio de rol afecta SÓLO la
        membresía en la universidad activa del solicitante — las membresías
        en otras universidades quedan intactas (ni siquiera se tocan).

        Returns:
            La `UsuarioUniversidad` actualizada, o `None` si no hay membresía
            activa `(usuario_id, universidad_id)` — el caller decide el 404.
        """
        membresia = await self.get_membresia(usuario_id, universidad_id)
        if membresia is None:
            return None
        membresia.rol = rol
        await self.db.commit()
        await self.db.refresh(membresia)
        return membresia

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

    # NOTA (Fase 6 multi-tenant, D1/tarea 1.5): `get_coordinadores()` se ELIMINÓ
    # acá — no tenía ningún llamador (código muerto). Verificado con grep antes
    # de borrar: 0 imports/usos fuera de este archivo.

    async def get_tutores(self, *, universidad_id: int | None = None) -> list[Usuario]:
        """
        Get all active tutors.

        Fase 6 multi-tenant (D2/D3): `universidad_id` acota a tutores con
        membresía ACTIVA con rol TUTOR en esa universidad. `None` = sin
        filtro (usado por el cron de notificaciones sin `ctx`, que resuelve
        la universidad por otra vía si corresponde).

        Args:
            universidad_id: Universidad a la que acotar. `None` = todas.

        Returns:
            List of active users with TUTOR role (en `universidad_id`, si se pasa).
        """
        query = select(Usuario).where(Usuario.activo == True)  # noqa: E712
        membresia_conditions = [
            UsuarioUniversidad.usuario_id == Usuario.id,
            UsuarioUniversidad.activo == True,  # noqa: E712
            UsuarioUniversidad.rol == RolEnum.TUTOR,
        ]
        if universidad_id is not None:
            membresia_conditions.append(UsuarioUniversidad.universidad_id == universidad_id)
        query = query.where(
            select(UsuarioUniversidad.id).where(*membresia_conditions).exists()
        ).order_by(Usuario.nombre.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # NOTA (Fase 3 multi-tenant, D4): el write-path viejo `update_moodle_credentials`
    # (escribía usuarios.moodle_* global) se ELIMINÓ acá — reemplazado por
    # `update_moodle_credentials_membresia` (abajo), que escribe en la membresía
    # (usuario, universidad activa). Los campos `usuarios.moodle_*` siguen
    # existiendo en la tabla (conviven hasta Fase 6) pero ya no se escriben.

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

    async def get_rol_en_universidad(
        self, usuario_id: int, universidad_id: int
    ) -> RolEnum | None:
        """
        Rol de la membresía ACTIVA `(usuario, universidad)`, o `None` si no
        existe (usuario sin membresía activa en esa universidad).

        Fase 6 multi-tenant (D3, hallazgo tarea 3.5): reemplaza lecturas de
        `usuario.rol` (global) que validaban "¿esta persona tiene rol X?"
        para un usuario DISTINTO del solicitante (ej. candidato a tutor/
        coordinador) — el rol correcto a validar es el de la membresía en la
        universidad de destino, no un rol global. Wrapper fino sobre
        `get_membresia` para dar un nombre claro en el call site.

        Args:
            usuario_id: ID del usuario a consultar (NO necesariamente el
                solicitante — puede ser un candidato a tutor/coordinador).
            universidad_id: Universidad en la que se evalúa el rol.

        Returns:
            El `RolEnum` de la membresía activa, o `None`.
        """
        membresia = await self.get_membresia(usuario_id, universidad_id)
        return membresia.rol if membresia is not None else None

    async def get_roles_en_universidad(
        self, usuario_ids: list[int], universidad_id: int
    ) -> dict[int, RolEnum]:
        """
        Rol de la membresía ACTIVA de cada usuario en `universidad_id` —
        versión BATCH de `get_rol_en_universidad` (una sola query con `IN`,
        para no hacer N+1 al construir `UsuarioListItem` en un listado).

        Fase 6 multi-tenant (D5, tarea 5.1): usado por `listar_usuarios`
        cuando hay universidad activa — todo `usuario_id` en la lista YA fue
        filtrado por `get_all` con membresía activa en esa universidad, así
        que en la práctica el dict cubre todos los ids pedidos.

        Returns:
            `{usuario_id: rol}` — usuarios sin membresía activa en esa
            universidad simplemente no aparecen en el dict.
        """
        if not usuario_ids:
            return {}
        result = await self.db.execute(
            select(UsuarioUniversidad.usuario_id, UsuarioUniversidad.rol).where(
                UsuarioUniversidad.usuario_id.in_(usuario_ids),
                UsuarioUniversidad.universidad_id == universidad_id,
                UsuarioUniversidad.activo == True,  # noqa: E712
            )
        )
        return {row.usuario_id: row.rol for row in result.all()}

    async def get_roles_mas_antiguos(self, usuario_ids: list[int]) -> dict[int, RolEnum]:
        """
        Versión BATCH de `get_rol_mas_antiguo` — una sola query con `IN`,
        para listados en modo superadmin global (sin `universidad_id` al que
        acotar). Mismo criterio "mejor esfuerzo" documentado ahí (D6).

        Returns:
            `{usuario_id: rol}` de la membresía activa más antigua de cada
            usuario. Usuarios sin ninguna membresía activa no aparecen.
        """
        if not usuario_ids:
            return {}
        result = await self.db.execute(
            select(UsuarioUniversidad.usuario_id, UsuarioUniversidad.rol)
            .where(
                UsuarioUniversidad.usuario_id.in_(usuario_ids),
                UsuarioUniversidad.activo == True,  # noqa: E712
            )
            .order_by(UsuarioUniversidad.usuario_id.asc(), UsuarioUniversidad.id.asc())
        )
        roles: dict[int, RolEnum] = {}
        for row in result.all():
            roles.setdefault(row.usuario_id, row.rol)
        return roles

    async def get_rol_mas_antiguo(self, usuario_id: int) -> RolEnum | None:
        """
        Rol de la membresía ACTIVA más antigua (menor `id`, sin `created_at`
        en `UsuarioUniversidad`) de un usuario — o `None` si no tiene ninguna.

        Fase 6 multi-tenant (D6, hallazgo tarea 3.5): usado donde hace falta
        mostrar "el" rol de una persona sin un contexto de universidad
        puntual (ej. el audit log de `Actividad`, que no tiene
        `universidad_id`). Es la MISMA convención que usa el `downgrade` de
        la migración de esta fase para repoblar `usuarios.rol` — mejor
        esfuerzo, no una fuente de verdad (una persona con roles distintos
        por universidad no tiene un "rol único" real).

        Returns:
            El `RolEnum` de la membresía activa más antigua, o `None`.
        """
        result = await self.db.execute(
            select(UsuarioUniversidad.rol)
            .where(
                UsuarioUniversidad.usuario_id == usuario_id,
                UsuarioUniversidad.activo == True,  # noqa: E712
            )
            .order_by(UsuarioUniversidad.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_credenciales_moodle(
        self, usuario_id: int, universidad_id: int
    ) -> CredencialesMoodle | None:
        """
        Resolver ÚNICO de credenciales Moodle (Fase 3 multi-tenant, D2).

        Terna `(moodle_host, moodle_username, moodle_password_encrypted)` de
        la membresía ACTIVA `(usuario, universidad)` + el host de esa
        `Universidad` — NUNCA de `usuarios.moodle_*` (campo viejo). Reusa
        `get_membresia` (ya precarga `.universidad`, selectinload).

        Devuelve `None` si no hay membresía activa (mismo criterio que
        `get_membresia`); si hay membresía, los campos individuales pueden
        ser `None` (host/credenciales sin cargar) — el fail-fast 424/D1 lo
        decide el service, no el repo.
        """
        membresia = await self.get_membresia(usuario_id, universidad_id)
        if membresia is None:
            return None
        return CredencialesMoodle(
            host=membresia.universidad.moodle_host,
            username=membresia.moodle_username,
            password_encrypted=membresia.moodle_password_encrypted,
        )

    async def update_moodle_credentials_membresia(
        self,
        usuario_id: int,
        universidad_id: int,
        username: str,
        password_encrypted: str,
    ) -> UsuarioUniversidad | None:
        """
        Escribe las credenciales Moodle en la membresía ACTIVA (usuario, universidad).

        Fase 3 multi-tenant (D4, rediseño del perfil). `moodle_host` NO se
        escribe acá: es propiedad de la `Universidad`, read-only desde el
        perfil. Devuelve `None` si no existe la membresía activa.
        """
        membresia = await self.get_membresia(usuario_id, universidad_id)
        if membresia is None:
            return None
        membresia.moodle_username = username
        membresia.moodle_password_encrypted = password_encrypted
        await self.db.commit()
        await self.db.refresh(membresia)
        return membresia

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
