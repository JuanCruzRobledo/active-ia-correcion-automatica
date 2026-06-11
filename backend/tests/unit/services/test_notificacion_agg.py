"""
Tests de notificacion_agg (T6 — agregación PURA de destinatarios).

Cruza los AvanceAlumno de los últimos snapshots y arma los destinatarios de cada
tipo. Sin DB ni red: los "alumnos" son SimpleNamespace con los attrs de AvanceAlumno.
Reglas clave: omitir sin-email; omitir materias/alumnos sin faltantes; matchear
tutor académico por comision == moodle_group_code; nexo por regional.
"""

from types import SimpleNamespace

from app.services.notificacion_agg import (
    construir_destinatarios_alumnos,
    construir_destinatarios_tutores_academicos,
    construir_destinatarios_tutores_nexo,
)


def _u(nums):
    # Simula deudas (formato §9.bis): una deuda de cierre por cada unidad indicada.
    return {"deudas": [{"unidad": n, "tipo": "CIERRE", "estado": "pendiente"} for n in nums]}


def _al(uid, nombre, apellido, email, comision, regional, faltantes, examenes=None):
    return SimpleNamespace(
        moodle_user_id=uid, nombre=nombre, apellido=apellido, email=email,
        comision=comision, regional=regional, actividades_faltantes=faltantes,
        resultados_examenes=examenes,
    )


def _ex(resultado, etiqueta="Parcial 1"):
    # Resultado de un examen en el formato persistido.
    return {"examenes": [{"etiqueta": etiqueta, "resultado": resultado, "rescatado": False}]}


# ===================== alumnos =====================


def test_alumno_con_faltantes_en_dos_materias_se_agrupa_en_uno():
    avances = [
        {"materia_id": 1, "materia": "Prog 1",
         "alumnos": [_al(10, "Ana", "Gómez", "ana@x.com", "M26 C1-09", "Mendoza", _u([4, 5]))]},
        {"materia_id": 2, "materia": "Org Emp",
         "alumnos": [_al(10, "Ana", "Gómez", "ana@x.com", "M26 C1-01", "Mendoza", _u([2]))]},
    ]
    dests = construir_destinatarios_alumnos(avances)
    assert len(dests) == 1
    d = dests[0]
    assert d["email"] == "ana@x.com"
    assert len(d["filas"]) == 2
    materias = {f["materia"] for f in d["filas"]}
    assert materias == {"Prog 1", "Org Emp"}


def test_alumno_fila_lleva_corte_de_la_materia():
    avances = [{
        "materia_id": 1, "materia": "PYE", "unidad_actual": 4, "etiqueta": "Semana",
        "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", _u([2]))],
    }]
    dests = construir_destinatarios_alumnos(avances)
    assert dests[0]["filas"][0]["corte"] == "Semana 4"


def test_tutor_academico_materia_lleva_unidad_actual():
    avances = [{
        "materia_id": 1, "materia": "Prog 1", "unidad_actual": 8, "etiqueta": "Unidad",
        "alumnos": [_al(10, "Ana", "Gómez", "ana@x.com", "M26 C1-09", "Mendoza", _u([4]))],
    }]
    tutores = [_tutor("juan@x.com", [_comi(1, 9)])]
    dests = construir_destinatarios_tutores_academicos(tutores, avances)
    mat = dests[0]["materias"][0]
    assert mat["unidad_actual"] == 8
    assert mat["etiqueta"] == "Unidad"


def test_alumno_sin_email_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1",
                "alumnos": [_al(10, "Ana", "G", None, "M26 C1-09", "Mendoza", _u([4]))]}]
    assert construir_destinatarios_alumnos(avances) == []


def test_alumno_sin_faltantes_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1",
                "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", None)]}]
    assert construir_destinatarios_alumnos(avances) == []


def test_alumno_al_dia_pero_examen_desaprobado_se_incluye():
    avances = [{"materia_id": 1, "materia": "Prog 1", "alumnos": [
        _al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", None,
            examenes=_ex("desaprobado")),
    ]}]
    dests = construir_destinatarios_alumnos(avances)
    assert len(dests) == 1
    fila = dests[0]["filas"][0]
    assert fila["actividad"] == ""  # no le falta nada
    assert fila["examenes"] == "Parcial 1: Desaprobó"


def test_alumno_al_dia_con_examen_ausente_no_dispara():
    # Ausente NO dispara (antes del examen todos figuran ausentes).
    avances = [{"materia_id": 1, "materia": "Prog 1", "alumnos": [
        _al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", None,
            examenes=_ex("ausente")),
    ]}]
    assert construir_destinatarios_alumnos(avances) == []


def test_alumno_solo_lista_materias_con_faltantes():
    avances = [
        {"materia_id": 1, "materia": "Prog 1",
         "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", _u([4]))]},
        {"materia_id": 2, "materia": "Org Emp",
         "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-01", "Mendoza", None)]},  # al día
    ]
    dests = construir_destinatarios_alumnos(avances)
    assert len(dests) == 1
    assert [f["materia"] for f in dests[0]["filas"]] == ["Prog 1"]


# ===================== tutor académico =====================


def _tutor(email, comisiones):
    # comisiones: list[{"materia_id","materia","numero","nombre"}]
    return {"email": email, "nombre": "Juan", "comisiones": comisiones}


def _comi(materia_id, numero, materia="Prog 1"):
    return {"materia_id": materia_id, "materia": materia, "numero": numero, "nombre": f"COMI-{numero}"}


def test_tutor_academico_solo_ve_sus_comisiones():
    # Matching por número: alumno "M26 C1-09" → 9; tutor con COMI-9.
    avances = [{
        "materia_id": 1, "materia": "Prog 1", "alumnos": [
            _al(10, "Ana", "Gómez", "ana@x.com", "M26 C1-09", "Mendoza", _u([4])),
            _al(11, "Beto", "Páez", "beto@x.com", "M26 C1-10", "Córdoba", _u([3])),  # comisión 10
        ],
    }]
    tutores = [_tutor("juan@x.com", [_comi(1, 9)])]
    dests = construir_destinatarios_tutores_academicos(tutores, avances)
    assert len(dests) == 1
    comision = dests[0]["materias"][0]["comisiones"][0]
    assert comision["comision"] == "COMI-9"
    # Beto (comisión 10) NO aparece en los faltantes de la comisión 9.
    assert [a["apellido"] for a in comision["faltantes"]] == ["Gómez"]


def test_tutor_sin_email_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1",
                "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", _u([4]))]}]
    tutores = [_tutor(None, [_comi(1, 9)])]
    assert construir_destinatarios_tutores_academicos(tutores, avances) == []


def test_tutor_sin_alumnos_con_faltantes_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1",
                "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", None)]}]
    tutores = [_tutor("juan@x.com", [_comi(1, 9)])]
    assert construir_destinatarios_tutores_academicos(tutores, avances) == []


def _ex2(r1, r2, e1="Parcial 1", e2="Parcial 2"):
    """Resultados con DOS exámenes (para la matriz)."""
    return {"examenes": [
        {"etiqueta": e1, "resultado": r1, "rescatado": False},
        {"etiqueta": e2, "resultado": r2, "rescatado": False},
    ]}


def test_tutor_matriz_examenes_solo_desaprobados_y_ausentes():
    # Ana reprobó P2 (entra), Beto aprobó todo (NO entra), Carla ausente en P1 (entra).
    avances = [{"materia_id": 1, "materia": "Prog 1", "alumnos": [
        _al(10, "Ana", "Gómez", "ana@x.com", "M26 C1-09", "Mendoza", None,
            examenes=_ex2("aprobado", "desaprobado")),
        _al(11, "Beto", "Páez", "beto@x.com", "M26 C1-09", "Mendoza", None,
            examenes=_ex2("aprobado", "aprobado")),
        _al(12, "Carla", "Díaz", "carla@x.com", "M26 C1-09", "Mendoza", None,
            examenes=_ex2("ausente", "aprobado")),
    ]}]
    tutores = [_tutor("juan@x.com", [_comi(1, 9)])]
    com = construir_destinatarios_tutores_academicos(tutores, avances)[0]["materias"][0]["comisiones"][0]

    assert com["faltantes"] == []  # nadie debe actividades
    assert com["examenes_columnas"] == ["Parcial 1", "Parcial 2"]
    apellidos = [f["apellido"] for f in com["examenes_filas"]]
    assert apellidos == ["Gómez", "Díaz"]  # Beto (todo aprobado) NO aparece
    # Ana: aprobó P1, reprobó P2 → celdas en orden de columnas.
    ana = next(f for f in com["examenes_filas"] if f["apellido"] == "Gómez")
    assert ana["celdas"] == ["Aprobó", "Desaprobó"]


def test_tutor_comision_sin_numero_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1",
                "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", _u([4]))]}]
    tutores = [_tutor("juan@x.com", [{"materia_id": 1, "materia": "Prog 1", "numero": None, "nombre": "X"}])]
    assert construir_destinatarios_tutores_academicos(tutores, avances) == []


def test_tutor_filtro_comisiones_objetivo():
    # Solo se incluye la comisión (1, 9); la (1, 10) queda afuera por el filtro QA.
    avances = [{
        "materia_id": 1, "materia": "Prog 1", "alumnos": [
            _al(10, "Ana", "Gómez", "ana@x.com", "M26 C1-09", "Mendoza", _u([4])),
            _al(11, "Beto", "Páez", "beto@x.com", "M26 C1-10", "Córdoba", _u([3])),
        ],
    }]
    tutores = [_tutor("juan@x.com", [_comi(1, 9), _comi(1, 10)])]
    dests = construir_destinatarios_tutores_academicos(
        tutores, avances, comisiones_objetivo={(1, 9)}
    )
    comisiones = dests[0]["materias"][0]["comisiones"]
    assert [c["comision"] for c in comisiones] == ["COMI-9"]  # solo la objetivo


# ===================== tutor nexo =====================


def test_nexo_agrupa_su_regional_por_materia():
    avances = [
        {"materia_id": 1, "materia": "Prog 1", "alumnos": [
            _al(10, "Ana", "Gómez", "ana@x.com", "M26 C1-09", "Mendoza", _u([4])),
            _al(11, "Beto", "Páez", "beto@x.com", "M26 C1-10", "Córdoba", _u([3])),  # otra regional
        ]},
        {"materia_id": 2, "materia": "Org Emp", "alumnos": [
            _al(12, "Carla", "Díaz", "c@x.com", "M26 C1-01", "Mendoza", _u([2])),
        ]},
    ]
    nexos = [{"email": "nexo.mza@x.com", "nombre": "Nexo Mza", "regional": "Mendoza"}]
    dests = construir_destinatarios_tutores_nexo(nexos, avances)
    assert len(dests) == 1
    d = dests[0]
    assert {m["materia"] for m in d["materias"]} == {"Prog 1", "Org Emp"}
    # En Prog 1 solo está la alumna de Mendoza (Beto de Córdoba queda afuera)
    prog1 = next(m for m in d["materias"] if m["materia"] == "Prog 1")
    assert [f["apellido"] for f in prog1["filas"]] == ["Gómez"]


def test_nexo_materia_lleva_unidad_actual_y_etiqueta():
    avances = [{
        "materia_id": 1, "materia": "PYE", "unidad_actual": 4, "etiqueta": "Semana",
        "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", _u([2]))],
    }]
    nexos = [{"email": "nexo@x.com", "nombre": "Nexo", "regional": "Mendoza"}]
    dests = construir_destinatarios_tutores_nexo(nexos, avances)
    mat = dests[0]["materias"][0]
    assert mat["unidad_actual"] == 4
    assert mat["etiqueta"] == "Semana"


def test_nexo_sin_alumnos_con_faltantes_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1", "alumnos": [
        _al(11, "Beto", "Páez", "beto@x.com", "M26 C1-10", "Córdoba", _u([3])),
    ]}]
    nexos = [{"email": "nexo.mza@x.com", "nombre": "Nexo", "regional": "Mendoza"}]
    assert construir_destinatarios_tutores_nexo(nexos, avances) == []
