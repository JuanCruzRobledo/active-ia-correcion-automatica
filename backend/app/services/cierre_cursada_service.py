# app/services/cierre_cursada_service.py
"""
CierreCursadaService — orquesta el cierre de cursada (PROMOCIONA/REGULARIZA/
RECURSA) de una materia dirigido por `ExamenMateria` (fuente de verdad única,
ver diseño "Destino de CierreCursadaItem"): trae el calificador completo de
Moodle (WS + 1 sesión + 1 export masivo, número CONSTANTE de requests, mismo
patrón que SnapshotService), resuelve rescates + valor por examen con
`examen_mapper.calcular_resultados_examenes`, clasifica con la función PURA
`cierre_cursada_calculo.calcular_estado_cierre` y persiste una corrida con el
detalle por alumno.

Ya NO existe un mapeo manual de ítems del calificador (`CierreCursadaItem`):
si la materia no tiene exámenes PARCIAL/GLOBAL configurados en el dashboard,
`generar` bloquea con 400.
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.models.enums import EstadoCierreEnum, TipoActividadEnum
from app.repositories.cierre_cursada_repository import CierreCursadaRepository
from app.repositories.comision_repository import ComisionRepository
from app.repositories.examen_repository import ExamenRepository
from app.repositories.materia_repository import MateriaRepository
from app.services.actividad_service import ActividadService
from app.services.cierre_cursada_calculo import SinExamenesConfigurados, calcular_estado_cierre
from app.services.examen_mapper import TIPOS_PRINCIPALES, calcular_resultados_examenes
from app.services.gestion_parser import parse_comision
from app.services.moodle_bulk_parser import (
    construir_indice_nombre_cmid,
    parsear_export_calificador_dual,
)
from app.services.moodle_service import (
    MoodleAuthError,
    MoodleConnectionError,
    MoodleService,
    construir_mapa_uid_grupos,
)

logger = logging.getLogger(__name__)


class CierreCursadaService:
    """Orquesta la generación del cierre de cursada dirigido por ExamenMateria."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.materia_repo = MateriaRepository(db)
        self.comision_repo = ComisionRepository(db)
        self.examen_repo = ExamenRepository(db)
        self.cierre_repo = CierreCursadaRepository(db)
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

    async def _get_materia_configurada(self, materia_id: int):
        materia = await self.materia_repo.get_by_id(materia_id)
        if materia is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Materia no encontrada")
        if not materia.moodle_course_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="La materia no tiene un curso de Moodle configurado",
            )
        return materia

    @staticmethod
    def _es_student(usuario: dict) -> bool:
        return any(r.get("shortname") == "student" for r in (usuario.get("roles") or []))

    @staticmethod
    def _resolver_comision(grupos: list[dict], comisiones: list) -> tuple[int | None, str | None, str | None]:
        """(comision_id, comision_nombre, tutor_nombre) resolviendo el/los grupo(s) de
        comisión del alumno dentro de `grupos` (que trae VARIOS grupos: comisión +
        regional + TPI + cohortes...). Bridge primario por `moodle_group_id` (mismo
        puente confiable que `gestion_service`/`moodle_import_service`); fallback por
        nombre de comisión derivado del grupo (`parse_comision`) contra `Comision.nombre`.
        Los grupos que no son de comisión (regional "R-*", TPI "Grupo_NN", cohortes...)
        no matchean ninguno de los dos puentes y se descartan naturalmente. 0 o >1
        `Comision` DISTINTAS matcheadas -> sin comisión (nunca se rompe la corrida por
        un alumno con mapeo ambiguo/roto)."""
        por_group_id = {c.moodle_group_id: c for c in comisiones if c.moodle_group_id}
        por_nombre = {c.nombre.strip().casefold(): c for c in comisiones if c.nombre}
        encontradas: dict[int, object] = {}
        for g in grupos:
            gid = g.get("id")
            if gid is not None and gid in por_group_id:
                c = por_group_id[gid]
                encontradas[c.id] = c
                continue
            codigo = parse_comision(g.get("name") or "")
            if codigo:
                c = por_nombre.get(codigo.strip().casefold())
                if c:
                    encontradas[c.id] = c
        if len(encontradas) != 1:
            return None, "Sin comisión asignada", None
        comision = next(iter(encontradas.values()))
        tutor_nombre = " / ".join(ct.tutor.nombre for ct in comision.tutores) or None
        return comision.id, comision.nombre, tutor_nombre

    # ----- Generación del cierre -----

    async def generar(
        self,
        materia_id: int,
        cuatrimestre_id: int,
        usuario,
    ) -> CierreCursadaRun:
        """Genera y persiste una corrida de cierre dirigida por `ExamenMateria`.

        Carga la config de exámenes (PARCIAL/GLOBAL únicamente cuentan como
        principales), descarga el calificador completo de Moodle (WS + sesión
        + export dual, número CONSTANTE de requests, igual patrón que
        `SnapshotService.generar`), resuelve rescates + `valor_real` por
        alumno con `examen_mapper.calcular_resultados_examenes` y clasifica
        con la función PURA `calcular_estado_cierre` (que también calcula la
        Nota Final ponderada).
        """
        materia = await self._get_materia_configurada(materia_id)
        course_id = materia.moodle_course_id

        examenes_materia = await self.examen_repo.get_by_materia(materia_id)
        examenes_principales = [e for e in examenes_materia if e.tipo.value in TIPOS_PRINCIPALES]
        if not examenes_principales:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="La materia no tiene exámenes configurados en el dashboard",
            )

        # Config completa (incluye recuperatorio/extensión/extraordinaria: necesarios
        # para que examen_mapper resuelva las cadenas de rescate de cada principal).
        examenes_config = [
            {
                "id": e.id,
                "tipo": e.tipo.value,
                "tipo_actividad": e.tipo_actividad.value,
                "moodle_cmid": e.moodle_cmid,
                "modo_aprobacion": e.modo_aprobacion.value,
                "nota_minima": e.nota_minima,
                "recupera_examen_id": e.recupera_examen_id,
                "orden": e.orden,
            }
            for e in examenes_materia
        ]

        token, host = await self.token_de_usuario(usuario)
        comisiones = await self.comision_repo.get_by_materia_con_tutores(materia_id)

        sesion = self.moodle.crear_cliente_sesion()
        try:
            await self.moodle.login_sesion(
                sesion, host, usuario.moodle_username, usuario.moodle_password_encrypted
            )
            enrolled = await self.moodle.get_enrolled_users_full(token, host, course_id, client=sesion)
            students = [u for u in enrolled if isinstance(u, dict) and self._es_student(u)]

            # Mapa autoritativo `uid → grupos` (Bug 3). El `groups[]` embebido en
            # `core_enrol_get_enrolled_users` puede venir incompleto en cursos con grupos
            # separados (`groupmode=1`) → se arma una fuente autoritativa cruzando TODOS los
            # grupos del curso (`core_group_get_course_groups`, 1 request) con sus miembros
            # (`core_group_get_group_members`, 1 request por grupo, reutilizando la sesión).
            #
            # Fallback ante WS de grupos deshabilitado/forbidden (tarea 11.5): si el cliente
            # no tiene habilitado `core_group_get_course_groups`/`core_group_get_group_members`
            # (o el token no tiene permiso → `nopermissions`), NO se rompe la corrida: se degrada
            # a `mapa_uid_grupos = {}` y se loguea la degradación. El loop de alumnos usa
            # `mapa_uid_grupos.get(uid) or (u.get("groups") or [])`, así que un mapa vacío cae
            # limpiamente al `groups[]` embebido (comportamiento actual, preserva 3.7).
            try:
                grupos_curso = await self.moodle.get_course_groups(token, host, course_id, client=sesion)
                members_por_group = {
                    g["id"]: await self.moodle.get_group_members(token, host, g["id"], client=sesion)
                    for g in grupos_curso
                }
                mapa_uid_grupos = construir_mapa_uid_grupos(grupos_curso, members_por_group)
            except (MoodleConnectionError, MoodleAuthError) as e:
                logger.warning(
                    "Cierre de cursada: grupos autoritativos no disponibles "
                    "(course_id=%s); se degrada al groups[] embebido: %s",
                    course_id, e,
                )
                mapa_uid_grupos = {}

            secciones = await self.moodle.get_course_contents(token, host, course_id, client=sesion)
            nombre_a_cmid = construir_indice_nombre_cmid(secciones)
            email_a_uid = {
                (u.get("email") or "").strip().lower(): u.get("id")
                for u in students
                if u.get("email")
            }
            csv_text = await self.moodle.descargar_export_calificador(
                sesion, host, course_id, incluir_porcentaje=True
            )
            notas_por_uid = parsear_export_calificador_dual(csv_text, nombre_a_cmid, email_a_uid)

            # Grade ESTRUCTURAL de los exámenes-Tarea (assign): {cmid: {uid: entry}} —
            # única señal que distingue 'entregado sin corregir' (grade=-1) de 'ausente'
            # (el texto del calificador muestra '-' en ambos casos). Igual patrón que
            # SnapshotService.generar: 1 request por examen assign.
            mod_por_cmid = {
                mod.get("id"): mod
                for sec in secciones
                for mod in sec.get("modules", [])
            }
            grades_por_cmid: dict[int, dict] = {}
            for ex in examenes_config:
                mod = mod_por_cmid.get(ex.get("moodle_cmid")) or {}
                # Sólo los exámenes marcados como Tarea (assign) usan el grade
                # estructural (`mod_assign_get_grades`). Un `quiz` NO tiene grade
                # estructural: su nota sale por el texto del calificador en
                # `examen_mapper`, así que se excluye acá para no pegarle al WS de
                # assign con una instancia que no corresponde.
                if (
                    ex["tipo_actividad"] == "assign"
                    and mod.get("modname") == "assign"
                    and mod.get("instance")
                ):
                    grades_por_cmid[ex["moodle_cmid"]] = await self.moodle.get_grades_full(
                        token, host, mod["instance"]
                    )
        finally:
            await sesion.aclose()

        alumnos: list[CierreCursadaAlumno] = []
        conteos = {"PROMOCIONA": 0, "REGULARIZA": 0, "RECURSA": 0, "ABANDONO": 0}
        for u in students:
            uid = u.get("id")
            notas_uid = {
                cmid: valores.get("real") for cmid, valores in notas_por_uid.get(uid, {}).items()
            }
            examenes_alumno = calcular_resultados_examenes(
                notas_uid,
                examenes_config,
                estructural_uid={
                    cmid: grades.get(uid) for cmid, grades in grades_por_cmid.items()
                },
            )
            # examen_mapper expone `resultado`; calcular_estado_cierre espera
            # `resultado_escala` (ver diseño, entrada de calcular_estado_cierre).
            examenes_para_estado = [
                {
                    "examen_id": ex["examen_id"],
                    "tipo": ex["tipo"],
                    "modo_aprobacion": ex["modo_aprobacion"],
                    "nota_minima": ex["nota_minima"],
                    "valor_real": ex["valor_real"],
                    "resultado_escala": ex["resultado"],
                }
                for ex in examenes_alumno
            ]

            try:
                veredicto = calcular_estado_cierre(examenes_para_estado)
            except SinExamenesConfigurados as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="La materia no tiene exámenes configurados en el dashboard",
                ) from exc

            # Preferir los grupos del mapa autoritativo para este uid (Bug 3); si el uid no
            # tiene entrada allí, caer al `groups[]` embebido (fallback seguro que preserva 3.7).
            comision_id, comision_nombre, tutor_nombre = self._resolver_comision(
                mapa_uid_grupos.get(uid) or (u.get("groups") or []), comisiones
            )

            conteos[veredicto["estado"]] += 1
            alumnos.append(
                CierreCursadaAlumno(
                    moodle_user_id=uid,
                    nombre=u.get("firstname"),
                    apellido=u.get("lastname"),
                    email=u.get("email"),
                    comision_id=comision_id,
                    comision_nombre=comision_nombre,
                    tutor_nombre=tutor_nombre,
                    resultados_examenes=veredicto["resultados_examenes"],
                    global_valor=veredicto["global_valor"],
                    estado=EstadoCierreEnum(veredicto["estado"]),
                    nota_final=veredicto["nota_final"],
                )
            )

        run = CierreCursadaRun(
            materia_id=materia_id,
            cuatrimestre_id=cuatrimestre_id,
            examenes_snapshot=examenes_config,
            generado_por_id=usuario.id,
            total_alumnos=len(alumnos),
            total_promociona=conteos["PROMOCIONA"],
            total_regulariza=conteos["REGULARIZA"],
            total_recursa=conteos["RECURSA"],
            total_abandono=conteos["ABANDONO"],
        )
        run.alumnos = alumnos
        creado = await self.cierre_repo.crear_run(run)

        logger.info(
            "Cierre de cursada generado: materia=%s cuatrimestre=%s alumnos=%s "
            "(promociona=%s regulariza=%s recursa=%s abandono=%s)",
            materia_id, cuatrimestre_id, creado.total_alumnos,
            creado.total_promociona, creado.total_regulariza, creado.total_recursa,
            creado.total_abandono,
        )
        await ActividadService(self.db).registrar_actividad(
            tipo=TipoActividadEnum.CIERRE_CURSADA_GENERADO,
            descripcion=(
                f"Cierre de cursada de '{materia.nombre}' generado "
                f"({creado.total_alumnos} alumnos: {creado.total_promociona} promociona, "
                f"{creado.total_regulariza} regulariza, {creado.total_recursa} recursa, "
                f"{creado.total_abandono} abandono)"
            ),
            entidad_id=creado.id,
            entidad_nombre=materia.nombre,
            usuario_id=usuario.id,
        )
        return creado

    async def listar_historial(self, materia_id: int) -> list[CierreCursadaRun]:
        return await self.cierre_repo.listar_runs(materia_id)

    async def obtener_run(self, run_id: int) -> CierreCursadaRun | None:
        return await self.cierre_repo.get_run(run_id)
