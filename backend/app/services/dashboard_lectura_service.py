# app/services/dashboard_lectura_service.py
"""
DashboardLecturaService — lecturas del Dashboard de Gestores.

Sirve el árbol de selectores (cohorte→cuatrimestre→materia), el gráfico de torta
(conteos por estado del ÚLTIMO snapshot) y el detalle de alumnos por estado.
Ref: PLAN_DASHBOARD_GESTORES.md §7, §8 (T7).
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.avance import AvanceSnapshot
from app.models.enums import EstadoAvanceEnum
from app.repositories.avance_repository import AvanceRepository
from app.repositories.cohorte_repository import (
    CohorteRepository,
    CuatrimestreRepository,
)
from app.repositories.materia_repository import MateriaRepository
from app.services.dashboard_excel import construir_excel_avance
from app.schemas.dashboard_gestores import (
    AlumnoDetalle,
    AvanceResponse,
    CohorteArbol,
    ConteoEstados,
    CuatrimestreArbol,
    MateriaArbol,
    MateriaConfiguradaItem,
)


class DashboardLecturaService:
    """Lecturas del dashboard (selectores, gráfico, detalle)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cohorte_repo = CohorteRepository(db)
        self.cuatrimestre_repo = CuatrimestreRepository(db)
        self.materia_repo = MateriaRepository(db)
        self.avance_repo = AvanceRepository(db)

    async def materias_configuradas(self) -> list[MateriaConfiguradaItem]:
        """Materias listas para snapshot, con la fecha/total de su último snapshot."""
        materias = await self.materia_repo.get_configuradas_dashboard()
        items: list[MateriaConfiguradaItem] = []
        for m in materias:
            snap = await self.avance_repo.get_ultimo_snapshot(m.id)
            items.append(
                MateriaConfiguradaItem(
                    materia_id=m.id,
                    codigo=m.codigo,
                    nombre=m.nombre,
                    ultimo_snapshot=snap.generado_en if snap else None,
                    total_alumnos=snap.total_alumnos if snap else None,
                )
            )
        return items

    async def obtener_arbol(self) -> list[CohorteArbol]:
        """Árbol cohorte → cuatrimestre → materias para los selectores encadenados."""
        cohortes = await self.cohorte_repo.get_all(include_inactive=False)
        arbol: list[CohorteArbol] = []
        for cohorte in cohortes:
            cuatrimestres: list[CuatrimestreArbol] = []
            for cuatri in cohorte.cuatrimestres:
                materias = await self.materia_repo.get_by_cuatrimestre(cuatri.id)
                cuatrimestres.append(
                    CuatrimestreArbol(
                        id=cuatri.id,
                        numero=cuatri.numero,
                        nombre=cuatri.nombre,
                        materias=[MateriaArbol.model_validate(m) for m in materias],
                    )
                )
            arbol.append(
                CohorteArbol(
                    id=cohorte.id,
                    codigo=cohorte.codigo,
                    nombre=cohorte.nombre,
                    cuatrimestres=cuatrimestres,
                )
            )
        return arbol

    async def _resolver_materias(self, cuatrimestre_id: int, materia_id: int | None):
        if materia_id is not None:
            materia = await self.materia_repo.get_by_id(materia_id)
            if materia is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Materia no encontrada"
                )
            return [materia]
        return await self.materia_repo.get_by_cuatrimestre(cuatrimestre_id)

    async def _ultimos_snapshots(self, materias) -> list[AvanceSnapshot]:
        snapshots: list[AvanceSnapshot] = []
        for materia in materias:
            snap = await self.avance_repo.get_ultimo_snapshot(materia.id)
            if snap is not None:
                snapshots.append(snap)
        return snapshots

    async def _get_cuatrimestre_or_404(self, cuatrimestre_id: int):
        cuatrimestre = await self.cuatrimestre_repo.get_by_id(cuatrimestre_id)
        if cuatrimestre is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cuatrimestre no encontrado"
            )
        return cuatrimestre

    async def avance(
        self, cuatrimestre_id: int, materia_id: int | None = None
    ) -> AvanceResponse:
        cuatrimestre = await self._get_cuatrimestre_or_404(cuatrimestre_id)
        cohorte = await self.cohorte_repo.get_by_id(cuatrimestre.cohorte_id)
        materias = await self._resolver_materias(cuatrimestre_id, materia_id)
        snapshots = await self._ultimos_snapshots(materias)

        conteos_raw = await self.avance_repo.contar_por_estado([s.id for s in snapshots])
        conteos = ConteoEstados(
            al_dia=conteos_raw.get(EstadoAvanceEnum.AL_DIA, 0),
            riesgo_medio=conteos_raw.get(EstadoAvanceEnum.RIESGO_MEDIO, 0),
            riesgo_alto=conteos_raw.get(EstadoAvanceEnum.RIESGO_ALTO, 0),
            sin_actividad=conteos_raw.get(EstadoAvanceEnum.SIN_ACTIVIDAD, 0),
        )
        total = (
            conteos.al_dia + conteos.riesgo_medio + conteos.riesgo_alto + conteos.sin_actividad
        )
        generado_en = max((s.generado_en for s in snapshots), default=None)

        titulo = self._titulo(cohorte, cuatrimestre, materia_id, materias)

        return AvanceResponse(
            titulo=titulo, total=total, generado_en=generado_en, conteos=conteos
        )

    @staticmethod
    def _titulo(cohorte, cuatrimestre, materia_id, materias) -> str:
        codigo = cohorte.codigo if cohorte else "?"
        if materia_id is not None and materias:
            return f"{codigo} · {materias[0].nombre}"
        return f"Cohorte {codigo} · Cuatrimestre {cuatrimestre.numero}"

    async def avance_excel(
        self, cuatrimestre_id: int, materia_id: int | None = None
    ) -> tuple[bytes, str]:
        """Genera el .xlsx de avance (Resumen + 4 hojas de desglose)."""
        cuatrimestre = await self._get_cuatrimestre_or_404(cuatrimestre_id)
        cohorte = await self.cohorte_repo.get_by_id(cuatrimestre.cohorte_id)
        materias = await self._resolver_materias(cuatrimestre_id, materia_id)
        snapshots = await self._ultimos_snapshots(materias)
        snapshot_ids = [s.id for s in snapshots]

        conteos = await self.avance_repo.contar_por_estado(snapshot_ids)
        alumnos_por_estado = {
            estado: await self.avance_repo.get_alumnos_por_estado(snapshot_ids, estado)
            for estado in EstadoAvanceEnum
        }

        titulo = self._titulo(cohorte, cuatrimestre, materia_id, materias)
        contenido = construir_excel_avance(titulo, conteos, alumnos_por_estado)

        codigo = cohorte.codigo if cohorte else "cohorte"
        sufijo = (
            materias[0].codigo if materia_id is not None and materias
            else f"cuatri{cuatrimestre.numero}"
        )
        filename = f"avance_{codigo}_{sufijo}.xlsx"
        return contenido, filename

    async def detalle(
        self, cuatrimestre_id: int, estado: EstadoAvanceEnum, materia_id: int | None = None
    ) -> list[AlumnoDetalle]:
        await self._get_cuatrimestre_or_404(cuatrimestre_id)
        materias = await self._resolver_materias(cuatrimestre_id, materia_id)
        snapshots = await self._ultimos_snapshots(materias)
        alumnos = await self.avance_repo.get_alumnos_por_estado(
            [s.id for s in snapshots], estado
        )
        return [AlumnoDetalle.model_validate(a) for a in alumnos]
