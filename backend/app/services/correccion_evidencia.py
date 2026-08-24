# app/services/correccion_evidencia.py
"""
Verificación de la evidencia citada por el motor de corrección.

Change: `motor-anti-falsos-positivos`, bloque 3.

El bloque 2 le pide al motor que cite el código que respalda cada puntaje. Acá se
comprueba que esa cita EXISTA. Sin esta parte, pedir evidencia sería otra regla
declarada que el motor puede no honrar — exactamente el error del bug 2, donde la
rúbrica pedía una penalización del 30% y el modelo aplicó 0%.

Ataca los bugs 4 y 5, que son el mismo mecanismo: el criterio se cierra por
reconocimiento léxico y no por verificación. 100/100 a una entrega donde ningún
producto quedaba vinculado a ninguna categoría; puntaje completo a una "búsqueda"
que era `if puntajes[i] == 990`. Afirmar que el vínculo está no cuesta nada;
inventar código que exista literal en la entrega, sí.

**Degrada, no anula.** Esto es una heurística textual, no un analizador
sintáctico: puede dar falso negativo cuando el modelo cita código real pero
reformateado por él. Anular por un falso negativo desaprobaría a alguien por un
error NUESTRO, que es peor que el problema que venimos a resolver. Por eso el
criterio baja a la mitad de su peso y queda en WARNING, nunca en 0.

Vive en su propio módulo y no dentro de `correccion_service` porque ese archivo ya
supera holgadamente el máximo de 500 LOC del proyecto, y porque estas funciones
son puras y se testean sin montar una corrección entera.
"""

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# Nota que se agrega al feedback del criterio degradado. El tutor tiene que poder
# distinguir "el alumno no lo hizo" de "el motor no pudo probar que lo hizo".
_NOTA_DEGRADACION = (
    " [Revisión automática: la evidencia citada para este criterio no se encontró "
    "en el código entregado, así que el puntaje se acotó. Verificá a mano antes de "
    "publicar la nota.]"
)

_ESPACIOS = re.compile(r"[ \t\r\n]+")


@dataclass
class ResultadoEvidencias:
    """Criterios ya procesados, más las señales para el log.

    **`sin_cita` y `cita_no_verificada` se tratan DISTINTO, y la diferencia
    importa muchísimo.**

    - `cita_no_verificada`: el motor citó algo que NO está en el código. Eso es
      una afirmación falsa y comprobable → se degrada.
    - `sin_cita`: el motor omitió el campo. Eso NO se degrada.

    El motivo es el modo de fallo. Si degradáramos por omisión y el modelo dejara
    de emitir `evidencia` —por un cambio de versión, por un prompt más largo que
    le corre la atención, por lo que sea— TODAS las notas se cortarían a la mitad
    en silencio y de golpe. Un fallo catastrófico causado por nosotros, no por los
    alumnos.

    Degradar solo la cita falsa deja un hueco conocido: el motor puede evitar la
    verificación omitiendo el campo. Pero eso es MEDIBLE (`sin_cita` lo cuenta) y
    se arregla en el prompt. Entre un agujero medible y un desastre silencioso, el
    agujero medible.
    """

    criterios: list[dict[str, Any]]
    # Citó algo que no aparece en el código. Se degrada.
    cita_no_verificada: list[str] = field(default_factory=list)
    # Omitió el campo teniendo puntaje > 0. NO se degrada; se mide.
    sin_cita: list[str] = field(default_factory=list)
    # A los que efectivamente se les bajó el puntaje.
    degradados: list[str] = field(default_factory=list)
    # Denominador de la tasa: criterios que PODÍAN verificarse (excluye los exentos).
    total_verificables: int = 0

    @property
    def no_verificados(self) -> list[str]:
        """Unión de los dos casos — la métrica de salud del motor."""
        return self.cita_no_verificada + self.sin_cita


def normalizar_para_comparar(texto: str | None) -> str:
    """Colapsa todo el espaciado a un solo espacio, conservando el resto.

    Sensible a mayúsculas A PROPÓSITO: en casi todos los lenguajes `Cupo` y `cupo`
    son identificadores distintos, y una cita que cambia la capitalización no es
    la misma línea de código.
    """
    if not texto:
        return ""
    return _ESPACIOS.sub(" ", texto).strip()


def verificar_evidencia(cita: str | None, codigo: str | None) -> bool:
    """True si la cita aparece en el código, salvo diferencias de espaciado.

    Comparación por subcadena sobre el texto normalizado. No se parsea nada: es
    deliberadamente simple, porque una verificación que el motor pueda satisfacer
    reformateando sería inútil, y una que exija coincidencia byte a byte daría
    falsos negativos por la reindentación del propio modelo.
    """
    cita_norm = normalizar_para_comparar(cita)
    codigo_norm = normalizar_para_comparar(codigo)
    if not cita_norm or not codigo_norm:
        return False
    return cita_norm in codigo_norm


def _esta_exento(criterio: dict[str, Any]) -> bool:
    """Un criterio cerrado en 0 no tiene nada que citar.

    Degradarlo sería castigar dos veces lo mismo: ya perdió todos sus puntos.
    """
    return Decimal(str(criterio.get("puntaje_obtenido", 0) or 0)) <= 0


def evaluar_evidencias(
    criterios: list[dict[str, Any]],
    *,
    codigo: str | None,
    pesos_por_criterio: dict[str, Decimal] | None = None,
    degradar: bool = True,
) -> ResultadoEvidencias:
    """Verifica la evidencia de cada criterio y degrada los que no la respalden.

    `degradar=False` cubre los dos casos donde la verificación no es concluyente y
    bajar el puntaje sería injusto:

    - **Corrección de PDF**: no hay código consolidado contra el cual comparar.
    - **Código truncado**: la cita puede estar en la parte que no le llegó al
      modelo, y el corte lo hicimos nosotros.

    En ambos se registra igual en `no_verificados`, para no perder la métrica.
    """
    pesos = pesos_por_criterio or {}
    salida: list[dict[str, Any]] = []
    cita_no_verificada: list[str] = []
    sin_cita: list[str] = []
    degradados: list[str] = []
    verificables = 0

    for criterio in criterios:
        c = dict(criterio)
        crit_id = c.get("id") or ""

        if _esta_exento(c):
            salida.append(c)
            continue

        verificables += 1
        cita = c.get("evidencia")

        # Omitió el campo: se mide, NO se degrada. Ver el docstring de
        # ResultadoEvidencias — degradar por omisión convertiría un modelo que
        # deja de emitir el campo en un recorte del 50% a toda la cohorte.
        if not (cita or "").strip():
            sin_cita.append(crit_id)
            logger.warning(
                "Criterio %s con puntaje pero SIN cita de evidencia: no se degrada, "
                "se registra. Si esto pasa seguido, el prompt dejó de funcionar.",
                crit_id,
            )
            salida.append(c)
            continue

        if verificar_evidencia(cita, codigo):
            salida.append(c)
            continue

        cita_no_verificada.append(crit_id)
        logger.warning(
            "Evidencia no verificable en criterio %s: la cita no aparece en el "
            "código entregado (degradar=%s)",
            crit_id,
            degradar,
        )

        if not degradar:
            salida.append(c)
            continue

        peso = pesos.get(crit_id)
        if peso is None:
            peso = Decimal(str(c.get("puntaje_maximo", 0) or 0))
        techo = peso / Decimal("2")

        actual = Decimal(str(c.get("puntaje_obtenido", 0) or 0))
        # `min` y no asignación directa: degradar nunca puede SUBIR una nota.
        c["puntaje_obtenido"] = min(actual, techo)
        c["estado"] = "WARNING"
        c["feedback"] = f"{c.get('feedback', '')}{_NOTA_DEGRADACION}"
        degradados.append(crit_id)
        salida.append(c)

    total_flojos = len(cita_no_verificada) + len(sin_cita)
    if verificables and total_flojos:
        logger.warning(
            "Evidencia: %d de %d criterios verificables sin respaldo comprobable "
            "(%.0f%%) — %d con cita falsa, %d sin cita",
            total_flojos,
            verificables,
            100 * total_flojos / verificables,
            len(cita_no_verificada),
            len(sin_cita),
        )

    return ResultadoEvidencias(
        criterios=salida,
        cita_no_verificada=cita_no_verificada,
        sin_cita=sin_cita,
        degradados=degradados,
        total_verificables=verificables,
    )
