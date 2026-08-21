# app/services/trabajo_practico_service.py
"""
Servicio de Trabajos Prácticos y Ejercicios.

Change: `trabajos-practicos-y-external-ref`.

Lógica de negocio, sin acceso directo a la base (Clean Architecture): las
consultas van por los repositorios.

Acá vive la traducción entre la rúbrica **plana** que manda el cliente y la
`Rubrica` **jerárquica** de Active-IA. Esa traducción es lo que permite reusar el
motor de corrección entero sin tocarlo: el ejercicio es dueño de una `Rubrica`
normal y corriente, y desde el punto de vista del corrector no se distingue de
una rúbrica cargada a mano.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ejercicio import Ejercicio
from app.models.enums import FuenteRubricaEnum, TipoRubricaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.trabajo_practico import TrabajoPractico
from app.repositories.ejercicio_repository import EjercicioRepository
from app.repositories.trabajo_practico_repository import TrabajoPracticoRepository
from app.schemas.ejercicio import CriterioEjercicioInput, EjercicioWriteRequest
from app.schemas.trabajo_practico import TrabajoPracticoWriteRequest

# `Criterio.peso` es un entero de 1 a 100 y la suma de los criterios de una
# rúbrica tiene que dar exactamente 100 (`CriteriosStructure.validar_suma_pesos`).
_TOTAL_PESO = 100


def normalizar_pesos(puntajes: list[Decimal]) -> list[int]:
    """Lleva los puntajes del cliente a pesos enteros que suman exactamente 100.

    Usa el **método del resto mayor**: reparte la parte entera de cada
    proporción y asigna los puntos sobrantes a los criterios con mayor resto
    fraccionario. Redondear cada uno por separado no garantiza que la suma
    cierre, y una rúbrica cuyos pesos no suman 100 la rechaza el propio schema
    de Active-IA.

    Raises:
        ValueError: si no existe reparto entero posible — con más de 100
            criterios en un ejercicio, alguno tendría que valer menos de 1.
    """
    if not puntajes:
        raise ValueError("La rúbrica del ejercicio no tiene criterios")

    cantidad = len(puntajes)
    if cantidad > _TOTAL_PESO:
        raise ValueError(
            f"El ejercicio tiene {cantidad} criterios y la escala de la rúbrica es "
            f"de {_TOTAL_PESO} puntos: no hay reparto entero en el que todos pesen "
            "al menos 1. Agrupá criterios antes de publicar."
        )

    total = sum(puntajes, Decimal("0"))
    if total <= 0:
        raise ValueError("Los puntajes de los criterios tienen que sumar más que cero")

    exactos = [(p / total) * Decimal(_TOTAL_PESO) for p in puntajes]
    pesos = [int(v) for v in exactos]

    # Piso de 1: un criterio con peso 0 lo rechaza `Criterio.peso` (ge=1), y
    # además sería un criterio que no puede sumar nada.
    pesos = [max(1, p) for p in pesos]

    faltante = _TOTAL_PESO - sum(pesos)
    if faltante > 0:
        # Reparto los puntos que sobran empezando por el resto más grande.
        restos = sorted(
            range(cantidad), key=lambda i: exactos[i] - int(exactos[i]), reverse=True
        )
        for i in range(faltante):
            pesos[restos[i % cantidad]] += 1
    elif faltante < 0:
        # Me pasé por el piso de 1: saco de los más pesados, sin bajar de 1.
        sobrante = -faltante
        orden = sorted(range(cantidad), key=lambda i: pesos[i], reverse=True)
        idx = 0
        while sobrante > 0:
            i = orden[idx % cantidad]
            if pesos[i] > 1:
                pesos[i] -= 1
                sobrante -= 1
            idx += 1

    return pesos


def traducir_rubrica_del_cliente(
    criterios: list[CriterioEjercicioInput],
) -> list[dict[str, Any]]:
    """Criterios planos del cliente → `criterios_json` de una `Rubrica`.

    Cada criterio del cliente se convierte en un criterio de Active-IA con **un**
    subcriterio: el modelo jerárquico exige al menos uno, con al menos una
    evidencia. La descripción del criterio cumple los dos roles, que es lo más
    fiel que se puede ser a una rúbrica que nació plana — inventar subcriterios
    que el docente no escribió sería peor.
    """
    pesos = normalizar_pesos([c.puntaje_max for c in criterios])

    salida: list[dict[str, Any]] = []
    for indice, (criterio, peso) in enumerate(zip(criterios, pesos), start=1):
        criterio_id = f"C{indice}"
        salida.append(
            {
                "id": criterio_id,
                "nombre": criterio.nombre,
                "descripcion": criterio.descripcion,
                "peso": peso,
                "subcriterios": [
                    {
                        "id": f"{criterio_id}.1",
                        "descripcion": criterio.descripcion,
                        "evidencias": [criterio.descripcion],
                    }
                ],
            }
        )
    return salida


class TrabajoPracticoService:
    """Alta, actualización y baja lógica de TPs y ejercicios."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tp_repo = TrabajoPracticoRepository(db)
        self.ejercicio_repo = EjercicioRepository(db)

    async def crear(
        self, datos: TrabajoPracticoWriteRequest, *, materia: Materia
    ) -> TrabajoPractico:
        """Crea el TP con sus ejercicios y la rúbrica de cada uno.

        No hace commit: el llamador decide la transacción, que es lo que permite
        que el alta entera sea atómica.
        """
        tp = TrabajoPractico(
            universidad_id=materia.universidad_id,
            materia_id=materia.id,
            external_ref=datos.external_ref,
            titulo=datos.titulo,
            descripcion=datos.descripcion,
        )
        await self.tp_repo.create(tp)

        for ejercicio_datos in datos.ejercicios:
            await self._crear_ejercicio(ejercicio_datos, trabajo_practico=tp, materia=materia)

        return tp

    async def upsert_por_external_ref(
        self, datos: TrabajoPracticoWriteRequest, *, materia: Materia
    ) -> tuple[TrabajoPractico, bool, dict[str, int]]:
        """Crea el TP si no existe, o lo actualiza en su lugar si existe.

        Devuelve `(tp, fue_creado, conteos)`. `conteos` trae `creados`,
        `actualizados` y `dados_de_baja` para la auditoría: en un upsert
        idempotente, el registro de auditoría es la única forma de reconstruir
        qué publicación dejó al TP como está.

        No hace commit: el llamador es dueño de la transacción, que es lo que
        hace que la operación entera sea atómica.
        """
        existente = await self.tp_repo.get_by_external_ref(
            datos.external_ref,
            materia_id=materia.id,
            universidad_id=materia.universidad_id,
        )

        if existente is None:
            tp = await self.crear(datos, materia=materia)
            return tp, True, {
                "creados": len(datos.ejercicios),
                "actualizados": 0,
                "dados_de_baja": 0,
            }

        existente.titulo = datos.titulo
        existente.descripcion = datos.descripcion
        conteos = await self._reconciliar_ejercicios(
            datos, trabajo_practico=existente, materia=materia
        )
        await self.tp_repo.save(existente)
        return existente, False, conteos

    async def _reconciliar_ejercicios(
        self,
        datos: TrabajoPracticoWriteRequest,
        *,
        trabajo_practico: TrabajoPractico,
        materia: Materia,
    ) -> dict[str, int]:
        """Empareja los ejercicios del cuerpo con los vigentes del TP.

        **Se empareja SIEMPRE por `external_ref`**, nunca por orden ni por
        título. Reordenar los ejercicios en la plataforma del cliente, o
        renombrarlos, no puede rotar ninguna asociación: las entregas y las
        correcciones cuelgan de `rubrica_id`, y un `rubrica_id` que se mueve
        deja correcciones colgando de una rúbrica que ya no corresponde a ese
        ejercicio.

        | Situación                          | Acción                              |
        |------------------------------------|-------------------------------------|
        | El `external_ref` ya existe        | Se actualiza, CONSERVANDO su rúbrica|
        | El `external_ref` no existe        | Se crea el ejercicio y su rúbrica   |
        | Un ejercicio vigente no vino       | Baja lógica, con su rúbrica         |
        """
        vigentes = await self.ejercicio_repo.listar_vigentes_de_tp(trabajo_practico.id)
        por_ref = {e.external_ref: e for e in vigentes}

        creados = 0
        actualizados = 0
        refs_del_push: set[str] = set()

        for ejercicio_datos in datos.ejercicios:
            refs_del_push.add(ejercicio_datos.external_ref)
            existente = por_ref.get(ejercicio_datos.external_ref)

            if existente is None:
                # Puede haber uno dado de baja con este mismo `external_ref`:
                # reenviarlo lo devuelve a la vida en lugar de crear un duplicado
                # (y el índice único parcial rechazaría el duplicado igual).
                revivido = await self.ejercicio_repo.get_por_ref_incluyendo_borrados(
                    ejercicio_datos.external_ref,
                    trabajo_practico_id=trabajo_practico.id,
                )
                if revivido is not None:
                    revivido.deleted_at = None
                    if revivido.rubrica is not None:
                        revivido.rubrica.activa = True
                    await self._actualizar_ejercicio(revivido, ejercicio_datos, materia=materia)
                    actualizados += 1
                else:
                    await self._crear_ejercicio(
                        ejercicio_datos, trabajo_practico=trabajo_practico, materia=materia
                    )
                    creados += 1
            else:
                await self._actualizar_ejercicio(existente, ejercicio_datos, materia=materia)
                actualizados += 1

        dados_de_baja = 0
        for ejercicio in vigentes:
            if ejercicio.external_ref not in refs_del_push:
                await self.dar_de_baja_ejercicio(ejercicio)
                dados_de_baja += 1

        return {
            "creados": creados,
            "actualizados": actualizados,
            "dados_de_baja": dados_de_baja,
        }

    async def _actualizar_ejercicio(
        self,
        ejercicio: Ejercicio,
        datos: EjercicioWriteRequest,
        *,
        materia: Materia,
    ) -> Ejercicio:
        """Actualiza el ejercicio y REESCRIBE el contenido de su rúbrica.

        La rúbrica se actualiza, nunca se reemplaza: su `id` es lo que mantiene
        vivas las entregas y correcciones ya hechas.
        """
        ejercicio.orden = datos.orden
        ejercicio.titulo = datos.titulo
        ejercicio.enunciado_md = datos.enunciado_md
        ejercicio.peso = datos.peso
        ejercicio.test_cases = [caso.a_json() for caso in datos.test_cases]

        rubrica = ejercicio.rubrica
        if rubrica is None:
            # Un ejercicio sin rúbrica no debería existir, pero si aparece uno
            # (dato viejo, alta a medias), se le crea la que le falta en vez de
            # dejarlo incorregible.
            rubrica = self._construir_rubrica(
                datos,
                ejercicio=ejercicio,
                trabajo_practico=ejercicio.trabajo_practico,
                materia=materia,
            )
            self.db.add(rubrica)
        else:
            rubrica.titulo = f"{ejercicio.trabajo_practico.titulo} — {datos.titulo}"[:200]
            rubrica.descripcion = datos.enunciado_md or datos.titulo
            rubrica.numero = datos.orden
            rubrica.criterios_json = traducir_rubrica_del_cliente(datos.rubrica.criterios)
            rubrica.activa = True

        await self.db.flush()
        return ejercicio

    async def _crear_ejercicio(
        self,
        datos: EjercicioWriteRequest,
        *,
        trabajo_practico: TrabajoPractico,
        materia: Materia,
    ) -> Ejercicio:
        ejercicio = Ejercicio(
            universidad_id=materia.universidad_id,
            materia_id=materia.id,
            trabajo_practico_id=trabajo_practico.id,
            external_ref=datos.external_ref,
            orden=datos.orden,
            titulo=datos.titulo,
            enunciado_md=datos.enunciado_md,
            peso=datos.peso,
            test_cases=[caso.a_json() for caso in datos.test_cases],
        )
        await self.ejercicio_repo.create(ejercicio)

        rubrica = self._construir_rubrica(
            datos, ejercicio=ejercicio, trabajo_practico=trabajo_practico, materia=materia
        )
        self.db.add(rubrica)
        await self.db.flush()
        return ejercicio

    def _construir_rubrica(
        self,
        datos: EjercicioWriteRequest,
        *,
        ejercicio: Ejercicio,
        trabajo_practico: TrabajoPractico,
        materia: Materia,
    ) -> Rubrica:
        """Rúbrica del ejercicio.

        `tipo`, `numero` y `anio` dejan de ser una clave de unicidad para las
        rúbricas de ejercicio (el índice único es parcial sobre
        `ejercicio_id IS NULL`), así que pasan a ser metadata: `numero` toma el
        orden del ejercicio, que es lo más informativo que hay disponible.
        """
        return Rubrica(
            universidad_id=materia.universidad_id,
            materia_id=materia.id,
            tipo=TipoRubricaEnum.TP,
            numero=ejercicio.orden,
            anio=datetime.utcnow().year,
            titulo=f"{trabajo_practico.titulo} — {datos.titulo}"[:200],
            descripcion=datos.enunciado_md or datos.titulo,
            puntaje_maximo=_TOTAL_PESO,
            metadata_json={
                "origen": "integracion_externa",
                "trabajo_practico_external_ref": trabajo_practico.external_ref,
                "ejercicio_external_ref": datos.external_ref,
            },
            criterios_json=traducir_rubrica_del_cliente(datos.rubrica.criterios),
            penalizaciones_json=[],
            condiciones_desaprobacion_json=[],
            fuente=FuenteRubricaEnum.MANUAL,
            activa=True,
            ejercicio_id=ejercicio.id,
        )

    async def dar_de_baja_ejercicio(self, ejercicio: Ejercicio) -> None:
        """Baja lógica del ejercicio Y de su rúbrica, en la misma operación.

        Sin la cascada, la rúbrica queda huérfana: visible en los listados de la
        materia y sin ejercicio que la explique.

        OJO con las dos convenciones. El proyecto marca la baja lógica de dos
        formas distintas según la entidad, y ésta es la costura donde se tocan:

        - `Ejercicio` (como `Entrega`) usa `SoftDeleteMixin` → `deleted_at`.
        - `Rubrica` NO hereda el mixin: se da de baja con `activa = False`
          (ver `RubricaRepository.soft_delete`).

        Se usa la convención de cada una en vez de agregarle `deleted_at` a
        `Rubrica`: esa columna la leen el listado de rúbricas, el selector de
        entregas y el restore, y unificarlas es un change aparte.
        """
        ejercicio.deleted_at = datetime.utcnow()
        if ejercicio.rubrica is not None:
            ejercicio.rubrica.activa = False
            ejercicio.rubrica.updated_at = datetime.utcnow()
        await self.db.flush()

    async def dar_de_baja_trabajo_practico(self, trabajo_practico: TrabajoPractico) -> None:
        """Baja lógica del TP y, en cascada, de sus ejercicios y rúbricas."""
        ejercicios = await self.ejercicio_repo.listar_vigentes_de_tp(trabajo_practico.id)
        for ejercicio in ejercicios:
            await self.dar_de_baja_ejercicio(ejercicio)

        trabajo_practico.deleted_at = datetime.utcnow()
        await self.db.flush()
