"""
Tests de moodle_bulk_parser — parsers PUROS de los 2 CSV masivos de Moodle (§R1/R2).

Reemplazan las llamadas per-alumno (1+2N) por 2 descargas masivas parseadas en memoria:
  - export del calificador (notas)  → {uid: {cmid: gradeformatted}}  (alimenta notas_tp)
  - CSV de finalización (completion) → {uid: [{cmid, state}]}        (alimenta completion_statuses)

Ambos CSV keyean por NOMBRE de actividad (no cmid) → se mapea con nombre_a_cmid
(construido desde core_course_get_contents) y la fila→alumno por email.
Muestras basadas en el spike R0 (curso real Prog1, id=38).
"""

import pytest

from app.services.moodle_bulk_parser import (
    construir_indice_nombre_cmid,
    estado_finalizacion_a_state,
    parsear_csv_finalizacion,
    parsear_export_calificador,
    parsear_export_calificador_dual,
)


# ===================== estado de finalización (texto → state 0/1/2/3) =====================


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Finalizado", 1),
        ("Finalizado (ha alcanzado la califiación de aprobado)", 2),  # typo real de Moodle
        ("Finalizado (no ha alcanzado la califiación de aprobado)", 3),
        ("No finalizado", 0),
        ("", 0),
        (None, 0),
    ],
)
def test_estado_finalizacion_a_state(texto, esperado):
    assert estado_finalizacion_a_state(texto) == esperado


# ===================== índice nombre → cmid (puente desde course_contents) =====================


def test_construir_indice_nombre_cmid_normaliza():
    secciones = [
        {"modules": [
            {"id": 111, "name": "Cuestionario de Actividad 1 🧠"},
            {"id": 222, "name": "  TP1 - Estructuras  "},
        ]},
        {"modules": [{"id": 333, "name": "Autoevaluación"}]},
    ]
    idx = construir_indice_nombre_cmid(secciones)
    # match tolerante a mayúsculas/espacios
    assert idx["cuestionario de actividad 1 🧠"] == 111
    assert idx["tp1 - estructuras"] == 222
    assert idx["autoevaluación"] == 333


# ===================== export del calificador (notas) =====================

# Header real del spike: 6 columnas fijas + 1 por item con "<Tipo>:<Nombre> (Real)".
EXPORT_CALIF = (
    'Nombre,Apellido(s),"Número de ID",Institución,Departamento,"Dirección de correo",'
    '"Cuestionario:Cuestionario de Actividad 1 🧠 (Real)","Tarea:TP1 - Estructuras (Real)"\n'
    '"Juan","Pérez","33","Regional UTN","","JUAN@X.COM","10.00","Aprobado"\n'
    '"Ana","Gómez","34","Regional UTN","","ana@x.com","-","Desaprobado"\n'
)

IDX = {"cuestionario de actividad 1 🧠": 111, "tp1 - estructuras": 222}
EMAIL_UID = {"juan@x.com": 1001, "ana@x.com": 1002}


def test_parsear_export_calificador_mapea_cmid_y_nota():
    out = parsear_export_calificador(EXPORT_CALIF, IDX, EMAIL_UID)
    # Juan: quiz 10.00, TP "Aprobado"
    assert out[1001] == {111: "10.00", 222: "Aprobado"}
    # Ana: quiz sin nota "-", TP "Desaprobado"
    assert out[1002] == {111: "-", 222: "Desaprobado"}


def test_parsear_export_calificador_match_email_case_insensitive():
    # "JUAN@X.COM" en el CSV debe matchear "juan@x.com" del padrón.
    out = parsear_export_calificador(EXPORT_CALIF, IDX, EMAIL_UID)
    assert 1001 in out


def test_parsear_export_calificador_item_sin_match_se_ignora():
    # Si una columna de item no matchea ningún cmid, no rompe ni inventa cmid.
    csv = (
        'Nombre,Apellido(s),"Número de ID",Institución,Departamento,"Dirección de correo",'
        '"Cuestionario:Actividad Fantasma (Real)"\n'
        '"Juan","Pérez","33","R","","juan@x.com","7,00"\n'
    )
    out = parsear_export_calificador(csv, IDX, EMAIL_UID)
    assert out.get(1001, {}) == {}  # sin cmid conocido → dict vacío


def test_parsear_export_calificador_alumno_sin_email_en_padron_se_ignora():
    csv = (
        'Nombre,Apellido(s),"Número de ID",Institución,Departamento,"Dirección de correo",'
        '"Cuestionario:Cuestionario de Actividad 1 🧠 (Real)"\n'
        '"Otro","Sujeto","99","R","","desconocido@x.com","9,00"\n'
    )
    out = parsear_export_calificador(csv, IDX, EMAIL_UID)
    assert out == {}  # ningún uid matcheado


# ===================== CSV de finalización (completion) =====================

# Header real: col0 vacío (nombre), col1 email, luego PARES [estado, fecha] (fecha header vacío).
CSV_FIN = (
    ',"Dirección de correo","Cuestionario de Actividad 1 🧠","","TP1 - Estructuras",""\n'
    '"Juan Pérez","juan@x.com","Finalizado","2026-03-20 09:56:59","No finalizado",""\n'
    '"Ana Gómez","ANA@X.COM","Finalizado (ha alcanzado la califiación de aprobado)","2026-03-20","",""\n'
)


def test_parsear_csv_finalizacion_estructura_pares():
    out = parsear_csv_finalizacion(CSV_FIN, IDX, EMAIL_UID)
    # Juan: quiz Finalizado (state 1), TP No finalizado (state 0)
    assert {"cmid": 111, "state": 1} in out[1001]
    assert {"cmid": 222, "state": 0} in out[1001]


def test_parsear_csv_finalizacion_aprobado_es_state_2():
    out = parsear_csv_finalizacion(CSV_FIN, IDX, EMAIL_UID)
    # Ana: quiz "ha alcanzado" → state 2
    assert {"cmid": 111, "state": 2} in out[1002]


def test_parsear_csv_finalizacion_match_email_case_insensitive():
    out = parsear_csv_finalizacion(CSV_FIN, IDX, EMAIL_UID)
    assert 1002 in out  # "ANA@X.COM" matchea "ana@x.com"


def test_parsear_csv_finalizacion_actividad_sin_cmid_se_ignora():
    csv = (
        ',"Dirección de correo","Actividad Fantasma","","Cuestionario de Actividad 1 🧠",""\n'
        '"Juan Pérez","juan@x.com","Finalizado","2026-01-01","Finalizado",""\n'
    )
    out = parsear_csv_finalizacion(csv, IDX, EMAIL_UID)
    # solo el quiz conocido (cmid 111); la fantasma se ignora
    assert out[1001] == [{"cmid": 111, "state": 1}]


# ===================== export del calificador — variante dual (real + porcentaje) =====================

# Mismo item ("Primer Parcial") pedido en las 2 representaciones a la vez — el caso que
# rompería a parsear_export_calificador (una pisaría a la otra al compartir cmid).
EXPORT_CALIF_DUAL = (
    'Nombre,Apellido(s),"Número de ID",Institución,Departamento,"Dirección de correo",'
    '"Tarea:TP1 - Estructuras (Real)",'
    '"Cuestionario:Primer Parcial (Real)","Cuestionario:Primer Parcial (Porcentaje)"\n'
    '"Juan","Pérez","33","Regional UTN","","juan@x.com","Aprobado","70,00","70,00 %"\n'
    '"Ana","Gómez","34","Regional UTN","","ana@x.com","Desaprobado","-","-"\n'
)

IDX_DUAL = {**IDX, "primer parcial": 444}


def test_parsear_export_calificador_dual_preserva_real_y_percentage_del_mismo_cmid():
    out = parsear_export_calificador_dual(EXPORT_CALIF_DUAL, IDX_DUAL, EMAIL_UID)
    # El TP (solo "real") queda con una sola clave.
    assert out[1001][222] == {"real": "Aprobado"}
    # El parcial (real + percentage) preserva AMBOS, ninguno pisa al otro.
    assert out[1001][444] == {"real": "70,00", "percentage": "70,00 %"}


def test_parsear_export_calificador_dual_alumno_sin_notas():
    out = parsear_export_calificador_dual(EXPORT_CALIF_DUAL, IDX_DUAL, EMAIL_UID)
    assert out[1002][444] == {"real": "-", "percentage": "-"}


def test_parsear_export_calificador_dual_columna_sin_sufijo_reconocido_se_ignora():
    csv = (
        'Nombre,Apellido(s),"Número de ID",Institución,Departamento,"Dirección de correo",'
        '"Cuestionario:Primer Parcial"\n'  # sin sufijo de display -> no se puede saber la representación
        '"Juan","Pérez","33","R","","juan@x.com","70,00"\n'
    )
    out = parsear_export_calificador_dual(csv, IDX_DUAL, EMAIL_UID)
    assert out.get(1001, {}) == {}


def test_parsear_export_calificador_dual_item_sin_match_se_ignora():
    csv = (
        'Nombre,Apellido(s),"Número de ID",Institución,Departamento,"Dirección de correo",'
        '"Cuestionario:Actividad Fantasma (Real)"\n'
        '"Juan","Pérez","33","R","","juan@x.com","7,00"\n'
    )
    out = parsear_export_calificador_dual(csv, IDX_DUAL, EMAIL_UID)
    assert out.get(1001, {}) == {}


def test_parsear_export_calificador_dual_match_email_case_insensitive():
    out = parsear_export_calificador_dual(EXPORT_CALIF_DUAL, IDX_DUAL, EMAIL_UID)
    assert 1001 in out
