# app/core/moodle_config.py
"""
Configuración de mapeo de escalas cualitativas de Moodle, POR CAMPUS.

Las escalas de Moodle no tienen un WS simple para leer sus textos, así que el
índice de cada resultado va en config explícita (PLAN_FEAT.md §7.4).

⚠️ EL ORDEN NO ES INTUITIVO, Y EL `scale_id` NO ES GLOBAL.

Los `scale_id` son **por instancia de Moodle**, y cada universidad tiene la suya
(`Universidad.moodle_host`). El mismo número identifica escalas distintas en
campus distintos. Verificado el 2026-08-20 leyendo los dos campus:

    tup.sied.utn.edu.ar
        scale_id=5  →  Aprobado (1), Desaprobado (2)          ← INVERTIDO

    campustest.frm.utn.edu.ar
        scale_id=3  →  Aprobado (1), Desaprobado (2)          ← INVERTIDO
        scale_id=5  →  No satisfactorio (1), Satisfactorio (2),
                       Supera lo esperado (3)                 ← 3 NIVELES

Es decir: el `5` de FRM no tiene nada que ver con el `5` de TUPaD. Un mapa
global indexado solo por `scale_id` —como era esto hasta el 2026-08-20— mandaba
índice 1 para el alumno aprobado de FRM, que en ese campus significa
"No satisfactorio". Invertido, en silencio, y sin que ningún guard saltara,
porque el 5 SÍ estaba en el mapa.

Por eso la clave es `(host, scale_id)` y no `scale_id` solo, y por eso los
índices van hardcodeados y verificados campus por campus, nunca inferidos por
"lógica".

**Para dar de alta un campus nuevo**: entrar a su Moodle en
`/grade/edit/scale/index.php`, leer los ítems EN ORDEN (el primero es el índice
1) y el `id=` del enlace de editar de cada escala. No alcanza con la pantalla:
esa lista no muestra los ids.

`mod_assign_save_grade` recibe el ÍNDICE (1-based) como float.

**Escalas de más de dos niveles**: el mapeo actual es binario
(`aprobado`/`desaprobado`) porque la nota de Active-IA se compara contra un
umbral. Una escala de tres niveles como la 5 de FRM NO se puede mapear sin una
decisión de cátedra (qué nota corresponde a "Supera lo esperado"), así que
deliberadamente NO está cargada: mejor que el envío falle con un error claro a
que califique con dos de los tres niveles.
"""

MOODLE_SCALE_MAP: dict[str, dict[int, dict]] = {
    # TUPaD — confirmado en Fase 0 y revalidado el 2026-08-20.
    "tup.sied.utn.edu.ar": {
        5: {"aprobado": 1, "desaprobado": 2, "items": ["Aprobado", "Desaprobado"]},
    },
    # UTN FRM (campus de PRUEBA) — leído el 2026-08-20 de
    # campustest.frm.utn.edu.ar/grade/edit/scale/index.php
    #
    # OJO: éste es el campus de test. El de producción de FRM es otro host y va a
    # necesitar su propia entrada. Hasta que se cargue, un envío desde ahí falla
    # con error claro en vez de calificar mal — que es el comportamiento correcto.
    #
    # La escala 5 de este campus (No satisfactorio / Satisfactorio / Supera lo
    # esperado) NO se carga a propósito: son tres niveles y el mapeo es binario.
    "campustest.frm.utn.edu.ar": {
        3: {"aprobado": 1, "desaprobado": 2, "items": ["Aprobado", "Desaprobado"]},
    },
}

# Umbral de aprobación para TP (escala 0-100 de Active-IA).
UMBRAL_APROBACION_TP = 60


def normalizar_host(moodle_host: str | None) -> str:
    """Reduce un `moodle_host` a su forma canónica para usarlo como clave.

    El valor viene de `Universidad.moodle_host` y es una URL base
    (`https://campus.edu.ar`), pero puede llegar con o sin protocolo, con barra
    final o con mayúsculas. Todas esas variantes son el mismo campus.
    """
    if not moodle_host:
        return ""
    host = moodle_host.strip().lower()
    for prefijo in ("https://", "http://"):
        if host.startswith(prefijo):
            host = host[len(prefijo) :]
            break
    return host.rstrip("/")


def escala_de(moodle_host: str | None, scale_id: int | None) -> dict | None:
    """Escala mapeada para ese campus, o None si no está.

    Devolver None es un resultado legítimo y esperado: significa "no sé cómo
    calificar con esta escala en este campus", y el llamador tiene que abortar
    el envío. Nunca cae a la escala de otro campus.
    """
    if scale_id is None:
        return None
    return MOODLE_SCALE_MAP.get(normalizar_host(moodle_host), {}).get(scale_id)
