"""
Tests de notificacion_render (T4 — adjuntos de las notificaciones).

- formatear_faltantes: lógica PURA texto (UNIDADES vs ACTIVIDADES) → TDD fino.
- construir_pdf_tutor_academico / construir_excel_tutor_nexo: devuelven bytes;
  se verifica estructura (PDF magic; n.º de hojas del Excel == n.º de materias).
"""

import io

import pytest
from openpyxl import load_workbook

from app.services.notificacion_render import (
    construir_excel_tutor_nexo,
    construir_html_alumno,
    construir_pdf_tutor_academico,
    formatear_faltantes,
)


# ===================== formatear_faltantes =====================


def test_formatear_none_devuelve_vacio():
    assert formatear_faltantes(None) == ""
    assert formatear_faltantes({"deudas": []}) == ""


def test_formatear_tp_desaprobado():
    f = {"deudas": [{"unidad": 3, "tipo": "TP", "estado": "desaprobado"}]}
    assert formatear_faltantes(f) == "Unidad 3: TP (desaprobado)"


def test_formatear_tp_no_entregado():
    f = {"deudas": [{"unidad": 3, "tipo": "TP", "estado": "no entregado"}]}
    assert formatear_faltantes(f) == "Unidad 3: TP"


def test_formatear_agrupa_por_unidad():
    f = {"deudas": [
        {"unidad": 3, "tipo": "TP", "estado": "desaprobado"},
        {"unidad": 3, "tipo": "AUTOEVALUACION", "estado": "pendiente"},
        {"unidad": 5, "tipo": "CIERRE", "estado": "pendiente"},
    ]}
    assert formatear_faltantes(f) == "Unidad 3: TP (desaprobado), Autoevaluación · Unidad 5: Cierre"


def test_formatear_quiz_y_quiz_desaprobado():
    f = {"deudas": [
        {"unidad": 2, "tipo": "QUIZ", "estado": "pendiente"},
        {"unidad": 2, "tipo": "QUIZ", "estado": "desaprobado"},
    ]}
    assert formatear_faltantes(f) == "Unidad 2: Quiz, Quiz (desaprobado)"


# ===================== construir_pdf_tutor_academico =====================

MATERIAS_PDF = [
    {
        "materia": "Programación 1",
        "comisiones": [
            {
                "comision": "M26 C1-09",
                "alumnos": [
                    {"apellido": "Gómez", "nombre": "Ana", "faltantes": "Falta Unidad 4 y 5"},
                    {"apellido": "Páez", "nombre": "Beto", "faltantes": "Actividad de cierre unidad 8"},
                ],
            },
            {
                "comision": "M26 C1-10",
                "alumnos": [
                    {"apellido": "Díaz", "nombre": "Carla", "faltantes": "Falta Unidad 3"},
                ],
            },
        ],
    },
    {
        "materia": "Programación 2",
        "comisiones": [
            {"comision": "M26 C2-01", "alumnos": [
                {"apellido": "Ruiz", "nombre": "Eva", "faltantes": "Falta Unidad 2"},
            ]},
        ],
    },
]


def test_pdf_tutor_academico_devuelve_pdf_valido():
    data = construir_pdf_tutor_academico("Juan Tutor", MATERIAS_PDF)
    assert isinstance(data, bytes)
    assert data[:5] == b"%PDF-"
    assert len(data) > 800  # contenido real, no un PDF vacío


def test_pdf_tutor_academico_sin_materias_no_rompe():
    data = construir_pdf_tutor_academico("Juan Tutor", [])
    assert data[:5] == b"%PDF-"


# ===================== construir_excel_tutor_nexo =====================

MATERIAS_XLSX = [
    {
        "materia": "Programación 1",
        "filas": [
            {"comision": "M26 C1-09", "apellido": "Gómez", "nombre": "Ana", "faltantes": "Falta Unidad 4 y 5"},
            {"comision": "M26 C1-10", "apellido": "Díaz", "nombre": "Carla", "faltantes": "Falta Unidad 3"},
        ],
    },
    {
        "materia": "Organización Empresarial",
        "filas": [
            {"comision": "M26 C1-01", "apellido": "Ruiz", "nombre": "Eva", "faltantes": "Falta Unidad 2"},
        ],
    },
]


def test_excel_tutor_nexo_una_hoja_por_materia():
    data = construir_excel_tutor_nexo("Mendoza", MATERIAS_XLSX)
    wb = load_workbook(io.BytesIO(data))
    assert len(wb.sheetnames) == 2  # una hoja por materia


def test_excel_tutor_nexo_header_y_filas():
    data = construir_excel_tutor_nexo("Mendoza", MATERIAS_XLSX)
    wb = load_workbook(io.BytesIO(data))
    ws = wb[wb.sheetnames[0]]
    # Título en fila 1; header en fila 3 (patrón de dashboard_excel)
    headers = [c.value for c in ws[3]]
    assert "Comisión" in headers and "Alumno" in headers and "Actividades faltantes" in headers
    # Las 2 filas de la materia 1 están presentes (busca un apellido)
    valores = [cell.value for row in ws.iter_rows() for cell in row]
    assert any(v and "Gómez" in str(v) for v in valores)


def test_excel_nombres_de_hoja_se_sanitizan_a_31_chars():
    materias = [{"materia": "X" * 50, "filas": []}]
    data = construir_excel_tutor_nexo("Mendoza", materias)
    wb = load_workbook(io.BytesIO(data))
    assert all(len(name) <= 31 for name in wb.sheetnames)


# ===================== construir_html_alumno =====================

FILAS_ALUMNO = [
    {"comision": "M26 C1-09", "materia": "Programación 1", "actividad": "Falta Unidad 4 y 5"},
    {"comision": "M26 C1-01", "materia": "Organización Empresarial", "actividad": "Actividad de cierre unidad 8"},
]


def test_html_alumno_incluye_nombre_y_headers():
    html = construir_html_alumno("Ana Gómez", FILAS_ALUMNO)
    assert "Ana Gómez" in html
    assert "Comisión" in html and "Materia" in html and "Actividad" in html
    assert "<table" in html


def test_html_alumno_una_fila_de_datos_por_materia():
    html = construir_html_alumno("Ana", FILAS_ALUMNO)
    # 1 <tr> de header + 1 por fila de datos
    assert html.count("<tr") == len(FILAS_ALUMNO) + 1


def test_html_alumno_incluye_contenido_de_cada_fila():
    html = construir_html_alumno("Ana", FILAS_ALUMNO)
    assert "Programación 1" in html
    assert "Falta Unidad 4 y 5" in html
    assert "Actividad de cierre unidad 8" in html


def test_html_alumno_escapa_caracteres_especiales():
    html = construir_html_alumno("Ana & <script>", [
        {"comision": "C1", "materia": "M & <b>", "actividad": "x"},
    ])
    assert "&amp;" in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html  # no debe inyectarse markup crudo


def test_html_alumno_usa_estilos_inline():
    # Los clientes de correo ignoran <style>/CSS externo → todo debe ir inline.
    html = construir_html_alumno("Ana", FILAS_ALUMNO)
    assert "style=" in html
    assert "<style" not in html


def test_html_alumno_sin_filas_mensaje_al_dia():
    html = construir_html_alumno("Ana", [])
    assert "<table" not in html  # sin tabla
    assert "Ana" in html
