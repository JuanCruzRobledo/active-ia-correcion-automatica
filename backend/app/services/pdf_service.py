# app/services/pdf_service.py
"""
PDF service for Active-IA.

Business logic for generating PDF feedback documents for corrections and rubricas.
Uses ReportLab to create professional-looking PDFs with grades, criteria, and feedback.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 10
"""

import io
import zipfile
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepInFrame,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correccion import Correccion
from app.models.rubrica import Rubrica
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.rubrica_repository import RubricaRepository


class PDFService:
    """Service for generating PDF documents."""

    def __init__(self, db: AsyncSession):
        """Initialize PDF service."""
        self.db = db
        self.correccion_repo = CorreccionRepository(db)
        self.rubrica_repo = RubricaRepository(db)

    @staticmethod
    def _escape_xml(text: str) -> str:
        """
        Escape special XML/HTML characters in free-form user text so that
        ReportLab's paragraph parser does not misinterpret them as markup tags.

        Only escapes the three characters that would break XML parsing:
        - & -> &amp;  (must be first to avoid double-escaping)
        - < -> &lt;
        - > -> &gt;
        """
        if not text:
            return text
        # Order matters: & must be escaped before < and >
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    async def generar_pdf_devolucion(self, correccion_id: int) -> bytes:
        """
        Generate a PDF feedback document for a correction.

        Args:
            correccion_id: ID of the correction.

        Returns:
            PDF file content as bytes.

        Raises:
            HTTPException 404: Correction not found.
        """
        from fastapi import HTTPException, status

        # Get correction with all relations
        correccion = await self.correccion_repo.get_by_id_with_relations(correccion_id)
        if not correccion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Corrección {correccion_id} no encontrada",
            )

        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build PDF content
        story = self._build_pdf_content(correccion)

        # Generate PDF
        doc.build(story)

        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        return pdf_bytes

    async def generar_zip_pdfs(
        self,
        comision_id: int,
        rubrica_id: int,
    ) -> tuple[bytes, str]:
        """
        Generate a ZIP file with PDFs for all corrected entregas.

        Args:
            comision_id: ID of the comision.
            rubrica_id: ID of the rubrica.

        Returns:
            Tuple of (ZIP file bytes, suggested filename).

        Raises:
            HTTPException 404: No corrections found.
        """
        from fastapi import HTTPException, status

        # Get all corrections for this comision and rubrica
        correcciones_list, total = await self.correccion_repo.get_all(
            comision_id=comision_id,
            rubrica_id=rubrica_id,
            page=1,
            per_page=1000,  # Get all
        )

        if not correcciones_list:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay correcciones para esta comisión y rúbrica",
            )

        import re
        import unicodedata

        def _sanitize_part(text: str) -> str:
            """Strip accents, replace spaces with hyphens, remove invalid filename chars."""
            # Decompose unicode and strip diacritics
            text = unicodedata.normalize("NFD", text)
            text = "".join(c for c in text if unicodedata.category(c) != "Mn")
            # Replace spaces with hyphens, remove anything not alphanumeric/hyphen/underscore
            text = re.sub(r"\s+", "-", text)
            text = re.sub(r"[^a-zA-Z0-9\-_]", "", text)
            text = re.sub(r"-{2,}", "-", text).strip("-")
            return text

        # Get rubrica tipo/numero from first correction (same for all)
        first_correccion = correcciones_list[0]
        rubrica = first_correccion.entrega.rubrica
        rubrica_tipo = rubrica.tipo.value if hasattr(rubrica.tipo, "value") else str(rubrica.tipo)
        rubrica_part = f"{rubrica_tipo}-{rubrica.numero}"

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for correccion in correcciones_list:
                # Generate PDF for this correction
                pdf_bytes = await self.generar_pdf_devolucion(correccion.id)

                # Build PDF filename: AlumnoNombre-Devolucion-TP-1.pdf
                alumno_safe = _sanitize_part(correccion.entrega.alumno_nombre)
                pdf_filename = f"{alumno_safe}-Devolucion-{rubrica_part}.pdf"
                zip_file.writestr(pdf_filename, pdf_bytes)

        # Get ZIP bytes
        zip_bytes = zip_buffer.getvalue()
        zip_buffer.close()

        # ZIP filename is built by the frontend (has comision name context)
        # Return a sensible fallback used only if frontend doesn't override it
        zip_filename = f"Devoluciones-{rubrica_part}.zip"

        return zip_bytes, zip_filename

    def _build_pdf_content(self, correccion: Correccion) -> list:
        """
        Build PDF content elements for a correction.

        Args:
            correccion: Correction model with relations loaded.

        Returns:
            List of ReportLab flowables.
        """
        story = []
        styles = getSampleStyleSheet()

        # ==================== CUSTOM STYLES ====================

        # Main title style
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.HexColor("#1e3a8a"),  # Deep blue
            spaceAfter=6,
            alignment=1,  # Center
            fontName="Helvetica-Bold",
        )

        # Subtitle style
        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),  # Slate gray
            spaceAfter=12,
            alignment=1,  # Center
        )

        # Section heading style
        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=10,
            spaceBefore=6,
            fontName="Helvetica-Bold",
            borderPadding=(0, 0, 8, 0),
        )

        # Body text style
        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            leading=14,
        )

        # List item style
        list_style = ParagraphStyle(
            "CustomList",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            leftIndent=20,
            leading=14,
        )

        # ==================== HEADER ====================

        # Top decorative line
        header_line = Table([[""]], colWidths=[6.5 * inch])
        header_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(header_line)
        story.append(Spacer(1, 0.15 * inch))

        # Title
        story.append(Paragraph("ACTIVE-IA", title_style))
        story.append(Paragraph("Devolución de Trabajo Práctico", subtitle_style))
        story.append(Spacer(1, 0.25 * inch))

        # ==================== INFO SECTION ====================

        entrega = correccion.entrega
        comision = entrega.comision
        materia = comision.materia
        rubrica = entrega.rubrica

        info_data = [
            ["Materia:", f"{materia.codigo} - {materia.nombre}"],
            ["Comisión:", f"{comision.nombre} ({comision.anio})"],
            ["Trabajo:", rubrica.titulo],
            ["Alumno:", entrega.alumno_nombre],
        ]

        info_table = Table(info_data, colWidths=[1.3 * inch, 5.2 * inch])
        info_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 0.3 * inch))

        # ==================== GRADE SECTION ====================

        nota_color = self._get_nota_color(correccion.nota)
        nota_bg = self._get_nota_bg_color(correccion.nota)

        grade_data = [[f"Calificación Final: {int(correccion.nota)}/100"]]
        grade_table = Table(grade_data, colWidths=[6.5 * inch])
        grade_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 20),
                ("TEXTCOLOR", (0, 0), (-1, -1), nota_color),
                ("BACKGROUND", (0, 0), (-1, -1), nota_bg),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 2, nota_color),
                ("TOPPADDING", (0, 0), (-1, -1), 16),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
            ])
        )
        story.append(grade_table)

        # ==================== CD / PENALTY ALERTS ====================

        if correccion.condicion_desaprobacion_aplicada:
            story.append(Spacer(1, 0.15 * inch))
            # Look up CD description from rubrica
            cd_id = correccion.condicion_desaprobacion_aplicada
            cd_descripcion = cd_id
            cd_techo = int(correccion.nota)
            for cd in (rubrica.condiciones_desaprobacion_json or []):
                if cd.get("id") == cd_id:
                    cd_descripcion = cd.get("condicion", cd_id)
                    cd_techo = cd.get("nota_maxima", cd.get("nota_final", cd_techo))
                    break

            cd_text = (
                f"<b>Nota limitada por incumplimiento de requisitos</b><br/>"
                f"{self._escape_xml(cd_descripcion)}<br/>"
                f"Esto limita la nota máxima alcanzable a <b>{cd_techo}</b> puntos."
            )
            if correccion.nota_antes_penalizaciones is not None:
                cd_text += (
                    f" Tu puntaje obtenido por mérito fue "
                    f"<b>{int(correccion.nota_antes_penalizaciones)}</b>/100."
                )
            alert_style = ParagraphStyle(
                "CDAlert",
                parent=styles["Normal"],
                fontSize=10,
                textColor=colors.HexColor("#991b1b"),
                leading=14,
            )
            cd_data = [[Paragraph(cd_text, alert_style)]]
            cd_table = Table(cd_data, colWidths=[6.5 * inch])
            cd_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
                    ("BOX", (0, 0), (-1, -1), 2, colors.HexColor("#dc2626")),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ])
            )
            story.append(cd_table)

        if correccion.penalizaciones_aplicadas and len(correccion.penalizaciones_aplicadas) > 0:
            story.append(Spacer(1, 0.15 * inch))
            # Look up penalty descriptions from rubrica
            pen_descriptions = []
            for pen_id in correccion.penalizaciones_aplicadas:
                pen_desc = pen_id
                pen_pct = 0
                for p in (rubrica.penalizaciones_json or []):
                    if p.get("id") == pen_id:
                        pen_desc = p.get("descripcion", pen_id)
                        pen_pct = p.get("descuento_porcentaje", 0)
                        break
                pen_descriptions.append((pen_desc, pen_pct))

            pen_text = f"<b>Penalizaciones aplicadas:</b><br/>"
            for desc, pct in pen_descriptions:
                pen_text += f"• {self._escape_xml(desc)} (descuento del {pct}%)<br/>"
            if correccion.nota_antes_penalizaciones is not None:
                pen_text += (
                    f"<br/>Puntaje antes de penalizaciones: "
                    f"<b>{int(correccion.nota_antes_penalizaciones)}</b>/100 → "
                    f"Nota final: <b>{int(correccion.nota)}</b>/100"
                )
            pen_alert_style = ParagraphStyle(
                "PenAlert",
                parent=styles["Normal"],
                fontSize=10,
                textColor=colors.HexColor("#92400e"),
                leading=14,
            )
            pen_data = [[Paragraph(pen_text, pen_alert_style)]]
            pen_table = Table(pen_data, colWidths=[6.5 * inch])
            pen_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                    ("BOX", (0, 0), (-1, -1), 2, colors.HexColor("#f59e0b")),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ])
            )
            story.append(pen_table)

        if (correccion.nota_antes_penalizaciones is not None
                and not correccion.condicion_desaprobacion_aplicada
                and not correccion.penalizaciones_aplicadas):
            merit = int(correccion.nota_antes_penalizaciones)
            final = int(correccion.nota)
            if merit != final:
                story.append(Spacer(1, 0.1 * inch))
                merit_style = ParagraphStyle(
                    "MeritNote",
                    parent=styles["Normal"],
                    fontSize=9,
                    textColor=colors.HexColor("#64748b"),
                    alignment=2,
                )
                story.append(Paragraph(f"Puntaje por mérito: {merit}/100", merit_style))

        story.append(Spacer(1, 0.35 * inch))

        # ==================== CRITERIA EVALUATION ====================

        story.append(Paragraph("EVALUACIÓN POR CRITERIOS", heading_style))
        story.append(Spacer(1, 0.15 * inch))

        # Extract criterios list from criterios_json dict
        criterios = correccion.criterios_json.get("criterios", [])
        for i, criterio in enumerate(criterios):
            criterio_element = self._format_criterio(criterio, i + 1)
            story.append(criterio_element)
            story.append(Spacer(1, 0.12 * inch))

        # ==================== FORTALEZAS ====================

        if correccion.fortalezas and len(correccion.fortalezas) > 0:
            story.append(Spacer(1, 0.25 * inch))
            story.append(Paragraph("FORTALEZAS", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            for fortaleza in correccion.fortalezas:
                bullet = Paragraph(f"• {self._escape_xml(fortaleza)}", list_style)
                story.append(bullet)
                story.append(Spacer(1, 0.08 * inch))

        # ==================== RECOMENDACIONES ====================

        if correccion.recomendaciones and len(correccion.recomendaciones) > 0:
            story.append(Spacer(1, 0.25 * inch))
            story.append(Paragraph("RECOMENDACIONES", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            for i, recomendacion in enumerate(correccion.recomendaciones, 1):
                rec_para = Paragraph(f"{i}. {self._escape_xml(recomendacion)}", list_style)
                story.append(rec_para)
                story.append(Spacer(1, 0.08 * inch))

        # ==================== COMENTARIO GENERAL ====================

        if correccion.comentario_general:
            story.append(Spacer(1, 0.25 * inch))
            story.append(Paragraph("COMENTARIOS DEL EVALUADOR", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            comment_data = [[Paragraph(self._escape_xml(correccion.comentario_general), body_style)]]
            comment_table = Table(comment_data, colWidths=[6.5 * inch])
            comment_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ])
            )
            story.append(comment_table)

        # ==================== FOOTER ====================

        story.append(Spacer(1, 0.4 * inch))

        # Bottom line
        footer_line = Table([[""]], colWidths=[6.5 * inch])
        footer_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(footer_line)

        # Footer text
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )

        footer_text = "Documento generado por ACTIVE-IA"
        if correccion.editado_manualmente:
            footer_text += " • Corrección editada manualmente por el tutor"

        story.append(Paragraph(footer_text, footer_style))

        return story

    def _format_criterio(self, criterio: dict[str, Any], numero: int) -> Table:
        """
        Format a criterion as a professional table with progress bar.

        Args:
            criterio: Criterion dictionary.
            numero: Criterion number (for display).

        Returns:
            ReportLab Table.
        """
        nombre = criterio.get("nombre", "")
        puntaje_obtenido = criterio.get("puntaje_obtenido", 0)
        puntaje_maximo = criterio.get("puntaje_maximo", 0)
        estado = criterio.get("estado", "OK")
        feedback = criterio.get("feedback", "")

        # Get estado colors (without icons)
        estado_color = self._get_estado_color(estado)
        estado_bg = self._get_estado_bg_color(estado)

        # Calculate percentage for progress bar
        percentage = (puntaje_obtenido / puntaje_maximo * 100) if puntaje_maximo > 0 else 0

        # Build main criterion data
        criterio_header = [
            [
                f"C{numero}: {nombre}",
                f"{int(puntaje_obtenido)}/{int(puntaje_maximo)}",
            ]
        ]

        # Progress bar (visual representation)
        progress_bar_data = self._create_progress_bar(percentage, estado_color)

        # Feedback section
        styles = getSampleStyleSheet()
        feedback_style = ParagraphStyle(
            "FeedbackStyle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#475569"),
            leading=12,
        )

        feedback_para = Paragraph(self._escape_xml(feedback), feedback_style)

        # Complete table data
        data = [
            criterio_header[0],  # Header with name and score
            [progress_bar_data, ""],  # Progress bar
            [feedback_para, ""],  # Feedback
        ]

        table = Table(data, colWidths=[5.2 * inch, 1.3 * inch])
        table.setStyle(
            TableStyle([
                # Header row (criterion name and score)
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (0, 0), 10),
                ("FONTSIZE", (1, 0), (1, 0), 11),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (1, 0), (1, 0), estado_color),
                ("BACKGROUND", (0, 0), (-1, 0), estado_bg),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("LEFTPADDING", (0, 0), (-1, 0), 12),
                ("RIGHTPADDING", (0, 0), (-1, 0), 12),

                # Progress bar row
                ("SPAN", (0, 1), (-1, 1)),
                ("TOPPADDING", (0, 1), (-1, 1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                ("LEFTPADDING", (0, 1), (-1, 1), 12),
                ("RIGHTPADDING", (0, 1), (-1, 1), 12),

                # Feedback row
                ("SPAN", (0, 2), (-1, 2)),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica"),
                ("FONTSIZE", (0, 2), (-1, 2), 9),
                ("TOPPADDING", (0, 2), (-1, 2), 8),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 10),
                ("LEFTPADDING", (0, 2), (-1, 2), 12),
                ("RIGHTPADDING", (0, 2), (-1, 2), 12),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#fafafa")),

                # Overall border
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#cbd5e1")),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("LINEBELOW", (0, 1), (-1, 1), 1, colors.HexColor("#e2e8f0")),
            ])
        )

        return table

    def _get_estado_color(self, estado: str) -> colors.Color:
        """Get color for estado (without icons)."""
        estado_map = {
            "OK": colors.HexColor("#16a34a"),      # Green
            "WARNING": colors.HexColor("#d97706"),  # Amber
            "ERROR": colors.HexColor("#dc2626"),    # Red
        }
        return estado_map.get(estado, estado_map["OK"])

    def _get_estado_bg_color(self, estado: str) -> colors.Color:
        """Get background color for estado."""
        estado_map = {
            "OK": colors.HexColor("#f0fdf4"),      # Light green
            "WARNING": colors.HexColor("#fef3c7"), # Light amber
            "ERROR": colors.HexColor("#fef2f2"),   # Light red
        }
        return estado_map.get(estado, estado_map["OK"])

    def _get_nota_color(self, nota: float) -> colors.Color:
        """Get color for nota based on value."""
        if nota >= 80:
            return colors.HexColor("#16a34a")  # Green
        elif nota >= 60:
            return colors.HexColor("#d97706")  # Amber
        else:
            return colors.HexColor("#dc2626")  # Red

    def _get_nota_bg_color(self, nota: float) -> colors.Color:
        """Get background color for nota based on value."""
        if nota >= 80:
            return colors.HexColor("#f0fdf4")  # Light green
        elif nota >= 60:
            return colors.HexColor("#fef3c7")  # Light amber
        else:
            return colors.HexColor("#fef2f2")  # Light red

    def _create_progress_bar(self, percentage: float, color: colors.Color) -> Table:
        """
        Create a visual progress bar for criterion score.

        Args:
            percentage: Percentage of score achieved (0-100).
            color: Color for the filled portion.

        Returns:
            Table representing the progress bar.
        """
        # Progress bar dimensions
        bar_width = 4.5 * inch
        bar_height = 0.15 * inch

        # Calculate filled width
        filled_width = bar_width * (percentage / 100)
        empty_width = bar_width - filled_width

        # Create progress bar cells
        if percentage > 0:
            progress_data = [["", ""]]
            col_widths = [filled_width, empty_width] if empty_width > 0 else [filled_width]
        else:
            progress_data = [[""]]
            col_widths = [bar_width]

        progress_table = Table(progress_data, colWidths=col_widths, rowHeights=[bar_height])

        if percentage > 0:
            progress_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (0, 0), color),  # Filled portion
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e2e8f0")) if empty_width > 0 else ("BACKGROUND", (0, 0), (0, 0), color),  # Empty portion
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ])
            )
        else:
            # 0% - empty bar
            progress_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ])
            )

        return progress_table

    async def generar_pdf_rubrica_resumido(self, rubrica_id: int) -> bytes:
        """
        Generate a SUMMARY PDF document for a rubrica (1-2 pages max).

        Args:
            rubrica_id: ID of the rubrica.

        Returns:
            PDF file content as bytes.

        Raises:
            HTTPException 404: Rubrica not found.
        """
        from fastapi import HTTPException, status

        # Get rubrica with all relations
        rubrica = await self.rubrica_repo.get_by_id_with_relations(rubrica_id)
        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rúbrica {rubrica_id} no encontrada",
            )

        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build PDF content (SUMMARY VERSION)
        story = self._build_rubrica_pdf_content_resumido(rubrica)

        # Generate PDF
        doc.build(story)

        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        return pdf_bytes

    def generar_pdf_rubrica_resumido_preview(self, data: dict[str, Any]) -> bytes:
        """
        Generate a SUMMARY preview PDF for a rubrica from form data.

        Args:
            data: Dictionary with rubrica data.

        Returns:
            PDF file content as bytes.
        """
        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build PDF content from dictionary data (SUMMARY VERSION)
        story = self._build_rubrica_pdf_content_resumido_from_dict(data)

        # Generate PDF
        doc.build(story)

        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        return pdf_bytes

    async def generar_pdf_rubrica(self, rubrica_id: int) -> bytes:
        """
        Generate a PDF document for a rubrica.

        Args:
            rubrica_id: ID of the rubrica.

        Returns:
            PDF file content as bytes.

        Raises:
            HTTPException 404: Rubrica not found.
        """
        from fastapi import HTTPException, status

        # Get rubrica with all relations
        rubrica = await self.rubrica_repo.get_by_id_with_relations(rubrica_id)
        if not rubrica:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rúbrica {rubrica_id} no encontrada",
            )

        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build PDF content
        story = self._build_rubrica_pdf_content(rubrica)

        # Generate PDF
        doc.build(story)

        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        return pdf_bytes

    def generar_pdf_rubrica_preview(self, data: dict[str, Any]) -> bytes:
        """
        Generate a preview PDF for a rubrica from form data (without saving to database).

        Args:
            data: Dictionary with rubrica data (titulo, descripcion, criterios, etc.)

        Returns:
            PDF file content as bytes.
        """
        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build PDF content from dictionary data
        story = self._build_rubrica_pdf_content_from_dict(data)

        # Generate PDF
        doc.build(story)

        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        return pdf_bytes

    def _build_rubrica_pdf_content(self, rubrica: Rubrica) -> list:
        """
        Build PDF content elements for a rubrica.

        Args:
            rubrica: Rubrica model with relations loaded.

        Returns:
            List of ReportLab flowables.
        """
        story = []
        styles = getSampleStyleSheet()

        # ==================== CUSTOM STYLES ====================

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.HexColor("#1e3a8a"),  # Deep blue
            spaceAfter=6,
            alignment=1,  # Center
            fontName="Helvetica-Bold",
        )

        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),  # Slate gray
            spaceAfter=12,
            alignment=1,  # Center
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=10,
            spaceBefore=6,
            fontName="Helvetica-Bold",
        )

        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            leading=14,
        )

        # ==================== HEADER ====================

        header_line = Table([[""]], colWidths=[6.5 * inch])
        header_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(header_line)
        story.append(Spacer(1, 0.15 * inch))

        # Title
        story.append(Paragraph("ACTIVE-IA", title_style))
        story.append(Paragraph("Rúbrica de Evaluación", subtitle_style))
        story.append(Spacer(1, 0.25 * inch))

        # ==================== INFO SECTION ====================

        materia = rubrica.materia
        tipo_labels = {
            "TP": "Trabajo Práctico",
            "PARCIAL_1": "Parcial 1",
            "PARCIAL_2": "Parcial 2",
            "RECUPERATORIO_1": "Recuperatorio 1",
            "RECUPERATORIO_2": "Recuperatorio 2",
            "FINAL": "Final",
            "GLOBAL": "Global",
        }
        tipo_label = tipo_labels.get(rubrica.tipo.value, rubrica.tipo.value)

        info_data = [
            ["Materia:", f"{materia.codigo} - {materia.nombre}"],
            ["Tipo:", tipo_label],
            ["Número:", f"#{rubrica.numero}"],
            ["Año:", str(rubrica.anio)],
            ["Puntaje Máximo:", f"{rubrica.puntaje_maximo} puntos"],
        ]

        info_table = Table(info_data, colWidths=[1.5 * inch, 5.0 * inch])
        info_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 0.3 * inch))

        # ==================== TITULO Y DESCRIPCION ====================

        # Título de la rúbrica
        title_data = [[Paragraph(f"<b>{self._escape_xml(rubrica.titulo)}</b>", body_style)]]
        title_table = Table(title_data, colWidths=[6.5 * inch])
        title_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(title_table)
        story.append(Spacer(1, 0.15 * inch))

        # Descripción
        desc_para = Paragraph(self._escape_xml(rubrica.descripcion), body_style)
        desc_data = [[desc_para]]
        desc_table = Table(desc_data, colWidths=[6.5 * inch])
        desc_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(desc_table)
        story.append(Spacer(1, 0.35 * inch))

        # ==================== CRITERIOS ====================

        story.append(Paragraph("CRITERIOS DE EVALUACIÓN", heading_style))
        story.append(Spacer(1, 0.15 * inch))

        for i, criterio in enumerate(rubrica.criterios_json):
            # Get list of elements instead of single table (allows natural page breaks)
            criterio_elements = self._format_rubrica_criterio_flat(criterio, i + 1, body_style)
            for element in criterio_elements:
                story.append(element)
            story.append(Spacer(1, 0.15 * inch))

        # ==================== PENALIZACIONES ====================

        if rubrica.penalizaciones_json and len(rubrica.penalizaciones_json) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("PENALIZACIONES", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            pen_data = [["ID", "Descripción", "Descuento"]]
            for pen in rubrica.penalizaciones_json:
                pen_data.append([
                    pen.get("id", ""),
                    Paragraph(self._escape_xml(pen.get("descripcion", "")), table_cell_style),
                    f"-{pen.get('descuento_porcentaje', 0)}%",
                ])

            pen_table = Table(pen_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            pen_table.setStyle(
                TableStyle([
                    # Header
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#92400e")),
                    # Body
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fffbeb")),
                    # All cells
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#fbbf24")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(pen_table)

        # ==================== CONDICIONES DE DESAPROBACION ====================

        if rubrica.condiciones_desaprobacion_json and len(rubrica.condiciones_desaprobacion_json) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("CONDICIONES DE DESAPROBACIÓN", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            cond_data = [["ID", "Condición", "Nota Final"]]
            for cond in rubrica.condiciones_desaprobacion_json:
                cond_data.append([
                    cond.get("id", ""),
                    Paragraph(self._escape_xml(cond.get("condicion", "")), table_cell_style),
                    f"Máx: {cond.get('nota_maxima', cond.get('nota_final', 0))}",
                ])

            cond_table = Table(cond_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            cond_table.setStyle(
                TableStyle([
                    # Header
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                    # Body
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fef2f2")),
                    # All cells
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#ef4444")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(cond_table)

        # ==================== FOOTER ====================

        story.append(Spacer(1, 0.4 * inch))

        footer_line = Table([[""]], colWidths=[6.5 * inch])
        footer_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(footer_line)

        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )

        footer_text = f"Documento generado por ACTIVE-IA • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        story.append(Paragraph(footer_text, footer_style))

        return story

    def _build_rubrica_pdf_content_from_dict(self, data: dict[str, Any]) -> list:
        """
        Build PDF content elements for a rubrica from dictionary data (preview mode).

        Args:
            data: Dictionary with rubrica data.

        Returns:
            List of ReportLab flowables.
        """
        story = []
        styles = getSampleStyleSheet()

        # ==================== CUSTOM STYLES ====================

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=6,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=12,
            alignment=1,
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=10,
            spaceBefore=6,
            fontName="Helvetica-Bold",
        )

        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            leading=14,
        )

        # ==================== HEADER ====================

        header_line = Table([[""]], colWidths=[6.5 * inch])
        header_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(header_line)
        story.append(Spacer(1, 0.15 * inch))

        story.append(Paragraph("ACTIVE-IA", title_style))
        story.append(Paragraph("Rúbrica de Evaluación", subtitle_style))
        story.append(Spacer(1, 0.25 * inch))

        # ==================== INFO SECTION ====================

        tipo_labels = {
            "TP": "Trabajo Práctico",
            "PARCIAL_1": "Parcial 1",
            "PARCIAL_2": "Parcial 2",
            "RECUPERATORIO_1": "Recuperatorio 1",
            "RECUPERATORIO_2": "Recuperatorio 2",
            "FINAL": "Final",
            "GLOBAL": "Global",
        }
        tipo_label = tipo_labels.get(data.get("tipo", "TP"), data.get("tipo", "TP"))

        info_data = [
            ["Materia:", data.get("materia_nombre", "N/A")],
            ["Tipo:", tipo_label],
            ["Número:", f"#{data.get('numero', 1)}"],
            ["Año:", str(data.get("anio", datetime.now().year))],
            ["Puntaje Máximo:", f"{data.get('puntaje_maximo', 100)} puntos"],
        ]

        info_table = Table(info_data, colWidths=[1.5 * inch, 5.0 * inch])
        info_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 0.3 * inch))

        # ==================== TITULO Y DESCRIPCION ====================

        titulo = data.get("titulo", "Sin título")
        title_data = [[Paragraph(f"<b>{self._escape_xml(titulo)}</b>", body_style)]]
        title_table = Table(title_data, colWidths=[6.5 * inch])
        title_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(title_table)
        story.append(Spacer(1, 0.15 * inch))

        descripcion = data.get("descripcion", "Sin descripción")
        desc_para = Paragraph(self._escape_xml(descripcion), body_style)
        desc_data = [[desc_para]]
        desc_table = Table(desc_data, colWidths=[6.5 * inch])
        desc_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ])
        )
        story.append(desc_table)
        story.append(Spacer(1, 0.35 * inch))

        # ==================== CRITERIOS ====================

        story.append(Paragraph("CRITERIOS DE EVALUACIÓN", heading_style))
        story.append(Spacer(1, 0.15 * inch))

        criterios = data.get("criterios", [])
        for i, criterio in enumerate(criterios):
            # Get list of elements instead of single table (allows natural page breaks)
            criterio_elements = self._format_rubrica_criterio_flat(criterio, i + 1, body_style)
            for element in criterio_elements:
                story.append(element)
            story.append(Spacer(1, 0.15 * inch))

        # ==================== PENALIZACIONES ====================

        penalizaciones = data.get("penalizaciones", [])
        if penalizaciones and len(penalizaciones) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("PENALIZACIONES", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            pen_data = [["ID", "Descripción", "Descuento"]]
            for pen in penalizaciones:
                pen_data.append([
                    pen.get("id", ""),
                    Paragraph(self._escape_xml(pen.get("descripcion", "")), table_cell_style),
                    f"-{pen.get('descuento_porcentaje', 0)}%",
                ])

            pen_table = Table(pen_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            pen_table.setStyle(
                TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#92400e")),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fffbeb")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#fbbf24")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(pen_table)

        # ==================== CONDICIONES DE DESAPROBACION ====================

        condiciones = data.get("condiciones_desaprobacion", [])
        if condiciones and len(condiciones) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("CONDICIONES DE DESAPROBACIÓN", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            cond_data = [["ID", "Condición", "Nota Final"]]
            for cond in condiciones:
                cond_data.append([
                    cond.get("id", ""),
                    Paragraph(self._escape_xml(cond.get("condicion", "")), table_cell_style),
                    f"Máx: {cond.get('nota_maxima', cond.get('nota_final', 0))}",
                ])

            cond_table = Table(cond_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            cond_table.setStyle(
                TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fef2f2")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#ef4444")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(cond_table)

        # ==================== FOOTER ====================

        story.append(Spacer(1, 0.4 * inch))

        footer_line = Table([[""]], colWidths=[6.5 * inch])
        footer_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(footer_line)

        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )

        footer_text = f"Vista previa generada por ACTIVE-IA • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        story.append(Paragraph(footer_text, footer_style))

        return story

    def _format_rubrica_criterio_flat(self, criterio: dict[str, Any], numero: int, body_style: ParagraphStyle) -> list:
        """
        Format a rubrica criterion as a list of elements (allows natural page breaks).

        Args:
            criterio: Criterion dictionary.
            numero: Criterion number (for display).
            body_style: Paragraph style for body text.

        Returns:
            List of ReportLab flowables that can break across pages.
        """
        elements = []
        nombre = criterio.get("nombre", "")
        descripcion = criterio.get("descripcion", "")
        peso = criterio.get("peso", 0)
        subcriterios = criterio.get("subcriterios", [])

        # ===== HEADER TABLE =====
        header_data = [[f"Criterio {numero}: {nombre}", f"{peso}%"]]
        header_table = Table(header_data, colWidths=[5.5 * inch, 1.0 * inch])
        header_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (0, 0), 11),
                ("FONTSIZE", (1, 0), (1, 0), 12),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("LEFTPADDING", (0, 0), (-1, 0), 12),
                ("RIGHTPADDING", (0, 0), (-1, 0), 12),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
            ])
        )
        elements.append(header_table)

        # ===== DESCRIPTION TABLE =====
        desc_para = Paragraph(self._escape_xml(descripcion), body_style)
        desc_table = Table([[desc_para]], colWidths=[6.5 * inch])
        desc_table.setStyle(
            TableStyle([
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ("LINEABOVE", (0, 0), (-1, 0), 0, colors.white),  # No top line (header has it)
            ])
        )
        elements.append(desc_table)

        # ===== SUBCRITERIOS TABLE (FLAT) =====
        if subcriterios and len(subcriterios) > 0:
            sub_data = []
            for sub in subcriterios:
                sub_id = sub.get("id", "")
                sub_desc = self._escape_xml(sub.get("descripcion", ""))
                evidencias = sub.get("evidencias", [])

                # Format evidencias
                evidencias_text = ""
                if evidencias:
                    evidencias_limited = evidencias[:15]  # Limit to 15
                    evidencias_bullets = [f"  \u2022 {self._escape_xml(ev)}" for ev in evidencias_limited]
                    evidencias_text = "<br/>".join(evidencias_bullets)
                    if len(evidencias) > 15:
                        evidencias_text += f"<br/>  \u2022 ... (+{len(evidencias) - 15} m\xe1s)"

                sub_text = f"<b>{sub_id}:</b> {sub_desc}"
                if evidencias_text:
                    sub_text += f"<br/>{evidencias_text}"

                sub_data.append([Paragraph(sub_text, body_style)])

            # Create flat table with all subcriterios
            sub_table = Table(sub_data, colWidths=[6.3 * inch])
            sub_table.setStyle(
                TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                    ("LINEABOVE", (0, 0), (-1, 0), 0, colors.white),  # No top line
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ])
            )
            # CRITICAL: Allow table to split across pages
            sub_table.splitByRow = True
            elements.append(sub_table)
        else:
            # No subcriterios message
            no_sub_table = Table([[Paragraph("Sin subcriterios definidos", body_style)]], colWidths=[6.5 * inch])
            no_sub_table.setStyle(
                TableStyle([
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                    ("LINEABOVE", (0, 0), (-1, 0), 0, colors.white),
                ])
            )
            elements.append(no_sub_table)

        return elements

    def _format_rubrica_criterio(self, criterio: dict[str, Any], numero: int, body_style: ParagraphStyle) -> Table:
        """
        Format a rubrica criterion as a professional table.

        Args:
            criterio: Criterion dictionary.
            numero: Criterion number (for display).
            body_style: Paragraph style for body text.

        Returns:
            ReportLab Table with splitByRow enabled for page breaks.
        """
        nombre = criterio.get("nombre", "")
        descripcion = criterio.get("descripcion", "")
        peso = criterio.get("peso", 0)
        subcriterios = criterio.get("subcriterios", [])

        # Build header
        header_data = [[f"Criterio {numero}: {nombre}", f"{peso}%"]]

        # Build description row
        desc_para = Paragraph(self._escape_xml(descripcion), body_style)

        # Build subcriterios table
        if subcriterios and len(subcriterios) > 0:
            sub_rows = []
            for sub in subcriterios:
                sub_id = sub.get("id", "")
                sub_desc = self._escape_xml(sub.get("descripcion", ""))
                evidencias = sub.get("evidencias", [])

                # Format evidencias (limit to avoid huge cells)
                evidencias_text = ""
                if evidencias:
                    # Limit evidencias to first 10 to avoid huge tables
                    evidencias_limited = evidencias[:10]
                    evidencias_bullets = [f"  \u2022 {self._escape_xml(ev)}" for ev in evidencias_limited]
                    evidencias_text = "<br/>".join(evidencias_bullets)
                    if len(evidencias) > 10:
                        evidencias_text += f"<br/>  \u2022 ... (+{len(evidencias) - 10} m\xe1s)"

                sub_text = f"<b>{sub_id}:</b> {sub_desc}"
                if evidencias_text:
                    sub_text += f"<br/>{evidencias_text}"

                sub_rows.append([Paragraph(sub_text, body_style)])

            sub_table_data = sub_rows
            sub_table = Table(sub_table_data, colWidths=[6.0 * inch])
            sub_table.setStyle(
                TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            # Enable split for subtable
            sub_table.splitByRow = True
        else:
            sub_table = Paragraph("Sin subcriterios definidos", body_style)

        # Complete table data
        data = [
            header_data[0],
            [desc_para, ""],
            [sub_table, ""],
        ]

        table = Table(data, colWidths=[5.5 * inch, 1.0 * inch])
        table.setStyle(
            TableStyle([
                # Header row
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (0, 0), 11),
                ("FONTSIZE", (1, 0), (1, 0), 12),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("LEFTPADDING", (0, 0), (-1, 0), 12),
                ("RIGHTPADDING", (0, 0), (-1, 0), 12),

                # Description row
                ("SPAN", (0, 1), (-1, 1)),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, 1), 10),
                ("TOPPADDING", (0, 1), (-1, 1), 10),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ("LEFTPADDING", (0, 1), (-1, 1), 12),
                ("RIGHTPADDING", (0, 1), (-1, 1), 12),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),

                # Subcriterios row
                ("SPAN", (0, 2), (-1, 2)),
                ("TOPPADDING", (0, 2), (-1, 2), 10),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 10),
                ("LEFTPADDING", (0, 2), (-1, 2), 8),
                ("RIGHTPADDING", (0, 2), (-1, 2), 8),
                ("BACKGROUND", (0, 2), (-1, 2), colors.white),
                ("VALIGN", (0, 2), (-1, 2), "TOP"),

                # Overall border
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("LINEBELOW", (0, 1), (-1, 1), 1, colors.HexColor("#e2e8f0")),
            ])
        )

        # CRITICAL: Enable split by row to allow page breaks within the table
        table.splitByRow = True

        return table

    def _build_rubrica_pdf_content_resumido(self, rubrica: Rubrica) -> list:
        """
        Build SUMMARY PDF content for a rubrica (1-2 pages max).

        Args:
            rubrica: Rubrica model with relations loaded.

        Returns:
            List of ReportLab flowables.
        """
        story = []
        styles = getSampleStyleSheet()

        # ==================== CUSTOM STYLES ====================

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=6,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=12,
            alignment=1,
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=10,
            spaceBefore=6,
            fontName="Helvetica-Bold",
        )

        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            leading=14,
        )

        # ==================== HEADER ====================

        header_line = Table([[""]], colWidths=[6.5 * inch])
        header_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(header_line)
        story.append(Spacer(1, 0.15 * inch))

        story.append(Paragraph("ACTIVE-IA", title_style))
        story.append(Paragraph("Rúbrica de Evaluación - Guía para Estudiantes", subtitle_style))
        story.append(Spacer(1, 0.2 * inch))

        # ==================== INFO SECTION ====================

        materia = rubrica.materia
        tipo_labels = {
            "TP": "Trabajo Práctico",
            "PARCIAL_1": "Parcial 1",
            "PARCIAL_2": "Parcial 2",
            "RECUPERATORIO_1": "Recuperatorio 1",
            "RECUPERATORIO_2": "Recuperatorio 2",
            "FINAL": "Final",
            "GLOBAL": "Global",
        }
        tipo_label = tipo_labels.get(rubrica.tipo.value, rubrica.tipo.value)

        info_data = [
            ["Materia:", f"{materia.codigo} - {materia.nombre}"],
            ["Tipo:", tipo_label],
            ["Número:", f"#{rubrica.numero}"],
            ["Año:", str(rubrica.anio)],
            ["Puntaje Máximo:", f"{rubrica.puntaje_maximo} puntos"],
        ]

        info_table = Table(info_data, colWidths=[1.5 * inch, 5.0 * inch])
        info_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 0.2 * inch))

        # ==================== TITULO ====================

        title_data = [[Paragraph(f"<b>{rubrica.titulo}</b>", body_style)]]
        title_table = Table(title_data, colWidths=[6.5 * inch])
        title_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(title_table)
        story.append(Spacer(1, 0.25 * inch))

        # ==================== TABLA DE CRITERIOS DETALLADA ====================

        story.append(Paragraph("CRITERIOS DE EVALUACIÓN", heading_style))
        story.append(Spacer(1, 0.15 * inch))

        # Style for criterion details
        criterio_title_style = ParagraphStyle(
            "CriterioTitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#1e3a8a"),
            fontName="Helvetica-Bold",
            spaceAfter=4,
        )

        criterio_desc_style = ParagraphStyle(
            "CriterioDesc",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#334155"),
            leading=12,
            spaceAfter=6,
        )

        criterio_sub_style = ParagraphStyle(
            "CriterioSub",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#475569"),
            leading=11,
            leftIndent=12,
            bulletIndent=6,
        )

        # Build detailed table for each criterion
        for idx, criterio in enumerate(rubrica.criterios_json):
            criterio_id = criterio.get("id", f"C{idx+1}")
            nombre = criterio.get("nombre", "")
            descripcion = criterio.get("descripcion", "")
            peso = criterio.get("peso", 0)
            subcriterios = criterio.get("subcriterios", [])

            # Criterion header with ID, name and weight
            header_text = f"<b>{criterio_id}</b> - {self._escape_xml(nombre)}"

            # Build criterion content
            criterion_content = []
            criterion_content.append(Paragraph(header_text, criterio_title_style))

            # Add description if present
            if descripcion:
                criterion_content.append(Paragraph(self._escape_xml(descripcion), criterio_desc_style))

            # Add subcriterios as bullet points
            if subcriterios:
                subcriterios_text = ""
                for sub in subcriterios:
                    sub_desc = sub.get("descripcion", "")
                    if sub_desc:
                        subcriterios_text += f"• {self._escape_xml(sub_desc)}<br/>"

                if subcriterios_text:
                    criterion_content.append(Paragraph(subcriterios_text, criterio_sub_style))

            # Create table for this criterion (ID/Name/Weight | Content)
            criterio_data = [
                [
                    Paragraph(f"<b>{peso}%</b>", ParagraphStyle(
                        "Weight",
                        parent=styles["Normal"],
                        fontSize=11,
                        textColor=colors.HexColor("#1e3a8a"),
                        fontName="Helvetica-Bold",
                        alignment=1,
                    )),
                    criterion_content
                ]
            ]

            criterio_table = Table(criterio_data, colWidths=[0.7 * inch, 5.8 * inch])
            criterio_table.setStyle(
                TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("VALIGN", (0, 0), (0, 0), "TOP"),
                    ("VALIGN", (1, 0), (1, 0), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ])
            )
            story.append(criterio_table)
            story.append(Spacer(1, 0.12 * inch))

        # ==================== PENALIZACIONES ====================

        if rubrica.penalizaciones_json and len(rubrica.penalizaciones_json) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("PENALIZACIONES", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            pen_data = [["ID", "Descripción", "Descuento"]]
            for pen in rubrica.penalizaciones_json:
                pen_data.append([
                    pen.get("id", ""),
                    Paragraph(pen.get("descripcion", ""), table_cell_style),
                    f"-{pen.get('descuento_porcentaje', 0)}%",
                ])

            pen_table = Table(pen_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            pen_table.setStyle(
                TableStyle([
                    # Header
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#92400e")),
                    # Body
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fffbeb")),
                    # All cells
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#fbbf24")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(pen_table)

        # ==================== CONDICIONES DE DESAPROBACIÓN ====================

        if rubrica.condiciones_desaprobacion_json and len(rubrica.condiciones_desaprobacion_json) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("CONDICIONES DE DESAPROBACIÓN", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            cond_data = [["ID", "Condición", "Nota Final"]]
            for cond in rubrica.condiciones_desaprobacion_json:
                cond_data.append([
                    cond.get("id", ""),
                    Paragraph(cond.get("condicion", ""), table_cell_style),
                    f"Máx: {cond.get('nota_maxima', cond.get('nota_final', 0))}",
                ])

            cond_table = Table(cond_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            cond_table.setStyle(
                TableStyle([
                    # Header
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                    # Body
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fef2f2")),
                    # All cells
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#ef4444")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(cond_table)

        # ==================== FOOTER ====================

        story.append(Spacer(1, 0.3 * inch))

        footer_line = Table([[""]], colWidths=[6.5 * inch])
        footer_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(footer_line)

        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )

        footer_text = f"Guía para estudiantes generada por ACTIVE-IA • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        story.append(Paragraph(footer_text, footer_style))

        return story

    def _build_rubrica_pdf_content_resumido_from_dict(self, data: dict[str, Any]) -> list:
        """
        Build SUMMARY PDF content for a rubrica from dictionary data.

        Args:
            data: Dictionary with rubrica data.

        Returns:
            List of ReportLab flowables.
        """
        story = []
        styles = getSampleStyleSheet()

        # ==================== CUSTOM STYLES ====================

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=6,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=12,
            alignment=1,
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=10,
            spaceBefore=6,
            fontName="Helvetica-Bold",
        )

        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
            leading=14,
        )

        # ==================== HEADER ====================

        header_line = Table([[""]], colWidths=[6.5 * inch])
        header_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(header_line)
        story.append(Spacer(1, 0.15 * inch))

        story.append(Paragraph("ACTIVE-IA", title_style))
        story.append(Paragraph("Rúbrica de Evaluación - Guía para Estudiantes", subtitle_style))
        story.append(Spacer(1, 0.2 * inch))

        # ==================== INFO SECTION ====================

        tipo_labels = {
            "TP": "Trabajo Práctico",
            "PARCIAL_1": "Parcial 1",
            "PARCIAL_2": "Parcial 2",
            "RECUPERATORIO_1": "Recuperatorio 1",
            "RECUPERATORIO_2": "Recuperatorio 2",
            "FINAL": "Final",
            "GLOBAL": "Global",
        }
        tipo_label = tipo_labels.get(data.get("tipo", "TP"), data.get("tipo", "TP"))

        info_data = [
            ["Materia:", data.get("materia_nombre", "N/A")],
            ["Tipo:", tipo_label],
            ["Número:", f"#{data.get('numero', 1)}"],
            ["Año:", str(data.get("anio", datetime.now().year))],
            ["Puntaje Máximo:", f"{data.get('puntaje_maximo', 100)} puntos"],
        ]

        info_table = Table(info_data, colWidths=[1.5 * inch, 5.0 * inch])
        info_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 0.2 * inch))

        # ==================== TITULO ====================

        titulo = data.get("titulo", "Sin título")
        title_data = [[Paragraph(f"<b>{titulo}</b>", body_style)]]
        title_table = Table(title_data, colWidths=[6.5 * inch])
        title_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        story.append(title_table)
        story.append(Spacer(1, 0.25 * inch))

        # ==================== TABLA DE CRITERIOS DETALLADA ====================

        story.append(Paragraph("CRITERIOS DE EVALUACIÓN", heading_style))
        story.append(Spacer(1, 0.15 * inch))

        # Style for criterion details
        criterio_title_style = ParagraphStyle(
            "CriterioTitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#1e3a8a"),
            fontName="Helvetica-Bold",
            spaceAfter=4,
        )

        criterio_desc_style = ParagraphStyle(
            "CriterioDesc",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#334155"),
            leading=12,
            spaceAfter=6,
        )

        criterio_sub_style = ParagraphStyle(
            "CriterioSub",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#475569"),
            leading=11,
            leftIndent=12,
            bulletIndent=6,
        )

        # Build detailed table for each criterion
        criterios = data.get("criterios", [])
        for idx, criterio in enumerate(criterios):
            criterio_id = criterio.get("id", f"C{idx+1}")
            nombre = criterio.get("nombre", "")
            descripcion = criterio.get("descripcion", "")
            peso = criterio.get("peso", 0)
            subcriterios = criterio.get("subcriterios", [])

            # Criterion header with ID, name and weight
            header_text = f"<b>{criterio_id}</b> - {nombre}"

            # Build criterion content
            criterion_content = []
            criterion_content.append(Paragraph(header_text, criterio_title_style))

            # Add description if present
            if descripcion:
                criterion_content.append(Paragraph(descripcion, criterio_desc_style))

            # Add subcriterios as bullet points
            if subcriterios:
                subcriterios_text = ""
                for sub in subcriterios:
                    sub_desc = sub.get("descripcion", "")
                    if sub_desc:
                        subcriterios_text += f"• {sub_desc}<br/>"

                if subcriterios_text:
                    criterion_content.append(Paragraph(subcriterios_text, criterio_sub_style))

            # Create table for this criterion (ID/Name/Weight | Content)
            criterio_data = [
                [
                    Paragraph(f"<b>{peso}%</b>", ParagraphStyle(
                        "Weight",
                        parent=styles["Normal"],
                        fontSize=11,
                        textColor=colors.HexColor("#1e3a8a"),
                        fontName="Helvetica-Bold",
                        alignment=1,
                    )),
                    criterion_content
                ]
            ]

            criterio_table = Table(criterio_data, colWidths=[0.7 * inch, 5.8 * inch])
            criterio_table.setStyle(
                TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("VALIGN", (0, 0), (0, 0), "TOP"),
                    ("VALIGN", (1, 0), (1, 0), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ])
            )
            story.append(criterio_table)
            story.append(Spacer(1, 0.12 * inch))

        # ==================== PENALIZACIONES ====================

        penalizaciones = data.get("penalizaciones", [])
        if penalizaciones and len(penalizaciones) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("PENALIZACIONES", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            pen_data = [["ID", "Descripción", "Descuento"]]
            for pen in penalizaciones:
                pen_data.append([
                    pen.get("id", ""),
                    Paragraph(pen.get("descripcion", ""), table_cell_style),
                    f"-{pen.get('descuento_porcentaje', 0)}%",
                ])

            pen_table = Table(pen_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            pen_table.setStyle(
                TableStyle([
                    # Header
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#92400e")),
                    # Body
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fffbeb")),
                    # All cells
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#fbbf24")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(pen_table)

        # ==================== CONDICIONES DE DESAPROBACIÓN ====================

        condiciones = data.get("condiciones_desaprobacion", [])
        if condiciones and len(condiciones) > 0:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("CONDICIONES DE DESAPROBACIÓN", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            # Style for table cells with word wrap
            table_cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#334155"),
                leading=11,
            )

            cond_data = [["ID", "Condición", "Nota Final"]]
            for cond in condiciones:
                cond_data.append([
                    cond.get("id", ""),
                    Paragraph(cond.get("condicion", ""), table_cell_style),
                    f"Máx: {cond.get('nota_maxima', cond.get('nota_final', 0))}",
                ])

            cond_table = Table(cond_data, colWidths=[0.7 * inch, 4.5 * inch, 1.3 * inch])
            cond_table.setStyle(
                TableStyle([
                    # Header
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                    # Body
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fef2f2")),
                    # All cells
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#ef4444")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(cond_table)

        # ==================== FOOTER ====================

        story.append(Spacer(1, 0.3 * inch))

        footer_line = Table([[""]], colWidths=[6.5 * inch])
        footer_line.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(footer_line)

        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )

        footer_text = f"Vista previa - Guía para estudiantes generada por ACTIVE-IA • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        story.append(Paragraph(footer_text, footer_style))

        return story

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing invalid characters.

        Args:
            filename: Original filename.

        Returns:
            Sanitized filename.
        """
        import re

        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Remove multiple spaces
        filename = re.sub(r"\s+", "_", filename)
        # Remove leading/trailing spaces and dots
        filename = filename.strip(". ")

        return filename
