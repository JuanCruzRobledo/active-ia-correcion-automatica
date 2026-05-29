# app/core/moodle_config.py
"""
Configuración de mapeo de escalas cualitativas de Moodle.

Las escalas de Moodle no tienen un WS simple para leer sus textos, así que el
índice de cada resultado va en config explícita (PLAN_FEAT.md §7.4).

⚠️ El orden NO es intuitivo. Confirmado en Fase 0 contra tup.sied.utn.edu.ar:
    scale_id=5  →  índice 1 = 'Aprobado', índice 2 = 'Desaprobado'  (INVERTIDO)
Asumir lo contrario desaprobaría a todos los aprobados. Por eso va hardcodeado
y verificado, nunca inferido por "lógica".

`mod_assign_save_grade` recibe el ÍNDICE (1-based) como float.
"""

MOODLE_SCALE_MAP: dict[int, dict] = {
    5: {"aprobado": 1, "desaprobado": 2, "items": ["Aprobado", "Desaprobado"]},
}

# Umbral de aprobación para TP (escala 0-100 de Active-IA).
UMBRAL_APROBACION_TP = 60
