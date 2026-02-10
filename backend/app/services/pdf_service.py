# app/services/pdf_service.py
"""
PDF service for Active-IA.

Business logic for generating PDF feedback documents for corrections.
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
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correccion import Correccion
from app.repositories.correccion_repository import CorreccionRepository


class PDFService:
    """Service for generating PDF documents."""

    def __init__(self, db: AsyncSession):
        """Initialize PDF service."""
        self.db = db
        self.correccion_repo = CorreccionRepository(db)

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
        correcciones = await self.correccion_repo.get_all(
            comision_id=comision_id,
            rubrica_id=rubrica_id,
            page=1,
            per_page=1000,  # Get all
        )

        if not correcciones["items"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay correcciones para esta comisión y rúbrica",
            )

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for correccion in correcciones["items"]:
                # Generate PDF for this correction
                pdf_bytes = await self.generar_pdf_devolucion(correccion.id)

                # Sanitize alumno name for filename
                alumno_safe = self._sanitize_filename(
                    correccion.entrega.alumno_nombre
                )

                # Add PDF to ZIP
                pdf_filename = f"{alumno_safe}_devolucion.pdf"
                zip_file.writestr(pdf_filename, pdf_bytes)

        # Get ZIP bytes
        zip_bytes = zip_buffer.getvalue()
        zip_buffer.close()

        # Build suggested filename
        # Get materia and rubrica info from first correction
        first_correccion = correcciones["items"][0]
        materia_codigo = first_correccion.entrega.comision.materia.codigo
        rubrica_nombre = first_correccion.entrega.rubrica.titulo
        fecha = datetime.now().strftime("%Y%m%d")

        zip_filename = f"devoluciones_{materia_codigo}_{rubrica_nombre}_{fecha}.zip"
        zip_filename = self._sanitize_filename(zip_filename)

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
                bullet = Paragraph(f"• {fortaleza}", list_style)
                story.append(bullet)
                story.append(Spacer(1, 0.08 * inch))

        # ==================== RECOMENDACIONES ====================

        if correccion.recomendaciones and len(correccion.recomendaciones) > 0:
            story.append(Spacer(1, 0.25 * inch))
            story.append(Paragraph("RECOMENDACIONES", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            for i, recomendacion in enumerate(correccion.recomendaciones, 1):
                rec_para = Paragraph(f"{i}. {recomendacion}", list_style)
                story.append(rec_para)
                story.append(Spacer(1, 0.08 * inch))

        # ==================== COMENTARIO GENERAL ====================

        if correccion.comentario_general:
            story.append(Spacer(1, 0.25 * inch))
            story.append(Paragraph("COMENTARIOS DEL EVALUADOR", heading_style))
            story.append(Spacer(1, 0.1 * inch))

            comment_data = [[Paragraph(correccion.comentario_general, body_style)]]
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

        feedback_para = Paragraph(feedback, feedback_style)

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
