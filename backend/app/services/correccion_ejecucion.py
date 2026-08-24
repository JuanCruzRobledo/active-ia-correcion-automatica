# app/services/correccion_ejecucion.py
"""
Uso del resultado de ejecución de tests en la corrección.

Change: `correccion-por-ejercicio-con-tests`, bloque 4.

**La garantía que pidió AI-Native, textual**: "con `compila: false`, no cierren
criterios del tipo 'el programa funciona'. Ninguna corrida los respalda."

Y la decisión que define este módulo: **eso NO puede vivir en el prompt.**
Ponerlo ahí sería repetir exactamente el bug 2 — la rúbrica pedía una
penalización del 30% y el motor aplicó 0%. De este motor ya está medido que no
honra reglas declaradas en su propia rúbrica, así que una garantía declarativa no
es una garantía.

Para hacerlo determinístico hace falta un dato que SOLO la rúbrica tiene: cuál de
sus criterios necesita que el programa corra. El backend no puede inferirlo — "usó
la interfaz o enumeró los tipos concretos" no depende de la ejecución; "produce la
salida esperada", sí. De ahí `Criterio.depende_de_ejecucion`.

**Lo que NO se fuerza, y es igual de importante:**

- `compila: true` con `0/6` → no se fuerza nada. Es la distinción que el cliente
  agregó el 2026-08-19: no compilar es un punto y coma, compilar y fallar todo es
  un programa que corre y hace otra cosa. Forzar los dos borraría la diferencia
  que motivó el pedido.
- Sin `resultado_tests` → no se fuerza nada. Un cliente que no ejecute código no
  puede ser penalizado por no ejecutarlo.
- Rúbrica sin criterios marcados → no se fuerza nada. Si nadie marcó, la garantía
  no aplica; no porque no queramos darla, sino porque no hay con qué distinguir
  un criterio de diseño de uno de funcionamiento.
"""

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

_FEEDBACK_SIN_COMPILAR = (
    "Este criterio requiere que el programa se ejecute, y el código no compila, "
    "así que ninguna corrida puede respaldarlo."
)


def _ids_que_dependen_de_ejecucion(criterios_rubrica: list[dict[str, Any]] | None) -> set[str]:
    """Ids de los criterios que la RÚBRICA marcó como dependientes de ejecución.

    Tolera rúbricas anteriores al change, donde la clave ni siquiera existe.
    """
    return {
        c.get("id")
        for c in (criterios_rubrica or [])
        if c.get("id") and c.get("depende_de_ejecucion") is True
    }


def forzar_criterios_de_ejecucion(
    criterios_evaluados: list[Any],
    *,
    resultado_tests: Any | None,
    criterios_rubrica: list[dict[str, Any]] | None,
) -> tuple[list[Any], list[str]]:
    """Cierra en 0 los criterios que dependen de ejecución cuando el código no compila.

    Devuelve `(criterios, ids_forzados)`. El forzado descarta el puntaje que haya
    puesto el modelo: si no compila, no hay corrida que lo respalde, sin importar
    cuán convencido esté el motor.

    Se aplica ANTES de la suma de la nota, para que el 0 sea el que entra en el
    cálculo y no un ajuste cosmético posterior.
    """
    if resultado_tests is None or getattr(resultado_tests, "compila", True):
        return list(criterios_evaluados), []

    marcados = _ids_que_dependen_de_ejecucion(criterios_rubrica)
    if not marcados:
        logger.info(
            "Código que no compila, pero la rúbrica no marca ningún criterio como "
            "dependiente de ejecución: no se fuerza nada. Cargá "
            "`depende_de_ejecucion` en la rúbrica para que la garantía aplique."
        )
        return list(criterios_evaluados), []

    error = getattr(resultado_tests, "error_compilacion", None)
    detalle = f" Error del compilador: {error}" if error else ""

    salida: list[Any] = []
    forzados: list[str] = []

    for criterio in criterios_evaluados:
        crit_id = getattr(criterio, "id", None)
        if crit_id not in marcados:
            salida.append(criterio)
            continue

        # `model_copy` en vez de mutar: los criterios evaluados pueden venir
        # compartidos con otras estructuras del flujo.
        actualizado = criterio.model_copy(
            update={
                "puntaje_obtenido": Decimal("0"),
                "estado": "ERROR",
                "feedback": f"{_FEEDBACK_SIN_COMPILAR}{detalle}",
            }
        )
        salida.append(actualizado)
        forzados.append(crit_id)

    if forzados:
        logger.warning(
            "Código que no compila: %d criterio(s) dependiente(s) de ejecución "
            "cerrado(s) en 0 (%s)",
            len(forzados),
            ", ".join(forzados),
        )

    return salida, forzados
