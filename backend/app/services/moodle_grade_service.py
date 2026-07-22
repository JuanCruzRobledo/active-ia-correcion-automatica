# app/services/moodle_grade_service.py
"""
MoodleGradeService — publica nota + feedback de una corrección en Moodle.

Núcleo de la Funcionalidad 2. La lógica de mapeo de nota (lo más sensible) está
aislada en `_mapear_nota` para testearla a fondo:
  - TP → escala cualitativa: nota >= 60 → índice 'Aprobado', < 60 → 'Desaprobado'.
    ⚠️ scale_id=5 está INVERTIDO (1=Aprobado, 2=Desaprobado) — ver MOODLE_SCALE_MAP.
  - No-TP → numérica: nota escalada al máximo REAL del assignment (no se asume 100).

La orquestación (cargar corrección, token, idempotencia con moodle_sync, save_grade)
se implementa en `subir_correccion` (T3.4, junto al endpoint).

Ref: PLAN_FEAT.md §5.4, §7
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import html
from dataclasses import dataclass

from app.core.comentario_templates import CIERRE_DEVOLUCION_HTML
from app.core.moodle_config import MOODLE_SCALE_MAP, UMBRAL_APROBACION_TP
from app.core.permissions import verificar_acceso_comision
from app.models.enums import MoodleSyncEstado
from app.models.moodle_sync import MoodleSync
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.moodle_sync_repository import MoodleSyncRepository
from app.services.comentario_template_service import ComentarioTemplateService
from app.services.devolucion_link_service import DevolucionLinkService
from app.services.moodle_service import (
    AssignmentGradeConfig,
    MoodleAuthError,
    MoodleConnectionError,
    MoodleService,
)


@dataclass
class PreviewCorreccion:
    """Datos para el modal de subir corrección a Moodle (antes de enviar)."""

    nota_a_enviar: str  # "Aprobado"/"Desaprobado" o el número (legible)
    nota_activeia: float
    comentario_sugerido: str
    requiere_comentario_tutor: bool
    link_devolucion: str
    ya_enviada: bool  # ya enviada por Active-IA (existe MoodleSync ENVIADO)
    ya_calificada_en_moodle: bool  # ya tiene nota en Moodle (aunque no la haya puesto Active-IA)


class GradeMapError(Exception):
    """La nota no se puede mapear a la escala del assignment (discordancia o escala no mapeada)."""


class MoodleGradeService:
    """Servicio para publicar correcciones en Moodle."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.correccion_repo = CorreccionRepository(db)
        self.moodle_sync_repo = MoodleSyncRepository(db)
        self.moodle = MoodleService(db)

    async def subir_correccion(
        self,
        *,
        correccion_id: int,
        comentario_final: str,
        usuario,
        ctx,
        base_url: str,
        forzar: bool = False,
        verificar_moodle: bool = True,
    ) -> MoodleSync:
        """Publica nota + feedback de una corrección en Moodle (idempotente + auditado).

        Si `verificar_moodle` y no `forzar`, además de la idempotencia local chequea
        que la entrega no esté YA calificada en Moodle (puesta por fuera de Active-IA):
        si lo está, lanza 409 para no pisar la nota. El masivo lo desactiva porque ya
        verifica y registra esos casos antes (evita refetch por subida).

        Lanza HTTPException con el código adecuado en cada caso de error.
        """
        correccion = await self.correccion_repo.get_by_id_with_relations(correccion_id)
        if not correccion:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrección no encontrada")

        entrega = correccion.entrega
        rubrica = entrega.rubrica
        comision = entrega.comision
        materia = comision.materia

        # Permisos: sólo tutor de la comisión (o acceso total: admin/superadmin).
        await verificar_acceso_comision(self.db, usuario, ctx, comision.id)

        # moodle_user_id: se puebla al importar desde Moodle. Sin él no se puede publicar.
        if not entrega.moodle_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La entrega no tiene moodle_user_id. Importala desde Moodle (o reimportá) "
                    "para poder publicar la corrección."
                ),
            )

        if not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail="Configurá tus credenciales Moodle en tu perfil",
            )

        if not rubrica.moodle_assign_id or not materia.moodle_course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La rúbrica o la materia no tienen configurados los IDs de Moodle",
            )

        # Idempotencia: no reenviar salvo forzar
        if not forzar:
            ya = await self.moodle_sync_repo.get_ultimo_enviado(correccion_id)
            if ya is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Esta corrección ya fue enviada a Moodle. Usá 'forzar' para reenviarla.",
                )

        moodle_host = usuario.moodle_host or ""
        try:
            token = await self.moodle.get_token(
                user_id=usuario.id,
                moodle_host=moodle_host,
                username=usuario.moodle_username,
                password_encrypted=usuario.moodle_password_encrypted,
            )
            grade_config = await self.moodle.get_assignment_grade_config(
                token, moodle_host, materia.moodle_course_id, rubrica.moodle_assign_id
            )
        except MoodleAuthError as e:
            raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e)) from e
        except MoodleConnectionError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

        if grade_config is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El assignment (cmid={rubrica.moodle_assign_id}) no se encontró en Moodle",
            )

        # Anti-pisado: si ya está calificada en Moodle (por fuera de Active-IA) y no se
        # fuerza, no la reenviamos para no sobrescribir la nota existente.
        if verificar_moodle and not forzar:
            ya_en_moodle = await self._ya_calificada_en_moodle(
                token, moodle_host, grade_config.instance_id, entrega.moodle_user_id
            )
            if ya_en_moodle:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Esta entrega ya está calificada en Moodle (por fuera de Active-IA). "
                        "Usá 'forzar' para sobrescribir la nota."
                    ),
                )

        # Mapeo de nota (escala invertida / escalado numérico). GradeMapError → 422.
        try:
            grade = self._mapear_nota(rubrica.tipo.value, float(correccion.nota), grade_config)
        except GradeMapError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

        nota_texto = self._nota_texto(grade, grade_config)
        intento = await self.moodle_sync_repo.contar_por_correccion(correccion_id) + 1

        # El comentario del tutor + cierre con el link "devolución" como hipervínculo (HTML).
        link = f"{base_url.rstrip('/')}{DevolucionLinkService.generar_path(correccion_id)}"
        feedback_html = self._construir_feedback_html(comentario_final, link)

        try:
            await self.moodle.save_grade(
                token=token,
                moodle_host=moodle_host,
                assignment_instance_id=grade_config.instance_id,
                moodle_user_id=entrega.moodle_user_id,
                grade=grade,
                feedback_comment=feedback_html,
            )
        except (MoodleAuthError, MoodleConnectionError) as e:
            # Auditar el fallo y propagar
            await self.moodle_sync_repo.create(MoodleSync(
                correccion_id=correccion_id,
                estado=MoodleSyncEstado.ERROR,
                nota_enviada=nota_texto,
                comentario_enviado=comentario_final,
                moodle_assignment_id=grade_config.instance_id,
                moodle_user_id=entrega.moodle_user_id,
                mensaje_error=str(e),
                intento=intento,
                enviado_por_id=usuario.id,
            ))
            code = (
                status.HTTP_424_FAILED_DEPENDENCY
                if isinstance(e, MoodleAuthError)
                else status.HTTP_502_BAD_GATEWAY
            )
            raise HTTPException(status_code=code, detail=str(e)) from e

        return await self.moodle_sync_repo.create(MoodleSync(
            correccion_id=correccion_id,
            estado=MoodleSyncEstado.ENVIADO,
            nota_enviada=nota_texto,
            comentario_enviado=comentario_final,
            moodle_assignment_id=grade_config.instance_id,
            moodle_user_id=entrega.moodle_user_id,
            intento=intento,
            enviado_por_id=usuario.id,
        ))

    async def preview_correccion(
        self,
        *,
        correccion_id: int,
        usuario,
        ctx,
        base_url: str,
    ) -> PreviewCorreccion:
        """Calcula lo que se enviaría a Moodle SIN enviarlo (para el modal)."""
        correccion = await self.correccion_repo.get_by_id_with_relations(correccion_id)
        if not correccion:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrección no encontrada")

        entrega = correccion.entrega
        rubrica = entrega.rubrica
        comision = entrega.comision
        materia = comision.materia

        await verificar_acceso_comision(self.db, usuario, ctx, comision.id)

        if not usuario.moodle_username or not usuario.moodle_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail="Configurá tus credenciales Moodle en tu perfil",
            )
        if not rubrica.moodle_assign_id or not materia.moodle_course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La rúbrica o la materia no tienen configurados los IDs de Moodle",
            )

        moodle_host = usuario.moodle_host or ""
        try:
            token = await self.moodle.get_token(
                user_id=usuario.id,
                moodle_host=moodle_host,
                username=usuario.moodle_username,
                password_encrypted=usuario.moodle_password_encrypted,
            )
            grade_config = await self.moodle.get_assignment_grade_config(
                token, moodle_host, materia.moodle_course_id, rubrica.moodle_assign_id
            )
        except MoodleAuthError as e:
            raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e)) from e
        except MoodleConnectionError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

        if grade_config is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El assignment (cmid={rubrica.moodle_assign_id}) no se encontró en Moodle",
            )

        try:
            grade = self._mapear_nota(rubrica.tipo.value, float(correccion.nota), grade_config)
        except GradeMapError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

        link = f"{base_url.rstrip('/')}{DevolucionLinkService.generar_path(correccion_id)}"
        render = ComentarioTemplateService.render(
            tipo_rubrica=rubrica.tipo.value,
            nota=float(correccion.nota),
            nombre_alumno=entrega.alumno_nombre,
        )
        ya = await self.moodle_sync_repo.get_ultimo_enviado(correccion_id)
        ya_en_moodle = await self._ya_calificada_en_moodle(
            token, moodle_host, grade_config.instance_id, entrega.moodle_user_id
        )

        return PreviewCorreccion(
            nota_a_enviar=self._nota_texto(grade, grade_config),
            nota_activeia=float(correccion.nota),
            comentario_sugerido=render.comentario,
            requiere_comentario_tutor=render.requiere_comentario_tutor,
            link_devolucion=link,
            ya_enviada=ya is not None,
            ya_calificada_en_moodle=ya_en_moodle,
        )

    async def _ya_calificada_en_moodle(
        self, token: str, moodle_host: str, instance_id: int, moodle_user_id: int | None
    ) -> bool:
        """True si el alumno ya tiene una calificación en este assignment de Moodle.

        Criterio consistente con el resto de la app: existe grade con timemodified > 0.
        """
        if not moodle_user_id:
            return False
        grades_full = await self.moodle.get_grades_full(token, moodle_host, instance_id)
        return MoodleService.es_calificacion_real(grades_full.get(moodle_user_id))

    @staticmethod
    def _construir_feedback_html(comentario_usuario: str, link: str) -> str:
        """Arma el feedback HTML: mensaje del tutor + cierre con 'devolución' como hipervínculo.

        El comentario del tutor se escapa (texto plano → HTML) y los saltos de línea se
        convierten en <br>. El link va como href del texto 'devolución' (no la URL cruda).
        """
        cierre = CIERRE_DEVOLUCION_HTML.format(link=html.escape(link, quote=True))
        cuerpo = html.escape(comentario_usuario or "").replace("\n", "<br>")
        if cuerpo.strip():
            return f"{cuerpo}<br><br>{cierre}"
        return cierre

    @staticmethod
    def _nota_texto(grade: float, grade_config: AssignmentGradeConfig) -> str:
        """Representación legible de la nota enviada (para auditoría)."""
        if grade_config.tipo == "escala":
            scale = MOODLE_SCALE_MAP.get(grade_config.scale_id) or {}
            items = scale.get("items") or []
            idx = int(grade) - 1
            if 0 <= idx < len(items):
                return items[idx]
            return f"índice {int(grade)}"
        return f"{grade:g}"

    @staticmethod
    def _mapear_nota(
        tipo_rubrica: str,
        nota: float,
        grade_config: AssignmentGradeConfig,
    ) -> float:
        """Traduce la nota 0-100 de Active-IA a la nota que espera Moodle.

        Lanza GradeMapError si el tipo de escala real no coincide con lo esperado
        para el tipo de rúbrica, o si la escala cualitativa no está mapeada.
        """
        if tipo_rubrica == "TP":
            if grade_config.tipo != "escala":
                raise GradeMapError(
                    "La rúbrica es TP pero el assignment en Moodle no usa escala cualitativa "
                    f"(tipo real: {grade_config.tipo}). No se envía para no calificar mal."
                )
            scale = MOODLE_SCALE_MAP.get(grade_config.scale_id)
            if not scale:
                raise GradeMapError(
                    f"La escala de Moodle (scale_id={grade_config.scale_id}) no está mapeada "
                    "en Active-IA. Configurala en MOODLE_SCALE_MAP antes de enviar."
                )
            indice = scale["aprobado"] if nota >= UMBRAL_APROBACION_TP else scale["desaprobado"]
            return float(indice)

        # No-TP → numérica, escalada al máximo real del assignment
        if grade_config.tipo != "numerica":
            raise GradeMapError(
                "La rúbrica no es TP pero el assignment en Moodle no usa escala numérica "
                f"(tipo real: {grade_config.tipo})."
            )
        grade_max = grade_config.grade_max or 100.0
        return round(nota / 100.0 * grade_max, 2)
