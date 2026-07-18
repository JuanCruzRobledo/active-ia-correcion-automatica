"""BUG-014: las fechas generadas (filename del Excel de cierre y "Fecha de generación"
del documento consolidado) deben usar hora Argentina (`ahora_ar()`), no UTC.

Se monkeypatchea `ahora_ar` a un instante fijo de AR; si el código sigue usando
`datetime.utcnow()`/`datetime.now()` (bug), la fecha resultante NO coincide con el
valor inyectado y el test falla.
"""

from datetime import datetime

from openpyxl import load_workbook  # noqa: F401 (import estable del entorno)

import app.services.consolidacion_service as consolidacion_mod
import app.services.excel_cierre_cursada as excel_mod
from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.models.enums import EstadoCierreEnum
from app.services.consolidacion_service import ConsolidacionService

# Instante donde UTC y AR caen en días distintos: 2026-07-18 01:30 UTC = 2026-07-17 22:30 AR
_AR_FIJO = datetime(2026, 7, 17, 22, 30, 0)

_EXAMENES_SNAPSHOT = [
    {"id": 1, "tipo": "PARCIAL", "moodle_cmid": 101, "modo_aprobacion": "NUMERICO",
     "nota_minima": 60, "recupera_examen_id": None, "orden": 1},
    {"id": 2, "tipo": "GLOBAL", "moodle_cmid": 103, "modo_aprobacion": "NUMERICO",
     "nota_minima": 6, "recupera_examen_id": None, "orden": 2},
]


def _run():
    alumno = CierreCursadaAlumno(
        moodle_user_id=1, nombre="Ana", apellido="Gómez", email="ana@x.com",
        comision_id=None, comision_nombre="Comisión 1", tutor_nombre="Juan Pérez",
        resultados_examenes=[
            {"examen_id": 1, "valor_real": 80.0},
            {"examen_id": 2, "valor_real": 9.0},
        ],
        global_valor=9.0,
        estado=EstadoCierreEnum("PROMOCIONA"),
        nota_final=8,
    )
    run = CierreCursadaRun(
        id=1, materia_id=1, cuatrimestre_id=1,
        examenes_snapshot=_EXAMENES_SNAPSHOT,
        generado_por_id=1, total_alumnos=1,
        total_promociona=1, total_regulariza=0, total_recursa=0,
    )
    run.created_at = datetime(2026, 1, 1, 12, 0)
    run.alumnos = [alumno]
    return run


def test_filename_excel_cierre_usa_hora_argentina(monkeypatch):
    monkeypatch.setattr(excel_mod, "ahora_ar", lambda: _AR_FIJO)

    _, filename = excel_mod.generar_excel_cierre("Programación 1", _run())

    # AR = 2026-07-17 → "20260717" (no "20260718" que daría el UTC del instante).
    assert "20260717" in filename
    assert "20260718" not in filename


def test_documento_consolidado_un_archivo_usa_hora_argentina(monkeypatch):
    monkeypatch.setattr(consolidacion_mod, "ahora_ar", lambda: _AR_FIJO)

    doc = ConsolidacionService()._build_single_file_document(
        "main.py", "print('hola')", "Solo código"
    )

    assert "2026-07-17 22:30:00" in doc


def test_documento_consolidado_multiarchivo_usa_hora_argentina(monkeypatch):
    monkeypatch.setattr(consolidacion_mod, "ahora_ar", lambda: _AR_FIJO)

    doc = ConsolidacionService()._build_document(
        [("main.py", "print('hola')"), ("util.py", "x = 1")], "Solo código"
    )

    assert "2026-07-17 22:30:00" in doc
