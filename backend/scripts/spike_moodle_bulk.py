#!/usr/bin/env python3
"""Spike R0 — Refactor Moodle carga masiva (PLAN_REFACTOR_MOODLE_BULK.md §R0).

Valida los DOS supuestos del refactor, de forma independiente, SIN escribir nada en
la DB y pegándole a Moodle lo MÍNIMO (one-shot, sin loops por alumno). User-Agent
identificable. NO loguea token ni password; enmascara nombres/emails de alumnos (PII).

  A  NOTAS BULK — ¿gradereport_user_get_grade_items con userid=0 devuelve las notas
     de TODOS los alumnos en 1 sola llamada? ¿El token tiene permiso? Reporta cuántos
     usergrades vinieron y una muestra de gradeitems (cmid + gradeformatted).

  B  CSV FINALIZACIÓN — ¿se puede bajar /report/progress/index.php?course=X&format=csv
     con login programático (usuario/clave que YA tenemos cifrados)? Reporta el
     content-type, la fila de headers (nombres de actividad) y una fila de datos con
     el nombre/email ENMASCARADOS (los valores de completion se muestran tal cual).

──────────────────────────────────────────────────────────────────────────────
USO (dentro del contenedor backend):

    docker compose -f docker-compose.local.yml exec \
      -e MOODLE_COURSE_ID=38 \
      backend python scripts/spike_moodle_bulk.py

  (si no pasás MOODLE_COURSE_ID, usa la 1ra materia configurada accesible)

Dependencias: httpx (ya instalado) + el paquete `app` (PYTHONPATH=/app). Descartable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

MOODLE_COURSE_ID = os.environ.get("MOODLE_COURSE_ID") or ""
# User-Agent identificable: que el admin de Moodle sepa quiénes somos (no anónimo).
UA = "Active-IA/1.0 (integracion academica TUD; spike R0)"


def _section(title: str) -> None:
    print(f"\n{'─' * 72}\n{title}\n{'─' * 72}")


def _mask(s: str) -> str:
    """Enmascara PII: deja 2 primeros chars + longitud (no vuelca nombres/emails)."""
    s = (s or "").strip()
    if not s:
        return "∅"
    return f"{s[:2]}…({len(s)})"


async def _resolver_usuario_y_curso(db):
    """Devuelve (usuario, token, host, course_id) reusando credenciales del cron."""
    from sqlalchemy import select

    from app.models.avance import SnapshotCronConfig
    from app.repositories.materia_repository import MateriaRepository
    from app.repositories.usuario_repository import UsuarioRepository
    from app.services.moodle_service import MoodleService
    from app.services.snapshot_service import SnapshotService

    cfg = (
        await db.execute(select(SnapshotCronConfig).where(SnapshotCronConfig.id == 1))
    ).scalar_one_or_none()
    usuario_repo = UsuarioRepository(db)
    usuario = None
    if cfg and cfg.usuario_id:
        usuario = await usuario_repo.get_by_id(cfg.usuario_id)
    if usuario is None or not getattr(usuario, "moodle_username", None):
        print("⚠️  No hay usuario con credenciales de Moodle (cron config). Abortando.")
        return None

    snap = SnapshotService(db)
    token, host = await snap.token_de_usuario(usuario)
    moodle = MoodleService(db)

    # Curso: el pasado por env, o el 1ro configurado accesible.
    if MOODLE_COURSE_ID:
        course_id = int(MOODLE_COURSE_ID)
    else:
        materias = await MateriaRepository(db).get_configuradas_dashboard()
        course_id = next((m.moodle_course_id for m in materias if m.moodle_course_id), 0)
        if not course_id:
            print("⚠️  No hay materias configuradas y no pasaste MOODLE_COURSE_ID.")
            return None
    return usuario, token, host, course_id, moodle


# ──────────────────────────────────────────────────────────────────────────────
# A — Notas en bulk (userid=0)
# ──────────────────────────────────────────────────────────────────────────────
async def _fallback_por_grupo(client, url, token, course_id, moodle, host) -> None:
    """Si userid=0 es demasiado pesado, medir el approach chunked por grupo (comisión)."""
    print("\n   ── Fallback: chunking por grupo (comisión) ──")
    g_url = f"{host.rstrip('/')}/webservice/rest/server.php"
    try:
        grupos = await client.get(g_url, params={
            "wstoken": token, "wsfunction": "core_group_get_course_groups",
            "moodlewsrestformat": "json", "courseid": course_id,
        }, timeout=60.0)
        grupos = grupos.json()
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️  no pude listar grupos: {type(e).__name__}: {e!r}")
        return
    if isinstance(grupos, dict) and "exception" in grupos:
        print(f"   ⚠️  excepción listando grupos: {grupos.get('message')}")
        return
    print(f"   grupos en el curso: {len(grupos)} → el chunked haría ~{len(grupos)} llamadas")
    if not grupos:
        return
    gid = grupos[0].get("id")
    try:
        data, dt, nbytes = await _ws_grades(client, url, token, course_id, groupid=gid, timeout=120.0)
        ug = data.get("usergrades", []) if isinstance(data, dict) else []
        print(f"   grupo[0] id={gid}: {len(ug)} alumno(s) · {dt:.1f}s · {nbytes/1024:.0f} KB → "
              f"{'VIABLE ✅' if not (isinstance(data, dict) and 'exception' in data) else 'excepción ❌'}")
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️  WS por grupo también falló: {type(e).__name__}: {e!r}")


async def _ws_grades(client, url, token, course_id, *, userid=0, groupid=0, timeout=180.0):
    """Llama gradereport_user_get_grade_items y devuelve (data, segundos, tamaño_bytes)."""
    import time

    params = {
        "wstoken": token,
        "wsfunction": "gradereport_user_get_grade_items",
        "moodlewsrestformat": "json",
        "courseid": course_id,
        "userid": userid,
        "groupid": groupid,
    }
    t0 = time.monotonic()
    resp = await client.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    dt = time.monotonic() - t0
    return resp.json(), dt, len(resp.content)


async def parte_a_notas_bulk(token, host, course_id, moodle, client) -> None:
    _section("A — Notas BULK: gradereport_user_get_grade_items con userid=0")
    url = f"{host.rstrip('/')}/webservice/rest/server.php"
    data = None
    try:
        data, dt, nbytes = await _ws_grades(client, url, token, course_id, timeout=180.0)
        print(f"   ⏱  respondió en {dt:.1f}s · {nbytes/1024:.0f} KB")
    except Exception as e:  # noqa: BLE001
        print(f"❌ userid=0 falló → {type(e).__name__}: {e!r}")
        print("   → Probable: respuesta gigante (772 alumnos) → ReadTimeout / conexión cortada.")
        await _fallback_por_grupo(client, url, token, course_id, moodle, host)
        return

    if isinstance(data, dict) and "exception" in data:
        print(f"❌ Moodle devolvió excepción: {data.get('errorcode')} — {data.get('message')}")
        print("   → Si es de permisos, el token NO puede ver notas de otros (userid=0).")
        await _fallback_por_grupo(client, url, token, course_id, moodle, host)
        return

    usergrades = data.get("usergrades", []) if isinstance(data, dict) else []
    print(f"✅ Respondió sin excepción. usergrades = {len(usergrades)} alumno(s)")
    if not usergrades:
        print("   ⚠️  Vino vacío. ¿El curso no tiene alumnos o el token ve solo lo propio?")
        return

    # Comparar contra el padrón (1 request extra, cacheado) — sanity check del bulk.
    try:
        enrolled = await moodle.get_enrolled_users_full(token, host, course_id, client=client)
        students = [
            u for u in enrolled
            if isinstance(u, dict)
            and any(r.get("shortname") == "student" for r in (u.get("roles") or []))
        ]
        print(f"   padrón (core_enrol, rol student) = {len(students)} alumno(s)")
        print(f"   → {'COINCIDE (o cercano)' if len(usergrades) >= len(students) else 'MENOS que el padrón ⚠️'}")
    except Exception as e:  # noqa: BLE001
        print(f"   (no pude comparar contra el padrón: {str(e)[:80]})")

    # Muestra del 1er alumno: estructura de gradeitems (cmid + gradeformatted).
    u0 = usergrades[0]
    items = u0.get("gradeitems", []) or []
    con_cmid = [it for it in items if it.get("cmid") is not None]
    print(f"\n   muestra alumno[0] (userid={u0.get('userid')}): {len(items)} gradeitems, "
          f"{len(con_cmid)} con cmid")
    for it in con_cmid[:6]:
        print(f"     · cmid={it.get('cmid'):<8} "
              f"name={_mask(it.get('itemname') or '')!s:<14} "
              f"gradeformatted={it.get('gradeformatted')!r}")
    print("\n📌 A: confirmá que usergrades ≈ nº de alumnos y que hay cmid+gradeformatted. "
          "Eso valida _pivot_usergrades (R1).")


# ──────────────────────────────────────────────────────────────────────────────
# B — CSV de finalización (login programático)
# ──────────────────────────────────────────────────────────────────────────────
async def _login(client, usuario, host) -> bool:
    """Login programático → cookie MoodleSession. Reusa credenciales cifradas."""
    from app.core.security import decrypt_api_key

    password = decrypt_api_key(usuario.moodle_password_encrypted)
    base = host.rstrip("/")
    r = await client.get(f"{base}/login/index.php", timeout=30.0)
    m = re.search(r'name="logintoken"\s+value="([^"]+)"', r.text)
    form = {"username": usuario.moodle_username, "password": password}
    if m:
        form["logintoken"] = m.group(1)
    await client.post(f"{base}/login/index.php", data=form, timeout=30.0)
    ok = any("MoodleSession" in c for c in client.cookies.keys())
    print(f"   sesión web: {'✅ cookie MoodleSession presente' if ok else '⚠️ sin cookie'}")
    return ok


async def parte_a2_grade_export(usuario, host, course_id, client) -> None:
    """A2 — export del calificador vía sesión (idea original del usuario). TXT (compacto)."""
    _section("A2 — Export calificador: grade/export/txt vía sesión")
    base = host.rstrip("/")
    if not await _login(client, usuario, host):
        return
    # 1) GET la página del form de export TXT → sesskey + itemids.
    idx = f"{base}/grade/export/txt/index.php"
    try:
        r = await client.get(idx, params={"id": course_id}, timeout=60.0)
    except Exception as e:  # noqa: BLE001
        print(f"❌ No pude cargar el form de export: {type(e).__name__}: {e!r}")
        return
    sesskey = None
    for pat in (
        r'name="sesskey"\s+value="([^"]+)"',
        r'value="([^"]+)"\s+name="sesskey"',
        r'"sesskey":"([^"]+)"',
        r'sesskey=([A-Za-z0-9]+)',
    ):
        m = re.search(pat, r.text)
        if m:
            sesskey = m.group(1)
            break
    itemids = re.findall(r'name="itemids\[(\d+)\]"', r.text)
    print(f"   form: sesskey={'OK' if sesskey else 'NO'} · itemids detectados={len(itemids)}")
    if not sesskey:
        print(f"   ⚠️  no encontré sesskey. primeros 160: {r.text[:160]!r}")
        return
    sesskey_m = type("M", (), {"group": lambda self, n: sesskey})()

    # 2) POST al export con TODOS los itemids + opciones mínimas.
    form = {
        "mform_isexpanded_id_gradeitems": "1",
        "checkbox_controller1": "1",
        "id": str(course_id),
        "sesskey": sesskey_m.group(1),
        "_qf__grade_export_form": "1",
        "export_feedback": "0",
        "export_onlyactive": "1",
        "display[real]": "1", "display[percentage]": "0", "display[letter]": "0",
        "decimals": "2",
        "separator": "comma",
        "submitbutton": "Descargar",
    }
    for iid in itemids:
        form[f"itemids[{iid}]"] = "1"
    export_url = f"{base}/grade/export/txt/export.php"
    try:
        r = await client.post(export_url, data=form, timeout=120.0)
    except Exception as e:  # noqa: BLE001
        print(f"❌ POST export falló: {type(e).__name__}: {e!r}")
        return
    ctype = r.headers.get("content-type", "")
    cuerpo = r.text or ""
    print(f"   POST {export_url} → HTTP {r.status_code} · {ctype} · {len(r.content)/1024:.0f} KB")
    lineas = cuerpo.splitlines()
    if "<html" in cuerpo[:200].lower() or not lineas:
        # Quizá el download sale del propio index.php (sin export.php). Reintento.
        print("   ⚠️  no parece archivo. Reintento POST contra index.php …")
        try:
            r = await client.post(idx, params={"id": course_id}, data=form, timeout=120.0)
            ctype = r.headers.get("content-type", "")
            cuerpo = r.text or ""
            lineas = cuerpo.splitlines()
            print(f"   POST {idx} → HTTP {r.status_code} · {ctype} · {len(r.content)/1024:.0f} KB")
        except Exception as e:  # noqa: BLE001
            print(f"   ❌ reintento falló: {type(e).__name__}: {e!r}")
            return
    if lineas and "<html" not in cuerpo[:200].lower():
        print(f"✅ Export recibido: {len(lineas)} líneas")
        print(f"\n   HEADER: {lineas[0][:300]}")
        if len(lineas) > 1:
            cols = lineas[1].split(",")
            masked = [_mask(c) for c in cols[:3]] + cols[3:9]
            print(f"   fila[1] (col0-2 enmascaradas): {masked}")
        print("\n📌 A2: confirmá columnas de nota por actividad. Esto reemplaza al WS userid=0.")
    else:
        print(f"   ⚠️  volvió HTML. primeros 200: {cuerpo[:200]!r}")


async def parte_b_csv_finalizacion(usuario, host, course_id, client) -> None:
    _section("B — CSV finalización: login programático + report/progress?format=csv")
    base = host.rstrip("/")
    if not await _login(client, usuario, host):
        return

    # 3) GET del CSV del reporte de progreso/finalización.
    csv_url = f"{base}/report/progress/index.php"
    try:
        r = await client.get(csv_url, params={"course": course_id, "format": "csv"}, timeout=60.0)
        ctype = r.headers.get("content-type", "")
        print(f"   GET {csv_url}?course={course_id}&format=csv → HTTP {r.status_code} · {ctype}")
    except Exception as e:  # noqa: BLE001
        print(f"❌ Error bajando el CSV: {e}")
        return

    cuerpo = r.text or ""
    es_csv = "csv" in ctype.lower() or ("," in cuerpo.splitlines()[0] if cuerpo else False)
    if not es_csv or "<html" in cuerpo[:200].lower():
        print("   ⚠️  No parece CSV (volvió HTML). Puede requerir otro param/POST o permisos.")
        print(f"      primeros 160 chars: {cuerpo[:160]!r}")
        print("      Fallback del plan: opción B (subida manual del CSV) para el MVP.")
        return

    lineas = cuerpo.splitlines()
    print(f"✅ CSV recibido: {len(lineas)} líneas")
    if lineas:
        # Header = nombres de actividad (sin PII): se muestra completo (truncado).
        print(f"\n   HEADER: {lineas[0][:300]}")
    if len(lineas) > 1:
        # 1 fila de datos con las 2 primeras columnas (nombre/email) ENMASCARADAS.
        cols = lineas[1].split(",")
        masked = [_mask(c) for c in cols[:2]] + cols[2:8]
        print(f"   fila[1] (col0/1 enmascaradas): {masked}")
    print("\n📌 B: confirmá que el header trae nombres de actividad y los valores de "
          "completion ('Completed'/'Not completed'/…). Eso valida parsear_csv_finalizacion (R2).")


async def main() -> None:
    print("🔎 Spike R0 — Refactor Moodle carga masiva")
    from app.models.base import async_session_maker

    async with async_session_maker() as db:
        ctx = await _resolver_usuario_y_curso(db)
        if not ctx:
            return
        usuario, token, host, course_id, moodle = ctx
        print(f"   usuario={_mask(usuario.moodle_username)} host={host} course_id={course_id}")

        async with httpx.AsyncClient(
            headers={"User-Agent": UA}, follow_redirects=True, timeout=60.0
        ) as client:
            if os.environ.get("GRADE_PROBE") == "1":
                # Run enfocado: solo el export del calificador vía sesión.
                await parte_a2_grade_export(usuario, host, course_id, client)
            else:
                await parte_a_notas_bulk(token, host, course_id, moodle, client)
                if os.environ.get("SKIP_B") != "1":
                    await parte_b_csv_finalizacion(usuario, host, course_id, client)
                else:
                    print("\n(parte B salteada por SKIP_B=1)")

    _section("RESUMEN SPIKE R0")
    print("A=notas userid=0 · B=CSV finalización. Volcá conclusiones a PLAN_REFACTOR_MOODLE_BULK.md.")


if __name__ == "__main__":
    asyncio.run(main())
