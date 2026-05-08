# app/services/moodle_service.py
"""
MoodleService — integración con la API REST de Moodle.

Obtiene token vía /login/token.php y consulta mod_assign_get_submissions
para calcular pendientes por comisión.

Notas importantes sobre la API de Moodle:
- mod_assign_get_submissions necesita el assignment INSTANCE ID (tabla assign.id),
  no el cmid (course module id que aparece en la URL). Se resuelve vía
  mod_assign_get_assignments por curso.
- mod_assign_get_submissions no soporta filtro por groupid en esta versión.
  El filtrado por grupo se hace client-side usando core_enrol_get_enrolled_users.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.security import decrypt_api_key
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.pendientes import (
    ComisionPendiente,
    MateriaPendiente,
    MateriasPendientesResponse,
    UnidadPendiente,
)


class MoodleAuthError(Exception):
    pass


class MoodleConnectionError(Exception):
    pass


class MoodleService:
    _token_cache: dict[int, tuple[str, datetime]] = {}
    _TTL_MINUTES = 50

    def __init__(self, db: AsyncSession):
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        # Per-instance caches for a single get_pendientes call
        self._cmid_map: dict[int, dict[int, int]] = {}   # course_id -> {cmid: assign_id}
        self._group_members: dict[int, set[int]] = {}    # group_id -> {user_id, ...}

    async def get_token(
        self,
        user_id: int,
        moodle_host: str,
        username: str,
        password_encrypted: str,
    ) -> str:
        cached = self._token_cache.get(user_id)
        if cached:
            token, expires_at = cached
            if datetime.utcnow() < expires_at:
                return token

        password = decrypt_api_key(password_encrypted)
        url = f"{moodle_host.rstrip('/')}/login/token.php"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data={
                    "username": username,
                    "password": password,
                    "service": "moodle_mobile_app",
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout conectando a Moodle: {e}") from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red con Moodle: {e}") from e

        if "error" in data or "token" not in data:
            error_msg = data.get("error", "Error desconocido")
            if "invalidlogin" in str(data).lower() or "invalid login" in error_msg.lower():
                raise MoodleAuthError("Credenciales Moodle incorrectas")
            raise MoodleAuthError(f"Error autenticando en Moodle: {error_msg}")

        token = data["token"]
        self._token_cache[user_id] = (token, datetime.utcnow() + timedelta(minutes=self._TTL_MINUTES))
        return token

    async def _get_course_assignment_map(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
    ) -> dict[int, int]:
        """Resuelve cmid → assignment instance id para un curso.

        La API mod_assign_get_submissions necesita el instance ID (tabla assign),
        no el cmid que el usuario ve en la URL de Moodle.
        """
        if course_id in self._cmid_map:
            return self._cmid_map[course_id]

        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "mod_assign_get_assignments",
            "moodlewsrestformat": "json",
            "courseids[0]": course_id,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout resolviendo assignments: {e}") from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red resolviendo assignments: {e}") from e

        if isinstance(data, dict) and "exception" in data:
            raise MoodleConnectionError(f"Error Moodle al obtener assignments: {data.get('message', '')}")

        mapping: dict[int, int] = {}
        for course in data.get("courses", []):
            for assignment in course.get("assignments", []):
                mapping[assignment["cmid"]] = assignment["id"]

        self._cmid_map[course_id] = mapping
        return mapping

    async def _get_group_member_ids(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
        group_id: int,
    ) -> set[int]:
        """Retorna el conjunto de user_ids que pertenecen al grupo en el curso.

        mod_assign_get_submissions no acepta groupid en esta versión de Moodle,
        así que filtramos client-side usando core_enrol_get_enrolled_users.
        """
        if group_id in self._group_members:
            return self._group_members[group_id]

        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "core_enrol_get_enrolled_users",
            "moodlewsrestformat": "json",
            "courseid": course_id,
            "options[0][name]": "groupid",
            "options[0][value]": group_id,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout obteniendo miembros del grupo: {e}") from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red obteniendo miembros del grupo: {e}") from e

        if isinstance(data, dict) and "exception" in data:
            raise MoodleConnectionError(f"Error Moodle al obtener grupo: {data.get('message', '')}")

        member_ids = {u["id"] for u in data if isinstance(u, dict) and "id" in u}
        self._group_members[group_id] = member_ids
        return member_ids

    async def get_submissions_count(
        self,
        token: str,
        moodle_host: str,
        assignment_instance_id: int,
        group_member_ids: set[int],
    ) -> dict:
        """Cuenta submissions para un assignment, filtradas por grupo (client-side)."""
        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "mod_assign_get_submissions",
            "moodlewsrestformat": "json",
            "assignmentids[0]": assignment_instance_id,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout consultando submissions: {e}") from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red consultando Moodle: {e}") from e

        if isinstance(data, dict) and "exception" in data:
            if "invalidtoken" in str(data).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(f"Error de Moodle: {data.get('message', '')}")

        espera = 0
        corregidos = 0
        sin_entrega = 0

        assignments = data.get("assignments", [])
        for assignment in assignments:
            for submission in assignment.get("submissions", []):
                user_id = submission.get("userid")
                if user_id not in group_member_ids:
                    continue
                grading_status = submission.get("gradingstatus", "")
                status_val = submission.get("status", "")
                if status_val == "submitted":
                    if grading_status in ("notgraded", ""):
                        espera += 1
                    else:
                        corregidos += 1
                else:
                    sin_entrega += 1

        return {"espera": espera, "corregidos": corregidos, "sinEntrega": sin_entrega}

    async def get_pendientes(self, user_id: int) -> MateriasPendientesResponse:
        from app.models.comision import Comision, ComisionTutor
        from app.models.materia import Materia
        from app.models.rubrica import Rubrica
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        usuario = await self.usuario_repo.get_by_id(user_id)
        if not usuario or not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail="Configurá tus credenciales Moodle en tu perfil",
            )

        moodle_host = usuario.moodle_host or ""
        token = await self.get_token(
            user_id=user_id,
            moodle_host=moodle_host,
            username=usuario.moodle_username,
            password_encrypted=usuario.moodle_password_encrypted,
        )

        # Obtener comisiones del tutor con moodle_group_id configurado
        result = await self.db.execute(
            select(Comision)
            .join(ComisionTutor, ComisionTutor.comision_id == Comision.id)
            .where(
                ComisionTutor.tutor_id == user_id,
                Comision.activa == True,  # noqa: E712
                Comision.moodle_group_id.isnot(None),
            )
            .options(selectinload(Comision.materia))
        )
        comisiones = list(result.scalars().all())
        logger.info(
            "get_pendientes user_id=%s: %d comisiones activas con moodle_group_id",
            user_id, len(comisiones),
        )
        for c in comisiones:
            logger.debug(
                "  comision id=%s nombre=%r moodle_group_id=%s materia_id=%s",
                c.id, c.nombre, c.moodle_group_id, c.materia_id,
            )

        materia_ids = list({c.materia_id for c in comisiones})
        if not materia_ids:
            logger.warning(
                "get_pendientes user_id=%s: ninguna comisión activa tiene moodle_group_id configurado",
                user_id,
            )
            return MateriasPendientesResponse(materias=[])

        # Obtener rúbricas con moodle_assign_id (cmid) agrupadas por materia
        rubrica_result = await self.db.execute(
            select(Rubrica)
            .where(
                Rubrica.materia_id.in_(materia_ids),
                Rubrica.activa == True,  # noqa: E712
                Rubrica.moodle_assign_id.isnot(None),
            )
        )
        rubricas = list(rubrica_result.scalars().all())
        logger.info(
            "get_pendientes user_id=%s: %d rúbricas activas con moodle_assign_id para materia_ids=%s",
            user_id, len(rubricas), materia_ids,
        )
        for r in rubricas:
            logger.debug(
                "  rúbrica id=%s titulo=%r moodle_assign_id=%s materia_id=%s",
                r.id, r.titulo, r.moodle_assign_id, r.materia_id,
            )
        if not rubricas:
            logger.warning(
                "get_pendientes user_id=%s: ninguna rúbrica activa tiene moodle_assign_id configurado",
                user_id,
            )

        # Obtener materias para resolver course_id (necesario para cmid → assign_id y group members)
        materia_result = await self.db.execute(
            select(Materia).where(Materia.id.in_(materia_ids))
        )
        materias_by_id = {m.id: m for m in materia_result.scalars().all()}

        # Pre-resolver cmid → assignment instance id por curso
        for materia in materias_by_id.values():
            if materia.moodle_course_id:
                try:
                    await self._get_course_assignment_map(token, moodle_host, materia.moodle_course_id)
                except (MoodleConnectionError, MoodleAuthError) as e:
                    logger.warning(
                        "No se pudo obtener assignment map para course_id=%s (materia_id=%s): %s",
                        materia.moodle_course_id, materia.id, e,
                    )
            else:
                logger.warning(
                    "Materia id=%s no tiene moodle_course_id configurado — se omitirán sus rúbricas",
                    materia.id,
                )

        # Pre-resolver miembros de grupos únicos
        unique_group_comision_pairs = {
            (c.moodle_group_id, materias_by_id[c.materia_id].moodle_course_id)
            for c in comisiones
            if c.moodle_group_id and materias_by_id.get(c.materia_id) and materias_by_id[c.materia_id].moodle_course_id
        }
        for group_id, course_id in unique_group_comision_pairs:
            try:
                members = await self._get_group_member_ids(token, moodle_host, course_id, group_id)
                if not members:
                    logger.warning(
                        "El grupo moodle_group_id=%s en course_id=%s no tiene miembros — "
                        "todas sus submissions serán filtradas",
                        group_id, course_id,
                    )
                else:
                    logger.debug("Grupo group_id=%s tiene %d miembros", group_id, len(members))
            except (MoodleConnectionError, MoodleAuthError) as e:
                logger.warning(
                    "No se pudieron obtener miembros del grupo group_id=%s course_id=%s: %s",
                    group_id, course_id, e,
                )

        # Paralelizar consultas con semaphore
        semaphore = asyncio.Semaphore(10)

        async def fetch_with_semaphore(rubrica: Rubrica, comision: Comision):
            async with semaphore:
                materia = materias_by_id.get(rubrica.materia_id)
                if not materia or not materia.moodle_course_id:
                    logger.warning(
                        "Rúbrica id=%s (materia_id=%s) no tiene materia con moodle_course_id — omitida",
                        rubrica.id, rubrica.materia_id,
                    )
                    return rubrica, comision, {"espera": 0, "corregidos": 0, "sinEntrega": 0}

                # Resolver cmid → instance id
                cmid_map = self._cmid_map.get(materia.moodle_course_id, {})
                assignment_instance_id = cmid_map.get(rubrica.moodle_assign_id)
                if not assignment_instance_id:
                    logger.warning(
                        "cmid=%s no encontrado en el mapa del course_id=%s "
                        "(rúbrica id=%s, materia id=%s) — "
                        "verificá que el moodle_assign_id sea el cmid correcto y que el token tenga permisos",
                        rubrica.moodle_assign_id, materia.moodle_course_id,
                        rubrica.id, materia.id,
                    )
                    return rubrica, comision, {"espera": 0, "corregidos": 0, "sinEntrega": 0}

                # Obtener miembros del grupo
                group_members = self._group_members.get(comision.moodle_group_id, set())
                if not group_members:
                    logger.warning(
                        "Sin miembros para comision id=%s (moodle_group_id=%s) — "
                        "todas las submissions serán filtradas, resultado será 0/0/0",
                        comision.id, comision.moodle_group_id,
                    )

                counts = await self.get_submissions_count(
                    token=token,
                    moodle_host=moodle_host,
                    assignment_instance_id=assignment_instance_id,
                    group_member_ids=group_members,
                )
                logger.debug(
                    "comision id=%s rubrica id=%s → espera=%d corregidos=%d sinEntrega=%d",
                    comision.id, rubrica.id,
                    counts["espera"], counts["corregidos"], counts["sinEntrega"],
                )
                return rubrica, comision, counts

        # Construir pares rúbrica × comisión (misma materia)
        pairs = [
            (r, c)
            for r in rubricas
            for c in comisiones
            if r.materia_id == c.materia_id
        ]

        tasks = [fetch_with_semaphore(r, c) for r, c in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Agrupar por materia → rúbrica (unidad) → comisión
        materias_map: dict[int, dict] = {}
        for item in results:
            if isinstance(item, Exception):
                logger.error("Excepción en fetch_with_semaphore: %s", item, exc_info=item)
                continue
            rubrica, comision, counts = item
            mid = rubrica.materia_id
            rid = rubrica.id

            if mid not in materias_map:
                materias_map[mid] = {
                    "materia": materias_by_id[mid],
                    "unidades": {},
                }
            if rid not in materias_map[mid]["unidades"]:
                materias_map[mid]["unidades"][rid] = {
                    "rubrica": rubrica,
                    "comisiones": [],
                }
            materias_map[mid]["unidades"][rid]["comisiones"].append(
                ComisionPendiente(
                    id=comision.id,
                    nombre=comision.nombre,
                    codigo=comision.moodle_group_code or "",
                    groupId=comision.moodle_group_id,
                    espera=counts["espera"],
                    corregidos=counts["corregidos"],
                    sinEntrega=counts["sinEntrega"],
                    moodleGraderUrl=(
                        f"{moodle_host.rstrip('/')}/mod/assign/view.php"
                        f"?id={rubrica.moodle_assign_id}"
                        f"&action=grading&status=requiregrading"
                        f"&groupsearchvalue={comision.moodle_group_code or ''}"
                        f"&group={comision.moodle_group_id}"
                    ) if comision.moodle_group_id else None,
                )
            )

        materias_list = []
        for mid, mdata in materias_map.items():
            materia_obj = mdata["materia"]
            unidades_list = []
            total_espera = total_corregidos = total_sin = 0
            for rid, udata in mdata["unidades"].items():
                rubrica = udata["rubrica"]
                comisiones_list = udata["comisiones"]
                u_espera = sum(c.espera for c in comisiones_list)
                u_corregidos = sum(c.corregidos for c in comisiones_list)
                u_sin = sum(c.sinEntrega for c in comisiones_list)
                total_espera += u_espera
                total_corregidos += u_corregidos
                total_sin += u_sin
                unidades_list.append(UnidadPendiente(
                    id=rubrica.id,
                    titulo=rubrica.titulo,
                    subtitulo=f"{rubrica.tipo.value} {rubrica.numero} — {rubrica.anio}",
                    cmid=rubrica.moodle_assign_id,
                    espera=u_espera,
                    corregidos=u_corregidos,
                    sinEntrega=u_sin,
                    comisiones=comisiones_list,
                ))
            materias_list.append(MateriaPendiente(
                id=materia_obj.id,
                nombre=materia_obj.nombre,
                totalEspera=total_espera,
                totalCorregidos=total_corregidos,
                totalSinEntrega=total_sin,
                unidades=unidades_list,
            ))

        return MateriasPendientesResponse(materias=materias_list)
