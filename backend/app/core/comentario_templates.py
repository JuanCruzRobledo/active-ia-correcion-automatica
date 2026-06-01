# app/core/comentario_templates.py
"""
Plantillas de comentario para publicar en Moodle al subir una corrección.

Decisión (PLAN_FEAT.md §3.3): se guardan como constante en código (no en DB).
Placeholder soportado en el MENSAJE: {nombre_alumno}.

El link de devolución NO va en el texto del mensaje: se agrega automáticamente
como hipervínculo HTML al final del comentario (la palabra "devolución" es el
enlace, no la URL cruda — ver MoodleGradeService._construir_feedback_html).

- TP: mensaje automático según banda de nota (escala 0-100, >= 60 aprueba).
- No-TP: sin mensaje automático; el tutor escribe el suyo.
"""

# Bandas para TP: (nota_min, nota_max, mensaje). Rango inclusivo. SIN link (se agrega aparte).
COMENTARIO_TEMPLATES_TP = [
    (90, 100, "Excelente {nombre_alumno}!"),
    (81, 89, "Muy bien {nombre_alumno}!"),
    (71, 80, "Bien {nombre_alumno}!"),
    (60, 70, "Bien {nombre_alumno}! Revisá con detalle tu entrega PDF."),
    (0, 59, "Hola {nombre_alumno}, revisá tu entrega PDF para poder realizar la reentrega del TP."),
]

# Cierre que se agrega SIEMPRE como HTML al final. {link} es el href; la palabra
# "devolución" aparece UNA sola vez (es el propio enlace) y abre en ventana nueva.
CIERRE_DEVOLUCION_HTML = (
    'Te dejo tu <a href="{link}" target="_blank" rel="noopener noreferrer">devolución</a>'
)
