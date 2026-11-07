"""Orquestación de la edición manual, separada del flujo de corrección IA."""

from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from app.schemas.correccion import CorreccionResponse, CorreccionUpdate
from app.services.edicion_subcriterios import preparar_criterios_editados
from app.services.politica_entrega import aplicar_politica_correccion


async def editar_correccion_manual(
    service: Any, correccion_id: int, data: CorreccionUpdate, editado_por_id: int,
) -> CorreccionResponse:
    """Validar todo el comando antes de mutar y persistir la corrección."""
    correccion = await service.correccion_repo.get_by_id(correccion_id)
    if not correccion:
        raise HTTPException(status_code=404, detail="Corrección no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    documento = correccion.criterios_json or {}
    politica_anterior = documento.get("politica_entrega", {})
    academic = politica_anterior.get("nota_academica", correccion.nota)
    criterios = None
    if "criterios" in update_data:
        criterios = preparar_criterios_editados(
            update_data["criterios"], documento.get("criterios", []),
        )
        criterios = jsonable_encoder(criterios, custom_encoder={Decimal: float})

    # La consulta también sucede antes de mutar, para evitar cambios parciales.
    entrega = await service.entrega_repo.get_by_id(correccion.entrega_id)
    analisis = getattr(entrega, "analisis_archivos", None) or politica_anterior
    rubrica = None
    if (analisis or {}).get("rutas_penalizables") and getattr(entrega, "rubrica_id", None):
        rubrica = await service.rubrica_repo.get_by_id(entrega.rubrica_id)
    correccion.nota = Decimal(str(update_data.get("nota", academic)))
    if criterios is not None:
        correccion.criterios_json = {**documento, "criterios": criterios}
    if "nota_antes_penalizaciones" in update_data:
        value = update_data["nota_antes_penalizaciones"]
        correccion.nota_antes_penalizaciones = Decimal(str(value)) if value is not None else None
    if "condicion_desaprobacion_aplicada" in update_data:
        correccion.condicion_desaprobacion_aplicada = update_data["condicion_desaprobacion_aplicada"] or None
    if "penalizaciones_aplicadas" in update_data:
        correccion.penalizaciones_aplicadas = update_data["penalizaciones_aplicadas"] or []
    for field in ("fortalezas", "recomendaciones", "comentario_general"):
        if field in update_data:
            setattr(correccion, field, update_data[field])
    aplicar_politica_correccion(
        correccion, analisis, nota_academica=correccion.nota,
        tipo_rubrica=rubrica.tipo if rubrica else None,
        mostrar_recomendacion_archivos=data.mostrar_recomendacion_archivos,
    )
    correccion.editado_manualmente = True
    correccion.corregido_por_id = editado_por_id
    updated = await service.correccion_repo.update(correccion)
    return await service._build_correccion_response(updated)
