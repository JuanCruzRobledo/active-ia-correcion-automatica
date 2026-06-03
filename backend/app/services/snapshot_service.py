# app/services/snapshot_service.py
"""
SnapshotService — genera el snapshot de avance de una materia (Dashboard de Gestores).

Trae participantes + contenidos + completion desde Moodle, calcula el estado de
cada alumno (avance_mapper) y persiste un AvanceSnapshot fechado con N AvanceAlumno.

Las llamadas a Moodle van SERIALIZADAS (1 completion por alumno, ~2s) para no
saturar Moodle — lección de Gestión. Ver PLAN_DASHBOARD_GESTORES.md §7 (T5).
"""

import asyncio
import logging
from typing import Callable

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.avance import AvanceAlumno, AvanceSnapshot
from app.models.enums import OrigenSnapshotEnum
from app.repositories.avance_repository import AvanceRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.avance_mapper import calcular_avance_alumno
from app.services.gestion_parser import SIN_COMISION, resolver_grupos_alumno
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
        token, host = await self.token_de_usuario(usuario)

        materias = await self.materia_repo.get_configuradas_dashboard()
        resultados: list[AvanceSnapshot] = []
        for materia in materias:
            try:
                snap = await self.generar(
                    materia.id, token=token, moodle_host=host, origen=origen
                )
                resultados.append(snap)
            except Exception:  # noqa: BLE001 — un fallo por materia no debe frenar las demás
                logger.exception("Snapshot falló para materia %s", materia.id)
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
        token: str,
        moodle_host: str,
        origen: OrigenSnapshotEnum = OrigenSnapshotEnum.CRON,
        on_progress: Callable[[int, int], None] | None = None,
        concurrencia: int = 4,
    ) -> AvanceSnapshot:
        """Genera y persiste el snapshot de avance de una materia.

        Requiere que la materia esté configurada: moodle_course_id + unidad_actual
        + al menos una Unidad. El token/host de Moodle los provee el caller (botón
        manual: usuario actual; cron: usuario de servicio — T6).
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
        cabeceras_section_ids = [
            (u.numero, u.moodle_section_id) for u in materia.unidades
        ]

        alumnos: list[AvanceAlumno] = []
        # UN solo cliente HTTP reusado (keep-alive) para TODAS las llamadas a Moodle de
        # esta materia. Con cientos de alumnos, abrir una conexión TLS nueva por llamada
        # hace que Moodle/firewall throttlee las conexiones nuevas → ConnectTimeout.
        limits = httpx.Limits(
            max_connections=10, max_keepalive_connections=10, keepalive_expiry=30.0
        )
        async with httpx.AsyncClient(timeout=60.0, limits=limits) as client:
            # 1 sola llamada de contenidos (cacheada) para toda la materia.
            secciones = await self.moodle.get_course_contents(
                token, moodle_host, course_id, client=client
            )
            enrolled = await self.moodle.get_enrolled_users_full(
                token, moodle_host, course_id, client=client
            )
            students = [
                u for u in enrolled if isinstance(u, dict) and self._es_student(u)
            ]

            total = len(students)
            procesados = 0
            # Paralelismo MODERADO: hasta `concurrencia` alumnos a la vez, acotado por el
            # client compartido (max_connections=10). El semáforo evita saturar Moodle.
            sem = asyncio.Semaphore(max(1, concurrencia))

            async def _procesar(u: dict) -> AvanceAlumno:
                nonlocal procesados
                uid = u.get("id")
                async with sem:
                    statuses = await self.moodle.get_activities_completion(
                        token, moodle_host, course_id, uid, client=client
                    )
                calc = calcular_avance_alumno(
                    statuses,
                    secciones,
                    cabeceras_section_ids,
                    unidad_actual=materia.unidad_actual,
                    tope_section_id=materia.moodle_section_fin_id,
                )
                grupos = [g.get("name") for g in (u.get("groups") or []) if g.get("name")]
                _, comision = resolver_grupos_alumno(grupos)
                procesados += 1
                if on_progress is not None:
                    on_progress(procesados, total)
                return AvanceAlumno(
                    moodle_user_id=uid,
                    nombre=u.get("firstname"),
                    apellido=u.get("lastname"),
                    email=u.get("email"),
                    comision=None if comision == SIN_COMISION else comision,
                    unidad_alcanzada=calc["unidad_alcanzada"],
                    actividad_actual_nombre=calc["actividad_actual_nombre"],
                    actividad_actual_unidad=calc["actividad_actual_unidad"],
                    actividad_actual_desaprobada=calc["actividad_actual_desaprobada"],
                    estado=calc["estado"],
                )

            resultados = await asyncio.gather(
                *(_procesar(u) for u in students), return_exceptions=True
            )
            for r in resultados:
                if isinstance(r, AvanceAlumno):
                    alumnos.append(r)
                elif isinstance(r, Exception):
                    logger.warning("Alumno falló en snapshot materia %s: %s", materia_id, r)

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
        return await self.avance_repo.crear(snapshot)
