"""
Tests de `excel_cierre_cursada.generar_excel_cierre` — layout del modelo CORREGIDO
(bugfix cierre-cursada-fix, tarea 12).

Verifica contra el modelo `docs/modelos/modelo planilla de cierre CORREGIDO.xlsx`
(ver diseño, sección "Layout exacto del modelo CORREGIDO"):
  - título "TOTAL MATERIA {NOMBRE}" (merge A1:B1, mayúsculas)
  - resumen de 3 conteos PROMOCIONADOS/REGULARES/RECURSANTES en A2:B4
  - columnas dinámicas Nombre y Apellido | Email | Parcial n... | Global TPI |
    Estado Alumno | Nota Final (Nota Final es una adición deliberada, última columna)
  - barra de bloque por comisión mergeando desde la columna C hasta la última
  - SIN columnas de TPs y SIN gráfico de dona (0 charts)
  - Nota Final = entero o "N/E"; Global TPI = "N/E" cuando `global_valor is None`
"""

import io
from datetime import datetime

from hypothesis import given, strategies as st
from openpyxl import load_workbook

from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.models.enums import EstadoCierreEnum
from app.services.excel_cierre_cursada import (
    _agrupar_por_comision,
    _fmt_nota_final,
    _fmt_valor,
    generar_excel_cierre,
)

# Config congelada de 2 parciales + 1 global (examenes_snapshot), igual shape que el
# service arma en `generar` (ver cierre_cursada_service.py).
_EXAMENES_SNAPSHOT = [
    {"id": 1, "tipo": "PARCIAL", "moodle_cmid": 101, "modo_aprobacion": "NUMERICO",
     "nota_minima": 60, "recupera_examen_id": None, "orden": 1},
    {"id": 2, "tipo": "PARCIAL", "moodle_cmid": 102, "modo_aprobacion": "NUMERICO",
     "nota_minima": 60, "recupera_examen_id": None, "orden": 2},
    {"id": 3, "tipo": "GLOBAL", "moodle_cmid": 103, "modo_aprobacion": "NUMERICO",
     "nota_minima": 6, "recupera_examen_id": None, "orden": 3},
]


def _alumno(
    apellido, nombre, email, estado, *,
    p1=80.0, p2=60.0, global_valor=9.0, nota_final=8,
    comision_nombre="Comisión 1", tutor_nombre="Juan Pérez",
):
    resultados_examenes = [
        {"examen_id": 1, "valor_real": p1},
        {"examen_id": 2, "valor_real": p2},
        {"examen_id": 3, "valor_real": global_valor},
    ]
    return CierreCursadaAlumno(
        moodle_user_id=1, nombre=nombre, apellido=apellido, email=email,
        comision_id=None, comision_nombre=comision_nombre, tutor_nombre=tutor_nombre,
        resultados_examenes=resultados_examenes,
        global_valor=global_valor,
        estado=EstadoCierreEnum(estado),
        nota_final=nota_final,
    )


def _run(alumnos, *, promociona=1, regulariza=0, recursa=0):
    run = CierreCursadaRun(
        id=1, materia_id=1, cuatrimestre_id=1,
        examenes_snapshot=_EXAMENES_SNAPSHOT,
        generado_por_id=1, total_alumnos=len(alumnos),
        total_promociona=promociona, total_regulariza=regulariza, total_recursa=recursa,
    )
    run.created_at = datetime(2026, 1, 1, 12, 0)
    run.alumnos = alumnos
    return run


def _wb(data: bytes):
    return load_workbook(io.BytesIO(data))


def test_titulo_total_materia_merge_a1_b1_mayusculas():
    run = _run([_alumno("Gómez", "Ana", "ana@x.com", "PROMOCIONA")])
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    assert ws["A1"].value == "TOTAL MATERIA PROGRAMACIÓN 1"
    merges = {str(m) for m in ws.merged_cells.ranges}
    assert "A1:B1" in merges


def test_headers_exactos_y_en_orden_2_parciales_1_global():
    run = _run([_alumno("Gómez", "Ana", "ana@x.com", "PROMOCIONA")])
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    fila_headers = next(
        [c.value for c in row]
        for row in ws.iter_rows()
        if row[0].value == "Nombre y Apellido"
    )
    assert fila_headers == [
        "Nombre y Apellido", "Email", "Parcial 1", "Parcial 2",
        "Global TPI", "Estado Alumno", "Nota Final",
    ]


def test_resumen_de_3_conteos_en_a2_b4():
    run = _run(
        [
            _alumno("Gómez", "Ana", "ana@x.com", "PROMOCIONA"),
            _alumno("Pérez", "Bruno", "bruno@x.com", "REGULARIZA"),
        ],
        promociona=1, regulariza=1, recursa=0,
    )
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    assert (ws["A2"].value, ws["B2"].value) == ("PROMOCIONADOS", 1)
    assert (ws["A3"].value, ws["B3"].value) == ("REGULARES", 1)
    assert (ws["A4"].value, ws["B4"].value) == ("RECURSANTES", 0)


def test_barra_de_bloque_mergea_c_hasta_g():
    run = _run([_alumno("Gómez", "Ana", "ana@x.com", "PROMOCIONA")])
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    barra_cell = next(
        c for row in ws.iter_rows() for c in row
        if isinstance(c.value, str) and c.value.startswith("Comisión 1")
    )
    fila = barra_cell.row
    merges = {str(m) for m in ws.merged_cells.ranges}
    assert f"C{fila}:G{fila}" in merges
    # La barra arranca en la columna C (3), no en A.
    assert barra_cell.column == 3


def test_sin_columnas_de_tp_y_sin_dona():
    run = _run([_alumno("Gómez", "Ana", "ana@x.com", "PROMOCIONA")])
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    valores = {c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)}
    columnas_viejas = {"TPs Aprobados", "Autoeval OK", "TPI", "Habilitado para Final"}
    assert not (valores & columnas_viejas)
    assert len(ws._charts) == 0


def test_celda_nota_final_entero_o_ne():
    alumno_con_nf = _alumno("Gómez", "Ana", "ana@x.com", "PROMOCIONA", nota_final=8)
    alumno_sin_nf = _alumno("Pérez", "Bruno", "bruno@x.com", "REGULARIZA", nota_final=None)
    run = _run([alumno_con_nf, alumno_sin_nf], promociona=1, regulariza=1)
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    fila_ana = next(row for row in ws.iter_rows() if row[0].value == "Gómez, Ana")
    fila_bruno = next(row for row in ws.iter_rows() if row[0].value == "Pérez, Bruno")
    assert fila_ana[-1].value == 8
    # Bug 4 (tarea 8.4): REGULARIZA con nota_final=None renderiza la celda "Nota
    # Final" en blanco, no "N/E" (ese formateo queda reservado a las columnas de
    # examen vía `_fmt_valor`).
    assert fila_bruno[-1].value == "" or fila_bruno[-1].value is None


def test_global_tpi_ne_cuando_global_valor_es_none():
    alumno = _alumno(
        "Gómez", "Ana", "ana@x.com", "REGULARIZA",
        global_valor=None, nota_final=None,
    )
    run = _run([alumno], promociona=0, regulariza=1)
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    fila_ana = next(row for row in ws.iter_rows() if row[0].value == "Gómez, Ana")
    # Columnas: Nombre, Email, Parcial 1, Parcial 2, Global TPI, Estado, Nota Final
    assert fila_ana[4].value == "N/E"


# ============================================================================
# _agrupar_por_comision — orden de los bloques de comisión (Bug 3, tarea 5)
# ============================================================================
#
# Property 5: Bug Condition - Bloques de comisión ordenados alfabéticamente (design.md).
# CRITICAL: estos tests DEBEN FALLAR sobre el código sin arreglar — hoy
# `_agrupar_por_comision` arma el dict en el orden de LLEGADA de los alumnos (orden de
# inserción), no alfabético, y el bloque "Sin comisión asignada" queda en la posición del
# primer alumno sin comisión en vez de al final. La falla confirma que el Bug 3 existe.
# NO se debe modificar `_agrupar_por_comision` (ni ningún otro código fuente) para hacer
# pasar estos tests.
# **Validates: Requirements 1.6, 1.7**


def test_bug_bloques_desordenados_no_quedan_alfabeticos():
    """Alumnos que llegan en el orden de comisiones "M26 C1-03", "M26 C1-01",
    "M26 C1-02" -> esperado (tras el fix): las claves de `_agrupar_por_comision`
    empiezan por el bloque de "M26 C1-01", luego "M26 C1-02", luego "M26 C1-03".
    HOY: `_agrupar_por_comision` arma el dict en el orden de llegada de los alumnos
    ("M26 C1-03", "M26 C1-01", "M26 C1-02"), no alfabético."""
    alumnos = [
        _alumno(
            "Gómez", "Ana", "ana@x.com", "PROMOCIONA",
            comision_nombre="M26 C1-03", tutor_nombre=None,
        ),
        _alumno(
            "Pérez", "Bruno", "bruno@x.com", "PROMOCIONA",
            comision_nombre="M26 C1-01", tutor_nombre=None,
        ),
        _alumno(
            "Díaz", "Carla", "carla@x.com", "PROMOCIONA",
            comision_nombre="M26 C1-02", tutor_nombre=None,
        ),
    ]

    titulos = list(_agrupar_por_comision(alumnos).keys())

    assert titulos == ["M26 C1-01", "M26 C1-02", "M26 C1-03"]


def test_bug_sin_comision_asignada_no_queda_al_final():
    """Un alumno sin comisión (`comision_nombre=None`) que llega PRIMERO, seguido de
    dos comisiones reales -> esperado (tras el fix): "Sin comisión asignada" queda
    como ÚLTIMA clave. HOY: `_agrupar_por_comision` lo deja primero, en el orden de
    llegada."""
    alumnos = [
        _alumno(
            "Gómez", "Ana", "ana@x.com", "PROMOCIONA",
            comision_nombre=None, tutor_nombre=None,
        ),
        _alumno(
            "Pérez", "Bruno", "bruno@x.com", "PROMOCIONA",
            comision_nombre="M26 C1-01", tutor_nombre=None,
        ),
        _alumno(
            "Díaz", "Carla", "carla@x.com", "PROMOCIONA",
            comision_nombre="M26 C1-02", tutor_nombre=None,
        ),
    ]

    titulos = list(_agrupar_por_comision(alumnos).keys())

    assert titulos[-1] == "Sin comisión asignada"


# ===================== Property 5 (property-based): orden siempre alfabético =====================
#
# Genera listas de alumnos con `comision_nombre` aleatorios (incluyendo `None`) en orden
# de llegada aleatorio. Pool con distinta capitalización ("m26 c1-01" vs "M26 C1-03") para
# ejercitar el orden case-insensitive, sin que dos nombres del pool colisionen al
# `casefold()` (evita ambigüedad sobre qué bloque "debería" aparecer primero).
# **Validates: Requirements 1.6, 1.7**

_POOL_COMISIONES = ["M26 C1-03", "m26 c1-01", "A27 C1-02", None]


@given(st.lists(st.sampled_from(_POOL_COMISIONES), min_size=1, max_size=8))
def test_prop5_bloques_siempre_alfabeticos_con_sin_comision_al_final(nombres):
    alumnos = [
        _alumno(
            f"Apellido{i}", f"Nombre{i}", f"a{i}@x.com", "PROMOCIONA",
            comision_nombre=nombre, tutor_nombre=None,
        )
        for i, nombre in enumerate(nombres)
    ]

    titulos = list(_agrupar_por_comision(alumnos).keys())

    nombres_reales = sorted(
        {a.comision_nombre for a in alumnos if a.comision_nombre is not None},
        key=str.casefold,
    )
    esperados = list(nombres_reales)
    if any(a.comision_nombre is None for a in alumnos):
        esperados.append("Sin comisión asignada")

    assert titulos == esperados
    if "Sin comisión asignada" in titulos:
        assert titulos[-1] == "Sin comisión asignada"


# ============================================================================
# _fmt_nota_final — celda "Nota Final" en blanco para no promocionados (Bug 4, tarea 6)
# ============================================================================
#
# Property 6: Bug Condition - Nota Final sólo para PROMOCIONA (design.md,
# isBugCondition_nota_no_promociona). CRITICAL: este test DEBE FALLAR sobre el código
# sin arreglar -- hoy `_fmt_nota_final(None)` devuelve "N/E" (mismo formateo que
# `_fmt_valor`), en vez de una celda en blanco (`""`). La falla confirma que el Bug 4
# existe. NO se debe modificar `_fmt_nota_final` (ni ningún otro código fuente) para
# hacer pasar este test.
# **Validates: Requirements 1.8, 1.9**


def test_bug_fmt_nota_final_none_deberia_ser_blanco_no_ne():
    """Bug 4: `_fmt_nota_final(None)` -> esperado (tras el fix) `""` (celda en blanco).
    HOY: devuelve "N/E", igual que `_fmt_valor(None)` (ambos formateadores deberían
    DIVERGER tras el fix: sólo `_fmt_nota_final` pasa a blanco-en-`None`)."""
    assert _fmt_nota_final(None) == ""


# ============================================================================
# Preservación (tarea 7, ANTES del fix de Bug 3 + Bug 4)
# ============================================================================
#
# Property 5: Preservation - Orden intra-bloque y encabezado (Bug 3, design.md).
# Property 6: Preservation - PROMOCIONA numérico, columna N/E de examen y estado (Bug 4).
# Metodología observation-first: se corre el código SIN arreglar con inputs que NO
# disparan cada bug y se captura el comportamiento observado, que debe seguir intacto
# después del fix de la tarea 8 (Bug 3 sólo reordena los BLOQUES por comisión, no los
# alumnos dentro de cada bloque ni el formato del encabezado; Bug 4 sólo cambia el
# render de `_fmt_nota_final`, no `_fmt_valor` ni la clasificación de estado).
#
# - PROMOCIONA conserva su nota (3.9) y estado sin cambios (3.11): ya cubiertos, sin
#   duplicar, por `test_promociona_todos_incluido_global` y los tests de
#   `calcular_estado_cierre` en `test_cierre_cursada_calculo.py`.


def test_preservacion_orden_intrabloque_por_apellido_nombre():
    """Orden intra-bloque (3.7): dentro de un bloque, los alumnos siguen ordenados por
    `(apellido, nombre)` -- comportamiento ya existente en `_escribir_detalle`
    (`sorted(del_grupo, key=lambda x: (x.apellido or "", x.nombre or ""))`). Observado
    sobre el código SIN arreglar: este orden es independiente del orden de llegada de
    los alumnos y no se ve afectado por el Bug 3 (que sólo reordena los BLOQUES).
    **Validates: Requirements 3.7**"""
    alumnos = [
        _alumno("Zeta", "Zoe", "zoe@x.com", "PROMOCIONA", comision_nombre="Comisión 1", tutor_nombre=None),
        _alumno("Alfa", "Ana", "ana@x.com", "PROMOCIONA", comision_nombre="Comisión 1", tutor_nombre=None),
        _alumno("Alfa", "Beto", "beto@x.com", "PROMOCIONA", comision_nombre="Comisión 1", tutor_nombre=None),
    ]
    run = _run(alumnos, promociona=3)
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    nombres_en_orden = [
        row[0].value
        for row in ws.iter_rows()
        if isinstance(row[0].value, str) and "," in row[0].value
    ]
    assert nombres_en_orden == ["Alfa, Ana", "Alfa, Beto", "Zeta, Zoe"]


def test_preservacion_encabezado_de_bloque_incluye_tutor():
    """Encabezado de bloque (3.8): la barra de cada bloque sigue con el formato
    "{comisión} — Tutor: {tutor}" (extiende `test_barra_de_bloque_mergea_c_hasta_g`,
    que sólo verifica el merge/posición, para observar el texto compuesto completo).
    **Validates: Requirements 3.8**"""
    run = _run(
        [
            _alumno(
                "Gómez", "Ana", "ana@x.com", "PROMOCIONA",
                comision_nombre="Comisión 1", tutor_nombre="Juan Pérez",
            )
        ]
    )
    data, _ = generar_excel_cierre("Programación 1", run)
    ws = _wb(data).active

    barra_cell = next(
        c for row in ws.iter_rows() for c in row
        if isinstance(c.value, str) and c.value.startswith("Comisión 1")
    )
    assert barra_cell.value == "Comisión 1 — Tutor: Juan Pérez"


def test_preservacion_una_sola_comision_orden_no_se_altera():
    """Edge (3.7/3.8-scope): con una sola comisión ya no hay otros bloques para
    reordenar -- `_agrupar_por_comision` sigue devolviendo un único bloque con el
    título compuesto intacto. **Validates: Requirements 3.7, 3.8**"""
    alumnos = [
        _alumno(
            "Gómez", "Ana", "ana@x.com", "PROMOCIONA",
            comision_nombre="M26 C1-01", tutor_nombre="Juan Pérez",
        )
    ]
    titulos = list(_agrupar_por_comision(alumnos).keys())
    assert titulos == ["M26 C1-01 — Tutor: Juan Pérez"]


def test_preservacion_solo_sin_comision_asignada_bloque_unico():
    """Edge (3.7/3.8-scope): si TODOS los alumnos están sin comisión, el único bloque
    es "Sin comisión asignada" -- no hay otros bloques con los que reordenar.
    **Validates: Requirements 3.7, 3.8**"""
    alumnos = [
        _alumno("Gómez", "Ana", "ana@x.com", "PROMOCIONA", comision_nombre=None, tutor_nombre=None),
        _alumno("Pérez", "Bruno", "bruno@x.com", "PROMOCIONA", comision_nombre=None, tutor_nombre=None),
    ]
    titulos = list(_agrupar_por_comision(alumnos).keys())
    assert titulos == ["Sin comisión asignada"]


def test_preservacion_fmt_valor_none_sigue_siendo_ne():
    """Columna de examen "N/E" bajo Bug 4 (3.10): `_fmt_valor(None)` sigue devolviendo
    "N/E" sin cambios -- diverge a propósito de `_fmt_nota_final`, que el fix de Bug 4
    (tarea 8) cambiará a celda en blanco (`""`) ante `None`.
    **Validates: Requirements 3.10**"""
    assert _fmt_valor(None) == "N/E"
