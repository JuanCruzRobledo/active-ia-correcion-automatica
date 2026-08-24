# app/services/correccion_ejercicio_service.py
"""
Corrección de UN ejercicio para UN alumno.

Change: `correccion-por-ejercicio-con-tests`, bloque 6.

Es la mitad que faltaba de la integración con AI-Native: hasta acá el cliente
podía PUBLICAR un TP con sus ejercicios y sus rúbricas, pero no podía pedir que
se corrija nada.

Corregir de a un ejercicio no es una comodidad de API: es lo que desactiva el
modo de fallo ya medido del motor. Con los cuatro ejercicios de un TP en un solo
archivo consolidado, una pieza del ejercicio 3 puede contar como cumplimiento de
un criterio del 1 — "distingue presencia, no vínculo". Corrigiendo de a uno, eso
desaparece por construcción.

Este servicio ORQUESTA; no corrige. La corrección la hace el motor de siempre
(`CorreccionService.corregir_individual`), que ya trae failover entre
proveedores, reclamo atómico, snapshot al historial y el cálculo determinístico
de la nota. Lo único que se agrega es el `resultado_tests`.
"""

import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import verificar_acceso_materia
from app.models.comision import Comision
from app.models.ejercicio import Ejercicio
from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum, TipoActividadEnum
from app.repositories.comision_repository import ComisionRepository
from app.repositories.ejercicio_repository import EjercicioRepository
from app.repositories.entrega_repository import EntregaRepository
from app.schemas.correccion import (
    CorreccionEjercicioRequest,
    CorreccionEjercicioResponse,
)
from app.services.actividad_service import ActividadService
from app.services.correccion_service import CorreccionService

logger = logging.getLogger(__name__)


class CorreccionEjercicioService:
    """Prepara la entrega de un ejercicio y delega la corrección al motor."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ejercicio_repo = EjercicioRepository(db)
        self.entrega_repo = EntregaRepository(db)

    async def corregir(
        self,
        *,
        ejercicio_ref: str,
        datos: CorreccionEjercicioRequest,
        usuario: Any,
        ctx: Any,
        api_key_encrypted: str,
        provider: str = "gemini",
    ) -> CorreccionEjercicioResponse:
        ejercicio = await self._resolver_ejercicio(ejercicio_ref, ctx)
        await verificar_acceso_materia(self.db, usuario, ctx, ejercicio.materia_id)

        rubrica = ejercicio.rubrica
        if rubrica is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"El ejercicio '{ejercicio_ref}' no tiene rúbrica asociada, "
                    "así que no hay contra qué corregir."
                ),
            )

        comision = await self._resolver_comision(ejercicio, datos.comision_external_ref)
        entrega = await self._preparar_entrega(datos, ejercicio=ejercicio,
                                               rubrica=rubrica, comision=comision)

        correccion = await CorreccionService(self.db).corregir_individual(
            entrega_id=entrega.id,
            api_key_encrypted=api_key_encrypted,
            corregido_por_id=usuario.id,
            provider=provider,
            resultado_tests=datos.resultado_tests,
        )

        await self._auditar(ejercicio, datos, usuario)

        return CorreccionEjercicioResponse(
            correccion_id=correccion.id,
            entrega_id=entrega.id,
            ejercicio_external_ref=ejercicio.external_ref,
            rubrica_id=rubrica.id,
            alumno_ref=datos.alumno_ref,
            nota=correccion.nota,
            criterios=list(getattr(correccion, "criterios", []) or []),
            fortalezas=list(getattr(correccion, "fortalezas", []) or []),
            recomendaciones=list(getattr(correccion, "recomendaciones", []) or []),
            comentario_general=getattr(correccion, "comentario_general", None),
            # Los criterios que se cerraron en 0 porque el código no compila. Se
            # devuelven aparte para que el cliente pueda mostrárselos distinto al
            # docente: "no lo hizo" y "no se pudo verificar porque no compila" son
            # dos cosas distintas y merecen leerse distinto.
            criterios_sin_ejecucion=list(
                getattr(correccion, "criterios_sin_ejecucion", []) or []
            ),
        )

    async def _resolver_ejercicio(self, ejercicio_ref: str, ctx: Any) -> Ejercicio:
        ejercicio = await self.ejercicio_repo.get_by_external_ref(
            ejercicio_ref, universidad_id=ctx.universidad_id
        )
        if ejercicio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No hay ningún ejercicio con la referencia '{ejercicio_ref}'",
            )
        return ejercicio

    async def _resolver_comision(
        self, ejercicio: Ejercicio, comision_external_ref: str | None
    ) -> Comision:
        """Comisión donde depositar la entrega.

        **El hueco que el pedido de AI-Native no podía ver**, porque no ve nuestro
        modelo: `entregas.comision_id` es NOT NULL y el cliente no tiene
        comisiones. Precedencia:

        1. La referencia de cohorte del cuerpo, si viene y resuelve DENTRO de la
           materia del ejercicio.
        2. La comisión de integración configurada en la materia.

        Si ninguna resuelve → 409 diciendo exactamente qué falta configurar.
        **Nunca se crea una comisión implícitamente**: dar de alta entidades por
        efecto colateral de una corrección es la clase de magia que después nadie
        puede explicar.
        """
        repo = ComisionRepository(self.db)

        if comision_external_ref:
            comision = await repo.get_by_external_ref(
                comision_external_ref, materia_id=ejercicio.materia_id
            )
            if comision is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"La referencia de comisión '{comision_external_ref}' no "
                        "corresponde a ninguna comisión de la materia de este ejercicio."
                    ),
                )
            return comision

        materia = ejercicio.materia
        comision_id = getattr(materia, "comision_integracion_id", None)
        comision = await repo.get_by_id(comision_id) if comision_id else None
        if comision is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"La materia '{materia.nombre}' no tiene configurada una "
                    "comisión de integración, y el pedido no trae referencia de "
                    "cohorte. Un administrador tiene que configurarla una vez "
                    "antes de poder corregir por esta vía."
                ),
            )
        return comision

    async def _preparar_entrega(
        self,
        datos: CorreccionEjercicioRequest,
        *,
        ejercicio: Ejercicio,
        rubrica: Any,
        comision: Comision,
    ) -> Entrega:
        """Crea la entrega, o REUSA la que ya existía para ese alumno y rúbrica.

        Reusar en vez de responder 409 es deliberado: para el cliente, reintentar
        es la misma llamada en lugar de una rama nueva. La corrección anterior no
        se pierde — el motor la snapshotea en el historial (CRUD-003).

        La clave `(rubrica_id, alumno_nombre)` es exactamente la granularidad
        correcta acá, porque cada ejercicio tiene SU rúbrica: dos ejercicios del
        mismo alumno son dos entregas distintas, sin interferir.
        """
        codigo = datos.codigo
        existente = await self.entrega_repo.get_by_rubrica_alumno(
            rubrica_id=rubrica.id, alumno_nombre=datos.alumno_ref
        )

        if existente is not None:
            existente.contenido_consolidado = codigo
            existente.contenido_preview = codigo[:500]
            existente.archivo_tamanio = len(codigo.encode("utf-8"))
            existente.estado = EstadoEntregaEnum.SUBIDA
            await self.db.flush()
            return existente

        entrega = Entrega(
            universidad_id=ejercicio.universidad_id,
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            # Literal. Active-IA NO lo resuelve a una persona ni lo cruza con
            # ningún padrón: es un pseudónimo por diseño del cliente, y esa
            # propiedad es la que hace posible el procedimiento de anonimización.
            alumno_nombre=datos.alumno_ref,
            archivo_nombre=f"{ejercicio.external_ref}.txt",
            archivo_tipo="individual",
            archivo_tamanio=len(codigo.encode("utf-8")),
            contenido_consolidado=codigo,
            contenido_preview=codigo[:500],
            archivos_incluidos=[f"{ejercicio.external_ref}.txt"],
            estado=EstadoEntregaEnum.SUBIDA,
            # Sin `subido_por_id`: no la subió una persona, la mandó un sistema.
            # Por eso el detalle de entrega tuvo que tolerar el nulo
            # (change fix-detalle-entrega-500).
        )
        self.db.add(entrega)
        await self.db.flush()
        return entrega

    async def _auditar(
        self, ejercicio: Ejercicio, datos: CorreccionEjercicioRequest, usuario: Any
    ) -> None:
        resultado = datos.resultado_tests
        await ActividadService(self.db).registrar_actividad(
            tipo=TipoActividadEnum.CORRECCION_RECORREGIDA,
            descripcion=(
                f"Corrección por ejercicio '{ejercicio.titulo}' "
                f"(alumno {datos.alumno_ref})"
            ),
            entidad_id=ejercicio.id,
            entidad_nombre=ejercicio.titulo,
            usuario_id=getattr(usuario, "id", None),
            metadatos=json.dumps(
                {
                    "ejercicio_external_ref": ejercicio.external_ref,
                    "alumno_ref": datos.alumno_ref,
                    "con_resultado_tests": resultado is not None,
                    "compila": getattr(resultado, "compila", None),
                }
            ),
        )
