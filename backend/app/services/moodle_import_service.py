# app/services/moodle_import_service.py
"""
MoodleImportService — importa entregas pendientes desde Moodle a Active-IA.

Orquesta:
  scope (comisión/unidad | materia | tutor)
    → resolver pares (Rúbrica × Comisión) con IDs Moodle configurados
    → por cada par: resolver assignment instance + miembros del grupo
    → traer submissions con archivos (MoodleService)
    → descargar archivos y delegar a EntregaService.crear_o_actualizar_desde_bytes
    → clasificar resultado en un resumen (cargadas/duplicadas/ya_corregidas/reentregas/errores)

No descifra credenciales fuera de MoodleService; no loguea token ni archivos con token.

Ref: PLAN_FEAT.md secciones 5.2 y 6
"""

import asyncio
import io
import logging
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import AsyncIterator

from app.models.base import async_session_maker

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.comision_repository import ComisionRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.entrega_service import EntregaService
from app.services.moodle_url_parser import construir_url_entrega
from app.services.moodle_service import (
    MoodleAuthError,
    MoodleConnectionError,
    MoodleService,
    MoodleSubmission,
)

logger = logging.getLogger(__name__)


@dataclass
class ResumenImportacion:
    """Resumen del resultado de una importación desde Moodle."""

    cargadas: int = 0
    duplicadas: int = 0
    omitidas_ya_corregidas: int = 0
    reentregas: int = 0
    sin_archivos: int = 0
    # Detalle de los que entregaron SIN archivos válidos (item #5): {alumno, url_moodle}
    # para poder ir a la entrega en Moodle y avisarle al alumno.
    sin_archivos_detalle: list[dict] = field(default_factory=list)
    errores: list[dict] = field(default_factory=list)  # {"alumno": str, "motivo": str}
    detalle_por_rubrica: list[dict] = field(default_factory=list)


@dataclass
class _Par:
    """Un par Rúbrica × Comisión a importar, con su materia (para course_id)."""

    rubrica: object
    comision: object
    materia: object


class MoodleImportService:
    """Importa entregas pendientes desde Moodle reusando EntregaService."""

    # Máximo de descargas concurrentes desde Moodle (acelera "Importar todo"
    # sin saturar el servidor Moodle ni abrir cientos de conexiones a la vez).
    DOWNLOAD_CONCURRENCY = 8

    def __init__(self, db: AsyncSession):
        self.db = db
        self.moodle = MoodleService(db)
        self.entrega_service = EntregaService(db)
        self.usuario_repo = UsuarioRepository(db)
        self.comision_repo = ComisionRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.materia_repo = MateriaRepository(db)

    async def importar(
        self,
        user_id: int,
        scope: str,
        *,
        rubrica_id: int | None = None,
        comision_id: int | None = None,
        materia_id: int | None = None,
    ) -> ResumenImportacion:
        """Importa las entregas pendientes según el scope.

        scope:
          - "comision_unidad": requiere rubrica_id + comision_id.
          - "materia":         requiere materia_id.
          - "tutor":           todas las comisiones/rúbricas del tutor.
        """
        usuario = await self.usuario_repo.get_by_id(user_id)
        if not usuario or not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail="Configurá tus credenciales Moodle en tu perfil",
            )

        moodle_host = usuario.moodle_host or ""
        token = await self.moodle.get_token(
            user_id=user_id,
            moodle_host=moodle_host,
            username=usuario.moodle_username,
            password_encrypted=usuario.moodle_password_encrypted,
        )

        pares = await self._resolver_pares(
            user_id, scope, rubrica_id=rubrica_id, comision_id=comision_id, materia_id=materia_id
        )

        resumen = ResumenImportacion()
        for par in pares:
            try:
                await self._importar_par(
                    token=token,
                    moodle_host=moodle_host,
                    par=par,
                    subido_por_id=user_id,
                    resumen=resumen,
                )
            except (MoodleConnectionError, MoodleAuthError) as e:
                resumen.errores.append({
                    "alumno": "-",
                    "motivo": f"Rúbrica '{getattr(par.rubrica, 'titulo', '?')}': {e}",
                })
        return resumen

    async def importar_stream(
        self,
        user_id: int,
        scope: str,
        *,
        rubrica_id: int | None = None,
        comision_id: int | None = None,
        materia_id: int | None = None,
    ) -> AsyncIterator[dict]:
        """Versión con progreso en vivo: yield eventos {tipo:inicio|progreso|resumen}.

        Fase 1 (recolección): resuelve pares y lista las submissions a procesar → total.
        Fase 2 (procesamiento): descarga/crea en paralelo (sesión propia por tarea) y
        emite un evento 'progreso' por cada entrega terminada (as_completed).
        """
        usuario = await self.usuario_repo.get_by_id(user_id)
        if not usuario or not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise MoodleAuthError("Configurá tus credenciales Moodle en tu perfil")

        moodle_host = usuario.moodle_host or ""
        token = await self.moodle.get_token(
            user_id=user_id,
            moodle_host=moodle_host,
            username=usuario.moodle_username,
            password_encrypted=usuario.moodle_password_encrypted,
        )

        pares = await self._resolver_pares(
            user_id, scope, rubrica_id=rubrica_id, comision_id=comision_id, materia_id=materia_id
        )

        resumen = ResumenImportacion()
        trabajo: list[tuple] = []  # (rubrica, comision, alumno_nombre, sub)

        # ── Fase 1a: resolver instance + miembros por par y AGRUPAR por assignment ──
        # Una rúbrica con N comisiones comparte el MISMO assignment de Moodle: así
        # consultamos sus submissions una sola vez (no N veces).
        grupos: dict[int, dict] = {}  # instance_id -> {rubrica, course_id, comisiones:[(comision, members)]}
        for par in pares:
            try:
                cmid_map = await self.moodle._get_course_assignment_map(
                    token, moodle_host, par.materia.moodle_course_id
                )
                instance_id = cmid_map.get(par.rubrica.moodle_assign_id)
                if not instance_id:
                    resumen.errores.append({
                        "alumno": "-",
                        "motivo": f"Rúbrica '{par.rubrica.titulo}': cmid {par.rubrica.moodle_assign_id} no encontrado en Moodle",
                    })
                    continue
                members = await self.moodle.get_group_members_map(
                    token, moodle_host, par.materia.moodle_course_id, par.comision.moodle_group_id
                )
            except (MoodleConnectionError, MoodleAuthError) as e:
                resumen.errores.append({
                    "alumno": "-",
                    "motivo": f"Rúbrica '{par.rubrica.titulo}': {e}",
                })
                continue

            grupo = grupos.setdefault(
                instance_id,
                {"rubrica": par.rubrica, "course_id": par.materia.moodle_course_id, "comisiones": []},
            )
            grupo["comisiones"].append((par.comision, members))

        # ── Fase 1b: traer submissions por assignment ÚNICO, en PARALELO, con progreso ──
        total_assignments = len(grupos)
        yield {"tipo": "preparando", "listos": 0, "total": total_assignments}

        sem_prep = asyncio.Semaphore(self.DOWNLOAD_CONCURRENCY)

        async def _fetch_grupo(instance_id: int, info: dict):
            union_members: set[int] = set()
            for _comision, members in info["comisiones"]:
                union_members |= set(members.keys())
            async with sem_prep:
                try:
                    subs = await self.moodle.get_submissions_with_files(
                        token, moodle_host, instance_id, union_members
                    )
                    return (info, subs, None)
                except (MoodleConnectionError, MoodleAuthError) as e:
                    return (info, None, e)

        prep_tasks = [asyncio.create_task(_fetch_grupo(iid, info)) for iid, info in grupos.items()]
        listos = 0
        for fut in asyncio.as_completed(prep_tasks):
            info, subs, err = await fut
            listos += 1
            yield {"tipo": "preparando", "listos": listos, "total": total_assignments}
            if err is not None:
                resumen.errores.append({
                    "alumno": "-",
                    "motivo": f"Rúbrica '{info['rubrica'].titulo}': {err}",
                })
                continue
            for sub in subs:
                # Asignar cada submission a la comisión a la que pertenece el alumno.
                comision_match = None
                alumno = f"Usuario {sub.userid}"
                for comision, members in info["comisiones"]:
                    if sub.userid in members:
                        comision_match = comision
                        fullname = members.get(sub.userid, "")
                        alumno = " ".join(fullname.split()).title() or alumno
                        break
                if comision_match is None:
                    continue
                if not sub.files:
                    resumen.sin_archivos += 1
                    resumen.sin_archivos_detalle.append({
                        "alumno": alumno,
                        "url_moodle": construir_url_entrega(
                            moodle_host, info["rubrica"].moodle_assign_id, sub.userid
                        ),
                    })
                    continue
                trabajo.append((info["rubrica"], comision_match, alumno, sub))

        total = len(trabajo)
        yield {"tipo": "inicio", "total": total}

        if total == 0:
            yield {"tipo": "resumen", **asdict(resumen)}
            return

        # ── Fase 2: procesamiento paralelo con progreso ──
        sem = asyncio.Semaphore(self.DOWNLOAD_CONCURRENCY)
        lock = asyncio.Lock()

        async def _procesar(item: tuple) -> None:
            rubrica, comision, alumno_nombre, sub = item
            async with sem:
                # Sesión propia por tarea (la AsyncSession no admite concurrencia).
                async with async_session_maker() as db:
                    entrega_service = EntregaService(db)
                    existente = await entrega_service.verificar_entrega_existente(
                        rubrica.id, alumno_nombre
                    )
                    if existente is not None:
                        async with lock:
                            if existente.status == "ya_corregida":
                                if self._es_reentrega(sub, existente.correccion_actualizada_en):
                                    resumen.reentregas += 1
                                else:
                                    resumen.omitidas_ya_corregidas += 1
                            else:
                                resumen.duplicadas += 1
                        return

                    try:
                        contenido_bytes, archivo_nombre = await self._obtener_bytes(
                            token, sub, alumno_nombre
                        )
                    except MoodleConnectionError as e:
                        async with lock:
                            resumen.errores.append(
                                {"alumno": alumno_nombre, "motivo": f"Descarga falló: {e}"}
                            )
                        return

                    res = await entrega_service.crear_o_actualizar_desde_bytes(
                        comision_id=comision.id,
                        rubrica_id=rubrica.id,
                        alumno_nombre=alumno_nombre,
                        archivo_nombre=archivo_nombre,
                        contenido_bytes=contenido_bytes,
                        subido_por_id=user_id,
                        moodle_user_id=sub.userid,
                        modo_consolidacion=getattr(rubrica, "modo_consolidacion", None) or "solo_codigo",
                        extensiones_personalizadas=getattr(rubrica, "extensiones_personalizadas", None),
                    )
                    async with lock:
                        if res.status == "creada":
                            resumen.cargadas += 1
                        elif res.status == "duplicada":
                            resumen.duplicadas += 1
                        elif res.status == "ya_corregida":
                            if self._es_reentrega(sub, res.correccion_actualizada_en):
                                resumen.reentregas += 1
                            else:
                                resumen.omitidas_ya_corregidas += 1
                        else:
                            resumen.errores.append(
                                {"alumno": alumno_nombre, "motivo": res.detalle or "error"}
                            )

        tasks = [asyncio.create_task(_procesar(it)) for it in trabajo]
        procesadas = 0
        for fut in asyncio.as_completed(tasks):
            await fut
            procesadas += 1
            yield {"tipo": "progreso", "procesadas": procesadas, "total": total}

        yield {"tipo": "resumen", **asdict(resumen)}

    async def _resolver_pares(
        self,
        user_id: int,
        scope: str,
        *,
        rubrica_id: int | None,
        comision_id: int | None,
        materia_id: int | None,
    ) -> list[_Par]:
        """Resuelve los pares Rúbrica × Comisión con IDs Moodle, según el scope.

        Sigue el mismo criterio que get_pendientes: sólo comisiones del tutor con
        moodle_group_id y rúbricas activas con moodle_assign_id.
        """
        if scope == "comision_unidad" and (not rubrica_id or not comision_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scope 'comision_unidad' requiere rubrica_id y comision_id",
            )
        if scope == "materia" and not materia_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scope 'materia' requiere materia_id",
            )

        # Comisiones del tutor con moodle_group_id (ARCH-001: vía repo, con scope opcional)
        comisiones = await self.comision_repo.get_moodle_habilitadas_de_tutor(
            user_id,
            comision_id=comision_id if scope == "comision_unidad" else None,
            materia_id=materia_id if scope == "materia" else None,
        )
        if not comisiones:
            return []

        materia_ids = list({c.materia_id for c in comisiones})

        rubricas = await self.rubrica_repo.get_moodle_habilitadas_por_materias(
            materia_ids,
            rubrica_id=rubrica_id if scope == "comision_unidad" else None,
        )

        materias = await self.materia_repo.get_by_ids(materia_ids)
        materias_by_id = {m.id: m for m in materias}

        pares: list[_Par] = []
        for r in rubricas:
            materia = materias_by_id.get(r.materia_id)
            if not materia or not materia.moodle_course_id:
                continue
            for c in comisiones:
                if c.materia_id == r.materia_id:
                    pares.append(_Par(rubrica=r, comision=c, materia=materia))
        return pares

    async def _importar_par(
        self,
        *,
        token: str,
        moodle_host: str,
        par: _Par,
        subido_por_id: int,
        resumen: ResumenImportacion,
    ) -> None:
        rubrica, comision, materia = par.rubrica, par.comision, par.materia

        cmid_map = await self.moodle._get_course_assignment_map(
            token, moodle_host, materia.moodle_course_id
        )
        instance_id = cmid_map.get(rubrica.moodle_assign_id)
        if not instance_id:
            resumen.errores.append({
                "alumno": "-",
                "motivo": f"Rúbrica '{rubrica.titulo}': cmid {rubrica.moodle_assign_id} no encontrado en el curso Moodle",
            })
            return

        members = await self.moodle.get_group_members_map(
            token, moodle_host, materia.moodle_course_id, comision.moodle_group_id
        )
        submissions = await self.moodle.get_submissions_with_files(
            token, moodle_host, instance_id, set(members.keys())
        )

        # 1) VERIFICAR EXISTENCIA PRIMERO (consulta barata a la DB, SIN descargar).
        #    Sólo se descargarán de Moodle las entregas que realmente faltan, evitando
        #    re-descargar en cada corrida lo que ya está subido/corregido.
        nuevas: list[tuple[MoodleSubmission, str]] = []
        for sub in submissions:
            fullname = members.get(sub.userid, "")
            alumno_nombre = " ".join(fullname.split()).title() or f"Usuario {sub.userid}"

            if not sub.files:
                resumen.sin_archivos += 1
                resumen.sin_archivos_detalle.append({
                    "alumno": alumno_nombre,
                    "url_moodle": construir_url_entrega(
                        moodle_host, rubrica.moodle_assign_id, sub.userid
                    ),
                })
                continue

            existente = await self.entrega_service.verificar_entrega_existente(
                rubrica.id, alumno_nombre
            )
            if existente is not None:
                if existente.status == "ya_corregida":
                    if self._es_reentrega(sub, existente.correccion_actualizada_en):
                        resumen.reentregas += 1
                    else:
                        resumen.omitidas_ya_corregidas += 1
                else:  # "duplicada"
                    resumen.duplicadas += 1
                continue

            nuevas.append((sub, alumno_nombre))

        # 2) DESCARGAR SÓLO LAS NUEVAS, EN PARALELO (I/O de red, el cuello de botella).
        sem = asyncio.Semaphore(self.DOWNLOAD_CONCURRENCY)

        async def _descargar(sub: MoodleSubmission, alumno_nombre: str):
            async with sem:
                try:
                    contenido_bytes, archivo_nombre = await self._obtener_bytes(
                        token, sub, alumno_nombre
                    )
                    return (sub, alumno_nombre, contenido_bytes, archivo_nombre, None)
                except MoodleConnectionError as e:
                    return (sub, alumno_nombre, None, None, f"Descarga falló: {e}")

        descargas = await asyncio.gather(*[_descargar(s, n) for s, n in nuevas])

        # 3) PERSISTENCIA SECUENCIAL (la AsyncSession no admite escrituras concurrentes).
        cargadas_par = 0
        for sub, alumno_nombre, contenido_bytes, archivo_nombre, error in descargas:
            if error is not None:
                resumen.errores.append({"alumno": alumno_nombre, "motivo": error})
                continue

            res = await self.entrega_service.crear_o_actualizar_desde_bytes(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=alumno_nombre,
                archivo_nombre=archivo_nombre,
                contenido_bytes=contenido_bytes,
                subido_por_id=subido_por_id,
                moodle_user_id=sub.userid,
                # El modo de consolidación lo define la rúbrica (no se asume solo_codigo).
                modo_consolidacion=getattr(rubrica, "modo_consolidacion", None) or "solo_codigo",
                extensiones_personalizadas=getattr(rubrica, "extensiones_personalizadas", None),
            )

            if res.status == "creada":
                resumen.cargadas += 1
                cargadas_par += 1
            elif res.status == "duplicada":
                resumen.duplicadas += 1
            elif res.status == "ya_corregida":
                if self._es_reentrega(sub, res.correccion_actualizada_en):
                    resumen.reentregas += 1
                else:
                    resumen.omitidas_ya_corregidas += 1
            else:  # "error"
                resumen.errores.append({"alumno": alumno_nombre, "motivo": res.detalle or "error"})

        resumen.detalle_por_rubrica.append({
            "rubrica_id": rubrica.id,
            "titulo": rubrica.titulo,
            "comision_id": comision.id,
            "cargadas": cargadas_par,
        })

    async def _obtener_bytes(
        self, token: str, sub: MoodleSubmission, alumno_nombre: str
    ) -> tuple[bytes, str]:
        """Descarga el/los archivo(s) de la submission. Si hay varios, los consolida en un ZIP."""
        if len(sub.files) == 1:
            f = sub.files[0]
            return await self.moodle.download_submission_file(token, f.fileurl), f.filename

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sub.files:
                data = await self.moodle.download_submission_file(token, f.fileurl)
                zf.writestr(f.filename, data)
        return buffer.getvalue(), f"{alumno_nombre}_moodle.zip"

    @staticmethod
    def _es_reentrega(sub: MoodleSubmission, correccion_actualizada_en: datetime | None) -> bool:
        """True si el alumno entregó en Moodle DESPUÉS de la última corrección en Active-IA."""
        if correccion_actualizada_en is None or not sub.timemodified:
            return False
        sub_dt = datetime.utcfromtimestamp(sub.timemodified)
        return sub_dt > correccion_actualizada_en
