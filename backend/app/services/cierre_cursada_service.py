# app/services/cierre_cursada_service.py
"""
CierreCursadaService — orquesta el cierre de cursada (PROMOCIONA/REGULARIZA/
RECURSA) de una materia: trae el calificador completo de Moodle (WS + 1
sesión + 1 export masivo, número CONSTANTE de requests, mismo patrón que
SnapshotService), aplica el mapeo de ítems confirmado y la fórmula PURA de
cierre_cursada_calculo, y persiste una corrida con el detalle por alumno.

Nunca calcula con un mapeo sin confirmar: generar() bloquea si hay ítems del
curso todavía sin una fila en cierre_cursada_items.
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.models.enums import CategoriaItemCierreEnum, EstadoCierreEnum, TipoActividadEnum
from app.repositories.cierre_cursada_repository import CierreCursadaRepository
from app.repositories.comision_repository import ComisionRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.actividad_service import ActividadService
from app.services.cierre_cursada_calculo import calcular_estado, sugerir_categoria
from app.services.examen_mapper import parsear_nota_numerica
from app.services.moodle_bulk_parser import (
    construir_indice_nombre_cmid,
    parsear_export_calificador_dual,
)
from app.services.moodle_service import MoodleService

logger = logging.getLogger(__name__)

REGLAS_CIERRE_DEFAULT = {
    "autoeval_min_pct": 90,
    "parcial_promocion_min_pct": 60,
    "parcial_regulariza_min_pct": 40,
    "tpi_min_pct": 60,
}

# Módulos de Moodle que pueden aportar una nota al calificador (assign=Tarea,
# quiz=Cuestionario); otros modname (resource, forum, etc.) no tienen nota.
_MODNAMES_CALIFICABLES = ("assign", "quiz")


def _parse_pct(texto: str | None) -> float | None:
    """"70,00 %" / "70,00" / "-" / None -> float o None (sin nota)."""
    if not texto:
        return None
    return parsear_nota_numerica(texto.strip().rstrip("%").strip())


def _tp_resultado(texto: str | None) -> str:
    """Texto crudo del ítem TP (escala) -> "Aprobado"/"Desaprobado"/"N/E"."""
    return texto if texto in ("Aprobado", "Desaprobado") else "N/E"


class CierreCursadaService:
    """Orquesta el mapeo de ítems y la generación del cierre de cursada."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.materia_repo = MateriaRepository(db)
        self.comision_repo = ComisionRepository(db)
        self.usuario_repo = UsuarioRepository(db)
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

    async def _items_del_curso(self, token: str, host: str, course_id: int) -> list[dict]:
        """Ítems calificables del curso (assign/quiz), en el orden real de Moodle."""
        secciones = await self.moodle.get_course_contents(token, host, course_id)
        items = []
        orden = 0
        for seccion in secciones:
            for modulo in seccion.get("modules", []):
                if modulo.get("modname") not in _MODNAMES_CALIFICABLES:
                    continue
                items.append({"cmid": modulo.get("id"), "nombre": modulo.get("name"), "orden": orden})
                orden += 1
        return items

    # ----- Mapeo de ítems -----

    async def obtener_items_calificador(
        self, materia_id: int, cuatrimestre_id: int, usuario
    ) -> list[dict]:
        """Ítems del calificador con sugerencia (regex) o mapeo ya confirmado."""
        materia = await self._get_materia_configurada(materia_id)
        token, host = await self.token_de_usuario(usuario)
        items = await self._items_del_curso(token, host, materia.moodle_course_id)

        guardados = {
            row.moodle_cmid: row
            for row in await self.cierre_repo.get_mapping(materia_id, cuatrimestre_id)
        }

        resultado = []
        for item in items:
            guardado = guardados.get(item["cmid"])
            if guardado is not None:
                resultado.append(
                    {
                        "moodle_cmid": item["cmid"],
                        "nombre_moodle": item["nombre"],
                        "orden": item["orden"],
                        "categoria": guardado.categoria.value,
                        "unidad": guardado.unidad,
                        "opcional": guardado.opcional,
                        "confirmado": True,
                    }
                )
            else:
                sugerencia = sugerir_categoria(item["nombre"] or "")
                resultado.append(
                    {
                        "moodle_cmid": item["cmid"],
                        "nombre_moodle": item["nombre"],
                        "orden": item["orden"],
                        "categoria": sugerencia["categoria"],
                        "unidad": sugerencia["unidad"],
                        "opcional": sugerencia["opcional"],
                        "confirmado": False,
                    }
                )
        return resultado

    async def confirmar_mapping(
        self, materia_id: int, cuatrimestre_id: int, items: list[dict]
    ) -> list[dict]:
        """Persiste el mapeo confirmado por el coordinador (reemplaza el anterior)."""
        filas = await self.cierre_repo.upsert_mapping(materia_id, cuatrimestre_id, items)
        return [
            {
                "moodle_cmid": f.moodle_cmid,
                "nombre_moodle": f.nombre_moodle,
                "orden": f.orden,
                "categoria": f.categoria.value,
                "unidad": f.unidad,
                "opcional": f.opcional,
            }
            for f in filas
        ]

    # ----- Generación del cierre -----

    @staticmethod
    def _es_student(usuario: dict) -> bool:
        return any(r.get("shortname") == "student" for r in (usuario.get("roles") or []))

    @staticmethod
    def _resolver_comision(grupos: list[str], comisiones: list) -> tuple[int | None, str | None, str | None]:
        """(comision_id, comision_nombre, tutor_nombre) matcheando el nombre del grupo
        Moodle del alumno contra Comision.moodle_group_code. 0 o >1 match -> sin comisión
        (nunca se rompe la corrida por un alumno con mapeo ambiguo/roto)."""
        nombres = {g.strip().casefold() for g in grupos if g}
        matches = [
            c for c in comisiones
            if c.moodle_group_code and c.moodle_group_code.strip().casefold() in nombres
        ]
        if len(matches) != 1:
            return None, "Sin comisión asignada", None
        comision = matches[0]
        tutor_nombre = " / ".join(ct.tutor.nombre for ct in comision.tutores) or None
        return comision.id, comision.nombre, tutor_nombre

    async def generar(
        self,
        materia_id: int,
        cuatrimestre_id: int,
        umbral_tp_pct: float,
        usuario,
        reglas_override: dict | None = None,
    ) -> CierreCursadaRun:
        materia = await self._get_materia_configurada(materia_id)
        course_id = materia.moodle_course_id
        reglas = {**REGLAS_CIERRE_DEFAULT, **(reglas_override or {})}

        token, host = await self.token_de_usuario(usuario)

        items_curso = await self._items_del_curso(token, host, course_id)
        mapping_rows = await self.cierre_repo.get_mapping(materia_id, cuatrimestre_id)
        cmids_mapeados = {row.moodle_cmid for row in mapping_rows}
        faltantes = [i for i in items_curso if i["cmid"] not in cmids_mapeados]
        if faltantes:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Faltan confirmar {len(faltantes)} ítem(s) del calificador antes de "
                    "generar el cierre — revisá el mapeo primero"
                ),
            )

        por_categoria: dict[CategoriaItemCierreEnum, list] = {}
        for row in mapping_rows:
            por_categoria.setdefault(row.categoria, []).append(row)
        tp_items = [r for r in por_categoria.get(CategoriaItemCierreEnum.TP, []) if not r.opcional]
        autoeval_items = [r for r in por_categoria.get(CategoriaItemCierreEnum.AUTOEVAL, []) if not r.opcional]
        p1_items = por_categoria.get(CategoriaItemCierreEnum.PARCIAL_1, [])
        p2_items = por_categoria.get(CategoriaItemCierreEnum.PARCIAL_2, [])
        tpi_items = por_categoria.get(CategoriaItemCierreEnum.TPI, [])

        # Guard contra el mapeo confirmado que termina sin ítems en NINGUNA categoría
        # relevante (todo IGNORAR): eso produce un cierre donde absolutamente todos
        # recursan, en silencio, y es casi siempre un error de clasificación, no la
        # realidad — bloquear ahora es mucho más barato que descubrirlo en el Excel.
        if not (tp_items or autoeval_items or p1_items or p2_items or tpi_items):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=(
                    "El mapeo confirmado no tiene ningún ítem en TP/Autoevaluación/Parcial 1/"
                    "Parcial 2/TPI — revisá las categorías del mapeo antes de generar el cierre"
                ),
            )

        comisiones = await self.comision_repo.get_by_materia_con_tutores(materia_id)

        sesion = self.moodle.crear_cliente_sesion()
        try:
            await self.moodle.login_sesion(
                sesion, host, usuario.moodle_username, usuario.moodle_password_encrypted
            )
            enrolled = await self.moodle.get_enrolled_users_full(token, host, course_id, client=sesion)
            students = [u for u in enrolled if isinstance(u, dict) and self._es_student(u)]
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
        finally:
            await sesion.aclose()

        # Guard contra el export sin ninguna columna "percentage" reconocida: si hay
        # ítems de autoeval/parcial/TPI mapeados pero el export nunca trajo un % para
        # NINGUNO de ellos en NINGÚN alumno, el problema es de parseo/formato del
        # export (no de datos) — cortar acá en vez de persistir 100% RECURSA.
        cmids_esperan_pct = {r.moodle_cmid for r in (autoeval_items + p1_items + p2_items + tpi_items)}
        cmids_con_pct_real = {
            cmid for notas in notas_por_uid.values() for cmid, valores in notas.items() if "percentage" in valores
        }
        if cmids_esperan_pct and not (cmids_esperan_pct & cmids_con_pct_real):
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "El export del calificador de Moodle no trajo el % de ningún ítem de "
                    "autoevaluación/parcial/TPI mapeado — no se generó el cierre. Puede ser un "
                    "problema de formato del export; avisá para revisarlo antes de reintentar."
                ),
            )

        alumnos: list[CierreCursadaAlumno] = []
        conteos = {"PROMOCIONA": 0, "REGULARIZA": 0, "RECURSA": 0}
        for u in students:
            uid = u.get("id")
            notas = notas_por_uid.get(uid, {})

            tps = [
                {"unidad": r.unidad, "cmid": r.moodle_cmid, "resultado": _tp_resultado(notas.get(r.moodle_cmid, {}).get("real"))}
                for r in tp_items
            ]
            autoeval = [
                {"unidad": r.unidad, "pct": _parse_pct(notas.get(r.moodle_cmid, {}).get("percentage"))}
                for r in autoeval_items
            ]
            p1 = [
                {"cmid": r.moodle_cmid, "etiqueta": r.nombre_moodle, "pct": _parse_pct(notas.get(r.moodle_cmid, {}).get("percentage"))}
                for r in p1_items
            ]
            p2 = [
                {"cmid": r.moodle_cmid, "etiqueta": r.nombre_moodle, "pct": _parse_pct(notas.get(r.moodle_cmid, {}).get("percentage"))}
                for r in p2_items
            ]
            tpi = [
                {"cmid": r.moodle_cmid, "etiqueta": r.nombre_moodle, "pct": _parse_pct(notas.get(r.moodle_cmid, {}).get("percentage"))}
                for r in tpi_items
            ]

            veredicto = calcular_estado(
                {
                    "tps": [t["resultado"] for t in tps],
                    "autoeval_pcts": [a["pct"] for a in autoeval],
                    "parcial1_pcts": [x["pct"] for x in p1],
                    "parcial2_pcts": [x["pct"] for x in p2],
                    "tpi_pcts": [x["pct"] for x in tpi],
                },
                reglas,
                umbral_tp_pct,
            )

            grupos = [g.get("name") for g in (u.get("groups") or []) if g.get("name")]
            comision_id, comision_nombre, tutor_nombre = self._resolver_comision(grupos, comisiones)

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
                    tps=tps,
                    autoeval_pcts=autoeval,
                    parcial1_instancias=p1,
                    parcial2_instancias=p2,
                    tpi_instancias=tpi,
                    tp_ok=veredicto["tp_ok"],
                    autoeval_ok=veredicto["autoeval_ok"],
                    p1_max=veredicto["p1_max"],
                    p2_max=veredicto["p2_max"],
                    tpi_max=veredicto["tpi_max"],
                    estado=EstadoCierreEnum(veredicto["estado"]),
                    nota_final=veredicto["nota_final"],
                    habilitado_final=veredicto["habilitado_final"],
                )
            )

        run = CierreCursadaRun(
            materia_id=materia_id,
            cuatrimestre_id=cuatrimestre_id,
            umbral_tp_pct=umbral_tp_pct,
            reglas_snapshot=reglas,
            generado_por_id=usuario.id,
            total_alumnos=len(alumnos),
            total_promociona=conteos["PROMOCIONA"],
            total_regulariza=conteos["REGULARIZA"],
            total_recursa=conteos["RECURSA"],
        )
        run.alumnos = alumnos
        creado = await self.cierre_repo.crear_run(run)

        logger.info(
            "Cierre de cursada generado: materia=%s cuatrimestre=%s alumnos=%s "
            "(promociona=%s regulariza=%s recursa=%s)",
            materia_id, cuatrimestre_id, creado.total_alumnos,
            creado.total_promociona, creado.total_regulariza, creado.total_recursa,
        )
        await ActividadService(self.db).registrar_actividad(
            tipo=TipoActividadEnum.CIERRE_CURSADA_GENERADO,
            descripcion=(
                f"Cierre de cursada de '{materia.nombre}' generado "
                f"({creado.total_alumnos} alumnos: {creado.total_promociona} promociona, "
                f"{creado.total_regulariza} regulariza, {creado.total_recursa} recursa)"
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
