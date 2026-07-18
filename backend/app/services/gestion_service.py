"""GestionService — pantalla "Gestión" (rol GESTOR).

Lista cursos de Moodle, expone las opciones de filtro (regionales/comisiones reales
del curso + catálogos) y consulta los participantes aplicando los filtros que Moodle
permite (rol, estatus, regional, comisión, inactividad), para listarlos y exportarlos.

Decisiones y formatos confirmados en el spike T0 (ver PLAN_GESTION.md):
- Regional/Comisión salen de los grupos del alumno (R-* y M.. C..-..); el resto se ignora.
- Estatus activo/suspendido = doble llamada a Moodle (no hay flag por usuario).
- Inactividad = bandas cerradas sobre lastcourseaccess (no acumulativo).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.comision_repository import ComisionRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.services.gestion_inactividad import (
    NUNCA,
    RANGO,
    coincide_inactividad,
    dias_inactividad,
)
from app.services.gestion_parser import (
    SIN_COMISION,
    parse_comision,
    parse_regional,
    resolver_grupos_alumno,
)
from app.services.excel_service import ExcelService
from app.services.moodle_service import (
    MoodleAuthError,
    MoodleConnectionError,
    MoodleService,
    construir_mapa_uid_grupos,
)

logger = logging.getLogger(__name__)

# --- Catálogos de filtros (lo que ofrece la UI) -------------------------------

ROLES_CATALOGO = [
    {"value": "student", "label": "Estudiante"},
    {"value": "editingteacher", "label": "Profesor"},
    {"value": "teacher", "label": "Profesor sin permiso de edición"},
]

ESTATUS_CATALOGO = [
    {"value": "activo", "label": "Activo"},
    {"value": "inactivo", "label": "Inactivo"},
]

INACTIVIDAD_CATALOGO = [
    {"value": "1_dia", "label": "1 día"},
    {"value": "2_dias", "label": "2 días"},
    {"value": "1_semana", "label": "1 semana"},
    {"value": "2_semanas", "label": "2 semanas"},
    {"value": "3_semanas", "label": "3 semanas"},
    {"value": "1_mes", "label": "1 mes"},
    {"value": "2_meses", "label": "2 meses o más"},
    {"value": RANGO, "label": "Rango personalizado (de N a M días)"},
    {"value": NUNCA, "label": "Nunca ingresó"},
]


# --- DTOs (dataclasses) -------------------------------------------------------

@dataclass
class CursoGestion:
    materia_id: int
    nombre: str
    codigo: str
    moodle_course_id: int


@dataclass
class FiltrosDisponibles:
    regionales: list[str]
    comisiones: list[str]
    roles: list[dict]
    estatus: list[dict]
    inactividad: list[dict]


@dataclass
class FiltrosGestion:
    rol: str | None = None          # 'student' | 'editingteacher' | 'teacher' | None(todos)
    estatus: str | None = None      # 'activo' | 'inactivo' | None(todos)
    regionales: list[str] = field(default_factory=list)   # vacío = todas
    comisiones: list[str] = field(default_factory=list)    # vacío = todas
    inactividad_tipo: str | None = None  # clave de BANDAS, RANGO, NUNCA, o None(sin filtro)
    inactividad_desde: int | None = None
    inactividad_hasta: int | None = None


@dataclass
class AlumnoGestion:
    nombre: str
    apellido: str
    email: str
    regional: str
    comision: str
    dias_inactividad: int | None
    tiempo_inactividad: str
    suspendido: bool


@dataclass
class ResultadoGestion:
    items: list[AlumnoGestion]
    total: int


@dataclass
class EntregaPendiente:
    """Una entrega pendiente de corregir (entregada en Moodle, sin calificar)."""

    trabajo: str
    comision: str
    tutor: str
    nombre: str
    apellido: str
    email: str
    fecha_entrega: str


def _humanizar_inactividad(dias: int | None) -> str:
    if dias is None:
        return "Nunca"
    if dias == 1:
        return "1 día"
    return f"{dias} días"


class GestionService:
    _MOODLE_REINTENTOS = 3  # reintentos ante ConnectTimeout transitorio de Moodle

    def __init__(self, db):
        self.db = db
        self.materia_repo = MateriaRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.comision_repo = ComisionRepository(db)
        self.moodle = MoodleService(db)
        self.excel = ExcelService(db)

    async def listar_cursos(self, usuario) -> list[CursoGestion]:
        materias = await self.materia_repo.get_con_moodle()
        return [
            CursoGestion(
                materia_id=m.id, nombre=m.nombre, codigo=m.codigo,
                moodle_course_id=m.moodle_course_id,
            )
            for m in materias
        ]

    async def opciones_filtros(self, usuario, materia_id: int) -> FiltrosDisponibles:
        materia = await self._resolver_curso(materia_id)
        token, host = await self._token(usuario)
        users = await self.moodle.get_enrolled_users_full(token, host, materia.moodle_course_id)
        mapa = await self._mapa_uid_grupos(token, host, materia.moodle_course_id)

        regionales: set[str] = set()
        comisiones: set[str] = set()
        for u in users:
            if not isinstance(u, dict):
                continue
            for nombre in self._grupos_nombres(u, mapa):
                r = parse_regional(nombre)
                if r:
                    regionales.add(r)
                c = parse_comision(nombre)
                if c:
                    comisiones.add(c)

        return FiltrosDisponibles(
            regionales=sorted(regionales),
            comisiones=sorted(comisiones),
            roles=ROLES_CATALOGO,
            estatus=ESTATUS_CATALOGO,
            inactividad=INACTIVIDAD_CATALOGO,
        )

    async def consultar(
        self,
        usuario,
        materia_id: int,
        filtros: FiltrosGestion,
        *,
        now: int | None = None,
    ) -> ResultadoGestion:
        if now is None:
            now = int(time.time())

        materia = await self._resolver_curso(materia_id)
        token, host = await self._token(usuario)
        users = await self.moodle.get_enrolled_users_with_status(token, host, materia.moodle_course_id)
        mapa = await self._mapa_uid_grupos(token, host, materia.moodle_course_id)

        items: list[AlumnoGestion] = []
        for u in users:
            if not isinstance(u, dict):
                continue

            # --- Rol ---
            shortnames = {r.get("shortname") for r in u.get("roles", [])}
            if filtros.rol and filtros.rol not in shortnames:
                continue

            # --- Estatus (activo/suspendido) ---
            suspendido = bool(u.get("suspendido"))
            if filtros.estatus == "activo" and suspendido:
                continue
            if filtros.estatus == "inactivo" and not suspendido:
                continue

            # --- Regional / Comisión (de los grupos autoritativos) ---
            group_names = self._grupos_nombres(u, mapa)
            regional, comision = resolver_grupos_alumno(group_names)
            if filtros.regionales and regional not in filtros.regionales:
                continue
            if filtros.comisiones and comision not in filtros.comisiones:
                continue

            # --- Inactividad ---
            lca = u.get("lastcourseaccess")
            if filtros.inactividad_tipo:
                if not coincide_inactividad(
                    lca, now, filtros.inactividad_tipo,
                    desde=filtros.inactividad_desde, hasta=filtros.inactividad_hasta,
                ):
                    continue

            dias = dias_inactividad(lca, now)
            items.append(AlumnoGestion(
                nombre=u.get("firstname", ""),
                apellido=u.get("lastname", ""),
                email=u.get("email", ""),
                regional=regional,
                comision=comision,
                dias_inactividad=dias,
                tiempo_inactividad=_humanizar_inactividad(dias),
                suspendido=suspendido,
            ))

        # Orden: regional → comisión → apellido → nombre (igual que las hojas del Excel).
        items.sort(key=lambda a: (a.regional.lower(), a.comision, a.apellido.lower(), a.nombre.lower()))
        return ResultadoGestion(items=items, total=len(items))

    async def exportar_excel(
        self,
        usuario,
        materia_id: int,
        filtros: FiltrosGestion,
        *,
        agrupar_por: str = "regional",
        now: int | None = None,
    ) -> tuple[bytes, str]:
        """Consulta con los filtros y arma el .xlsx.

        `agrupar_por`: "regional" (Excel para Nexos) o "comision" (Excel para Tutores).
        """
        materia = await self._resolver_curso(materia_id)
        resultado = await self.consultar(usuario, materia_id, filtros, now=now)
        # PERF-004: el render openpyxl (CPU-bound) corre en un thread para no bloquear el
        # event loop. `resultado` ya viene materializado (dataclasses simples, sin ORM).
        return await asyncio.to_thread(
            self.excel.exportar_gestion, resultado, materia.nombre, agrupar_por=agrupar_por
        )

    async def exportar_pendientes_excel(
        self,
        usuario,
        materia_id: int,
        *,
        agrupar_por: str = "trabajo",
    ) -> tuple[bytes, str]:
        """Excel de entregas pendientes de corregir del curso (entregadas sin calificar).

        `agrupar_por`: "trabajo" (Pendientes por Práctico) o "comision" (Pendientes
        por Comisión). En ambos, las filas salen de la misma lista plana.

        Eficiente: UNA sola consulta de participantes (get_enrolled_users_full) da
        nombre/apellido/email, quién es alumno y la comisión (parseada del código del
        grupo). Luego, por rúbrica, una sola consulta de submissions (cacheada por
        assignment). NO consulta miembros por comisión.
        """
        materia = await self._resolver_curso(materia_id)
        token, host = await self._token(usuario)
        course_id = materia.moodle_course_id

        rubricas = [
            r for r in await self.rubrica_repo.get_by_materia(materia_id)
            if r.activa and r.moodle_assign_id
        ]

        # 1 query: comisiones + tutores → mapa {moodle_group_id: "Tutor1, Tutor2"}.
        # El puente comisión↔tutor es moodle_group_id (la comisión-código sale del nombre
        # del grupo, pero el id de ESE grupo coincide con Comision.moodle_group_id).
        tutor_por_group: dict[int, str] = {}
        for c in await self.comision_repo.get_by_materia_con_tutores(materia_id):
            if c.moodle_group_id:
                tutor_por_group[c.moodle_group_id] = ", ".join(
                    ct.tutor.nombre for ct in c.tutores if ct.tutor
                )

        # 1 consulta: de acá salen los alumnos, sus datos, su comisión y su tutor.
        enrolled = await self.moodle.get_enrolled_users_full(token, host, course_id)
        # Mapa autoritativo `uid → grupos` (Bug 3): prioriza los grupos reales del curso
        # sobre el `groups[]` embebido (que puede omitir comisiones con grupos separados).
        # Los dicts del mapa también traen "id", así que el puente comisión↔tutor por
        # moodle_group_id sigue funcionando igual.
        mapa = await self._mapa_uid_grupos(token, host, course_id)
        info_por_user: dict[int, dict] = {}
        alumno_ids: set[int] = set()
        for u in enrolled:
            if not isinstance(u, dict) or "id" not in u:
                continue
            comision = SIN_COMISION
            tutor = ""
            for g in (mapa.get(u["id"]) or u.get("groups", [])):
                if parse_comision(g.get("name", "")):
                    comision = parse_comision(g.get("name", ""))
                    tutor = tutor_por_group.get(g.get("id"), "")
                    break
            info_por_user[u["id"]] = {
                "nombre": u.get("firstname", ""),
                "apellido": u.get("lastname", ""),
                "email": u.get("email", ""),
                "comision": comision,
                "tutor": tutor,
            }
            if any(rol.get("shortname") == "student" for rol in u.get("roles", [])):
                alumno_ids.add(u["id"])

        cmid_map = await self.moodle._get_course_assignment_map(token, host, course_id)

        pendientes: list[EntregaPendiente] = []
        for r in rubricas:
            instance_id = cmid_map.get(r.moodle_assign_id)
            if not instance_id:
                continue  # cmid sin assignment en Moodle → se omite

            subs = await self._submissions_pendientes(token, host, instance_id, alumno_ids, r.titulo)
            if subs is None:
                continue  # falló tras reintentos → se saltea esa rúbrica (logueado)

            for s in subs:
                info = info_por_user.get(s.userid)
                if info is None:
                    continue  # submission de alguien que no es alumno del curso
                pendientes.append(EntregaPendiente(
                    trabajo=r.titulo,
                    comision=info["comision"],
                    tutor=info["tutor"],
                    nombre=info["nombre"],
                    apellido=info["apellido"],
                    email=info["email"],
                    fecha_entrega=self._fmt_fecha(getattr(s, "timemodified", None)),
                ))

        # PERF-004: render openpyxl (CPU-bound) en un thread. `pendientes` es una lista
        # plana de EntregaPendiente ya materializada (sin ORM ni relaciones lazy).
        return await asyncio.to_thread(
            self.excel.exportar_pendientes, pendientes, materia.nombre, agrupar_por=agrupar_por
        )

    async def _submissions_pendientes(self, token, host, instance_id, alumno_ids, titulo):
        """Submissions pendientes de una rúbrica, con reintentos ante ConnectTimeout
        transitorio de Moodle. Devuelve None (y loguea) si falla tras los reintentos."""
        ultimo_error = None
        for intento in range(self._MOODLE_REINTENTOS):
            try:
                return await self.moodle.get_submissions_with_files(
                    token, host, instance_id, alumno_ids, solo_pendientes=True
                )
            except (MoodleConnectionError, MoodleAuthError) as e:
                ultimo_error = e
                if intento < self._MOODLE_REINTENTOS - 1:
                    await asyncio.sleep(0.5 * (intento + 1))
        logger.warning(
            "Pendientes: salteo rúbrica %r tras %d intentos: %s",
            titulo, self._MOODLE_REINTENTOS, ultimo_error,
        )
        return None

    @staticmethod
    def _fmt_fecha(timemodified: int | None) -> str:
        if not timemodified:
            return ""
        return datetime.fromtimestamp(timemodified).strftime("%d/%m/%Y %H:%M")

    # --- helpers privados -----------------------------------------------------

    async def _mapa_uid_grupos(self, token, host, course_id) -> dict[int, list[dict]]:
        """Mapa autoritativo `uid → [{id, name}]` de grupos del curso (Bug 3).

        El `groups[]` embebido en `core_enrol_get_enrolled_users` puede venir incompleto
        en cursos con grupos separados (`groupmode=1`) → se arma una fuente autoritativa
        cruzando TODOS los grupos del curso (`core_group_get_course_groups`) con sus
        miembros (`core_group_get_group_members`).

        GestionService (rol GESTOR) es el punto más probable de toparse con
        `nopermissions` al pedir los grupos: si el WS falla o está deshabilitado se
        degrada devolviendo `{}`, de modo que los callers caen al `groups[]` embebido
        (comportamiento actual) sin romper la corrida. Esa degradación segura cubre lo
        pedido por la tarea 11.5 para GestionService.
        """
        try:
            grupos_curso = await self.moodle.get_course_groups(token, host, course_id)
            members_por_group = {
                g["id"]: await self.moodle.get_group_members(token, host, g["id"])
                for g in grupos_curso
            }
            return construir_mapa_uid_grupos(grupos_curso, members_por_group)
        except (MoodleConnectionError, MoodleAuthError) as e:
            logger.warning(
                "Gestión: grupos autoritativos no disponibles (course_id=%s); "
                "se degrada al groups[] embebido: %s",
                course_id, e,
            )
            return {}

    @staticmethod
    def _grupos_nombres(u: dict, mapa: dict[int, list[dict]]) -> list[str]:
        """Nombres de grupo de un alumno, priorizando el mapa autoritativo y cayendo
        al `groups[]` embebido cuando el mapa no tiene entrada para ese uid."""
        grupos = mapa.get(u.get("id")) or u.get("groups", [])
        return [g.get("name", "") for g in grupos]

    async def _resolver_curso(self, materia_id: int):
        materia = await self.materia_repo.get_by_id(materia_id)
        if not materia or not materia.moodle_course_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curso no encontrado o sin vínculo a Moodle",
            )
        return materia

    async def _token(self, usuario) -> tuple[str, str]:
        if not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail="Configurá tus credenciales Moodle en tu perfil",
            )
        host = usuario.moodle_host or ""
        token = await self.moodle.get_token(
            user_id=usuario.id,
            moodle_host=host,
            username=usuario.moodle_username,
            password_encrypted=usuario.moodle_password_encrypted,
        )
        return token, host
