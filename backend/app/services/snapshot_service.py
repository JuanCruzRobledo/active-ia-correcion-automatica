# app/services/snapshot_service.py
"""
SnapshotService — genera el snapshot de avance de una materia (Dashboard de Gestores).

Trae participantes + contenidos (WS) + notas y completion (2 descargas MASIVAS por
sesión web), calcula el estado de cada alumno EN MEMORIA (avance_mapper) y persiste un
AvanceSnapshot fechado con N AvanceAlumno.

Refactor §R3 (2026-06-08): se reemplazó el loop per-alumno (1+2N requests = volteó
Moodle) por un número CONSTANTE de requests, independiente de N alumnos. Ver
PLAN_REFACTOR_MOODLE_BULK.md.
"""

import logging
from typing import Callable

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.avance import AvanceAlumno, AvanceSnapshot
from app.models.enums import OrigenSnapshotEnum, TipoActividadEnum
from app.repositories.avance_repository import AvanceRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.actividad_service import ActividadService
from app.services.avance_mapper import calcular_avance_alumno
from app.services.examen_mapper import calcular_resultados_examenes
from app.services.moodle_bulk_parser import (
    construir_indice_nombre_cmid,
    parsear_csv_finalizacion,
    parsear_export_calificador,
)
from app.services.gestion_parser import (
    SIN_COMISION,
    SIN_REGIONAL,
    resolver_grupos_alumno,
)
from app.services.moodle_service import MoodleService

logger = logging.getLogger(__name__)


class SnapshotService:
    """Genera y persiste snapshots de avance por materia."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.materia_repo = MateriaRepository(db)
        self.avance_repo = AvanceRepository(db)
        self.usuario_repo = UsuarioRepository(db)
        self.moodle = MoodleService(db)

    async def token_de_usuario(self, usuario) -> tuple[str, str]:
        """(token, host) de Moodle de un usuario. Lanza ValueError si sin credenciales."""
        if not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise ValueError("El usuario no tiene credenciales de Moodle configuradas")
        host = usuario.moodle_host or ""
        token = await self.moodle.get_token(
            user_id=usuario.id,
            moodle_host=host,
            username=usuario.moodle_username,
            password_encrypted=usuario.moodle_password_encrypted,
        )
        return token, host

    async def generar_todas_para_usuario(
        self, usuario_id: int, *, origen: OrigenSnapshotEnum = OrigenSnapshotEnum.CRON
    ) -> list[AvanceSnapshot]:
        """Genera snapshots de TODAS las materias configuradas, con las credenciales
        de un usuario (lo usa el cron). Continúa ante errores por materia."""
        usuario = await self.usuario_repo.get_by_id(usuario_id)
        if usuario is None:
            raise ValueError(f"Usuario {usuario_id} no encontrado")
        _, host = await self.token_de_usuario(usuario)

        materias = await self.materia_repo.get_configuradas_dashboard()
        resultados: list[AvanceSnapshot] = []
        # UNA sola sesión web para TODAS las materias (no re-loguear por materia).
        sesion = self.moodle.crear_cliente_sesion()
        try:
            await self.moodle.login_sesion(
                sesion, host, usuario.moodle_username, usuario.moodle_password_encrypted
            )
            for materia in materias:
                try:
                    snap = await self.generar(
                        materia.id, usuario=usuario, origen=origen, sesion=sesion
                    )
                    resultados.append(snap)
                except Exception:  # noqa: BLE001 — un fallo por materia no frena las demás
                    logger.exception("Snapshot falló para materia %s", materia.id)
        finally:
            await sesion.aclose()
        logger.info(
            "Snapshots generados: %s/%s materias (origen=%s)",
            len(resultados), len(materias), origen,
        )
        return resultados

    @staticmethod
    def _es_student(usuario: dict) -> bool:
        return any(
            r.get("shortname") == "student" for r in (usuario.get("roles") or [])
        )

    async def generar(
        self,
        materia_id: int,
        *,
        usuario,
        origen: OrigenSnapshotEnum = OrigenSnapshotEnum.CRON,
        on_progress: Callable[[int, int], None] | None = None,
        sesion: "httpx.AsyncClient | None" = None,
    ) -> AvanceSnapshot:
        """Genera y persiste el snapshot de avance de una materia (carga MASIVA, §R3).

        Le pega a Moodle un número CONSTANTE de veces (NO 1+2N): padrón + contenidos (WS)
        + export del calificador + CSV de finalización (descargas por sesión web). Luego
        calcula el avance de cada alumno EN MEMORIA (avance_mapper, sin tocar Moodle).

        Requiere que la materia esté configurada (moodle_course_id + unidad_actual + ≥1
        Unidad) y que `usuario` tenga credenciales de Moodle. Si se pasa `sesion` (cliente
        ya logueado) se reusa; si no, abre y cierra una propia.
        """
        materia = await self.materia_repo.get_by_id(materia_id)
        if materia is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Materia no encontrada"
            )
        if not materia.moodle_course_id or materia.unidad_actual is None or not materia.unidades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La materia no está configurada para el dashboard: requiere curso de "
                    "Moodle, unidad actual y al menos una unidad mapeada"
                ),
            )

        course_id = materia.moodle_course_id
        # Config de las unidades: cada una con sus N componentes dinámicos (§9.bis F).
        # La fuente viaja como string para que avance_mapper sea puro.
        unidades_config = [
            {
                "numero": u.numero,
                "componentes": [
                    {
                        "tipo": c.tipo.value,
                        "cmid": c.moodle_cmid,
                        "fuente": c.fuente.value,
                    }
                    for c in u.componentes
                ],
            }
            for u in materia.unidades
        ]
        # Config de exámenes (parciales/recuperatorios/etc.) para el seguimiento sumativo.
        examenes_config = [
            {
                "id": e.id,
                "tipo": e.tipo.value,
                "moodle_cmid": e.moodle_cmid,
                "modo_aprobacion": e.modo_aprobacion.value,
                "nota_minima": e.nota_minima,
                "recupera_examen_id": e.recupera_examen_id,
                "orden": e.orden,
            }
            for e in materia.examenes
        ]

        token, host = await self.token_de_usuario(usuario)

        # ── 1 login + 2 WS livianos + 2 descargas masivas (constante en N alumnos) ──
        propia = sesion is None
        if propia:
            sesion = self.moodle.crear_cliente_sesion()
        try:
            if propia:
                await self.moodle.login_sesion(
                    sesion, host, usuario.moodle_username, usuario.moodle_password_encrypted
                )
            enrolled = await self.moodle.get_enrolled_users_full(
                token, host, course_id, client=sesion
            )
            students = [u for u in enrolled if isinstance(u, dict) and self._es_student(u)]
            secciones = await self.moodle.get_course_contents(
                token, host, course_id, client=sesion
            )
            nombre_a_cmid = construir_indice_nombre_cmid(secciones)
            email_a_uid = {
                (u.get("email") or "").strip().lower(): u.get("id")
                for u in students
                if u.get("email")
            }
            # Notas (calificador) y completion (reporte de finalización), 1 descarga c/u.
            notas_por_uid = parsear_export_calificador(
                await self.moodle.descargar_export_calificador(sesion, host, course_id),
                nombre_a_cmid,
                email_a_uid,
            )
            completion_por_uid = parsear_csv_finalizacion(
                await self.moodle.descargar_reporte_finalizacion_csv(sesion, host, course_id),
                nombre_a_cmid,
                email_a_uid,
            )
        finally:
            if propia:
                await sesion.aclose()

        # ── Cálculo EN MEMORIA por alumno (cero requests a Moodle en el loop) ──
        alumnos: list[AvanceAlumno] = []
        total = len(students)
        for i, u in enumerate(students, 1):
            uid = u.get("id")
            calc = calcular_avance_alumno(
                completion_por_uid.get(uid, []),
                notas_por_uid.get(uid, {}),
                unidades_config,
                unidad_actual=materia.unidad_actual,
            )
            # Resultados de exámenes (mismas notas en memoria; rescate ya aplicado).
            examenes = (
                calcular_resultados_examenes(notas_por_uid.get(uid, {}), examenes_config)
                if examenes_config
                else None
            )
            grupos = [g.get("name") for g in (u.get("groups") or []) if g.get("name")]
            regional, comision = resolver_grupos_alumno(grupos)
            alumnos.append(
                AvanceAlumno(
                    moodle_user_id=uid,
                    nombre=u.get("firstname"),
                    apellido=u.get("lastname"),
                    email=u.get("email"),
                    comision=None if comision == SIN_COMISION else comision,
                    regional=None if regional == SIN_REGIONAL else regional,
                    unidad_alcanzada=calc["unidad_alcanzada"],
                    actividad_actual_nombre=calc["actividad_actual_nombre"],
                    actividad_actual_unidad=calc["actividad_actual_unidad"],
                    actividad_actual_desaprobada=calc["actividad_actual_desaprobada"],
                    estado=calc["estado"],
                    actividades_faltantes=calc["actividades_faltantes"],
                    resultados_examenes={"examenes": examenes} if examenes else None,
                )
            )
            if on_progress is not None:
                on_progress(i, total)

        snapshot = AvanceSnapshot(
            materia_id=materia_id,
            unidad_actual=materia.unidad_actual,
            origen=origen,
            total_alumnos=len(alumnos),
        )
        snapshot.alumnos = alumnos
        logger.info(
            "Snapshot materia=%s origen=%s alumnos=%s", materia_id, origen, len(alumnos)
        )
        creado = await self.avance_repo.crear(snapshot)
        # Auditoría: solo los snapshots MANUALES (el cron no registra para no hacer ruido).
        if origen == OrigenSnapshotEnum.MANUAL:
            await ActividadService(self.db).registrar_actividad(
                tipo=TipoActividadEnum.SNAPSHOT_GENERADO,
                descripcion=f"Snapshot de '{materia.nombre}' generado ({len(alumnos)} alumnos)",
                entidad_id=creado.id,
                entidad_nombre=materia.nombre,
                usuario_id=getattr(usuario, "id", None),
            )
        return creado
