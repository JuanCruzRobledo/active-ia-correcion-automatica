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
    examen_para_atender,
    formatear_examenes,
    formatear_faltantes,
    label_resultado_examen,
    tiene_examen_desaprobado,
)


def test_examen_para_atender_incluye_desaprobado_y_ausente():
    assert examen_para_atender(None) is False
    assert examen_para_atender({"examenes": [{"resultado": "aprobado"}]}) is False
    assert examen_para_atender({"examenes": [{"resultado": "ausente"}]}) is True
    assert examen_para_atender({"examenes": [{"resultado": "desaprobado"}]}) is True


def test_label_resultado_examen():
    assert label_resultado_examen(None) == "—"
    assert label_resultado_examen({"resultado": "aprobado"}) == "Aprobó"
    assert label_resultado_examen({"resultado": "desaprobado"}) == "Desaprobó"
    assert label_resultado_examen({"resultado": "ausente"}) == "Ausente"
    # rescatado → aprobado con marca (R).
    assert label_resultado_examen({"resultado": "aprobado", "rescatado": True}) == "Aprobó (R)"


# ===================== tiene_examen_desaprobado (disparo) =====================


def test_tiene_examen_desaprobado_true_solo_con_desaprobado():
    assert tiene_examen_desaprobado(None) is False
    assert tiene_examen_desaprobado({"examenes": []}) is False
    # Ausente NO dispara (antes del examen todos están ausentes).
    assert tiene_examen_desaprobado(
        {"examenes": [{"resultado": "ausente"}, {"resultado": "aprobado"}]}
    ) is False
    assert tiene_examen_desaprobado(
        {"examenes": [{"resultado": "desaprobado"}]}
    ) is True


# ===================== formatear_examenes =====================


def test_formatear_examenes_none_devuelve_vacio():
    assert formatear_examenes(None) == ""
    assert formatear_examenes({"examenes": []}) == ""


def test_formatear_examenes_aprobado_y_ausente():
    r = {"examenes": [
        {"etiqueta": "Parcial 1", "resultado": "aprobado", "rescatado": False},
        {"etiqueta": "Parcial 2", "resultado": "ausente", "rescatado": False},
    ]}
    assert formatear_examenes(r) == "Parcial 1: Aprobó · Parcial 2: Ausente"


def test_formatear_examenes_rescatado_marca_recuperado():
    r = {"examenes": [
        {"etiqueta": "Parcial 2", "resultado": "aprobado", "rescatado": True},
    ]}
    assert formatear_examenes(r) == "Parcial 2: Aprobó (recuperado)"


def test_formatear_examenes_desaprobado():
    r = {"examenes": [{"etiqueta": "Global 1", "resultado": "desaprobado", "rescatado": False}]}
    assert formatear_examenes(r) == "Global 1: Desaprobó"


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


def test_formatear_con_etiqueta_semana():
    # Materias por semana (ej. PYE) → "Semana" en vez de "Unidad".
    f = {"deudas": [
        {"unidad": 8, "tipo": "QUIZ", "estado": "pendiente"},
        {"unidad": 8, "tipo": "TP", "estado": "desaprobado"},
    ]}
    assert formatear_faltantes(f, "Semana") == "Semana 8: Quiz, TP (desaprobado)"


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

def _comi_pdf(comision, faltantes=None, columnas=None, filas=None):
    return {
        "comision": comision,
        "faltantes": faltantes or [],
        "examenes_columnas": columnas or [],
        "examenes_filas": filas or [],
    }


MATERIAS_PDF = [
    {
        "materia": "Programación 1",
        "comisiones": [
            _comi_pdf("M26 C1-09", faltantes=[
                {"apellido": "Gómez", "nombre": "Ana", "detalle": "Falta Unidad 4 y 5"},
                {"apellido": "Páez", "nombre": "Beto", "detalle": "Actividad de cierre unidad 8"},
            ]),
            _comi_pdf("M26 C1-10", faltantes=[
                {"apellido": "Díaz", "nombre": "Carla", "detalle": "Falta Unidad 3"},
            ]),
        ],
    },
    {
        "materia": "Programación 2",
        "comisiones": [
            _comi_pdf("M26 C2-01", faltantes=[
                {"apellido": "Ruiz", "nombre": "Eva", "detalle": "Falta Unidad 2"},
            ]),
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


def test_excel_tutor_nexo_muestra_corte_y_fecha_creacion():
    materias = [
        {"materia": "Prog 1", "unidad_actual": 8, "etiqueta": "Unidad", "filas": [
            {"comision": "M26 C1-09", "apellido": "Gómez", "nombre": "Ana", "faltantes": "Falta Unidad 4"},
        ]},
        {"materia": "PYE", "unidad_actual": 4, "etiqueta": "Semana", "filas": [
            {"comision": "M26 C1-01", "apellido": "Ruiz", "nombre": "Eva", "faltantes": "Falta Semana 2"},
        ]},
    ]
    wb = load_workbook(io.BytesIO(construir_excel_tutor_nexo("Mendoza", materias)))
    # Línea de corte (hasta qué unidad/semana se evalúa) + fecha de creación.
    assert wb["Prog 1"]["A2"].value == "Corte: hasta Unidad 8"
    assert wb["PYE"]["A2"].value == "Corte: hasta Semana 4"
    assert "Documento generado el" in wb["Prog 1"]["A3"].value
    # El header quedó en la fila 4 y los datos en la 5.
    assert wb["Prog 1"]["A4"].value == "Comisión"


def test_excel_tutor_nexo_unidad_actual_none_muestra_guion():
    materias = [{"materia": "Prog 1", "unidad_actual": None, "etiqueta": "Unidad", "filas": [
        {"comision": "C1", "apellido": "G", "nombre": "A", "faltantes": "x"},
    ]}]
    wb = load_workbook(io.BytesIO(construir_excel_tutor_nexo("Mendoza", materias)))
    assert wb["Prog 1"]["A2"].value == "Corte: —"


def test_excel_tutor_nexo_header_y_filas():
    data = construir_excel_tutor_nexo("Mendoza", MATERIAS_XLSX)
    wb = load_workbook(io.BytesIO(data))
    ws = wb[wb.sheetnames[0]]
    # Título en fila 1; corte en 2; fecha de creación en 3; header en fila 4.
    headers = [c.value for c in ws[4]]
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


def test_html_alumno_incluye_corte_y_fecha_creacion():
    html = construir_html_alumno("Ana", [
        {"comision": "C1", "materia": "Prog 1", "actividad": "Falta U4",
         "examenes": "—", "corte": "Unidad 8"},
    ])
    assert "Hasta" in html  # header de la columna de corte
    assert "Unidad 8" in html  # valor del corte
    assert "Documento generado el" in html  # fecha de creación


def test_html_alumno_incluye_columna_examenes():
    html = construir_html_alumno("Ana", [
        {"comision": "C1", "materia": "Prog 1", "actividad": "Falta U4",
         "examenes": "Parcial 1: Desaprobó"},
    ])
    assert "Exámenes" in html  # header de la columna
    assert "Parcial 1: Desaprobó" in html  # valor de la fila


def test_pdf_tutor_academico_con_matriz_examenes_genera_apartado():
    materias = [{
        "materia": "Programación 1",
        "comisiones": [_comi_pdf(
            "M26 C1-09",
            columnas=["Parcial 1", "Parcial 2", "Global 1"],
            filas=[
                {"apellido": "Gómez", "nombre": "Ana",
                 "celdas": ["Aprobó", "Desaprobó", "Ausente"]},
            ],
        )],
    }]
    data = construir_pdf_tutor_academico("Juan Tutor", materias)
    assert data[:5] == b"%PDF-"
    assert len(data) > 800  # la matriz de exámenes se renderizó
