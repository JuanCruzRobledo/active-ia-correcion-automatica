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
from dataclasses import dataclass, field
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


@dataclass
class MoodleFile:
    """Archivo entregado por un alumno en Moodle (de assignsubmission_file)."""

    filename: str
    fileurl: str
    filesize: int = 0
    mimetype: str | None = None


@dataclass
class MoodleSubmission:
    """Submission de un alumno con sus archivos descargables.

    `timemodified` permite detectar re-entregas comparando contra la fecha
    de la corrección existente en Active-IA.
    """

    userid: int
    status: str
    gradingstatus: str
    timemodified: int
    attemptnumber: int
    files: list[MoodleFile] = field(default_factory=list)


@dataclass
class AssignmentGradeConfig:
    """Configuración de calificación de un assignment de Moodle.

    Derivada del campo `grade` de mod_assign_get_assignments:
      - grade > 0  → numérica (grade_max = grade)
      - grade < 0  → escala cualitativa (scale_id = abs(grade))
      - grade == 0 → sin calificación
    """

    instance_id: int
    tipo: str  # "numerica" | "escala" | "sin_calificacion"
    grade_max: float | None = None
    scale_id: int | None = None


class MoodleService:
    _token_cache: dict[int, tuple[str, datetime]] = {}
    _TTL_MINUTES = 50

    def __init__(self, db: AsyncSession):
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        # Per-instance caches for a single get_pendientes call
        self._cmid_map: dict[int, dict[int, int]] = {}   # course_id -> {cmid: assign_id}
        self._group_members: dict[int, set[int]] = {}    # group_id -> {user_id, ...}
        self._group_member_names: dict[int, dict[int, str]] = {}  # group_id -> {user_id: fullname}
        # Cache de fetches pesados por assignment instance (evita refetch cuando una
        # rúbrica tiene varias comisiones: las submissions del assignment son las mismas).
        self._submissions_cache: dict[int, dict] = {}    # instance_id -> submissions data
        self._grades_cache: dict[int, dict[int, int]] = {}  # instance_id -> {userid: timemodified}
        # Detalle del grade más reciente por user (timemodified + valor crudo de Moodle).
        self._grades_full_cache: dict[int, dict[int, dict]] = {}  # instance_id -> {userid: {timemodified, grade}}
        # Participantes completos por (course_id, only_active) — evita refetch en la misma request.
        self._enrolled_cache: dict[tuple[int, bool], list] = {}
        # Contenidos (secciones + módulos) por course_id — el snapshot lo usa 1 vez para N alumnos.
        self._contents_cache: dict[int, list] = {}

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

    async def _fetch_assignments(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
    ) -> dict:
        """GET crudo de mod_assign_get_assignments para un curso (con manejo de errores)."""
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
        return data

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

        data = await self._fetch_assignments(token, moodle_host, course_id)

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

        # Filtrar solo alumnos — excluye docentes, tutores y no-editores.
        # La API devuelve roles como lista en u["roles"][N]["shortname"].
        # El rol de alumno en Moodle estándar es "student" (roleid 5).
        STUDENT_ROLES = {"student"}
        member_ids: set[int] = set()
        for u in data:
            if not isinstance(u, dict) or "id" not in u:
                continue
            roles = u.get("roles", [])
            if any(r.get("shortname") in STUDENT_ROLES for r in roles):
                member_ids.add(u["id"])

        logger.debug(
            "Grupo group_id=%s course_id=%s: %d alumnos (de %d usuarios totales)",
            group_id, course_id, len(member_ids), len(data) if isinstance(data, list) else "?",
        )
        self._group_members[group_id] = member_ids
        return member_ids

    async def get_enrolled_users_full(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
        *,
        only_active: bool = False,
        client: "httpx.AsyncClient | None" = None,
    ) -> list[dict]:
        """Trae los matriculados de un curso con todos los campos que usa Gestión.

        core_enrol_get_enrolled_users devuelve por usuario: id, firstname, lastname,
        fullname, email, roles[] (con shortname), groups[] (con name), lastcourseaccess,
        lastaccess (confirmado en T0). `only_active=True` agrega onlyactive=1 (solo
        matriculaciones activas). Cacheado por (course_id, only_active).
        """
        cache_key = (course_id, only_active)
        if cache_key in self._enrolled_cache:
            return self._enrolled_cache[cache_key]

        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "core_enrol_get_enrolled_users",
            "moodlewsrestformat": "json",
            "courseid": course_id,
        }
        if only_active:
            params["options[0][name]"] = "onlyactive"
            params["options[0][value]"] = 1

        # Timeout amplio: cursos grandes pueden tardar >30s (visto en T0).
        data = await self._ws_get_json(
            url, params, timeout=60.0, descripcion="obteniendo participantes", client=client
        )

        if isinstance(data, dict) and "exception" in data:
            if "invalidtoken" in str(data).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(
                f"Error Moodle al obtener participantes: {data.get('message', '')}"
            )

        self._enrolled_cache[cache_key] = data
        return data

    async def get_enrolled_users_with_status(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
    ) -> list[dict]:
        """Devuelve TODOS los matriculados, anotando cada uno con `suspendido` (bool).

        Moodle no expone el estado de la matriculación por usuario (T0), así que se
        resuelve por DOBLE llamada: los que están en 'todos' (onlyactive=0) pero no en
        'activos' (onlyactive=1) están suspendidos.
        """
        todos = await self.get_enrolled_users_full(token, moodle_host, course_id, only_active=False)
        activos = await self.get_enrolled_users_full(token, moodle_host, course_id, only_active=True)

        activos_ids = {u["id"] for u in activos if isinstance(u, dict) and "id" in u}
        for u in todos:
            if isinstance(u, dict):
                u["suspendido"] = u.get("id") not in activos_ids
        return todos

    async def _ws_get_json(
        self,
        url: str,
        params: dict,
        *,
        timeout: float,
        descripcion: str,
        client: "httpx.AsyncClient | None" = None,
        reintentos: int = 2,
    ):
        """GET a un web service con reintentos ante timeout/conexión.

        Si se pasa `client`, se REUSA (keep-alive → no abre una conexión TLS nueva por
        llamada, clave para los snapshots con cientos de alumnos: evita el throttling
        de conexiones nuevas que dispara ConnectTimeout). Si no, crea uno efímero.
        """
        last_exc: Exception | None = None
        for intento in range(reintentos + 1):
            try:
                if client is not None:
                    resp = await client.get(url, params=params, timeout=timeout)
                else:
                    async with httpx.AsyncClient(timeout=timeout) as efimero:
                        resp = await efimero.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.TimeoutException as e:
                # ConnectTimeout/ReadTimeout: reintentar con backoff (Moodle puede
                # estar throttleando conexiones nuevas momentáneamente).
                last_exc = e
                if intento < reintentos:
                    await asyncio.sleep(1.5 * (intento + 1))
                    continue
                raise MoodleConnectionError(f"Timeout {descripcion}: {e}") from e
            except httpx.RequestError as e:
                last_exc = e
                if intento < reintentos:
                    await asyncio.sleep(1.5 * (intento + 1))
                    continue
                raise MoodleConnectionError(f"Error de red {descripcion}: {e}") from e
        raise MoodleConnectionError(f"Error {descripcion}: {last_exc}")

    async def get_course_contents(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
        *,
        client: "httpx.AsyncClient | None" = None,
    ) -> list[dict]:
        """Secciones (unidades) y módulos del curso vía core_course_get_contents.

        Devuelve la lista de secciones; cada una con 'id' (estable), 'section' (orden
        visual #), 'name' y 'modules[]' (cada módulo con 'id'=cmid, 'modname',
        'name', 'completion'). Cacheado por course_id (el snapshot lo usa una sola
        vez para todos los alumnos de la materia). Validado en spike T0 (§6.1).
        """
        if course_id in self._contents_cache:
            return self._contents_cache[course_id]

        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "core_course_get_contents",
            "moodlewsrestformat": "json",
            "courseid": course_id,
        }
        data = await self._ws_get_json(
            url, params, timeout=60.0, descripcion="obteniendo contenidos del curso", client=client
        )

        if isinstance(data, dict) and "exception" in data:
            if "invalidtoken" in str(data).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(
                f"Error Moodle al obtener contenidos: {data.get('message', '')}"
            )

        if not isinstance(data, list):
            raise MoodleConnectionError("Respuesta inesperada de core_course_get_contents")

        self._contents_cache[course_id] = data
        return data

    async def get_activities_completion(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
        user_id: int,
        *,
        client: "httpx.AsyncClient | None" = None,
    ) -> list[dict]:
        """Estado de finalización de actividades de UN alumno en el curso.

        core_completion_get_activities_completion_status → lista de statuses, cada uno
        con 'cmid', 'state' (0 incompleta / 1 completa / 2 completa-aprobada /
        3 completa-reprobada) y 'timecompleted'. Es **1 llamada por alumno** (~2s en
        T0). Pasá `client` para reusar la conexión (evita ConnectTimeout por volumen).
        """
        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "core_completion_get_activities_completion_status",
            "moodlewsrestformat": "json",
            "courseid": course_id,
            "userid": user_id,
        }
        data = await self._ws_get_json(
            url, params, timeout=30.0, descripcion="obteniendo completion", client=client
        )

        if isinstance(data, dict) and "exception" in data:
            if "invalidtoken" in str(data).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(
                f"Error Moodle al obtener completion: {data.get('message', '')}"
            )

        if isinstance(data, dict):
            return data.get("statuses", []) or []
        return []

    async def get_grade_items(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
        user_id: int,
        *,
        client: "httpx.AsyncClient | None" = None,
    ) -> dict[int, str]:
        """Notas del alumno por actividad (gradereport_user_get_grade_items).

        Devuelve {cmid: gradeformatted} — el texto tal cual se ve en Moodle
        ("Aprobado" / "Desaprobado" / "-" …). Lo usa el estado del TP (que se mide
        por CALIFICACIÓN, no por seguimiento). Es 1 llamada por alumno.
        """
        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "gradereport_user_get_grade_items",
            "moodlewsrestformat": "json",
            "courseid": course_id,
            "userid": user_id,
        }
        data = await self._ws_get_json(
            url, params, timeout=30.0, descripcion="obteniendo notas", client=client
        )
        if isinstance(data, dict) and "exception" in data:
            if "invalidtoken" in str(data).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(
                f"Error Moodle al obtener notas: {data.get('message', '')}"
            )
        usergrades = data.get("usergrades", []) if isinstance(data, dict) else []
        if not usergrades:
            return {}
        items = usergrades[0].get("gradeitems", []) or []
        return {
            it.get("cmid"): (it.get("gradeformatted") or "")
            for it in items
            if it.get("cmid") is not None
        }

    async def _fetch_submissions(
        self,
        token: str,
        moodle_host: str,
        assignment_instance_id: int,
    ) -> dict:
        # Cache por assignment: si una rúbrica tiene N comisiones, no refetcheamos N veces.
        if assignment_instance_id in self._submissions_cache:
            return self._submissions_cache[assignment_instance_id]

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

        self._submissions_cache[assignment_instance_id] = data
        return data

    async def _fetch_grades_map(
        self,
        token: str,
        moodle_host: str,
        assignment_instance_id: int,
    ) -> dict[int, int]:
        """Retorna userid → timemodified de la calificación más reciente.

        Se usa para detectar re-entregas: si submission.timemodified > grade.timemodified,
        el alumno volvió a entregar después de haber sido corregido.
        """
        if assignment_instance_id in self._grades_cache:
            return self._grades_cache[assignment_instance_id]

        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "mod_assign_get_grades",
            "moodlewsrestformat": "json",
            "assignmentids[0]": assignment_instance_id,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout consultando grades: {e}") from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red consultando grades: {e}") from e

        if isinstance(data, dict) and "exception" in data:
            if "invalidtoken" in str(data).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(f"Error de Moodle: {data.get('message', '')}")

        grades_map: dict[int, int] = {}
        for assignment in data.get("assignments", []):
            for grade in assignment.get("grades", []):
                uid = grade.get("userid")
                if uid is None:
                    continue
                tm = grade.get("timemodified") or 0
                # quedarnos con el grade más reciente por user (puede haber varios attempts)
                if tm > grades_map.get(uid, -1):
                    grades_map[uid] = tm
        self._grades_cache[assignment_instance_id] = grades_map
        return grades_map

    async def get_grades_full(
        self,
        token: str,
        moodle_host: str,
        assignment_instance_id: int,
    ) -> dict[int, dict]:
        """Retorna userid → {'timemodified': int, 'grade': str|None} del grade más reciente.

        A diferencia de `_fetch_grades_map` (que sólo guarda el timemodified para detectar
        re-entregas), acá conservamos también el valor del grade. Se usa para saber si una
        corrección YA está calificada en Moodle (timemodified > 0) y con qué nota, sin
        depender de un MoodleSync local.
        """
        if assignment_instance_id in self._grades_full_cache:
            return self._grades_full_cache[assignment_instance_id]

        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        params = {
            "wstoken": token,
            "wsfunction": "mod_assign_get_grades",
            "moodlewsrestformat": "json",
            "assignmentids[0]": assignment_instance_id,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout consultando grades: {e}") from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red consultando grades: {e}") from e

        if isinstance(data, dict) and "exception" in data:
            if "invalidtoken" in str(data).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(f"Error de Moodle: {data.get('message', '')}")

        full: dict[int, dict] = {}
        for assignment in data.get("assignments", []):
            for grade in assignment.get("grades", []):
                uid = grade.get("userid")
                if uid is None:
                    continue
                tm = grade.get("timemodified") or 0
                # quedarnos con el grade más reciente por user (puede haber varios attempts)
                if tm > full.get(uid, {}).get("timemodified", -1):
                    full[uid] = {"timemodified": tm, "grade": grade.get("grade")}
        self._grades_full_cache[assignment_instance_id] = full
        return full

    @staticmethod
    def es_calificacion_real(entry: dict | None) -> bool:
        """True si el entry de get_grades_full representa una nota REAL puesta en Moodle.

        ⚠️ Moodle crea un registro de grade (con timemodified) al entregar, pero con
        `grade = -1` mientras NO esté calificada. Por eso NO alcanza con timemodified > 0:
        hay que mirar el valor. Calificada ⇔ existe grade y su valor es >= 0
        (el 0 es nota válida; en escalas el índice es >= 1; -1 = sin nota).
        """
        if not entry:
            return False
        if (entry.get("timemodified") or 0) <= 0:
            return False
        try:
            return float(entry.get("grade")) >= 0
        except (TypeError, ValueError):
            return False

    async def get_submissions_count(
        self,
        token: str,
        moodle_host: str,
        assignment_instance_id: int,
        group_member_ids: set[int],
    ) -> dict:
        """Cuenta submissions para un assignment, filtradas por grupo (client-side).

        Una entrega cuenta como `espera` si:
        - status == "submitted" y gradingstatus indica sin corregir, O
        - fue corregida pero el alumno volvió a entregar después (submission.timemodified > grade.timemodified)
        """
        submissions_data, grades_map = await asyncio.gather(
            self._fetch_submissions(token, moodle_host, assignment_instance_id),
            self._fetch_grades_map(token, moodle_host, assignment_instance_id),
        )

        espera = 0
        corregidos = 0

        for assignment in submissions_data.get("assignments", []):
            for submission in assignment.get("submissions", []):
                user_id = submission.get("userid")
                if user_id not in group_member_ids:
                    continue
                status_val = submission.get("status", "")
                if status_val != "submitted":
                    # draft, new, etc. no cuenta como entregado
                    continue

                grading_status = submission.get("gradingstatus", "")
                sub_timemodified = submission.get("timemodified") or 0
                grade_timemodified = grades_map.get(user_id, 0)

                # Sin calificar nunca → espera
                if grading_status in ("notgraded", "") or grade_timemodified == 0:
                    espera += 1
                    continue

                # Re-entrega: entregó después de la última corrección → espera
                if sub_timemodified > grade_timemodified:
                    espera += 1
                else:
                    corregidos += 1

        # Los alumnos sin registro en submissions tampoco entregaron,
        # así que sinEntrega = total del grupo - los que sí entregaron
        sin_entrega = max(0, len(group_member_ids) - espera - corregidos)

        return {"espera": espera, "corregidos": corregidos, "sinEntrega": sin_entrega}

    async def get_group_members_map(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
        group_id: int,
    ) -> dict[int, str]:
        """Retorna {user_id: fullname} de los alumnos del grupo.

        Usado por la importación para resolver el nombre del alumno a partir del
        userid de la submission (NO se parsea del nombre del archivo).
        """
        if group_id in self._group_member_names:
            return self._group_member_names[group_id]

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

        STUDENT_ROLES = {"student"}
        members: dict[int, str] = {}
        for u in data:
            if not isinstance(u, dict) or "id" not in u:
                continue
            roles = u.get("roles", [])
            if any(r.get("shortname") in STUDENT_ROLES for r in roles):
                members[u["id"]] = u.get("fullname", "") or ""

        self._group_member_names[group_id] = members
        return members

    async def get_submissions_with_files(
        self,
        token: str,
        moodle_host: str,
        assignment_instance_id: int,
        group_member_ids: set[int],
        solo_pendientes: bool = True,
    ) -> list[MoodleSubmission]:
        """Lista las submissions entregadas del grupo con sus archivos descargables.

        Filtra client-side por `group_member_ids` (la API no soporta groupid) y
        sólo incluye submissions con status 'submitted'. Extrae los archivos del
        plugin de tipo 'file' (estructura confirmada en Fase 0 contra el TUP).

        Si `solo_pendientes` (default), aplica la MISMA lógica que el panel de
        pendientes (get_submissions_count): incluye sólo las que están en "espera"
        de corrección — sin calificar o re-entregadas después de la última nota —
        y excluye las ya corregidas en Moodle. Así la importación trae sólo lo
        pendiente, no todo el histórico.
        """
        if solo_pendientes:
            data, grades_map = await asyncio.gather(
                self._fetch_submissions(token, moodle_host, assignment_instance_id),
                self._fetch_grades_map(token, moodle_host, assignment_instance_id),
            )
        else:
            data = await self._fetch_submissions(token, moodle_host, assignment_instance_id)
            grades_map = {}

        result: list[MoodleSubmission] = []
        for assignment in data.get("assignments", []):
            for sub in assignment.get("submissions", []):
                user_id = sub.get("userid")
                if user_id not in group_member_ids:
                    continue
                if sub.get("status") != "submitted":
                    continue

                if solo_pendientes:
                    grading_status = sub.get("gradingstatus", "")
                    sub_tm = sub.get("timemodified") or 0
                    grade_tm = grades_map.get(user_id, 0)
                    # "espera" = sin calificar, o re-entregada después de la última nota.
                    es_espera = (
                        grading_status in ("notgraded", "")
                        or grade_tm == 0
                        or sub_tm > grade_tm
                    )
                    if not es_espera:
                        continue  # ya corregida en Moodle → no es pendiente

                files: list[MoodleFile] = []
                for plugin in sub.get("plugins", []):
                    if plugin.get("type") != "file":
                        continue
                    for area in plugin.get("fileareas", []):
                        for f in area.get("files", []):
                            url = f.get("fileurl")
                            if url:
                                files.append(MoodleFile(
                                    filename=f.get("filename", ""),
                                    fileurl=url,
                                    filesize=f.get("filesize", 0) or 0,
                                    mimetype=f.get("mimetype"),
                                ))

                result.append(MoodleSubmission(
                    userid=user_id,
                    status=sub.get("status", ""),
                    gradingstatus=sub.get("gradingstatus", "") or "",
                    timemodified=sub.get("timemodified") or 0,
                    attemptnumber=sub.get("attemptnumber", 0) or 0,
                    files=files,
                ))

        return result

    async def download_submission_file(self, token: str, fileurl: str) -> bytes:
        """Descarga el contenido de un archivo de Moodle (pluginfile.php) usando el token.

        El token se agrega como query param `token=` (confirmado en Fase 0).
        Nunca se loguea el fileurl con token.
        """
        sep = "&" if "?" in fileurl else "?"
        url = f"{fileurl}{sep}token={token}"
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout descargando archivo de Moodle: {e}") from e
        except httpx.HTTPStatusError as e:
            raise MoodleConnectionError(
                f"Moodle devolvió {e.response.status_code} al descargar el archivo"
            ) from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red descargando archivo de Moodle: {e}") from e

    async def get_assignment_grade_config(
        self,
        token: str,
        moodle_host: str,
        course_id: int,
        cmid: int,
    ) -> AssignmentGradeConfig | None:
        """Devuelve la config de calificación del assignment (por cmid), o None si no existe.

        Interpreta el campo `grade` (confirmado en Fase 0):
          grade > 0 → numérica; grade < 0 → escala (scale_id=abs); grade == 0 → sin calificación.
        """
        data = await self._fetch_assignments(token, moodle_host, course_id)
        for course in data.get("courses", []):
            for assignment in course.get("assignments", []):
                if assignment.get("cmid") == cmid:
                    grade = assignment.get("grade")
                    instance_id = assignment.get("id")
                    if grade is None or grade == 0:
                        return AssignmentGradeConfig(instance_id=instance_id, tipo="sin_calificacion")
                    if grade > 0:
                        return AssignmentGradeConfig(
                            instance_id=instance_id, tipo="numerica", grade_max=float(grade)
                        )
                    return AssignmentGradeConfig(
                        instance_id=instance_id, tipo="escala", scale_id=abs(int(grade))
                    )
        return None

    async def save_grade(
        self,
        token: str,
        moodle_host: str,
        assignment_instance_id: int,
        moodle_user_id: int,
        grade: float,
        feedback_comment: str,
    ) -> None:
        """Publica nota + feedback en Moodle vía mod_assign_save_grade.

        Para escalas cualitativas, `grade` es el ÍNDICE 1-based del ítem de la escala.
        Para numéricas, es la nota en la escala del assignment.
        El feedback va como HTML en el plugin assignfeedbackcomments.
        NO se loguea el token.
        """
        url = f"{moodle_host.rstrip('/')}/webservice/rest/server.php"
        data = {
            "wstoken": token,
            "wsfunction": "mod_assign_save_grade",
            "moodlewsrestformat": "json",
            "assignmentid": assignment_instance_id,
            "userid": moodle_user_id,
            "grade": grade,
            "attemptnumber": -1,  # último intento
            "addattempt": 0,
            "workflowstate": "",
            "applytoall": 1,
            "plugindata[assignfeedbackcomments_editor][text]": feedback_comment,
            "plugindata[assignfeedbackcomments_editor][format]": 1,  # 1 = HTML
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, data=data)
                resp.raise_for_status()
                result = resp.json()
        except httpx.TimeoutException as e:
            raise MoodleConnectionError(f"Timeout enviando nota a Moodle: {e}") from e
        except httpx.RequestError as e:
            raise MoodleConnectionError(f"Error de red enviando nota a Moodle: {e}") from e

        # mod_assign_save_grade devuelve null en éxito; un dict con 'exception' indica error.
        if isinstance(result, dict) and "exception" in result:
            msg = result.get("message", "Error desconocido")
            if "invalidtoken" in str(result).lower():
                raise MoodleAuthError("Token Moodle inválido")
            raise MoodleConnectionError(f"Moodle rechazó la nota: {msg}")

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

        # Pre-cargar submissions + grades por assignment ÚNICO, en paralelo.
        # Evita refetchear el mismo assignment una vez por comisión: el conteo posterior
        # lee del cache (self._submissions_cache / self._grades_cache).
        unique_instances: set[int] = set()
        for rubrica in rubricas:
            materia = materias_by_id.get(rubrica.materia_id)
            if materia and materia.moodle_course_id:
                cmid_map = self._cmid_map.get(materia.moodle_course_id, {})
                iid = cmid_map.get(rubrica.moodle_assign_id)
                if iid:
                    unique_instances.add(iid)

        prefetch_sem = asyncio.Semaphore(10)

        async def _precargar(iid: int):
            async with prefetch_sem:
                try:
                    await asyncio.gather(
                        self._fetch_submissions(token, moodle_host, iid),
                        self._fetch_grades_map(token, moodle_host, iid),
                    )
                except (MoodleConnectionError, MoodleAuthError) as e:
                    logger.warning(
                        "No se pudieron precargar submissions del assignment %s: %s", iid, e
                    )

        if unique_instances:
            await asyncio.gather(*[_precargar(iid) for iid in unique_instances])

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
