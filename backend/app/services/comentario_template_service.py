# app/services/comentario_template_service.py
"""
ComentarioTemplateService — arma el MENSAJE sugerido (editable) del comentario.

El link de devolución NO se incluye acá: lo agrega MoodleGradeService como
hipervínculo HTML al final (la palabra "devolución" es el enlace).

Ref: PLAN_FEAT.md §7.1 (TP por banda) y §7.2 (no-TP exige comentario del tutor).
"""

from dataclasses import dataclass

from app.core.comentario_templates import COMENTARIO_TEMPLATES_TP


@dataclass
class ComentarioRender:
    """Resultado del render de la plantilla de comentario."""

    comentario: str  # mensaje editable (SIN el link; el cierre se agrega al enviar)
    # True si el tutor DEBE escribir su propio comentario antes de enviar (no-TP).
    requiere_comentario_tutor: bool


class ComentarioTemplateService:
    """Renderiza el mensaje sugerido según el tipo de rúbrica y la nota."""

    @staticmethod
    def render(
        *,
        tipo_rubrica: str,
        nota: float,
        nombre_alumno: str,
    ) -> ComentarioRender:
        if tipo_rubrica == "TP":
            texto = ComentarioTemplateService._template_tp(nota)
            return ComentarioRender(
                comentario=texto.format(
                    nombre_alumno=ComentarioTemplateService._primer_nombre(nombre_alumno)
                ),
                requiere_comentario_tutor=False,
            )

        # No-TP: sin mensaje automático; el tutor escribe el suyo.
        return ComentarioRender(comentario="", requiere_comentario_tutor=True)

    @staticmethod
    def _primer_nombre(nombre_completo: str) -> str:
        """Devuelve sólo el primer nombre para un saludo cálido.

        Asume formato 'Nombre(s) Apellido(s)' (confirmado en el TUP, sin coma):
        'Selene Araceli Miño' → 'Selene'.
        """
        partes = (nombre_completo or "").strip().split()
        return partes[0] if partes else (nombre_completo or "")

    @staticmethod
    def _template_tp(nota: float) -> str:
        for rango_min, rango_max, texto in COMENTARIO_TEMPLATES_TP:
            if rango_min <= nota <= rango_max:
                return texto
        return COMENTARIO_TEMPLATES_TP[-1][2]
