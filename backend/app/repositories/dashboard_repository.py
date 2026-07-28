"""
DashboardRepository — todas las queries de estadísticas del dashboard (conteos y
agregaciones). Solo acceso a datos; la composición de los DTOs de respuesta queda
en DashboardService.

Ref: ARCH-001 (Services no deben ejecutar SQLAlchemy directo). dashboard_service
era el caso más grave: el service entero eran queries crudas.
"""

from sqlalchemy import case, func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Comision,
    ComisionTutor,
    CoordinadorMateria,
    Correccion,
    Entrega,
    Materia,
    Rubrica,
    Usuario,
)
from app.models.enums import EstadoEntregaEnum
from app.models.usuario_universidad import UsuarioUniversidad

_PENDIENTES = [EstadoEntregaEnum.SUBIDA, EstadoEntregaEnum.PENDIENTE]


class DashboardRepository:
    """Queries de agregación para los dashboards (admin / coordinador / tutor)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ admin

    async def get_admin_counts(
        self, *, universidad_id: int | None = None
    ) -> dict[str, int]:
        """Conteos globales de entidades ACTIVAS (no soft-deleted).

        Fase 4 multi-tenant (D2, OQ3): None = sin filtro (bypass superadmin sin
        universidad activa) ⇒ agrega todas las universidades. `usuarios` no tiene
        `universidad_id` propio (es membresía N:M vía `UsuarioUniversidad`), así
        que se cuenta por membresía activa en la universidad, no por fila de Usuario.
        """
        materias_q = select(func.count(Materia.id)).where(Materia.activa == True)  # noqa: E712
        comisiones_q = select(func.count(Comision.id)).where(Comision.activa == True)  # noqa: E712
        rubricas_q = select(func.count(Rubrica.id)).where(Rubrica.activa == True)  # noqa: E712
        if universidad_id is not None:
            materias_q = materias_q.where(Materia.universidad_id == universidad_id)
            comisiones_q = comisiones_q.where(Comision.universidad_id == universidad_id)
            rubricas_q = rubricas_q.where(Rubrica.universidad_id == universidad_id)
            usuarios_q = (
                select(func.count(func.distinct(UsuarioUniversidad.usuario_id)))
                .join(Usuario, Usuario.id == UsuarioUniversidad.usuario_id)
                .where(
                    UsuarioUniversidad.universidad_id == universidad_id,
                    UsuarioUniversidad.activo == True,  # noqa: E712
                    Usuario.activo == True,  # noqa: E712
                )
            )
        else:
            usuarios_q = select(func.count(Usuario.id)).where(Usuario.activo == True)  # noqa: E712

        materias = await self.db.scalar(materias_q)
        comisiones = await self.db.scalar(comisiones_q)
        usuarios = await self.db.scalar(usuarios_q)
        rubricas = await self.db.scalar(rubricas_q)
        return {
            "materias": materias or 0,
            "comisiones": comisiones or 0,
            "usuarios": usuarios or 0,
            "rubricas": rubricas or 0,
        }

    # ------------------------------------------------------------ coordinador

    async def get_materia_ids_de_coordinador(self, coordinador_id: int) -> list[int]:
        """IDs de las materias que coordina el usuario."""
        result = await self.db.execute(
            select(CoordinadorMateria.materia_id).where(
                CoordinadorMateria.coordinador_id == coordinador_id
            )
        )
        return [row[0] for row in result.fetchall()]

    async def contar_comisiones_activas_en_materias(
        self, materia_ids: list[int], *, universidad_id: int | None = None
    ) -> int:
        query = select(func.count(Comision.id)).where(
            Comision.materia_id.in_(materia_ids),
            Comision.activa == True,  # noqa: E712
        )
        if universidad_id is not None:
            query = query.where(Comision.universidad_id == universidad_id)
        return await self.db.scalar(query) or 0

    async def contar_rubricas_activas_en_materias(
        self, materia_ids: list[int], *, universidad_id: int | None = None
    ) -> int:
        query = select(func.count(Rubrica.id)).where(
            Rubrica.materia_id.in_(materia_ids),
            Rubrica.activa == True,  # noqa: E712
        )
        if universidad_id is not None:
            query = query.where(Rubrica.universidad_id == universidad_id)
        return await self.db.scalar(query) or 0

    async def contar_pendientes_en_materias(
        self, materia_ids: list[int], *, universidad_id: int | None = None
    ) -> int:
        query = (
            select(func.count(Entrega.id))
            .join(Comision, Entrega.comision_id == Comision.id)
            .where(
                Comision.materia_id.in_(materia_ids),
                Entrega.estado.in_(_PENDIENTES),
            )
        )
        if universidad_id is not None:
            query = query.where(Entrega.universidad_id == universidad_id)
        return await self.db.scalar(query) or 0

    async def get_progreso_por_comision_de_materias(
        self, materia_ids: list[int], *, universidad_id: int | None = None
    ) -> list[Row]:
        """Progreso de corrección por comisión (total vs corregidas + última actividad)."""
        query = (
            select(
                Comision.id,
                Comision.nombre,
                Materia.nombre.label("materia_nombre"),
                Usuario.nombre.label("tutor_nombre"),
                func.count(Entrega.id).label("total_entregas"),
                func.count(Correccion.id).label("completed_entregas"),
                func.max(Correccion.created_at).label("last_activity"),
            )
            .join(Materia, Comision.materia_id == Materia.id)
            .join(ComisionTutor, Comision.id == ComisionTutor.comision_id)
            .join(Usuario, ComisionTutor.tutor_id == Usuario.id)
            .outerjoin(Entrega, Comision.id == Entrega.comision_id)
            .outerjoin(Correccion, Entrega.id == Correccion.entrega_id)
            .where(
                Comision.materia_id.in_(materia_ids),
                Comision.activa == True,  # noqa: E712
            )
        )
        if universidad_id is not None:
            query = query.where(Comision.universidad_id == universidad_id)
        query = query.group_by(Comision.id, Materia.nombre, Usuario.nombre)
        result = await self.db.execute(query)
        return list(result.fetchall())

    # ------------------------------------------------------------------ tutor

    async def get_comision_ids_de_tutor(self, tutor_id: int) -> list[int]:
        result = await self.db.execute(
            select(ComisionTutor.comision_id).where(ComisionTutor.tutor_id == tutor_id)
        )
        return [row[0] for row in result.fetchall()]

    async def contar_pendientes_en_comisiones(
        self, comision_ids: list[int], *, universidad_id: int | None = None
    ) -> int:
        query = select(func.count(Entrega.id)).where(
            Entrega.comision_id.in_(comision_ids),
            Entrega.estado.in_(_PENDIENTES),
        )
        if universidad_id is not None:
            query = query.where(Entrega.universidad_id == universidad_id)
        return await self.db.scalar(query) or 0

    async def contar_corregidas_en_comisiones(
        self, comision_ids: list[int], *, universidad_id: int | None = None
    ) -> int:
        query = select(func.count(Entrega.id)).where(
            Entrega.comision_id.in_(comision_ids),
            Entrega.estado == EstadoEntregaEnum.CORREGIDA,
        )
        if universidad_id is not None:
            query = query.where(Entrega.universidad_id == universidad_id)
        return await self.db.scalar(query) or 0

    async def get_detalle_comisiones(
        self, comision_ids: list[int], *, universidad_id: int | None = None
    ) -> list[Row]:
        """Detalle por comisión: total de alumnos y pendientes (COUNT condicional).

        PERF-010: los pendientes se agregan en la MISMA query con count(case(...)),
        que ignora los NULL del outerjoin — idéntico a un COUNT filtrado por comisión.
        """
        query = (
            select(
                Comision.id,
                Materia.nombre.label("materia_nombre"),
                Comision.nombre,
                Comision.anio,
                func.count(Entrega.id).label("total_alumnos"),
                func.count(
                    case(
                        (Entrega.estado.in_(_PENDIENTES), Entrega.id)
                    )
                ).label("pendientes"),
            )
            .join(Materia, Comision.materia_id == Materia.id)
            .outerjoin(Entrega, Comision.id == Entrega.comision_id)
            .where(
                Comision.id.in_(comision_ids),
                Comision.activa == True,  # noqa: E712
            )
        )
        if universidad_id is not None:
            query = query.where(Comision.universidad_id == universidad_id)
        query = query.group_by(Comision.id, Materia.nombre, Comision.nombre, Comision.anio)
        result = await self.db.execute(query)
        return list(result.fetchall())
