"""
Dashboard service - Business logic for dashboard statistics.

Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard designs
"""

from datetime import datetime
from sqlalchemy import case, func, select
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
from app.schemas.dashboard import (
    AdminStatsResponse,
    ComisionDetailItem,
    CoordinadorStatsResponse,
    CorrectionProgressItem,
    TutorStatsResponse,
)


class DashboardService:
    """Service for dashboard statistics."""

    @staticmethod
    async def get_admin_stats(db: AsyncSession) -> AdminStatsResponse:
        """
        Get admin dashboard statistics.

        Returns counts of active (not soft-deleted) entities:
        - Materias
        - Comisiones
        - Usuarios
        - Rubricas
        """
        # Count materias (not deleted)
        materias_count = await db.scalar(
            select(func.count(Materia.id)).where(Materia.activa == True)
        )

        # Count comisiones (not deleted)
        comisiones_count = await db.scalar(
            select(func.count(Comision.id)).where(Comision.activa == True)
        )

        # Count usuarios (not deleted)
        usuarios_count = await db.scalar(
            select(func.count(Usuario.id)).where(Usuario.activo == True)
        )

        # Count rubricas (not deleted)
        rubricas_count = await db.scalar(
            select(func.count(Rubrica.id)).where(Rubrica.activa == True)
        )

        return AdminStatsResponse(
            materias=materias_count or 0,
            comisiones=comisiones_count or 0,
            usuarios=usuarios_count or 0,
            rubricas=rubricas_count or 0,
        )

    @staticmethod
    async def get_coordinador_stats(
        db: AsyncSession, user_id: int
    ) -> CoordinadorStatsResponse:
        """
        Get coordinador dashboard statistics.

        Returns:
        - Number of comisiones in coordinador's materias
        - Number of rubricas for coordinador's materias
        - Number of pending entregas across all comisiones
        - Progress of corrections per comision
        """
        # Get materias where user is coordinador
        materia_ids_result = await db.execute(
            select(CoordinadorMateria.materia_id).where(
                CoordinadorMateria.coordinador_id == user_id
            )
        )
        materia_ids = [row[0] for row in materia_ids_result.fetchall()]

        if not materia_ids:
            return CoordinadorStatsResponse(
                comisiones=0,
                rubricas=0,
                pendientes=0,
                corrections_progress=[],
            )

        # Count comisiones in these materias
        comisiones_count = await db.scalar(
            select(func.count(Comision.id)).where(
                Comision.materia_id.in_(materia_ids), Comision.activa == True
            )
        )

        # Count rubricas for these materias
        rubricas_count = await db.scalar(
            select(func.count(Rubrica.id)).where(
                Rubrica.materia_id.in_(materia_ids), Rubrica.activa == True
            )
        )

        # Count pending entregas (SUBIDA or PENDIENTE states)
        pendientes_count = await db.scalar(
            select(func.count(Entrega.id))
            .join(Comision, Entrega.comision_id == Comision.id)
            .where(
                Comision.materia_id.in_(materia_ids),
                Entrega.estado.in_([EstadoEntregaEnum.SUBIDA, EstadoEntregaEnum.PENDIENTE]),
            )
        )

        # Get corrections progress per comision
        progress_query = (
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
            .where(Comision.materia_id.in_(materia_ids), Comision.activa == True)
            .group_by(Comision.id, Materia.nombre, Usuario.nombre)
        )

        progress_result = await db.execute(progress_query)
        progress_rows = progress_result.fetchall()

        corrections_progress = [
            CorrectionProgressItem(
                id=row.id,
                comision=f"{row.materia_nombre} - {row.nombre}",
                tutor=row.tutor_nombre,
                completed=row.completed_entregas or 0,
                total=row.total_entregas or 0,
                last_activity=row.last_activity,
            )
            for row in progress_rows
        ]

        return CoordinadorStatsResponse(
            comisiones=comisiones_count or 0,
            rubricas=rubricas_count or 0,
            pendientes=pendientes_count or 0,
            corrections_progress=corrections_progress,
        )

    @staticmethod
    async def get_tutor_stats(db: AsyncSession, user_id: int) -> TutorStatsResponse:
        """
        Get tutor dashboard statistics.

        Returns:
        - Number of comisiones assigned to tutor
        - Number of pending entregas
        - Number of corrected entregas
        - Details of each comision
        """
        # Get comisiones where user is tutor
        comision_ids_result = await db.execute(
            select(ComisionTutor.comision_id).where(ComisionTutor.tutor_id == user_id)
        )
        comision_ids = [row[0] for row in comision_ids_result.fetchall()]

        if not comision_ids:
            return TutorStatsResponse(
                comisiones=0,
                pendientes=0,
                corregidas=0,
                comisiones_details=[],
            )

        # Count comisiones
        comisiones_count = len(comision_ids)

        # Count pending entregas
        pendientes_count = await db.scalar(
            select(func.count(Entrega.id)).where(
                Entrega.comision_id.in_(comision_ids),
                Entrega.estado.in_([EstadoEntregaEnum.SUBIDA, EstadoEntregaEnum.PENDIENTE]),
            )
        )

        # Count corrected entregas
        corregidas_count = await db.scalar(
            select(func.count(Entrega.id)).where(
                Entrega.comision_id.in_(comision_ids),
                Entrega.estado == EstadoEntregaEnum.CORREGIDA,
            )
        )

        # Get details of each comision.
        # PERF-010: los pendientes por comisión se agregan en ESTA misma query con un
        # COUNT condicional (case), en vez de un SELECT COUNT extra por comisión en loop.
        # count(case(...)) ignora los NULL, así que sobre el outerjoin cuenta sólo las
        # entregas SUBIDA/PENDIENTE — resultado idéntico al COUNT filtrado del loop viejo.
        details_query = (
            select(
                Comision.id,
                Materia.nombre.label("materia_nombre"),
                Comision.nombre,
                Comision.anio,
                func.count(Entrega.id).label("total_alumnos"),
                func.count(
                    case(
                        (
                            Entrega.estado.in_(
                                [EstadoEntregaEnum.SUBIDA, EstadoEntregaEnum.PENDIENTE]
                            ),
                            Entrega.id,
                        )
                    )
                ).label("pendientes"),
            )
            .join(Materia, Comision.materia_id == Materia.id)
            .outerjoin(Entrega, Comision.id == Entrega.comision_id)
            .where(Comision.id.in_(comision_ids), Comision.activa == True)
            .group_by(Comision.id, Materia.nombre, Comision.nombre, Comision.anio)
        )

        details_result = await db.execute(details_query)
        details_rows = details_result.fetchall()

        comisiones_details = [
            ComisionDetailItem(
                id=row.id,
                nombre=row.materia_nombre,
                comision=f"{row.nombre} - {row.anio}",
                alumnos=row.total_alumnos or 0,
                pendientes=row.pendientes or 0,
            )
            for row in details_rows
        ]

        return TutorStatsResponse(
            comisiones=comisiones_count,
            pendientes=pendientes_count or 0,
            corregidas=corregidas_count or 0,
            comisiones_details=comisiones_details,
        )
