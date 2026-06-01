"""Tests para ComentarioTemplateService (Fase 3 — mensaje de comentario a Moodle).

Reglas (PLAN_FEAT.md §7.1/§7.2):
- TP: mensaje automático según banda de nota (escala 0-100), requiere_comentario_tutor=False.
- No-TP: sin mensaje automático (el tutor escribe), requiere_comentario_tutor=True.

El link de devolución NO va en el mensaje: lo agrega MoodleGradeService como hipervínculo.
"""

import pytest

from app.services.comentario_template_service import ComentarioTemplateService


@pytest.mark.parametrize(
    "nota,fragmento_esperado",
    [
        # Usa SOLO el primer nombre: "Juan Carlos Perez" → "Juan"
        (95, "Excelente Juan!"),
        (90, "Excelente Juan!"),
        (85, "Muy bien Juan!"),
        (81, "Muy bien Juan!"),
        (75, "Bien Juan!"),
        (71, "Bien Juan!"),
        (65, "Revisá con detalle"),
        (60, "Revisá con detalle"),
        (59, "revisá tu entrega PDF para poder realizar la reentrega"),
        (0, "revisá tu entrega PDF para poder realizar la reentrega"),
    ],
)
def test_render_tp_por_banda(nota, fragmento_esperado):
    res = ComentarioTemplateService.render(
        tipo_rubrica="TP", nota=nota, nombre_alumno="Juan Carlos Perez",
    )
    assert fragmento_esperado in res.comentario
    assert res.requiere_comentario_tutor is False
    # El mensaje NO incluye el link/URL (eso se agrega aparte como hipervínculo)
    assert "http" not in res.comentario
    assert "{link" not in res.comentario


def test_render_tp_usa_solo_primer_nombre():
    res = ComentarioTemplateService.render(
        tipo_rubrica="TP", nota=95, nombre_alumno="Selene Araceli Miño",
    )
    assert "Excelente Selene!" in res.comentario
    assert "Araceli" not in res.comentario
    assert "Miño" not in res.comentario
    assert "{nombre_alumno}" not in res.comentario


@pytest.mark.parametrize("tipo", ["PARCIAL_1", "PARCIAL_2", "RECUPERATORIO_1", "FINAL", "GLOBAL"])
def test_render_no_tp_sin_mensaje_y_exige_comentario(tipo):
    res = ComentarioTemplateService.render(
        tipo_rubrica=tipo, nota=80, nombre_alumno="Juan Perez",
    )
    assert res.requiere_comentario_tutor is True
    assert res.comentario == ""  # el tutor escribe el suyo
