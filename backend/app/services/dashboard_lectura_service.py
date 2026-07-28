# app/services/dashboard_lectura_service.py
"""
DashboardLecturaService — lecturas del Dashboard de Gestores.

Sirve el árbol de selectores (cohorte→cuatrimestre→materia), el gráfico de torta
(conteos por estado del ÚLTIMO snapshot) y el detalle de alumnos por estado.
Ref: PLAN_DASHBOARD_GESTORES.md §7, §8 (T7).
"""

import asyncio

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import verificar_pertenencia_universidad
from app.models.avance import AvanceSnapshot
from app.models.enums import EstadoAvanceEnum
from app.repositories.avance_repository import AvanceRepository
from app.repositories.cohorte_repository import (
    CohorteRepository,
    CuatrimestreRepository,
)
from app.repositories.materia_repository import MateriaRepository
from app.services.dashboard_excel import construir_excel_avance
from app.services.examen_mapper import examen_corte
from app.services.notificacion_render import formatear_examenes, formatear_faltantes
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

    async def materias_configuradas(
        self, *, universidad_id: int | None = None
    ) -> list[MateriaConfiguradaItem]:
        """Materias listas para snapshot, con la fecha/total de su último snapshot."""
        materias = await self.materia_repo.get_configuradas_dashboard(
            universidad_id=universidad_id
        )
        # PERF-011: el último snapshot de TODAS las materias en UNA query (antes:
        # get_ultimo_snapshot por materia en loop).
        snapshots = await self.avance_repo.get_ultimos_snapshots(
            [m.id for m in materias], universidad_id=universidad_id
        )
        snap_por_materia = {s.materia_id: s for s in snapshots}
        items: list[MateriaConfiguradaItem] = []
        for m in materias:
            snap = snap_por_materia.get(m.id)
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

    async def obtener_arbol(
        self, *, universidad_id: int | None = None
    ) -> list[CohorteArbol]:
        """Árbol cohorte → cuatrimestre → materias para los selectores encadenados."""
        cohortes = await self.cohorte_repo.get_all(include_inactive=False)
        # PERF-011: las materias de TODOS los cuatrimestres del árbol en UNA query
        # (antes: get_by_cuatrimestre por cuatrimestre en loop anidado), reagrupadas
        # por cuatrimestre_id preservando el orden por nombre.
        cuatri_ids = [cuatri.id for cohorte in cohortes for cuatri in cohorte.cuatrimestres]
        materias_todas = await self.materia_repo.get_by_cuatrimestres(
            cuatri_ids, universidad_id=universidad_id
        )
        materias_por_cuatri: dict[int, list] = {}
        for m in materias_todas:
            materias_por_cuatri.setdefault(m.cuatrimestre_id, []).append(m)

        arbol: list[CohorteArbol] = []
        for cohorte in cohortes:
            cuatrimestres: list[CuatrimestreArbol] = []
            for cuatri in cohorte.cuatrimestres:
                materias = materias_por_cuatri.get(cuatri.id, [])
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

    async def _resolver_materias(
        self, cuatrimestre_id: int, materia_id: int | None, *, universidad_id: int | None = None
    ):
        if materia_id is not None:
            materia = await self.materia_repo.get_by_id(materia_id)
            if materia is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Materia no encontrada"
                )
            verificar_pertenencia_universidad(
                materia, universidad_id, detail="Materia no encontrada"
            )
            return [materia]
        return await self.materia_repo.get_by_cuatrimestre(
            cuatrimestre_id, universidad_id=universidad_id
        )

    async def _ultimos_snapshots(
        self, materias, *, universidad_id: int | None = None
    ) -> list[AvanceSnapshot]:
        # PERF-011: último snapshot de cada materia en UNA query (antes:
        # get_ultimo_snapshot por materia en loop). Las materias sin snapshot no
        # vienen en la lista, igual que el `if snap is not None` del loop viejo.
        return await self.avance_repo.get_ultimos_snapshots(
            [m.id for m in materias], universidad_id=universidad_id
        )

    async def _get_cuatrimestre_or_404(self, cuatrimestre_id: int):
        cuatrimestre = await self.cuatrimestre_repo.get_by_id(cuatrimestre_id)
        if cuatrimestre is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cuatrimestre no encontrado"
            )
        return cuatrimestre

    async def avance(
        self,
        cuatrimestre_id: int,
        materia_id: int | None = None,
        *,
        universidad_id: int | None = None,
    ) -> AvanceResponse:
        cuatrimestre = await self._get_cuatrimestre_or_404(cuatrimestre_id)
        cohorte = await self.cohorte_repo.get_by_id(cuatrimestre.cohorte_id)
        materias = await self._resolver_materias(
            cuatrimestre_id, materia_id, universidad_id=universidad_id
        )
        snapshots = await self._ultimos_snapshots(materias, universidad_id=universidad_id)

        conteos_raw = await self.avance_repo.contar_por_estado(
            [s.id for s in snapshots], universidad_id=universidad_id
        )
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
        self,
        cuatrimestre_id: int,
        materia_id: int | None = None,
        *,
        universidad_id: int | None = None,
    ) -> tuple[bytes, str]:
        """Genera el .xlsx de avance (Resumen + 4 hojas de desglose)."""
        cuatrimestre = await self._get_cuatrimestre_or_404(cuatrimestre_id)
        cohorte = await self.cohorte_repo.get_by_id(cuatrimestre.cohorte_id)
        materias = await self._resolver_materias(
            cuatrimestre_id, materia_id, universidad_id=universidad_id
        )
        snapshots = await self._ultimos_snapshots(materias, universidad_id=universidad_id)
        snapshot_ids = [s.id for s in snapshots]

        conteos = await self.avance_repo.contar_por_estado(
            snapshot_ids, universidad_id=universidad_id
        )
        alumnos_por_estado = {
            estado: await self.avance_repo.get_alumnos_por_estado(snapshot_ids, estado)
            for estado in EstadoAvanceEnum
        }

        titulo = self._titulo(cohorte, cuatrimestre, materia_id, materias)
        # Etiqueta de la materia (Unidad/Semana) si el Excel es de UNA materia; si es
        # combinado (varias materias), se usa el default "Unidad".
        etiqueta = (
            materias[0].etiqueta_unidad
            if materia_id is not None and materias
            else "Unidad"
        )
        # Línea de corte: unidad + examen más alto (solo si el Excel es de UNA materia).
        unidad_actual = None
        corte_examen = None
        if materia_id is not None and materias:
            unidad_actual = materias[0].unidad_actual
            corte_examen = examen_corte([
                {"id": e.id, "tipo": e.tipo.value, "orden": e.orden}
                for e in (materias[0].examenes or [])
            ])
        # PERF-004: render openpyxl (CPU-bound) en un thread para no bloquear el event
        # loop. `alumnos_por_estado` son AvanceAlumno ya consultados; el builder sólo lee
        # columnas (sin relaciones lazy), así que no dispara MissingGreenlet en el thread.
        contenido = await asyncio.to_thread(
            construir_excel_avance,
            titulo,
            conteos,
            alumnos_por_estado,
            etiqueta,
            unidad_actual,
            corte_examen,
        )

        codigo = cohorte.codigo if cohorte else "cohorte"
        sufijo = (
            materias[0].codigo if materia_id is not None and materias
            else f"cuatri{cuatrimestre.numero}"
        )
        filename = f"avance_{codigo}_{sufijo}.xlsx"
        return contenido, filename

    async def detalle(
        self,
        cuatrimestre_id: int,
        estado: EstadoAvanceEnum,
        materia_id: int | None = None,
        *,
        universidad_id: int | None = None,
    ) -> list[AlumnoDetalle]:
        await self._get_cuatrimestre_or_404(cuatrimestre_id)
        materias = await self._resolver_materias(
            cuatrimestre_id, materia_id, universidad_id=universidad_id
        )
        snapshots = await self._ultimos_snapshots(materias, universidad_id=universidad_id)
        alumnos = await self.avance_repo.get_alumnos_por_estado(
            [s.id for s in snapshots], estado
        )
        # Etiqueta (Unidad/Semana) por snapshot → por alumno, para "le_falta" y los labels.
        etiqueta_mat = {m.id: (m.etiqueta_unidad or "Unidad") for m in materias}
        etiqueta_snap = {s.id: etiqueta_mat.get(s.materia_id, "Unidad") for s in snapshots}
        out: list[AlumnoDetalle] = []
        for a in alumnos:
            etq = etiqueta_snap.get(a.snapshot_id, "Unidad")
            d = AlumnoDetalle.model_validate(a)
            d.etiqueta_unidad = etq
            d.le_falta = formatear_faltantes(a.actividades_faltantes, etq)
            d.examenes = formatear_examenes(a.resultados_examenes)
            out.append(d)
        return out
