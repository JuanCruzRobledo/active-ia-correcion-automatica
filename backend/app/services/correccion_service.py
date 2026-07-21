# app/services/correccion_service.py
"""
Correccion service for Active-IA.

Business logic for AI-powered correction operations.
Handles integration with N8N and Gemini for automatic evaluation.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 8
Ref: docs/specs/10-INTEGRACIONES.md
Ref: skills/correccion-ia/SKILL.md
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import async_session_maker

logger = logging.getLogger(__name__)


from app.core.error_catalog import (
    ERROR_API_KEY_INVALID,
    ERROR_IA_RESPUESTA_INVALIDA,
    ERROR_N8N,
    ERROR_N8N_TIMEOUT,
    ERROR_OVERLOADED,
    ERROR_RATE_LIMIT,
    ERROR_SIN_CREDITOS,
    mensaje_error,
)
from app.core.exceptions import (
    APIKeyInvalidError,
    InsufficientCreditsError,
    ModelOverloadedError,
    N8NError,
    N8NTimeoutError,
    QuotaExceededError,
    ValidationError,
)
from app.core.security import decrypt_api_key
from app.integrations import openrouter_client
from app.integrations.gemini_correction_client import GeminiCorrectionClient
from app.models.correccion import Correccion, CorreccionHistorial
from app.models.enums import EstadoEntregaEnum, TipoActividadEnum
from app.repositories.correccion_historial_repository import (
    CorreccionHistorialRepository,
)
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.correccion import (
    CorreccionCreate,
    CorreccionHistorialItem,
    CorreccionHistorialResponse,
    CorreccionListItem,
    CorreccionResponse,
    CorreccionUpdate,
    CorregirLoteRequest,
    CorregirLoteResponse,
    GeminiResponse,
)
from app.services.actividad_service import ActividadService


def _techo_de_condicion(rubrica, cd_id) -> int | None:
    """IA-001: techo (nota_maxima) de una condición de desaprobación, tomado de la
    RÚBRICA (fuente autoritativa), no del modelo. None si no hay id o no existe en
    la rúbrica (el modelo pudo alucinar un id)."""
    if not cd_id:
        return None
    for cd in (getattr(rubrica, "condiciones_desaprobacion_json", None) or []):
        if cd.get("id") == cd_id:
            return cd.get("nota_maxima")
    return None


def _penalizaciones_validas(rubrica, ids) -> list[str]:
    """IA-001: filtra las penalizaciones informadas por el modelo a las que existen
    en la rúbrica (defensa contra ids alucinados). No alteran la nota (ya están en
    los criterios); son solo auditoría/display."""
    validos = {p.get("id") for p in (getattr(rubrica, "penalizaciones_json", None) or [])}
    return [i for i in (ids or []) if i in validos]


def _nota_deterministica(criterios_evaluados, gemini_response, rubrica):
    """IA-001: calcula la nota final en el BACKEND, no confía en la aritmética del
    modelo. Devuelve (nota_final, nota_antes_penalizaciones, condicion_aplicada,
    penalizaciones_aplicadas).

    - suma = sum(criterios) (ya refleja las penalizaciones, que el prompt aplica
      reduciendo el puntaje del criterio afectado).
    - si el modelo señaló una CD que existe en la rúbrica: nota = min(suma, techo),
      con techo tomado de la rúbrica; nota_antes = suma (para mostrar el sin-capar).
    - si no hay CD (o el id es alucinado): nota = suma, nota_antes = None.
    """
    from decimal import Decimal as _Dec

    suma = _Dec(str(sum(float(c.puntaje_obtenido) for c in criterios_evaluados)))
    cd_id = getattr(gemini_response, "condicion_desaprobacion_aplicada", None)
    techo = _techo_de_condicion(rubrica, cd_id)

    if techo is not None:
        condicion_aplicada = cd_id
        nota_antes = suma
        nota_final = min(suma, _Dec(str(techo)))
    else:
        condicion_aplicada = None
        nota_antes = None
        nota_final = suma

    penalizaciones = _penalizaciones_validas(
        rubrica, getattr(gemini_response, "penalizaciones_aplicadas", None)
    )
    return nota_final, nota_antes, condicion_aplicada, penalizaciones


def _snapshot_de_correccion(
    c: Correccion, reemplazada_por_id: int | None
) -> CorreccionHistorial:
    """
    CRUD-003: foto de una corrección saliente antes de reemplazarla al recorregir.

    Copia por VALOR: el CorreccionHistorial resultante NO depende de que `c` siga
    viva en la sesión tras el delete. Requiere que `raw_response` ya esté cargada
    (get_by_entrega_id(load_raw=True)) porque es deferred.

    Preserva `editado_manualmente` (lo más importante ante un reclamo académico) y
    usa el `created_at` original como `correccion_creada_en` ("cuándo se calificó
    por primera vez", no cuándo se archivó).
    """
    return CorreccionHistorial(
        entrega_id=c.entrega_id,
        nota=c.nota,
        criterios_json=c.criterios_json,
        fortalezas=c.fortalezas,
        recomendaciones=c.recomendaciones,
        comentario_general=c.comentario_general,
        nota_antes_penalizaciones=c.nota_antes_penalizaciones,
        condicion_desaprobacion_aplicada=c.condicion_desaprobacion_aplicada,
        penalizaciones_aplicadas=c.penalizaciones_aplicadas,
        editado_manualmente=c.editado_manualmente,
        raw_response=c.raw_response,
        corregido_por_id=c.corregido_por_id,
        correccion_creada_en=c.created_at,
        reemplazada_por_id=reemplazada_por_id,
    )


def _marcar_entrega_error(entrega, code: str, provider: str = "gemini") -> None:
    """Marca una entrega en ERROR con el detalle traducido (item #1).

    Guarda el código del catálogo + el mensaje claro (adaptado al proveedor activo)
    + el timestamp, para que el frontend muestre QUÉ pasó (no un ERROR seco) y para
    resumir las corridas masivas.
    """
    entrega.estado = EstadoEntregaEnum.ERROR
    entrega.error_code = code
    entrega.error_mensaje = mensaje_error(code, provider)
    entrega.error_at = datetime.utcnow()


def _limpiar_entrega_error(entrega) -> None:
    """Limpia el detalle de error (al corregir con éxito)."""
    entrega.error_code = None
    entrega.error_mensaje = None
    entrega.error_at = None


def _subcriterios_para_json(subcriterios) -> list[dict] | None:
    """Serializa `subcriterios_evaluados` para `criterios_json` (JSONB).

    Convierte los Decimal de puntaje a float (igual que se hace al nivel de
    criterio) para que el dict sea JSON-serializable. Devuelve None si no hay
    desglose (rubricas v1 o corrección vieja) — no se persiste una lista vacía
    ni una clave con valor engañoso.
    """
    if not subcriterios:
        return None
    resultado = []
    for sub in subcriterios:
        sub_dict = dict(sub) if isinstance(sub, dict) else sub
        resultado.append(
            {
                "id": sub_dict["id"],
                "puntaje_obtenido": float(sub_dict["puntaje_obtenido"]),
                "puntaje_maximo": float(sub_dict["puntaje_maximo"]),
                "estado": sub_dict["estado"],
                "feedback": sub_dict["feedback"],
            }
        )
    return resultado


class CorreccionService:
    """Service for AI-powered correction operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize correccion service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.correccion_repo = CorreccionRepository(db)
        self.correccion_historial_repo = CorreccionHistorialRepository(db)
        self.entrega_repo = EntregaRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.usuario_repo = UsuarioRepository(db)
        self.gemini_client = GeminiCorrectionClient()

    async def corregir_individual(
        self,
        entrega_id: int,
        api_key_encrypted: str,
        corregido_por_id: int,
        provider: str = "gemini",
    ) -> CorreccionResponse:
        """
        Correct a single entrega using AI.

        Args:
            entrega_id: ID of the entrega to correct.
            api_key_encrypted: Encrypted API key (del proveedor activo).
            corregido_por_id: ID of user performing correction.
            provider: Proveedor de corrección ("gemini" | "openrouter"). Rutea
                al webhook de n8n correspondiente.

        Returns:
            CorreccionResponse with correction data.

        Raises:
            HTTPException 404: Entrega or Rubrica not found.
            HTTPException 400: Invalid entrega state or missing data.
            HTTPException 502: N8N/Gemini error.
        """
        # Get entrega with relations. load_contenido=True: la corrección arma el payload
        # para la IA leyendo contenido_consolidado / pdf_contenido_b64 (columnas deferidas
        # por PERF-002/PERF-006), así que hay que cargarlas con undefer en esta query.
        entrega = await self.entrega_repo.get_by_id_with_relations(
            entrega_id, load_contenido=True
        )
        if not entrega:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrega no encontrada",
            )

        # La corrección de PDF todavía solo existe en el workflow de Gemini Studio.
        # En modo OpenRouter avisamos claro en vez de mandar la key al workflow equivocado.
        if entrega.archivo_tipo == "pdf" and provider == "openrouter":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La corrección de PDF todavía no está disponible en modo OpenRouter. "
                    "Cambiá a Gemini Studio en tu perfil para corregir PDFs."
                ),
            )

        # Validate entrega has content appropriate for its type
        if entrega.archivo_tipo == "pdf":
            if not entrega.pdf_contenido_b64:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La entrega PDF no tiene contenido disponible para corrección",
                )
        else:
            if not entrega.contenido_preview:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La entrega no tiene contenido consolidado",
                )

        # Get rubrica
        rubrica = await self.rubrica_repo.get_active_by_id(entrega.rubrica_id)
        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rúbrica no encontrada o inactiva",
            )

        # Decrypt API key
        try:
            api_key = decrypt_api_key(api_key_encrypted)
        except Exception:
            # No exponemos el detalle de crypto al cliente (posible rotación de
            # ENCRYPTION_KEY): va al log; el usuario recibe un mensaje accionable.
            logger.exception(
                "Error al desencriptar la API Key del usuario %s", corregido_por_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo procesar tu API Key. Reconfigurala en tu perfil.",
            )

        # Build payload for N8N and call appropriate webhook before updating state
        # (to avoid lazy loading issues after the state update)
        if entrega.archivo_tipo == "pdf":
            payload = self._build_pdf_correction_payload(entrega, rubrica, api_key)
        else:
            payload = self._build_correction_payload(entrega, rubrica, api_key)

        # IA-003: reclamo ATÓMICO en vez de un set no atómico. Evita que un doble
        # click / retry / lote con la misma entrega dispare DOS llamadas al LLM: el
        # segundo request concurrente no reclama y recibe 409 (sin gastar tokens).
        if not await self.entrega_repo.reclamar_para_correccion(entrega_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta entrega ya está siendo corregida (en proceso). Esperá a que termine.",
            )
        entrega.estado = EstadoEntregaEnum.PENDIENTE  # reflejar en memoria

        # Call the appropriate AI provider directly (Gemini or OpenRouter)
        try:
            if entrega.archivo_tipo == "pdf":
                result = await self._call_ia_pdf_with_retry(payload)
            else:
                result = await self._call_ia_with_retry(payload, provider=provider)
        except N8NTimeoutError:
            logger.warning(
                f"Timeout de {provider} corrigiendo entrega {entrega_id}",
                exc_info=True,
            )
            _marcar_entrega_error(entrega, ERROR_N8N_TIMEOUT, provider)
            await self.entrega_repo.update(entrega)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=mensaje_error(ERROR_N8N_TIMEOUT, provider),
            )
        except APIKeyInvalidError:
            _marcar_entrega_error(entrega, ERROR_API_KEY_INVALID, provider)
            await self.entrega_repo.update(entrega)
            # Marcar la API key del proveedor activo como inválida en la DB.
            usuario = await self.usuario_repo.get_by_id(corregido_por_id)
            if usuario:
                if provider == "openrouter":
                    usuario.openrouter_api_key_valid = False
                else:
                    usuario.gemini_api_key_valid = False
                await self.usuario_repo.update(usuario)
                logger.warning(
                    f"API Key de {provider} marcada como inválida para usuario {corregido_por_id}"
                )
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": ERROR_API_KEY_INVALID,
                    "message": mensaje_error(ERROR_API_KEY_INVALID, provider),
                },
            )
        except InsufficientCreditsError as e:
            # Sin créditos (OpenRouter): la key es válida, pero no se puede corregir.
            # Devolvemos 402 para que la masiva CORTE el lote (no tiene sentido seguir).
            _marcar_entrega_error(entrega, ERROR_SIN_CREDITOS, provider)
            await self.entrega_repo.update(entrega)
            logger.warning(
                f"Sin créditos en {provider} corrigiendo entrega {entrega_id}: {e}"
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": ERROR_SIN_CREDITOS,
                    "message": mensaje_error(ERROR_SIN_CREDITOS, provider),
                },
            )
        except QuotaExceededError as e:
            _marcar_entrega_error(entrega, ERROR_RATE_LIMIT, provider)
            await self.entrega_repo.update(entrega)
            logger.warning(
                f"Rate limit de {provider} alcanzado corrigiendo entrega {entrega_id}: {e}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": ERROR_RATE_LIMIT,
                    "message": mensaje_error(ERROR_RATE_LIMIT, provider),
                },
            )
        except ModelOverloadedError as e:
            _marcar_entrega_error(entrega, ERROR_OVERLOADED, provider)
            await self.entrega_repo.update(entrega)
            logger.warning(
                f"Modelo de {provider} sobrecargado corrigiendo entrega {entrega_id}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": ERROR_OVERLOADED,
                    "message": mensaje_error(ERROR_OVERLOADED, provider),
                },
            )
        except N8NError as e:
            # El str(e) puede traer el body crudo del proveedor: va SOLO al log.
            logger.warning(
                f"Error del proveedor {provider} corrigiendo entrega {entrega_id}: {e}",
                exc_info=True,
            )
            _marcar_entrega_error(entrega, ERROR_N8N, provider)
            await self.entrega_repo.update(entrega)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=mensaje_error(ERROR_N8N, provider),
            )

        # Parse and validate Gemini response
        try:
            gemini_response = self._parse_gemini_response(result)
        except ValidationError as e:
            # El detalle de validación Pydantic (potencialmente enorme) va SOLO al log.
            logger.warning(
                f"Respuesta inválida de {provider} corrigiendo entrega {entrega_id}: {e.message}",
                exc_info=True,
            )
            _marcar_entrega_error(entrega, ERROR_IA_RESPUESTA_INVALIDA, provider)
            await self.entrega_repo.update(entrega)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=mensaje_error(ERROR_IA_RESPUESTA_INVALIDA, provider),
            )

        # Check if correction already exists (re-correction case).
        # CRUD-003: load_raw=True para poder snapshotear el crudo ANTES del delete.
        existing_correccion = await self.correccion_repo.get_by_entrega_id(
            entrega_id, load_raw=True
        )

        if existing_correccion:
            # CRUD-003: versionar la corrección saliente antes de destruirla, para
            # poder reconstruir la nota anterior ante un reclamo. El snapshot se
            # construye leyendo los campos AHORA (existing está vivo), después se
            # borra, después se persiste — así el delete no expira datos que aún
            # necesito (evita MissingGreenlet en async).
            nota_anterior = existing_correccion.nota
            snapshot = _snapshot_de_correccion(
                existing_correccion, reemplazada_por_id=corregido_por_id
            )
            await self.correccion_repo.delete(existing_correccion)
            await self.correccion_historial_repo.create(snapshot)

            await ActividadService(self.db).registrar_actividad(
                tipo=TipoActividadEnum.CORRECCION_RECORREGIDA,
                descripcion=(
                    f"Recorrección de la entrega {entrega_id} "
                    f"(nota anterior: {nota_anterior})"
                ),
                entidad_id=entrega_id,
                entidad_nombre=f"entrega {entrega_id}",
                usuario_id=corregido_por_id,
            )

        # Convert CriterioGeminiSchema to CriterioEvaluado
        from app.schemas.correccion import CriterioEvaluado, SubcriterioEvaluado
        from decimal import Decimal as Dec

        def _subcriterios_evaluados_de(c) -> list[SubcriterioEvaluado] | None:
            """Convierte subcriterios_evaluados (RoundedInt, nivel Gemini) a
            SubcriterioEvaluado (Decimal, nivel API/persistencia). Ausente en
            rubricas v1 o si la IA lo omite — no rompe el parseo (D6)."""
            if not c.subcriterios_evaluados:
                return None
            return [
                SubcriterioEvaluado(
                    id=sub.id,
                    puntaje_obtenido=Dec(str(sub.puntaje_obtenido)),
                    puntaje_maximo=Dec(str(sub.puntaje_maximo)),
                    estado=sub.estado,
                    feedback=sub.feedback,
                )
                for sub in c.subcriterios_evaluados
            ]

        criterios_evaluados = [
            CriterioEvaluado(
                id=c.id if c.id is not None else str(i),
                nombre=c.nombre,
                puntaje_obtenido=Dec(str(c.puntaje_obtenido)),
                puntaje_maximo=Dec(str(c.puntaje_maximo)),
                estado=c.estado,
                feedback=c.feedback,
                subcriterios_evaluados=_subcriterios_evaluados_de(c),
            )
            for i, c in enumerate(gemini_response.criterios)
        ]

        # IA-001: la nota final la calcula el BACKEND determinísticamente
        # (min(suma, techo) con el techo de la RÚBRICA), no se confía en la
        # aritmética del modelo ni en gemini_response.nota. El modelo solo identifica
        # qué condición de desaprobación se cumple.
        nota_final, nota_antes, condicion_aplicada, penalizaciones = _nota_deterministica(
            criterios_evaluados, gemini_response, rubrica
        )

        # Create new correction
        correccion_data = CorreccionCreate(
            entrega_id=entrega_id,
            nota=nota_final,
            nota_antes_penalizaciones=nota_antes,
            condicion_desaprobacion_aplicada=condicion_aplicada,
            penalizaciones_aplicadas=penalizaciones,
            criterios=criterios_evaluados,
            fortalezas=gemini_response.fortalezas,
            recomendaciones=gemini_response.recomendaciones,
            comentario_general=gemini_response.comentario_general,
            corregido_por_id=corregido_por_id,
            raw_response=result,
        )

        # Convert to SQLAlchemy model - map 'criterios' to 'criterios_json'
        data_dict = correccion_data.model_dump()
        criterios_list = data_dict.pop('criterios')  # Remove 'criterios'

        # Convert Decimal to float for JSON serialization
        criterios_for_json = []
        for c in criterios_list:
            criterio_dict = dict(c) if isinstance(c, dict) else c
            criterio_dict['puntaje_obtenido'] = float(criterio_dict['puntaje_obtenido'])
            criterio_dict['puntaje_maximo'] = float(criterio_dict['puntaje_maximo'])
            criterio_dict['subcriterios_evaluados'] = _subcriterios_para_json(
                criterio_dict.get('subcriterios_evaluados')
            )
            criterios_for_json.append(criterio_dict)

        data_dict['criterios_json'] = {
            "criterios": criterios_for_json  # Store as JSON structure with float values
        }

        correccion = Correccion(**data_dict)
        created_correccion = await self.correccion_repo.create(correccion)

        # Update entrega state to CORREGIDA y limpiar cualquier error previo (item #1).
        entrega.estado = EstadoEntregaEnum.CORREGIDA
        _limpiar_entrega_error(entrega)
        await self.entrega_repo.update(entrega)

        # Return response
        return await self._build_correccion_response(created_correccion)

    async def encolar_lote(
        self,
        data: CorregirLoteRequest,
    ) -> list[int]:
        """
        Validate and return IDs for background processing.

        Args:
            data: Batch correction request data.

        Returns:
            List of entrega IDs to be processed asynchronously.
        """
        return list(data.entrega_ids)

    async def recorregir(
        self,
        entrega_id: int,
        api_key_encrypted: str,
        corregido_por_id: int,
        provider: str = "gemini",
    ) -> CorreccionResponse:
        """
        Re-correct an entrega (replaces existing correction).

        Args:
            entrega_id: ID of the entrega to re-correct.
            api_key_encrypted: Encrypted API key (del proveedor activo).
            corregido_por_id: ID of user performing re-correction.
            provider: Proveedor de corrección (rutea el webhook).

        Returns:
            CorreccionResponse with new correction data.
        """
        # Re-correction is handled by corregir_individual
        # It automatically deletes the old correction
        return await self.corregir_individual(
            entrega_id=entrega_id,
            api_key_encrypted=api_key_encrypted,
            corregido_por_id=corregido_por_id,
            provider=provider,
        )

    async def editar_correccion(
        self,
        correccion_id: int,
        data: CorreccionUpdate,
        editado_por_id: int,
    ) -> CorreccionResponse:
        """
        Manually edit a correction.

        Args:
            correccion_id: ID of the correction to edit.
            data: Update data.
            editado_por_id: ID of user editing.

        Returns:
            CorreccionResponse with updated correction.

        Raises:
            HTTPException 404: Correction not found.
        """
        correccion = await self.correccion_repo.get_by_id(correccion_id)
        if not correccion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Corrección no encontrada",
            )

        # Update fields
        update_data = data.model_dump(exclude_unset=True)

        if "nota" in update_data:
            correccion.nota = Decimal(str(update_data["nota"]))

        # Handle criterios: frontend sends 'criterios' but DB field is 'criterios_json'
        if "criterios" in update_data:
            # Convert list of CriterioEvaluado to criterios_json format
            criterios_list = update_data["criterios"]
            # Convert Decimal to float for JSON serialization
            criterios_serialized = [
                {
                    "id": c["id"],
                    "nombre": c["nombre"],
                    "puntaje_obtenido": float(c["puntaje_obtenido"]),
                    "puntaje_maximo": float(c["puntaje_maximo"]),
                    "estado": c["estado"],
                    "feedback": c["feedback"],
                    "subcriterios_evaluados": _subcriterios_para_json(
                        c.get("subcriterios_evaluados")
                    ),
                }
                for c in criterios_list
            ]
            correccion.criterios_json = {"criterios": criterios_serialized}

        if "nota_antes_penalizaciones" in update_data:
            val = update_data["nota_antes_penalizaciones"]
            correccion.nota_antes_penalizaciones = Decimal(str(val)) if val is not None else None

        if "condicion_desaprobacion_aplicada" in update_data:
            correccion.condicion_desaprobacion_aplicada = update_data["condicion_desaprobacion_aplicada"] or None

        if "penalizaciones_aplicadas" in update_data:
            correccion.penalizaciones_aplicadas = update_data["penalizaciones_aplicadas"] or []

        if "fortalezas" in update_data:
            correccion.fortalezas = update_data["fortalezas"]

        if "recomendaciones" in update_data:
            correccion.recomendaciones = update_data["recomendaciones"]

        if "comentario_general" in update_data:
            correccion.comentario_general = update_data["comentario_general"]

        # Mark as manually edited
        correccion.editado_manualmente = True
        correccion.corregido_por_id = editado_por_id

        updated_correccion = await self.correccion_repo.update(correccion)
        return await self._build_correccion_response(updated_correccion)

    async def obtener_correccion(self, correccion_id: int) -> CorreccionResponse:
        """
        Get a correction by ID.

        Args:
            correccion_id: Correction's database ID.

        Returns:
            CorreccionResponse with correction data.

        Raises:
            HTTPException 404: Correction not found.
        """
        correccion = await self.correccion_repo.get_by_id_with_relations(
            correccion_id
        )
        if not correccion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Corrección no encontrada",
            )

        return await self._build_correccion_response(correccion)

    async def obtener_por_entrega(self, entrega_id: int) -> CorreccionResponse:
        """
        Get correction for a specific entrega.

        Args:
            entrega_id: Entrega's database ID.

        Returns:
            CorreccionResponse with correction data.

        Raises:
            HTTPException 404: Correction not found.
        """
        correccion = await self.correccion_repo.get_by_entrega_id_with_relations(
            entrega_id
        )
        if not correccion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay corrección para esta entrega",
            )

        return await self._build_correccion_response(correccion)

    async def obtener_historial_correcciones(
        self, entrega_id: int
    ) -> CorreccionHistorialResponse:
        """
        CRUD-003: versiones históricas de las correcciones de una entrega (las que
        fueron reemplazadas al recorregir), de la más reciente a la más vieja.
        NO expone raw_response (forense). Lista vacía si nunca se recorrigió.
        """
        versiones = await self.correccion_historial_repo.list_by_entrega(entrega_id)
        items = [
            CorreccionHistorialItem(
                id=v.id,
                nota=float(v.nota),
                editado_manualmente=v.editado_manualmente,
                comentario_general=v.comentario_general,
                corregido_por_nombre=v.corregido_por.nombre if v.corregido_por else None,
                reemplazada_por_nombre=(
                    v.reemplazada_por.nombre if v.reemplazada_por else None
                ),
                correccion_creada_en=v.correccion_creada_en,
                reemplazada_en=v.reemplazada_en,
            )
            for v in versiones
        ]
        return CorreccionHistorialResponse(
            entrega_id=entrega_id,
            total_versiones=len(items),
            versiones=items,
        )

    def _build_correction_payload(
        self,
        entrega: Any,
        rubrica: Any,
        api_key: str,
    ) -> dict[str, Any]:
        """
        Build payload for N8N text correction webhook (/webhook/corregir).

        Used for code submissions (zip, txt, individual code files).

        Args:
            entrega: Entrega object with contenido_consolidado or contenido_preview.
            rubrica: Rubrica object.
            api_key: Decrypted Gemini API key.

        Returns:
            Payload dictionary for N8N.
        """
        # Use contenido_consolidado if available, fallback to preview for old entregas
        codigo = entrega.contenido_consolidado or entrega.contenido_preview

        return {
            "codigo": codigo,
            "rubrica": {
                "titulo": rubrica.titulo,
                "descripcion": rubrica.descripcion or "",
                "tipo": rubrica.tipo.value,
                "puntaje_maximo": rubrica.puntaje_maximo,
                "metadata": rubrica.metadata_json or {},
                "criterios": rubrica.criterios_json or [],
                "penalizaciones": rubrica.penalizaciones_json or [],
                "condiciones_desaprobacion": rubrica.condiciones_desaprobacion_json or [],
                "schema_version": rubrica.schema_version,
            },
            "api_key": api_key,
            "contexto": {
                "materia": entrega.comision.materia.nombre,
                "alumno": entrega.alumno_nombre,
            },
        }

    def _build_pdf_correction_payload(
        self,
        entrega: Any,
        rubrica: Any,
        api_key: str,
    ) -> dict[str, Any]:
        """
        Build payload for N8N PDF correction webhook (/webhook/corregir-pdf).

        Used for PDF submissions (e.g., handwritten exercises). Sends the raw
        PDF in Base64 instead of text, so N8N can pass it directly to Gemini's
        vision API.

        Args:
            entrega: Entrega object with pdf_contenido_b64 populated.
            rubrica: Rubrica object.
            api_key: Decrypted Gemini API key.

        Returns:
            Payload dictionary for N8N PDF correction webhook.
        """
        return {
            "pdf_base64": entrega.pdf_contenido_b64,
            "rubrica": {
                "titulo": rubrica.titulo,
                "descripcion": rubrica.descripcion or "",
                "tipo": rubrica.tipo.value,
                "puntaje_maximo": rubrica.puntaje_maximo,
                "metadata": rubrica.metadata_json or {},
                "criterios": rubrica.criterios_json or [],
                "penalizaciones": rubrica.penalizaciones_json or [],
                "condiciones_desaprobacion": rubrica.condiciones_desaprobacion_json or [],
                "schema_version": rubrica.schema_version,
            },
            "api_key": api_key,
            "contexto": {
                "materia": entrega.comision.materia.nombre,
                "alumno": entrega.alumno_nombre,
            },
        }

    async def _call_ia_with_retry(
        self,
        payload: dict[str, Any],
        max_retries: int = 1,
        provider: str = "gemini",
    ) -> dict[str, Any]:
        """
        Call the AI provider directly (Gemini or OpenRouter) with retry logic.

        Args:
            payload: Payload to send.
            max_retries: Maximum number of retries (default: 1).
            provider: AI provider to use ("gemini" or "openrouter").

        Returns:
            AI provider response.

        Raises:
            N8NTimeoutError: If timeout occurs after retries.
            N8NError: If other error occurs after retries.
        """
        for attempt in range(max_retries + 1):
            try:
                if provider == "openrouter":
                    result = await openrouter_client.corregir(payload)
                else:
                    result = await self.gemini_client.corregir_codigo(payload)
                return result

            except APIKeyInvalidError:
                # Never retry on invalid API key — re-raise immediately
                raise

            except InsufficientCreditsError:
                # Sin créditos: reintentar no sirve — re-raise immediately
                raise

            except QuotaExceededError:
                # Never retry on rate limit — re-raise immediately
                raise

            except N8NTimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise

            except ModelOverloadedError:
                # IA-009: 503 (modelo sobrecargado) es transitorio -> reintentar con
                # backoff, igual que el timeout. Antes se caía al primer intento.
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

            except N8NError as e:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        # Should not reach here
        raise N8NError("Error inesperado en reintentos")

    async def _call_ia_pdf_with_retry(
        self,
        payload: dict[str, Any],
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """
        Call Gemini Vision PDF correction directly with retry logic.

        Args:
            payload: Payload with pdf_base64 and rubrica to send.
            max_retries: Maximum number of retries (default: 1).

        Returns:
            Gemini response with correction data.

        Raises:
            N8NTimeoutError: If timeout occurs after retries.
            N8NError: If other error occurs after retries.
        """
        for attempt in range(max_retries + 1):
            try:
                result = await self.gemini_client.corregir_pdf(payload)
                return result

            except APIKeyInvalidError:
                # Never retry on invalid API key — re-raise immediately
                raise

            except InsufficientCreditsError:
                # Sin créditos: reintentar no sirve — re-raise immediately
                raise

            except QuotaExceededError:
                # Never retry on rate limit — re-raise immediately
                raise

            except N8NTimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise

            except ModelOverloadedError:
                # IA-009: 503 (modelo sobrecargado) es transitorio -> reintentar con
                # backoff, igual que el timeout. Antes se caía al primer intento.
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

            except N8NError:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        # Should not reach here
        raise N8NError("Error inesperado en reintentos (PDF)")

    def _parse_gemini_response(self, response: dict[str, Any]) -> GeminiResponse:
        """
        Parse and validate Gemini response from N8N.

        Args:
            response: Raw response from N8N.

        Returns:
            Validated GeminiResponse.

        Raises:
            ValidationError: If response is invalid.
        """
        try:
            # Extract correction data from N8N response
            if not response.get("success"):
                error_msg = response.get("error", {}).get("message", "Error desconocido")
                raise ValidationError(
                    message=f"N8N retornó error: {error_msg}",
                    field="n8n_response",
                )

            correccion_data = response.get("correccion", {})

            # Validate with Pydantic
            gemini_response = GeminiResponse.model_validate(correccion_data)

            return gemini_response

        except Exception as e:
            raise ValidationError(
                message=f"Error parseando respuesta de Gemini: {str(e)}",
                field="gemini_response",
            )

    async def _build_correccion_response(
        self, correccion: Correccion
    ) -> CorreccionResponse:
        """
        Build CorreccionResponse from Correccion model.

        Resolves CD and penalty IDs to human-readable descriptions
        from the rubrica so the frontend can display them clearly.

        Args:
            correccion: Correccion model instance.

        Returns:
            CorreccionResponse.
        """
        # Always reload with relations to avoid lazy loading issues in async context
        correccion = await self.correccion_repo.get_by_id_with_relations(
            correccion.id
        )

        response = CorreccionResponse.model_validate(correccion)

        # Resolve CD description from rubrica
        rubrica = correccion.entrega.rubrica
        if response.condicion_desaprobacion_aplicada and rubrica:
            for cd in (rubrica.condiciones_desaprobacion_json or []):
                if cd.get("id") == response.condicion_desaprobacion_aplicada:
                    response.condicion_desaprobacion_descripcion = cd.get("condicion")
                    break

        # Resolve penalty descriptions from rubrica
        if response.penalizaciones_aplicadas and rubrica:
            for pen_id in response.penalizaciones_aplicadas:
                for p in (rubrica.penalizaciones_json or []):
                    if p.get("id") == pen_id:
                        response.penalizaciones_descripciones.append({
                            "id": pen_id,
                            "descripcion": p.get("descripcion", pen_id),
                            "descuento_porcentaje": p.get("descuento_porcentaje", 0),
                        })
                        break

        return response


async def procesar_lote_background(
    entrega_ids: list[int],
    api_key_encrypted: str,
    corregido_por_id: int,
    provider: str = "gemini",
) -> None:
    """
    Standalone background task to correct multiple entregas sequentially.

    This function runs AFTER the HTTP response has been sent to the client,
    so it must create its own database session instead of using the
    request-scoped session (which is already closed by the time this runs).

    Args:
        entrega_ids: List of entrega IDs to correct.
        api_key_encrypted: Encrypted Gemini API key.
        corregido_por_id: ID of user performing corrections.
    """
    logger.info(f"[BG] Iniciando corrección masiva de {len(entrega_ids)} entregas")

    max_retries_429 = 3
    base_backoff = 30  # seconds — gives Gemini time to reset its RPM window

    async with async_session_maker() as db:
        service = CorreccionService(db)
        exitosas = 0
        fallidas = 0
        stop_batch = False

        for entrega_id in entrega_ids:
            if stop_batch:
                break

            succeeded = False
            for attempt in range(1 + max_retries_429):
                try:
                    await service.corregir_individual(
                        entrega_id=entrega_id,
                        api_key_encrypted=api_key_encrypted,
                        corregido_por_id=corregido_por_id,
                        provider=provider,
                    )
                    exitosas += 1
                    succeeded = True
                    logger.info(f"[BG] Entrega {entrega_id} corregida exitosamente")
                    break

                except HTTPException as e:
                    if e.status_code == 402:
                        fallidas += 1
                        stop_batch = True
                        remaining = len(entrega_ids) - exitosas - fallidas
                        # 402 puede ser API_KEY_INVALID o SIN_CREDITOS (OpenRouter):
                        # logueamos el error_code real para no confundir el diagnóstico.
                        error_code = (
                            e.detail.get("error_code")
                            if isinstance(e.detail, dict)
                            else e.detail
                        )
                        logger.error(
                            f"[BG] Lote detenido por 402 ({error_code}). "
                            f"{remaining} entregas no procesadas."
                        )
                        break

                    if e.status_code == 429:
                        if attempt < max_retries_429:
                            wait = base_backoff * (attempt + 1)
                            logger.warning(
                                f"[BG] Rate limit (429) en entrega {entrega_id}. "
                                f"Reintento {attempt + 1}/{max_retries_429} en {wait}s."
                            )
                            await asyncio.sleep(wait)
                            continue

                        fallidas += 1
                        stop_batch = True
                        remaining = len(entrega_ids) - exitosas - fallidas
                        logger.error(
                            f"[BG] Rate limit persistente tras {max_retries_429} "
                            f"reintentos. Deteniendo lote. "
                            f"{remaining} entregas no procesadas."
                        )
                        break

                    fallidas += 1
                    logger.warning(
                        f"[BG] Error corrigiendo entrega {entrega_id}: {e.detail}"
                    )
                    break

                except Exception as e:
                    fallidas += 1
                    logger.error(
                        f"[BG] Error inesperado corrigiendo entrega {entrega_id}: {e}"
                    )
                    break

            # Rate limiting between corrections
            if succeeded and not stop_batch:
                await asyncio.sleep(7)

    logger.info(
        f"[BG] Corrección masiva finalizada: {exitosas} exitosas, {fallidas} fallidas"
    )


async def procesar_global_background(
    entrega_ids: list[int],
    api_key_encrypted: str,
    corregido_por_id: int,
    concurrency: int = 5,
    provider: str = "gemini",
) -> None:
    """Corrección masiva GLOBAL (cross-rúbrica) para tutores con API key paga.

    A diferencia de procesar_lote_background (secuencial con sleep para free tier),
    esta versión PARALELIZA con un semáforo (key paga tolera más RPM). Cada tarea
    usa SU PROPIA sesión de DB (la AsyncSession no admite operaciones concurrentes).

    Resiliente: un 429 reintenta con backoff; si persiste, ESA entrega falla pero el
    job continúa (no aborta todo). Las que fallan quedan en estado ERROR (corregir_individual).
    """
    logger.info(
        f"[BG-GLOBAL] Iniciando corrección global de {len(entrega_ids)} entregas "
        f"(concurrencia={concurrency})"
    )
    max_retries_429 = 3
    base_backoff = 30
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _corregir_uno(entrega_id: int) -> str:
        async with sem:
            for attempt in range(1 + max_retries_429):
                # Sesión propia por intento — seguro para concurrencia.
                async with async_session_maker() as db:
                    service = CorreccionService(db)
                    try:
                        await service.corregir_individual(
                            entrega_id=entrega_id,
                            api_key_encrypted=api_key_encrypted,
                            corregido_por_id=corregido_por_id,
                            provider=provider,
                        )
                        return "ok"
                    except HTTPException as e:
                        if e.status_code == 429 and attempt < max_retries_429:
                            wait = base_backoff * (attempt + 1)
                            logger.warning(
                                f"[BG-GLOBAL] Rate limit (429) en entrega {entrega_id}. "
                                f"Reintento {attempt + 1}/{max_retries_429} en {wait}s."
                            )
                            await asyncio.sleep(wait)
                            continue
                        logger.warning(
                            f"[BG-GLOBAL] Error corrigiendo entrega {entrega_id}: "
                            f"{getattr(e, 'detail', e)}"
                        )
                        return "fail"
                    except Exception as e:  # noqa: BLE001
                        logger.error(
                            f"[BG-GLOBAL] Error inesperado en entrega {entrega_id}: {e}"
                        )
                        return "fail"
            return "fail"

    resultados = await asyncio.gather(*[_corregir_uno(eid) for eid in entrega_ids])
    exitosas = resultados.count("ok")
    fallidas = len(resultados) - exitosas
    logger.info(
        f"[BG-GLOBAL] Corrección global finalizada: {exitosas} exitosas, {fallidas} fallidas"
    )
