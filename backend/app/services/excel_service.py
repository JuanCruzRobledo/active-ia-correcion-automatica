# app/services/excel_service.py
"""
Excel service for Active-IA.

Business logic for exporting grades to Excel format.
Uses openpyxl to create .xlsx files with student grades and correction status.

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 10.4
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.entrega_repository import EntregaRepository


class ExcelService:
    """Service for generating Excel documents."""

    def __init__(self, db: AsyncSession):
        """Initialize Excel service."""
        self.db = db
        self.entrega_repo = EntregaRepository(db)

    async def exportar_notas_excel(
        self,
        comision_id: int,
        rubrica_id: int,
    ) -> tuple[bytes, str]:
        """
        Export grades to Excel format.

        Args:
            comision_id: ID of the comision.
            rubrica_id: ID of the rubrica.

        Returns:
            Tuple of (Excel file bytes, suggested filename).

        Raises:
            HTTPException 404: No entregas found.
        """
        from fastapi import HTTPException, status

        # Get all entregas for this comision and rubrica
        entregas_result = await self.entrega_repo.get_all(
            comision_id=comision_id,
            rubrica_id=rubrica_id,
            include_inactive=False,
            page=1,
            per_page=1000,  # Get all
        )

        if not entregas_result["items"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay entregas para esta comisión y rúbrica",
            )

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Notas"

        # Get materia and rubrica info from first entrega
        first_entrega = entregas_result["items"][0]
        materia_nombre = first_entrega.comision.materia.nombre
        rubrica_nombre = first_entrega.rubrica.nombre

        # Add title
        ws.merge_cells("A1:E1")
        title_cell = ws["A1"]
        title_cell.value = f"{materia_nombre} - {rubrica_nombre}"
        title_cell.font = Font(size=14, bold=True, color="1F4788")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        title_cell.fill = PatternFill(
            start_color="E7F3FF", end_color="E7F3FF", fill_type="solid"
        )

        # Add headers
        headers = ["Alumno", "Nota", "Estado", "Fecha", "Editado"]
        header_row = 3

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col_num)
            cell.value = header
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="1F4788", end_color="1F4788", fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(
                left=Side(style="thin"),
                right=Side(style="thin"),
                top=Side(style="thin"),
                bottom=Side(style="thin"),
            )

        # Add data rows
        current_row = header_row + 1

        for entrega in entregas_result["items"]:
            # Alumno
            ws.cell(row=current_row, column=1).value = entrega.alumno_nombre

            # Nota y Estado
            if entrega.correccion:
                nota = entrega.correccion.nota
                estado = "CORREGIDA"
                fecha = entrega.correccion.created_at.strftime("%d/%m/%Y %H:%M")
                editado = "Sí" if entrega.correccion.editado_manualmente else "No"

                # Nota cell with color
                nota_cell = ws.cell(row=current_row, column=2)
                nota_cell.value = nota
                nota_cell.fill = self._get_nota_fill(nota)
                nota_cell.alignment = Alignment(horizontal="center")
            else:
                # No corregida
                estado_map = {
                    "SUBIDA": "PENDIENTE",
                    "PENDIENTE": "EN PROCESO",
                    "ERROR": "ERROR",
                }
                estado = estado_map.get(entrega.estado, entrega.estado)
                fecha = "-"
                editado = "-"

                # Nota vacía
                ws.cell(row=current_row, column=2).value = "-"
                ws.cell(row=current_row, column=2).alignment = Alignment(
                    horizontal="center"
                )

            # Estado
            estado_cell = ws.cell(row=current_row, column=3)
            estado_cell.value = estado
            estado_cell.alignment = Alignment(horizontal="center")

            # Fecha
            ws.cell(row=current_row, column=4).value = fecha
            ws.cell(row=current_row, column=4).alignment = Alignment(horizontal="center")

            # Editado
            ws.cell(row=current_row, column=5).value = editado
            ws.cell(row=current_row, column=5).alignment = Alignment(horizontal="center")

            # Add borders to all cells
            for col_num in range(1, 6):
                cell = ws.cell(row=current_row, column=col_num)
                cell.border = Border(
                    left=Side(style="thin"),
                    right=Side(style="thin"),
                    top=Side(style="thin"),
                    bottom=Side(style="thin"),
                )

            current_row += 1

        # Adjust column widths
        ws.column_dimensions["A"].width = 30  # Alumno
        ws.column_dimensions["B"].width = 10  # Nota
        ws.column_dimensions["C"].width = 15  # Estado
        ws.column_dimensions["D"].width = 18  # Fecha
        ws.column_dimensions["E"].width = 10  # Editado

        # Add summary row
        summary_row = current_row + 1
        ws.merge_cells(f"A{summary_row}:B{summary_row}")
        summary_cell = ws.cell(row=summary_row, column=1)
        summary_cell.value = f"Total de entregas: {len(entregas_result['items'])}"
        summary_cell.font = Font(bold=True)

        # Freeze header rows
        ws.freeze_panes = "A4"

        # Save to bytes
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_bytes = excel_buffer.getvalue()
        excel_buffer.close()

        # Build suggested filename
        materia_codigo = first_entrega.comision.materia.codigo
        fecha = datetime.now().strftime("%Y%m%d")

        excel_filename = f"notas_{materia_codigo}_{rubrica_nombre}_{fecha}.xlsx"
        excel_filename = self._sanitize_filename(excel_filename)

        return excel_bytes, excel_filename

    def _get_nota_fill(self, nota: float) -> PatternFill:
        """
        Get background color for nota cell based on value.

        Args:
            nota: Grade value (0-100).

        Returns:
            PatternFill with appropriate color.
        """
        if nota >= 80:
            # Light green
            return PatternFill(
                start_color="D1F2EB", end_color="D1F2EB", fill_type="solid"
            )
        elif nota >= 60:
            # Light yellow
            return PatternFill(
                start_color="FEF9E7", end_color="FEF9E7", fill_type="solid"
            )
        else:
            # Light red
            return PatternFill(
                start_color="FADBD8", end_color="FADBD8", fill_type="solid"
            )

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
