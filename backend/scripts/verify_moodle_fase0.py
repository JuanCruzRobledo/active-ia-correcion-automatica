#!/usr/bin/env python3
"""Fase 0 — Verificación de la API Moodle (A1 + A3).

Verifica DOS supuestos del plan PLAN_FEAT.md contra el Moodle real, SIN escribir nada:

  A1  ¿`mod_assign_get_submissions` expone archivos descargables
      (plugins[].fileareas[].files[].fileurl) y se bajan con ?token=?
  A3  ¿El assignment del TP usa escala NUMÉRICA (grade > 0) o
      escala CUALITATIVA (grade < 0 ⇒ scale id) tipo Aprobado/Desaprobado?

Reutiliza EXACTAMENTE el patrón de app/services/moodle_service.py
(service=moodle_mobile_app, mod_assign_get_assignments para cmid→instance, etc.).

NO loguea token ni password. El fileurl base (pluginfile.php) no es secreto;
el token se agrega sólo al momento de la descarga de prueba y NO se imprime.

──────────────────────────────────────────────────────────────────────────────
USO (PowerShell):

    $env:MOODLE_HOST     = "https://tup.sied.utn.edu.ar"
    $env:MOODLE_USERNAME = "tu_usuario"
    $env:MOODLE_PASSWORD = "tu_password"
    $env:MOODLE_COURSE_ID = "38"        # moodle_course_id de una Materia
    $env:MOODLE_CMID      = "11237"     # moodle_assign_id (cmid) de una Rúbrica TP
    python backend/scripts/verify_moodle_fase0.py

USO (bash):

    MOODLE_HOST=... MOODLE_USERNAME=... MOODLE_PASSWORD=... \
    MOODLE_COURSE_ID=38 MOODLE_CMID=11237 \
    python backend/scripts/verify_moodle_fase0.py

Dependencia: httpx (ya está en requirements.txt).
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

HOST = (os.environ.get("MOODLE_HOST") or "").rstrip("/")
USERNAME = os.environ.get("MOODLE_USERNAME") or ""
PASSWORD = os.environ.get("MOODLE_PASSWORD") or ""
COURSE_ID = os.environ.get("MOODLE_COURSE_ID") or ""
CMID = os.environ.get("MOODLE_CMID") or ""


def _fail(msg: str) -> None:
    print(f"\n❌ {msg}")
    sys.exit(1)


def _section(title: str) -> None:
    print(f"\n{'─' * 70}\n{title}\n{'─' * 70}")


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


async def ws(client: httpx.AsyncClient, token: str, wsfunction: str, params: dict) -> dict | list:
    full = {
        "wstoken": token,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
        **params,
    }
    resp = await client.get(f"{HOST}/webservice/rest/server.php", params=full)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "exception" in data:
        _fail(f"{wsfunction} devolvió excepción: {data.get('message', data)}")
    return data


async def verify_scale(client: httpx.AsyncClient, token: str) -> int | None:
    """A3 — detecta escala del assignment. Devuelve el assignment INSTANCE id."""
    _section("A3 — Escala del assignment (mod_assign_get_assignments)")
    data = await ws(client, token, "mod_assign_get_assignments", {"courseids[0]": COURSE_ID})

    target_instance: int | None = None
    print(f"Assignments encontrados en course_id={COURSE_ID}:\n")
    for course in data.get("courses", []):
        for a in course.get("assignments", []):
            cmid = a.get("cmid")
            grade = a.get("grade")
            # Interpretación del campo grade de Moodle:
            #   grade > 0  → escala NUMÉRICA, máximo = grade
            #   grade < 0  → escala CUALITATIVA, scale_id = abs(grade)
            #   grade == 0 → sin calificación / "none"
            if grade is None:
                tipo = "desconocido (campo grade ausente)"
            elif grade > 0:
                tipo = f"NUMÉRICA (máximo={grade})"
            elif grade < 0:
                tipo = f"CUALITATIVA / ESCALA (scale_id={abs(grade)})"
            else:
                tipo = "SIN CALIFICACIÓN (grade=0)"
            marca = "  ← OBJETIVO" if str(cmid) == str(CMID) else ""
            print(f"  cmid={cmid:<8} instance_id={a.get('id'):<8} grade={grade!s:<6} {tipo:<40} {a.get('name','')[:30]}{marca}")
            if str(cmid) == str(CMID):
                target_instance = a.get("id")

    if target_instance is None:
        _fail(
            f"El cmid={CMID} no apareció en course_id={COURSE_ID}. "
            "Verificá que MOODLE_CMID sea el cmid (URL ?id=) y MOODLE_COURSE_ID el curso correcto."
        )

    print(
        "\n📌 CONCLUSIÓN A3: revisá la línea '← OBJETIVO'. Si dice CUALITATIVA/ESCALA, "
        "hay que mapear el índice Aprobado/Desaprobado (config). Si dice NUMÉRICA, "
        "para TP se necesita decidir cómo se traduce >=60 a esa escala numérica."
    )
    return target_instance


async def verify_scale_items(client: httpx.AsyncClient, token: str, instance_id: int) -> None:
    """T0.2-bis — descubre los textos+orden de la escala cruzando grades ya puestos.

    mod_assign_get_grades da el índice numérico (graderaw); gradereport_user_get_grade_items
    da el texto formateado (gradeformatted). Cruzando ambos por userid obtenemos índice→texto.
    """
    _section("T0.2-bis — Textos de la escala (índice → 'Aprobado'/'Desaprobado')")
    grades = await ws(client, token, "mod_assign_get_grades", {"assignmentids[0]": instance_id})

    # userid → índice (graderaw) de notas ya puestas, una muestra por valor distinto
    sample: dict[str, int] = {}  # str(grade_value) -> userid
    for a in grades.get("assignments", []):
        for g in a.get("grades", []):
            val = g.get("grade")
            uid = g.get("userid")
            if val is None or uid is None:
                continue
            key = str(val)
            if key not in sample:
                sample[key] = uid
            if len(sample) >= 6:
                break

    if not sample:
        print("⚠️  No hay grades puestos en este assignment todavía → no se puede inferir el texto.")
        print("   Alternativa: en Moodle → Administración del sitio → Calificaciones → Escalas → scale_id=5,")
        print("   anotá los ítems EN ORDEN (el 1º es índice 1).")
        return

    mapping: dict[int, str] = {}
    for grade_val, uid in sample.items():
        try:
            items = await ws(
                client, token, "gradereport_user_get_grade_items",
                {"courseid": COURSE_ID, "userid": uid},
            )
        except SystemExit:
            print("⚠️  gradereport_user_get_grade_items no disponible (permisos). "
                  "Mirá la escala scale_id=5 en Moodle (Admin → Calificaciones → Escalas).")
            return
        for ug in items.get("usergrades", []):
            for gi in ug.get("gradeitems", []):
                if gi.get("itemmodule") == "assign" and gi.get("iteminstance") == instance_id:
                    raw = gi.get("graderaw")
                    txt = gi.get("gradeformatted")
                    if raw is not None and txt and txt not in ("-", ""):
                        mapping[int(round(raw))] = txt

    if mapping:
        print(f"Mapeo descubierto para scale_id=5 (instance {instance_id}):\n")
        for idx in sorted(mapping):
            print(f"  índice {idx} → {mapping[idx]!r}")
        print("\n📌 CONCLUSIÓN T0.2-bis: cargá estos índices en MOODLE_SCALE_MAP del plan (§7.4). "
              "El índice de 'Aprobado' es el que se manda en mod_assign_save_grade para nota >= 60.")
    else:
        print("⚠️  No se pudo cruzar índice→texto. Mirá la escala scale_id=5 directamente en Moodle.")


async def verify_files(client: httpx.AsyncClient, token: str, instance_id: int) -> None:
    """A1 — busca files descargables en las submissions."""
    _section("A1 — Archivos en submissions (mod_assign_get_submissions)")
    data = await ws(client, token, "mod_assign_get_submissions", {"assignmentids[0]": instance_id})

    sample_fileurl: str | None = None
    sample_name: str | None = None
    submitted = 0
    with_files = 0

    for assignment in data.get("assignments", []):
        for sub in assignment.get("submissions", []):
            if sub.get("status") != "submitted":
                continue
            submitted += 1
            for plugin in sub.get("plugins", []):
                if plugin.get("type") != "file":
                    continue
                for area in plugin.get("fileareas", []):
                    for f in area.get("files", []):
                        url = f.get("fileurl")
                        if url:
                            with_files += 1
                            if sample_fileurl is None:
                                sample_fileurl = url
                                sample_name = f.get("filename")
                                print("Ejemplo de file encontrado en una submission:")
                                print(f"  filename : {f.get('filename')}")
                                print(f"  filesize : {f.get('filesize')} bytes")
                                print(f"  mimetype : {f.get('mimetype')}")
                                print(f"  fileurl  : {url}")
                                print(f"  (keys de la submission: {sorted(sub.keys())})")

    print(f"\nSubmissions con status=submitted: {submitted}")
    print(f"Archivos con fileurl detectados : {with_files}")

    if not sample_fileurl:
        _fail(
            "NO se encontró ningún fileurl. Puede que: (a) el assignment use entrega de "
            "texto en línea (onlinetext) en vez de archivo, (b) no haya entregas todavía, "
            "(c) esta versión de Moodle no exponga 'plugins'. Revisá las keys impresas arriba. "
            "→ El plan (A1) necesita ajuste: ver qué plugin trae el contenido."
        )

    # Descarga de prueba — confirma que fileurl + ?token= funciona. NO guarda el archivo.
    _section("A1 (cont.) — Descarga de prueba con ?token= (sin guardar archivo)")
    sep = "&" if "?" in sample_fileurl else "?"
    try:
        r = await client.get(f"{sample_fileurl}{sep}token={token}", timeout=30.0)
        print(f"  HTTP status   : {r.status_code}")
        print(f"  Content-Type  : {r.headers.get('content-type')}")
        print(f"  Bytes recibidos: {len(r.content)}")
        if r.status_code == 200 and r.content:
            print(f"\n✅ CONCLUSIÓN A1: el archivo '{sample_name}' se descarga con fileurl+token. "
                  "El plan de importación es viable tal como está diseñado.")
        else:
            _fail("La descarga no devolvió 200 con contenido. Revisar cómo autentica pluginfile.php en este Moodle.")
    except httpx.HTTPError as e:
        _fail(f"Error descargando el archivo de prueba: {e}")


async def main() -> None:
    missing = [k for k, v in {
        "MOODLE_HOST": HOST, "MOODLE_USERNAME": USERNAME, "MOODLE_PASSWORD": PASSWORD,
        "MOODLE_COURSE_ID": COURSE_ID, "MOODLE_CMID": CMID,
    }.items() if not v]
    if missing:
        _fail(f"Faltan variables de entorno: {', '.join(missing)}. Ver el docstring del script.")

    print(f"🔎 Verificando Moodle en {HOST} (course_id={COURSE_ID}, cmid={CMID})")
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        token = await get_token(client)
        instance_id = await verify_scale(client, token)
        await verify_scale_items(client, token, instance_id)
        await verify_files(client, token, instance_id)

    _section("RESUMEN FASE 0 — Moodle")
    print("Revisá las conclusiones A1 y A3 de arriba y volcalas al PLAN_FEAT.md.")


if __name__ == "__main__":
    asyncio.run(main())
