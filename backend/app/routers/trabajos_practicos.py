# app/routers/trabajos_practicos.py
"""
Trabajos prácticos router for Active-IA.

Change: `api-escritura-trabajos-practicos`.

Los tres endpoints que AI-Native necesita para publicar un TP con sus ejercicios
y sus rúbricas:

    POST   /trabajos-practicos/                 crea
    PUT    /trabajos-practicos/by-ref/{ref}     crea o actualiza (idempotente)
    GET    /trabajos-practicos/by-ref/{ref}     lo busca

**El camino que usa el cliente es el `PUT` por referencia externa**, no un
`PUT /{id}`: no guarda el id de Active-IA hasta después del primer push, así que
un `PUT /{id}` haría que la primera sincronización y las siguientes fueran dos
caminos distintos. Con `by-ref` es siempre la misma llamada.

Solo HTTP, validación y delegación (Clean Architecture): la lógica vive en
`TrabajoPracticoService`.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    ContextoUniversidad,
    get_current_user,
    get_db,
    get_universidad_activa,
)
from app.core.permissions import (
    require_any_authenticated,
    require_coordinador_or_admin,
    verificar_acceso_materia,
)
from app.models import Usuario
from app.models.enums import TipoActividadEnum
from app.models.materia import Materia
from app.models.trabajo_practico import TrabajoPractico
from app.repositories.materia_repository import MateriaRepository
from app.repositories.trabajo_practico_repository import TrabajoPracticoRepository
from app.schemas.ejercicio import EjercicioResponse
from app.schemas.trabajo_practico import (
    TrabajoPracticoResponse,
    TrabajoPracticoWriteRequest,
)
from app.services.actividad_service import ActividadService
from app.services.trabajo_practico_service import TrabajoPracticoService

router = APIRouter(prefix="/trabajos-practicos", tags=["trabajos-practicos"])


async def _resolver_materia(
    db: AsyncSession, materia_external_ref: str, ctx: ContextoUniversidad
) -> Materia:
    """Materia del TP, por su identificador externo.

    Nunca la crea implícitamente: dar de alta entidades por efecto colateral de
    una publicación es la clase de magia que después nadie puede explicar. Si no
    resuelve, el 404 nombra el identificador — el cliente publica desde una
    interfaz de docente y necesita saber cuál falló.
    """
    materia = await MateriaRepository(db).get_by_external_ref(
        materia_external_ref, universidad_id=ctx.universidad_id
    )
    if materia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No hay ninguna materia con la referencia externa "
                f"'{materia_external_ref}' en esta universidad"
            ),
        )
    return materia


def _a_response(tp: TrabajoPractico) -> TrabajoPracticoResponse:
    """Arma la respuesta, con el `rubrica_id` de cada ejercicio.

    Ese campo es el que le permite al cliente saber con qué rúbrica se corrige
    cada ejercicio. Sin él tendría que emparejar por orden o por título, que es
    adivinar.
    """
    vigentes = [e for e in tp.ejercicios if e.deleted_at is None]
    return TrabajoPracticoResponse(
        id=tp.id,
        external_ref=tp.external_ref,
        materia_id=tp.materia_id,
        titulo=tp.titulo,
        descripcion=tp.descripcion,
        ejercicios=[
            EjercicioResponse(
                id=e.id,
                external_ref=e.external_ref,
                orden=e.orden,
                titulo=e.titulo,
                peso=e.peso,
                rubrica_id=e.rubrica.id if e.rubrica else None,
                enunciado_md=e.enunciado_md,
                test_cases=e.test_cases or [],
            )
            for e in sorted(vigentes, key=lambda e: e.orden)
        ],
    )


async def _auditar(
    db: AsyncSession,
    tp: TrabajoPractico,
    conteos: dict[str, int],
    actor_id: int,
    external_ref: str,
) -> None:
    """Deja el rastro de qué publicación dejó al TP como está.

    En un upsert idempotente, la auditoría es la ÚNICA forma de reconstruirlo:
    el estado final no dice cuántos pushes hubo ni qué hizo cada uno.
    """
    await ActividadService(db).registrar_actividad(
        tipo=TipoActividadEnum.TRABAJO_PRACTICO_PUBLICADO,
        descripcion=(
            f"Publicación de '{tp.titulo}': {conteos['creados']} ejercicio(s) creado(s), "
            f"{conteos['actualizados']} actualizado(s), {conteos['dados_de_baja']} dado(s) de baja"
        ),
        entidad_id=tp.id,
        entidad_nombre=tp.titulo,
        usuario_id=actor_id,
        metadatos=json.dumps({"external_ref": external_ref, **conteos}),
    )


@router.post(
    "/",
    response_model=TrabajoPracticoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_trabajo_practico(
    datos: TrabajoPracticoWriteRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> TrabajoPracticoResponse:
    """Crea un TP con sus ejercicios anidados y la rúbrica de cada uno.

    La operación es atómica: si alguna parte del cuerpo es inválida, no queda
    persistido nada. Un TP a medio publicar es peor que ninguno — el docente ve
    tres ejercicios de cuatro y no tiene forma de saber que falta uno.
    """
    require_coordinador_or_admin(ctx)
    materia = await _resolver_materia(db, datos.materia_external_ref, ctx)
    await verificar_acceso_materia(db, current_user, ctx, materia.id)

    service = TrabajoPracticoService(db)
    tp = await service.crear(datos, materia=materia)
    await _auditar(
        db,
        tp,
        {"creados": len(datos.ejercicios), "actualizados": 0, "dados_de_baja": 0},
        current_user.id,
        datos.external_ref,
    )
    await db.commit()
    await db.refresh(tp)
    return _a_response(tp)


@router.put("/by-ref/{external_ref}", response_model=TrabajoPracticoResponse)
async def upsert_trabajo_practico_por_ref(
    external_ref: str,
    datos: TrabajoPracticoWriteRequest,
    response: Response,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> TrabajoPracticoResponse:
    """Crea el TP si no existe, o lo actualiza en su lugar si existe.

    Responde **201** cuando creó y **200** cuando actualizó, para que el cliente
    sepa qué pasó sin tener que consultar antes.

    Reenviar el mismo cuerpo produce el mismo estado final: sin esto, cada
    publicación crearía un TP nuevo y el docente terminaría eligiendo entre diez
    copias — y elegir mal no da una nota floja, corrige otra cosa.
    """
    require_coordinador_or_admin(ctx)

    if external_ref != datos.external_ref:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"La referencia externa de la URL ('{external_ref}') no coincide "
                f"con la del cuerpo ('{datos.external_ref}')"
            ),
        )

    materia = await _resolver_materia(db, datos.materia_external_ref, ctx)
    await verificar_acceso_materia(db, current_user, ctx, materia.id)

    service = TrabajoPracticoService(db)
    tp, fue_creado, conteos = await service.upsert_por_external_ref(datos, materia=materia)
    await _auditar(db, tp, conteos, current_user.id, external_ref)
    await db.commit()
    await db.refresh(tp)

    response.status_code = (
        status.HTTP_201_CREATED if fue_creado else status.HTTP_200_OK
    )
    return _a_response(tp)


@router.get("/by-ref/{external_ref}", response_model=TrabajoPracticoResponse)
async def obtener_trabajo_practico_por_ref(
    external_ref: str,
    materia_external_ref: str = Query(
        ..., description="Referencia externa de la materia que contiene el TP"
    ),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> TrabajoPracticoResponse:
    """Busca un TP por su referencia externa.

    Admite rol tutor con acceso a la materia: leer la estructura de un TP no es
    una operación de coordinación. Escribirla sí.
    """
    require_any_authenticated(current_user)
    materia = await _resolver_materia(db, materia_external_ref, ctx)
    await verificar_acceso_materia(db, current_user, ctx, materia.id)

    tp = await TrabajoPracticoRepository(db).get_by_external_ref(
        external_ref, materia_id=materia.id, universidad_id=ctx.universidad_id
    )
    if tp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay ningún trabajo práctico con la referencia '{external_ref}'",
        )
    return _a_response(tp)
