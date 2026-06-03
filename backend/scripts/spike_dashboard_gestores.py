#!/usr/bin/env python3
"""Spike T0 — Dashboard de Gestores (trazabilidad de avance).

Valida contra el Moodle REAL los supuestos de PLAN_DASHBOARD_GESTORES.md, SIN escribir nada:

  B1  core_course_get_contents → ¿devuelve SECCIONES (id, name, section#) y
      MÓDULOS (cmid, name, modname, pertenencia a sección)? ¿Las secciones
      sirven como "Unidades" y exponen un id estable para mapear a Unidad.moodle_section_id?

  B2  Completion por alumno → ¿core_completion_get_activities_completion_status(courseid,userid)
      funciona con el token mobile y devuelve por cmid el state (0..3) + timecompleted?

  B3  Alternativa de performance → ¿core_course_get_contents con &userid= trae
      completiondata EMBEBIDO (1 sola llamada por alumno en vez de 2)?

  B4  Performance → cuántos alumnos (student) hay y cuánto tarda 1 llamada de completion,
      para estimar el costo del cron (N alumnos × t).

NO loguea token ni password. Descartable (no es código de producción).

──────────────────────────────────────────────────────────────────────────────
USO (PowerShell):

    $env:MOODLE_HOST      = "https://tup.sied.utn.edu.ar"
    $env:MOODLE_USERNAME  = "tu_usuario"
    $env:MOODLE_PASSWORD  = "tu_password"
    $env:MOODLE_COURSE_ID = "38"               # M26 Programación 1
    # opcional: fijar el alumno de muestra; si no, toma el 1er student matriculado
    # $env:MOODLE_SAMPLE_USERID = "12345"
    python backend/scripts/spike_dashboard_gestores.py

USO (bash):

    MOODLE_HOST=... MOODLE_USERNAME=... MOODLE_PASSWORD=... MOODLE_COURSE_ID=38 \
    python backend/scripts/spike_dashboard_gestores.py

Dependencia: httpx (ya está en requirements.txt).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

# Windows: forzar UTF-8 en stdout para que los ✅/❌ no crasheen en cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

HOST = (os.environ.get("MOODLE_HOST") or "").rstrip("/")
USERNAME = os.environ.get("MOODLE_USERNAME") or ""
PASSWORD = os.environ.get("MOODLE_PASSWORD") or ""
COURSE_ID = os.environ.get("MOODLE_COURSE_ID") or ""
SAMPLE_USERID = os.environ.get("MOODLE_SAMPLE_USERID") or ""

# Estados de completion de Moodle (core_completion):
COMPLETION_STATES = {
    0: "incompleta",
    1: "completa",
    2: "completa (aprobada)",
    3: "completa (reprobada)",
}
COMPLETED = {1, 2}  # cuentan como "actividad completada" para unidad_alcanzada


def _fail(msg: str) -> None:
    print(f"\n❌ {msg}")
    sys.exit(1)


def _section(title: str) -> None:
    print(f"\n{'─' * 72}\n{title}\n{'─' * 72}")


async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{HOST}/login/token.php",
        data={"username": USERNAME, "password": PASSWORD, "service": "moodle_mobile_app"},
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data or "token" not in data:
        _fail(f"No se obtuvo token. Respuesta Moodle: {data.get('error', data)}")
    print("✅ Token obtenido (no se imprime por seguridad).")
    return data["token"]


async def ws(
    client: httpx.AsyncClient, token: str, wsfunction: str, params: dict, *, allow_fail: bool = False
) -> tuple[dict | list | None, float]:
    """Llama un web service. Devuelve (data, elapsed_seconds). Si allow_fail, no aborta ante excepción."""
    full = {"wstoken": token, "wsfunction": wsfunction, "moodlewsrestformat": "json", **params}
    t0 = time.perf_counter()
    resp = await client.get(f"{HOST}/webservice/rest/server.php", params=full)
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "exception" in data:
        msg = f"{wsfunction} → excepción Moodle: {data.get('errorcode')}: {data.get('message')}"
        if allow_fail:
            print(f"⚠️  {msg}")
            return None, elapsed
        _fail(msg)
    return data, elapsed


async def b1_contents(client: httpx.AsyncClient, token: str) -> list[dict]:
    """B1 — secciones (unidades) y módulos del curso."""
    _section("B1 — core_course_get_contents (secciones = unidades + módulos)")
    data, elapsed = await ws(client, token, "core_course_get_contents", {"courseid": COURSE_ID})
    if not isinstance(data, list):
        _fail(f"Respuesta inesperada (no es lista de secciones): {type(data)}")
    print(f"⏱  1 llamada core_course_get_contents = {elapsed:.2f}s · {len(data)} secciones\n")

    for sec in data:
        modules = sec.get("modules", [])
        tiene_completion = sum(1 for m in modules if m.get("completion", 0) != 0)
        print(
            f"  sección id={sec.get('id'):<7} section#={sec.get('section'):<3} "
            f"módulos={len(modules):<3} con-completion={tiene_completion:<3} "
            f"nombre={sec.get('name','')[:40]!r}"
        )
        # muestra hasta 3 módulos de la sección
        for m in modules[:3]:
            print(
                f"        · cmid={m.get('id'):<7} modname={m.get('modname',''):<10} "
                f"completion={m.get('completion')} name={m.get('name','')[:38]!r}"
            )

    print(
        "\n📌 B1: confirmá que (a) las secciones tienen un `id` estable (→ Unidad.moodle_section_id), "
        "(b) el `section` # sirve para ordenar/numerar unidades, y (c) los módulos traen `completion`≠0 "
        "(si es 0, esa actividad NO tiene seguimiento de finalización configurado y no cuenta)."
    )
    return data


async def get_sample_students(client: httpx.AsyncClient, token: str) -> list[dict]:
    """Trae alumnos (rol student) del curso para muestra y conteo."""
    _section("B4 (parte 1) — alumnos matriculados (core_enrol_get_enrolled_users)")
    data, elapsed = await ws(
        client, token, "core_enrol_get_enrolled_users",
        {"courseid": COURSE_ID, "options[0][name]": "userfields", "options[0][value]": "id,fullname,roles"},
    )
    if not isinstance(data, list):
        _fail("core_enrol_get_enrolled_users no devolvió lista.")
    students = [
        u for u in data
        if any(r.get("shortname") == "student" for r in (u.get("roles") or []))
    ]
    print(f"⏱  {elapsed:.2f}s · {len(data)} usuarios totales · {len(students)} con rol student")
    return students


async def b2_completion(client: httpx.AsyncClient, token: str, userid: int) -> float:
    """B2 — completion de un alumno vía endpoint dedicado."""
    _section(f"B2 — core_completion_get_activities_completion_status (userid={userid})")
    data, elapsed = await ws(
        client, token, "core_completion_get_activities_completion_status",
        {"courseid": COURSE_ID, "userid": userid}, allow_fail=True,
    )
    if data is None:
        print("⚠️  El endpoint dedicado de completion NO está disponible con este token "
              "(permisos / no habilitado). Caemos a B3 (contents?userid=).")
        return elapsed

    statuses = data.get("statuses", []) if isinstance(data, dict) else []
    completadas = [s for s in statuses if s.get("state") in COMPLETED]
    print(f"⏱  {elapsed:.2f}s · {len(statuses)} actividades con tracking · {len(completadas)} completadas\n")
    for s in statuses[:8]:
        st = s.get("state")
        print(
            f"  cmid={s.get('cmid'):<7} state={st} ({COMPLETION_STATES.get(st, '?')})  "
            f"timecompleted={s.get('timecompleted')}"
        )
    print(
        "\n📌 B2: si esto trae state+cmid por actividad, alcanza para el cálculo: cruzamos cmid→sección "
        "(de B1) → Unidad.numero, y unidad_alcanzada = max(numero) entre las completadas."
    )
    return elapsed


async def b3_contents_userid(client: httpx.AsyncClient, token: str, userid: int) -> float:
    """B3 — ¿contents con userid trae completiondata embebido? (1 sola llamada)."""
    _section(f"B3 — core_course_get_contents con &userid={userid} (completiondata embebido)")
    data, elapsed = await ws(
        client, token, "core_course_get_contents",
        {"courseid": COURSE_ID, "options[0][name]": "userid", "options[0][value]": str(userid)},
        allow_fail=True,
    )
    if data is None or not isinstance(data, list):
        print("⚠️  No se pudo traer contents?userid= (o no aplica).")
        return elapsed

    con_cd = 0
    ejemplo = None
    for sec in data:
        for m in sec.get("modules", []):
            cd = m.get("completiondata")
            if cd is not None:
                con_cd += 1
                if ejemplo is None:
                    ejemplo = (m.get("id"), sec.get("section"), cd)
    print(f"⏱  {elapsed:.2f}s · módulos con `completiondata` embebido: {con_cd}")
    if ejemplo:
        print(f"  ejemplo: cmid={ejemplo[0]} section#={ejemplo[1]} completiondata={ejemplo[2]}")
        print(
            "\n📌 B3: ✅ contents?userid= trae el completion embebido → se puede resolver TODO "
            "(secciones + completion del alumno) en 1 sola llamada por alumno. Mejor para el cron."
        )
    else:
        print("\n📌 B3: contents?userid= NO trae completiondata → usar el endpoint dedicado de B2.")
    return elapsed


async def main() -> None:
    missing = [k for k, v in {
        "MOODLE_HOST": HOST, "MOODLE_USERNAME": USERNAME,
        "MOODLE_PASSWORD": PASSWORD, "MOODLE_COURSE_ID": COURSE_ID,
    }.items() if not v]
    if missing:
        _fail(f"Faltan variables de entorno: {', '.join(missing)}. Ver el docstring del script.")

    print(f"🔎 Spike T0 Dashboard Gestores · {HOST} · course_id={COURSE_ID}")
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        token = await get_token(client)

        await b1_contents(client, token)

        students = await get_sample_students(client, token)
        if SAMPLE_USERID:
            sample_uid = int(SAMPLE_USERID)
        elif students:
            sample_uid = int(students[0]["id"])
            print(f"   → alumno de muestra: id={sample_uid} ({students[0].get('fullname','')})")
        else:
            _fail("No hay alumnos con rol student en el curso → no se puede probar completion.")

        t_b2 = await b2_completion(client, token, sample_uid)
        t_b3 = await b3_contents_userid(client, token, sample_uid)

        _section("B4 — Estimación de performance del cron")
        n = len(students)
        t_call = min(x for x in (t_b2, t_b3) if x > 0) if (t_b2 or t_b3) else 0.0
        print(f"Alumnos (student) en el curso : {n}")
        print(f"Tiempo de 1 llamada/alumno    : ~{t_call:.2f}s (la más barata entre B2/B3)")
        print(f"Estimado serial por materia   : ~{n * t_call:.0f}s ({n} alumnos × {t_call:.2f}s)")
        print("   (El cron corre 1×/día y serializa para no saturar Moodle — lección de Gestión.)")

    _section("RESUMEN SPIKE T0")
    print("Volcá las conclusiones B1–B4 a PLAN_DASHBOARD_GESTORES.md §6 (Moodle) y §11 (performance).")


if __name__ == "__main__":
    asyncio.run(main())
