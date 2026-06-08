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


def _al(uid, nombre, apellido, email, comision, regional, faltantes):
    return SimpleNamespace(
        moodle_user_id=uid, nombre=nombre, apellido=apellido, email=email,
        comision=comision, regional=regional, actividades_faltantes=faltantes,
    )


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


def test_alumno_sin_email_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1",
                "alumnos": [_al(10, "Ana", "G", None, "M26 C1-09", "Mendoza", _u([4]))]}]
    assert construir_destinatarios_alumnos(avances) == []


def test_alumno_sin_faltantes_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1",
                "alumnos": [_al(10, "Ana", "G", "ana@x.com", "M26 C1-09", "Mendoza", None)]}]
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
    assert [a["apellido"] for a in comision["alumnos"]] == ["Gómez"]  # Beto (com 10) NO aparece


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


def test_nexo_sin_alumnos_con_faltantes_se_omite():
    avances = [{"materia_id": 1, "materia": "Prog 1", "alumnos": [
        _al(11, "Beto", "Páez", "beto@x.com", "M26 C1-10", "Córdoba", _u([3])),
    ]}]
    nexos = [{"email": "nexo.mza@x.com", "nombre": "Nexo", "regional": "Mendoza"}]
    assert construir_destinatarios_tutores_nexo(nexos, avances) == []
