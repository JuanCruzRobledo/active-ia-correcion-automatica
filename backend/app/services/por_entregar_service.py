# app/services/por_entregar_service.py
"""
PorEntregarService — lista las correcciones pendientes de subir a Moodle y las
sube en bloque ("Entregar todos").

A diferencia de la vista "Pendientes (por corregir)", que consulta Moodle en vivo,
el LISTADO acá es 100% local (una query a nuestra base): una corrección está
"pendiente de entregar" si su entrega está CORREGIDA, vino de Moodle y todavía no
tiene un MoodleSync ENVIADO. Sólo se toca Moodle al SUBIR.

La subida masiva delega en MoodleGradeService.subir_correccion (permisos,
idempotencia, mapeo de nota y feedback HTML ya resueltos ahí) y sólo procesa las
correcciones con comentario automático (TP); las no-TP requieren texto del tutor
y se reportan como omitidas para subir a mano.

Ref: PLAN_POR_ENTREGAR.md §4
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

from fastapi import HTTPException

from app.core.moodle_config import UMBRAL_APROBACION_TP
from app.models.base import async_session_maker
from app.models.enums import MoodleSyncEstado, RolEnum
from app.models.moodle_sync import MoodleSync
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.moodle_sync_repository import MoodleSyncRepository
from app.services.comentario_template_service import ComentarioTemplateService
from app.services.moodle_grade_service import MoodleGradeService
from app.services.moodle_service import (
    MoodleAuthError,
    MoodleConnectionError,
    MoodleService,
    es_reentrega,
)

logger = logging.getLogger(__name__)


@dataclass
class CorreccionPorEntregaItem:
    """Una corrección lista para devolver al alumno en Moodle."""

    correccion_id: int
    entrega_id: int
    alumno_nombre: str
    materia_id: int
    materia_nombre: str
    comision_id: int
    comision_nombre: str
    rubrica_id: int
    rubrica_titulo: str
    tipo_rubrica: str
    nota: float
    etiqueta_nota: str  # "Aprobado"/"Desaprobado" (TP) o el número (no-TP)
    requiere_comentario_tutor: bool
    estado_ultimo_intento: str  # "none" | "error"
    mensaje_error: str | None
    corregido_at: datetime | None


@dataclass
class PorEntregarResultado:
    """Resultado del listado para la vista 'Por entregar'."""

    items: list[CorreccionPorEntregaItem] = field(default_factory=list)
    total_pendientes: int = 0
    total_automaticas: int = 0       # TP: suben con "Entregar todos"
    total_requieren_comentario: int = 0  # no-TP: subir a mano
    no_vinculadas: int = 0           # contador informativo (excluidas)


@dataclass
class ResumenEntregaMasiva:
    """Resumen del 'Entregar todos'."""

    enviadas: int = 0
    ya_enviadas: int = 0
    ya_calificadas_en_moodle: int = 0  # detectadas ya con nota en Moodle (no se subieron)
    reenviadas_reentrega: int = 0  # re-entregas (item #3b): tenían nota pero el alumno re-entregó
    omitidas_requieren_comentario: int = 0
    errores: list[dict] = field(default_factory=list)  # {"alumno": str, "motivo": str}


class PorEntregarService:
    """Lista y sube en bloque las correcciones pendientes de entregar a Moodle."""

    # Subidas concurrentes a Moodle (cada una es save_grade + lecturas previas).
    UPLOAD_CONCURRENCY = 5

    def __init__(self, db):
        self.db = db
        self.correccion_repo = CorreccionRepository(db)
        self.moodle_sync_repo = MoodleSyncRepository(db)
        self.moodle = MoodleService(db)

    async def listar(self, usuario) -> PorEntregarResultado:
        """Arma el listado de pendientes de subir (todo local, instantáneo)."""
        es_admin = usuario.rol == RolEnum.ADMIN
        correcciones = await self.correccion_repo.get_pendientes_subida_moodle(
            usuario.id, es_admin
        )
        ids = [c.id for c in correcciones]
        estados = await self.moodle_sync_repo.get_ultimo_estado_por_correcciones(ids)

        items: list[CorreccionPorEntregaItem] = []
        for c in correcciones:
            entrega = c.entrega
            rubrica = entrega.rubrica
            comision = entrega.comision
            materia = comision.materia
            tipo = rubrica.tipo.value if hasattr(rubrica.tipo, "value") else str(rubrica.tipo)
            nota = float(c.nota)

            estado_ultimo, mensaje_error = "none", None
            ultimo = estados.get(c.id)
            if ultimo is not None:
                est, err = ultimo
                est_val = est.value if hasattr(est, "value") else str(est)
                if est_val == MoodleSyncEstado.ERROR.value:
                    estado_ultimo, mensaje_error = "error", err

            items.append(
                CorreccionPorEntregaItem(
                    correccion_id=c.id,
                    entrega_id=entrega.id,
                    alumno_nombre=entrega.alumno_nombre,
                    materia_id=materia.id,
                    materia_nombre=materia.nombre,
                    comision_id=comision.id,
                    comision_nombre=comision.nombre,
                    rubrica_id=rubrica.id,
                    rubrica_titulo=rubrica.titulo,
                    tipo_rubrica=tipo,
                    nota=nota,
                    etiqueta_nota=self._etiqueta_nota(tipo, nota),
                    requiere_comentario_tutor=(tipo != "TP"),
                    estado_ultimo_intento=estado_ultimo,
                    mensaje_error=mensaje_error,
                    corregido_at=getattr(c, "created_at", None),
                )
            )

        total = len(items)
        requieren = sum(1 for i in items if i.requiere_comentario_tutor)
        no_vinculadas = await self.correccion_repo.contar_no_vinculadas_moodle(
            usuario.id, es_admin
        )

        return PorEntregarResultado(
            items=items,
            total_pendientes=total,
            total_automaticas=total - requieren,
            total_requieren_comentario=requieren,
            no_vinculadas=no_vinculadas,
        )

    async def entregar_masivo_stream(
        self, usuario, base_url: str
    ) -> AsyncIterator[dict]:
        """Sube en bloque las correcciones de comentario automático (TP), con progreso.

        ANTES de subir, verifica contra Moodle: si una entrega YA está calificada allá
        (por fuera de Active-IA), no se reenvía — se registra como ENVIADO (para que no
        vuelva a aparecer) y se cuenta aparte. Así no se pisa una nota existente.

        Emite eventos `data: {...}`:
          - {"tipo":"inicio","total":N}        (N = las que realmente se subirán)
          - {"tipo":"progreso","procesadas":i,"total":N}
          - {"tipo":"resumen", enviadas, ya_enviadas, ya_calificadas_en_moodle,
                               omitidas_requieren_comentario, errores[]}
          - {"tipo":"error","detail":"..."}    (no se pudo obtener token Moodle)

        Las no-TP (requieren comentario del tutor) NO se tocan: se cuentan como omitidas.
        La idempotencia local y los permisos los garantiza subir_correccion.
        """
        es_admin = usuario.rol == RolEnum.ADMIN
        correcciones = await self.correccion_repo.get_pendientes_subida_moodle(
            usuario.id, es_admin
        )
        automaticas = [c for c in correcciones if self._tipo(c) == "TP"]
        requieren = sum(1 for c in correcciones if self._tipo(c) != "TP")
        resumen = ResumenEntregaMasiva(omitidas_requieren_comentario=requieren)

        if not automaticas:
            yield {"tipo": "inicio", "total": 0}
            yield {"tipo": "resumen", **_asdict_resumen(resumen)}
            return

        # ── Verificación contra Moodle: ¿cuáles ya están calificadas allá? ──
        moodle_host = usuario.moodle_host or ""
        try:
            token = await self.moodle.get_token(
                user_id=usuario.id,
                moodle_host=moodle_host,
                username=usuario.moodle_username,
                password_encrypted=usuario.moodle_password_encrypted,
            )
        except (MoodleAuthError, MoodleConnectionError) as e:
            yield {"tipo": "error", "detail": str(e)}
            return

        instancia_por_correccion, graded_lookup, sub_tm_lookup, instancias_falladas = (
            await self._prefetch_grades(token, moodle_host, automaticas)
        )

        # ── Clasificar: ya calificadas / re-entregas / no verificables / a subir ──
        a_subir: list = []
        a_resubir: list = []  # re-entregas: tenían nota pero el alumno re-entregó (item #3b)
        ya_en_moodle: list = []  # (correccion, instance_id, grade_crudo)
        for c in automaticas:
            instance_id = instancia_por_correccion.get(c.id)
            if instance_id in instancias_falladas:
                resumen.errores.append({
                    "alumno": c.entrega.alumno_nombre,
                    "motivo": "No se pudo verificar el estado en Moodle (no se subió para no pisar la nota).",
                })
                continue
            entry = (graded_lookup.get(instance_id) or {}).get(c.entrega.moodle_user_id)
            if MoodleService.es_calificacion_real(entry):
                # Ya hay nota en Moodle. Si el alumno re-entregó DESPUÉS (item #3b), subimos
                # la nota nueva igual; si no, se respeta la existente y no se toca.
                sub_tm = (sub_tm_lookup.get(instance_id) or {}).get(c.entrega.moodle_user_id)
                if es_reentrega(sub_tm, entry.get("timemodified")):
                    a_resubir.append(c)
                else:
                    ya_en_moodle.append((c, instance_id, entry.get("grade")))
            else:
                a_subir.append(c)

        # Registrar las ya-calificadas para que no reaparezcan (sin reenviar nada).
        for c, instance_id, grade_crudo in ya_en_moodle:
            await self._registrar_ya_calificada(c, instance_id, grade_crudo, usuario)
            resumen.ya_calificadas_en_moodle += 1

        total = len(a_subir) + len(a_resubir)
        yield {"tipo": "inicio", "total": total}

        if total == 0:
            yield {"tipo": "resumen", **_asdict_resumen(resumen)}
            return

        sem = asyncio.Semaphore(self.UPLOAD_CONCURRENCY)
        lock = asyncio.Lock()

        async def _subir(correccion, es_reentrega_flag: bool = False) -> None:
            alumno = correccion.entrega.alumno_nombre
            async with sem:
                # Sesión propia por tarea (la AsyncSession no admite concurrencia).
                async with async_session_maker() as db:
                    grade_service = MoodleGradeService(db)
                    render = ComentarioTemplateService.render(
                        tipo_rubrica=self._tipo(correccion),
                        nota=float(correccion.nota),
                        nombre_alumno=alumno,
                    )
                    try:
                        await grade_service.subir_correccion(
                            correccion_id=correccion.id,
                            comentario_final=render.comentario,
                            usuario=usuario,
                            base_url=base_url,
                            # Re-entrega (item #3b): forzamos para pisar la nota vieja con la
                            # nueva (el alumno re-entregó después). El resto, sin forzar.
                            forzar=es_reentrega_flag,
                            # El masivo ya verificó/registró las ya-calificadas; evitar refetch.
                            verificar_moodle=False,
                        )
                        async with lock:
                            if es_reentrega_flag:
                                resumen.reenviadas_reentrega += 1
                            else:
                                resumen.enviadas += 1
                    except HTTPException as e:
                        async with lock:
                            if e.status_code == 409:
                                resumen.ya_enviadas += 1
                            else:
                                resumen.errores.append({"alumno": alumno, "motivo": str(e.detail)})
                    except Exception as e:  # noqa: BLE001
                        logger.exception("Error subiendo corrección %s", correccion.id)
                        async with lock:
                            resumen.errores.append({"alumno": alumno, "motivo": str(e)})

        tasks = [asyncio.create_task(_subir(c)) for c in a_subir]
        tasks += [asyncio.create_task(_subir(c, es_reentrega_flag=True)) for c in a_resubir]
        procesadas = 0
        for fut in asyncio.as_completed(tasks):
            await fut
            procesadas += 1
            yield {"tipo": "progreso", "procesadas": procesadas, "total": total}

        yield {"tipo": "resumen", **_asdict_resumen(resumen)}

    async def _prefetch_grades(self, token: str, moodle_host: str, correcciones: list):
        """Resuelve el assignment instance de cada corrección y trae sus grades de Moodle.

        Devuelve (instancia_por_correccion, graded_lookup, instancias_falladas):
          - instancia_por_correccion: {correccion_id: instance_id|None}
          - graded_lookup: {instance_id: {userid: {timemodified, grade}}}
          - instancias_falladas: set de instance_id cuyo fetch de grades falló.
        """
        # cmid map por curso (cacheado en MoodleService); fallo → curso sin mapa.
        course_ids = {c.entrega.comision.materia.moodle_course_id for c in correcciones}
        cmid_maps: dict[int, dict | None] = {}
        for course_id in course_ids:
            try:
                cmid_maps[course_id] = await self.moodle._get_course_assignment_map(
                    token, moodle_host, course_id
                )
            except (MoodleConnectionError, MoodleAuthError):
                cmid_maps[course_id] = None

        instancia_por_correccion: dict[int, int | None] = {}
        for c in correcciones:
            course_id = c.entrega.comision.materia.moodle_course_id
            cmid_map = cmid_maps.get(course_id)
            assign_cmid = c.entrega.rubrica.moodle_assign_id
            instancia_por_correccion[c.id] = cmid_map.get(assign_cmid) if cmid_map else None

        instancias = {iid for iid in instancia_por_correccion.values() if iid}

        graded_lookup: dict[int, dict] = {}
        sub_tm_lookup: dict[int, dict] = {}  # {instance_id: {userid: submission timemodified}}
        instancias_falladas: set[int] = set()

        async def _fetch(instance_id: int):
            try:
                # Grades + timemodified de submissions (para detectar re-entregas, item #3b).
                full = await self.moodle.get_grades_full(token, moodle_host, instance_id)
                subs = await self.moodle.get_submission_timemod_map(
                    token, moodle_host, instance_id
                )
                return instance_id, full, subs, None
            except (MoodleConnectionError, MoodleAuthError) as e:
                return instance_id, None, None, e

        sem = asyncio.Semaphore(self.UPLOAD_CONCURRENCY)

        async def _fetch_sem(instance_id: int):
            async with sem:
                return await _fetch(instance_id)

        for instance_id, full, subs, err in await asyncio.gather(
            *[_fetch_sem(i) for i in instancias]
        ):
            if err is not None:
                instancias_falladas.add(instance_id)
            else:
                graded_lookup[instance_id] = full
                sub_tm_lookup[instance_id] = subs or {}

        return instancia_por_correccion, graded_lookup, sub_tm_lookup, instancias_falladas

    async def _registrar_ya_calificada(
        self, correccion, instance_id, grade_crudo, usuario
    ) -> None:
        """Registra un MoodleSync ENVIADO para una corrección ya calificada en Moodle.

        No reenvía nada: sólo deja constancia (para que no vuelva a aparecer como
        pendiente) de que la nota ya existía en Moodle por fuera de Active-IA.
        """
        intento = await self.moodle_sync_repo.contar_por_correccion(correccion.id) + 1
        await self.moodle_sync_repo.create(
            MoodleSync(
                correccion_id=correccion.id,
                estado=MoodleSyncEstado.ENVIADO,
                nota_enviada=self._humanizar_grade(grade_crudo),
                comentario_enviado="Detectada ya calificada en Moodle (no enviada por Active-IA).",
                moodle_assignment_id=instance_id,
                moodle_user_id=correccion.entrega.moodle_user_id,
                intento=intento,
                enviado_por_id=usuario.id,
            )
        )

    @staticmethod
    def _tipo(correccion) -> str:
        tipo = correccion.entrega.rubrica.tipo
        return tipo.value if hasattr(tipo, "value") else str(tipo)

    @staticmethod
    def _humanizar_grade(grade_crudo) -> str | None:
        """Representa el grade crudo de Moodle de forma legible para la auditoría."""
        if grade_crudo is None:
            return None
        try:
            return f"{float(grade_crudo):g}"
        except (TypeError, ValueError):
            return str(grade_crudo)

    @staticmethod
    def _etiqueta_nota(tipo_rubrica: str, nota: float) -> str:
        """Etiqueta legible local (sin ir a Moodle): TP → Aprobado/Desaprobado; resto → número."""
        if tipo_rubrica == "TP":
            return "Aprobado" if nota >= UMBRAL_APROBACION_TP else "Desaprobado"
        return f"{nota:g}"


def _asdict_resumen(r: ResumenEntregaMasiva) -> dict:
    return {
        "enviadas": r.enviadas,
        "ya_enviadas": r.ya_enviadas,
        "ya_calificadas_en_moodle": r.ya_calificadas_en_moodle,
        "reenviadas_reentrega": r.reenviadas_reentrega,
        "omitidas_requieren_comentario": r.omitidas_requieren_comentario,
        "errores": r.errores,
    }
