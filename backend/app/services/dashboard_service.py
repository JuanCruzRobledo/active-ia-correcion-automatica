"""
Dashboard service - Business logic for dashboard statistics.

Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard designs
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dashboard_repository import DashboardRepository
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
        - Materias, Comisiones, Usuarios, Rubricas
        """
        counts = await DashboardRepository(db).get_admin_counts()
        return AdminStatsResponse(
            materias=counts["materias"],
            comisiones=counts["comisiones"],
            usuarios=counts["usuarios"],
            rubricas=counts["rubricas"],
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
        repo = DashboardRepository(db)

        materia_ids = await repo.get_materia_ids_de_coordinador(user_id)
        if not materia_ids:
            return CoordinadorStatsResponse(
                comisiones=0,
                rubricas=0,
                pendientes=0,
                corrections_progress=[],
            )

        comisiones_count = await repo.contar_comisiones_activas_en_materias(materia_ids)
        rubricas_count = await repo.contar_rubricas_activas_en_materias(materia_ids)
        pendientes_count = await repo.contar_pendientes_en_materias(materia_ids)
        progress_rows = await repo.get_progreso_por_comision_de_materias(materia_ids)

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
            comisiones=comisiones_count,
            rubricas=rubricas_count,
            pendientes=pendientes_count,
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
        repo = DashboardRepository(db)

        comision_ids = await repo.get_comision_ids_de_tutor(user_id)
        if not comision_ids:
            return TutorStatsResponse(
                comisiones=0,
                pendientes=0,
                corregidas=0,
                comisiones_details=[],
            )

        comisiones_count = len(comision_ids)
        pendientes_count = await repo.contar_pendientes_en_comisiones(comision_ids)
        corregidas_count = await repo.contar_corregidas_en_comisiones(comision_ids)
        details_rows = await repo.get_detalle_comisiones(comision_ids)

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
            pendientes=pendientes_count,
            corregidas=corregidas_count,
            comisiones_details=comisiones_details,
        )
