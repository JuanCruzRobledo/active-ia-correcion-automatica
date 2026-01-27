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
        rubrica_nombre = first_correccion.entrega.rubrica.nombre
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

        # Custom styles
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#1e40af"),
            spaceAfter=12,
            alignment=1,  # Center
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#1e40af"),
            spaceAfter=10,
        )

        # Header
        story.append(Paragraph("ACTIVE-IA", title_style))
        story.append(Paragraph("Devolución de Trabajo Práctico", styles["Normal"]))
        story.append(Spacer(1, 0.3 * inch))

        # Info section
        entrega = correccion.entrega
        comision = entrega.comision
        materia = comision.materia
        rubrica = entrega.rubrica

        info_data = [
            ["Materia:", f"{materia.codigo} - {materia.nombre}"],
            ["Comisión:", f"{comision.nombre} - {comision.anio}"],
            ["Trabajo:", rubrica.nombre],
            ["Alumno:", entrega.alumno_nombre],
            [
                "Fecha de corrección:",
                correccion.created_at.strftime("%d/%m/%Y %H:%M"),
            ],
        ]

        info_table = Table(info_data, colWidths=[1.5 * inch, 4.5 * inch])
        info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 0.3 * inch))

        # Grade section
        nota_style = ParagraphStyle(
            "Nota",
            parent=styles["Normal"],
            fontSize=24,
            textColor=self._get_nota_color(correccion.nota),
            alignment=1,  # Center
            spaceAfter=20,
        )
        story.append(Paragraph(f"CALIFICACIÓN: {correccion.nota}/100", nota_style))
        story.append(Spacer(1, 0.2 * inch))

        # Criteria evaluation
        story.append(Paragraph("EVALUACIÓN POR CRITERIOS", heading_style))

        criterios = correccion.criterios_json
        for criterio in criterios:
            criterio_data = self._format_criterio(criterio)
            story.append(criterio_data)
            story.append(Spacer(1, 0.15 * inch))

        # Fortalezas
        if correccion.fortalezas:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("FORTALEZAS", heading_style))
            for fortaleza in correccion.fortalezas:
                story.append(Paragraph(f"• {fortaleza}", styles["Normal"]))
                story.append(Spacer(1, 0.05 * inch))

        # Recomendaciones
        if correccion.recomendaciones:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("RECOMENDACIONES", heading_style))
            for i, recomendacion in enumerate(correccion.recomendaciones, 1):
                story.append(Paragraph(f"{i}. {recomendacion}", styles["Normal"]))
                story.append(Spacer(1, 0.05 * inch))

        # Comentario general
        if correccion.comentario_general:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("COMENTARIOS DEL EVALUADOR", heading_style))
            story.append(Paragraph(correccion.comentario_general, styles["Normal"]))

        # Footer
        if correccion.editado_manualmente:
            story.append(Spacer(1, 0.3 * inch))
            footer_style = ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontSize=8,
                textColor=colors.grey,
                alignment=1,
            )
            story.append(
                Paragraph(
                    "Esta corrección fue editada manualmente por el tutor",
                    footer_style,
                )
            )

        return story

    def _format_criterio(self, criterio: dict[str, Any]) -> Table:
        """
        Format a criterion as a table.

        Args:
            criterio: Criterion dictionary.

        Returns:
            ReportLab Table.
        """
        nombre = criterio.get("nombre", "")
        puntaje_obtenido = criterio.get("puntaje_obtenido", 0)
        puntaje_maximo = criterio.get("puntaje_maximo", 0)
        estado = criterio.get("estado", "OK")
        feedback = criterio.get("feedback", "")

        # Estado icon and color
        estado_info = self._get_estado_info(estado)

        # Build table
        data = [
            [
                f"{nombre}",
                f"{puntaje_obtenido}/{puntaje_maximo}",
                f"{estado_info['icon']} {estado}",
            ],
            [feedback, "", ""],
        ]

        table = Table(data, colWidths=[3.5 * inch, 1 * inch, 1.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    # Header row
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("TEXTCOLOR", (2, 0), (2, 0), estado_info["color"]),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    # Feedback row
                    ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, 1), 9),
                    ("SPAN", (0, 1), (-1, 1)),
                    ("TOPPADDING", (0, 1), (-1, 1), 6),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
                    # Border
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#d1d5db")),
                ]
            )
        )

        return table

    def _get_estado_info(self, estado: str) -> dict[str, Any]:
        """Get icon and color for estado."""
        estado_map = {
            "OK": {"icon": "✓", "color": colors.HexColor("#16a34a")},
            "WARNING": {"icon": "⚠", "color": colors.HexColor("#ca8a04")},
            "ERROR": {"icon": "✗", "color": colors.HexColor("#dc2626")},
        }
        return estado_map.get(estado, estado_map["OK"])

    def _get_nota_color(self, nota: float) -> colors.Color:
        """Get color for nota based on value."""
        if nota >= 80:
            return colors.HexColor("#16a34a")  # Green
        elif nota >= 60:
            return colors.HexColor("#ca8a04")  # Yellow
        else:
            return colors.HexColor("#dc2626")  # Red

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
