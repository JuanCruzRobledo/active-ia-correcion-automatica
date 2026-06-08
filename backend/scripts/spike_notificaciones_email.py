#!/usr/bin/env python3
"""Spike T0 — Notificaciones por email (PLAN_NOTIFICACIONES_EMAIL.md §6).

Valida DOS supuestos del plan, de forma independiente, SIN escribir nada en la DB:

  A  RESEND — ¿la API key funciona en modo SANDBOX? Manda 1 email de prueba
     (from: onboarding@resend.dev) a tu propia casilla. Confirma que el
     wrapper de envío es viable antes de construir EmailService (T3).

  B  REGIONALES — ¿el parseo de regional (grupo "R-…") detecta bien las
     regionales reales de Moodle? Reusa las credenciales del usuario del cron
     de snapshots (DB) y lista, para un curso configurado, las regionales
     distintas + cuántos alumnos caen en cada una (y cuántos "Sin regional").

NO loguea la API key ni el token/password de Moodle. Descartable.

──────────────────────────────────────────────────────────────────────────────
USO (dentro del contenedor backend; la RESEND_API_KEY ya está en su entorno):

    # Parte A (Resend) — pasá tu email de cuenta Resend como destino:
    docker compose -f docker-compose.local.yml exec \
      -e EMAIL_TEST_TO=tu-email@ejemplo.com \
      backend python scripts/spike_notificaciones_email.py

    # Para fijar otro curso en la parte B (default: 1ra materia configurada):
    #   -e MOODLE_COURSE_ID=38

Dependencias: httpx (ya instalado) + el propio paquete `app` (PYTHONPATH=/app).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx

# Forzar UTF-8 en stdout para que los ✅/❌ no crasheen.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# Silenciar el echo de SQLAlchemy (DEBUG del backend) para que no inunde la salida.
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY") or ""
EMAIL_REMITENTE = os.environ.get("EMAIL_REMITENTE") or "onboarding@resend.dev"
EMAIL_TEST_TO = os.environ.get("EMAIL_TEST_TO") or ""
MOODLE_COURSE_ID = os.environ.get("MOODLE_COURSE_ID") or ""

RESEND_ENDPOINT = "https://api.resend.com/emails"


def _section(title: str) -> None:
    print(f"\n{'─' * 72}\n{title}\n{'─' * 72}")


# ──────────────────────────────────────────────────────────────────────────────
# A — Resend (sandbox)
# ──────────────────────────────────────────────────────────────────────────────
async def parte_a_resend(client: httpx.AsyncClient) -> None:
    _section("A — Resend (envío de prueba en sandbox)")
    if not RESEND_API_KEY:
        print("⚠️  Falta RESEND_API_KEY en el entorno del contenedor. Salteo la parte A.")
        return
    if not EMAIL_TEST_TO:
        print(
            "⚠️  Falta EMAIL_TEST_TO. En sandbox, Resend SOLO deja enviar a la casilla "
            "de tu cuenta. Recorré con  -e EMAIL_TEST_TO=tu-email@ejemplo.com"
        )
        return

    print(f"   remitente : {EMAIL_REMITENTE}")
    print(f"   destino   : {EMAIL_TEST_TO}")
    payload = {
        "from": EMAIL_REMITENTE,
        "to": [EMAIL_TEST_TO],
        "subject": "Active-IA · prueba de notificaciones (spike T0)",
        "html": (
            "<h2>✅ Resend funciona</h2>"
            "<p>Este es el email de prueba del spike T0 de notificaciones.</p>"
            "<table border='1' cellpadding='6' style='border-collapse:collapse'>"
            "<tr><th>Comisión</th><th>Materia</th><th>Actividad</th></tr>"
            "<tr><td>M26 C1-09</td><td>Programación 1</td>"
            "<td>Actividad de Cierre unidad 8</td></tr></table>"
            "<p style='color:#666'>Si ves esto, el canal de envío está listo.</p>"
        ),
    }
    try:
        resp = await client.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    except Exception as e:  # noqa: BLE001
        print(f"❌ Error de red al llamar a Resend: {e}")
        return

    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"✅ Email aceptado por Resend. id={data.get('id')}")
        print("   Revisá tu casilla (y spam). Si llegó, la parte A está VERDE.")
    else:
        try:
            err = resp.json()
        except Exception:  # noqa: BLE001
            err = resp.text
        print(f"❌ Resend rechazó el envío (HTTP {resp.status_code}): {err}")
        print(
            "   Pista típica en sandbox: el destino debe ser el email de tu cuenta Resend, "
            "y el 'from' debe ser onboarding@resend.dev hasta verificar el dominio."
        )


# ──────────────────────────────────────────────────────────────────────────────
# B — Regionales reales de Moodle (reusa credenciales del cron de snapshots)
# ──────────────────────────────────────────────────────────────────────────────
async def parte_b_regionales() -> None:
    _section("B — Regionales reales de Moodle (parseo de grupo 'R-…')")
    try:
        from sqlalchemy import select

        from app.models.avance import SnapshotCronConfig
        from app.models.base import async_session_maker
        from app.repositories.materia_repository import MateriaRepository
        from app.repositories.usuario_repository import UsuarioRepository
        from app.services.gestion_parser import parse_comision, parse_regional
        from app.services.moodle_service import MoodleService
        from app.services.snapshot_service import SnapshotService
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  No pude importar el stack de la app (salteo parte B): {e}")
        return

    async with async_session_maker() as db:
        # 1) Usuario con credenciales de Moodle: el del cron de snapshots, o el 1º disponible.
        cfg = (
            await db.execute(select(SnapshotCronConfig).where(SnapshotCronConfig.id == 1))
        ).scalar_one_or_none()
        usuario_repo = UsuarioRepository(db)
        usuario = None
        if cfg and cfg.usuario_id:
            usuario = await usuario_repo.get_by_id(cfg.usuario_id)
        if usuario is None or not getattr(usuario, "moodle_username", None):
            print(
                "⚠️  No hay usuario con credenciales de Moodle (ni en el cron config). "
                "Configurá el usuario de servicio del cron de snapshots y reintentá."
            )
            return

        snap = SnapshotService(db)
        try:
            token, host = await snap.token_de_usuario(usuario)
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  No pude obtener token de Moodle: {e}")
            return

        # 2) Curso: si pasaron MOODLE_COURSE_ID, ese; si no, probar TODAS las
        #    materias configuradas y usar la primera ACCESIBLE con este usuario.
        moodle = MoodleService(db)
        if MOODLE_COURSE_ID:
            candidatos = [int(MOODLE_COURSE_ID)]
        else:
            materias = await MateriaRepository(db).get_configuradas_dashboard()
            candidatos = [m.moodle_course_id for m in materias if m.moodle_course_id]
            if not candidatos:
                print("⚠️  No hay materias configuradas y no pasaste MOODLE_COURSE_ID.")
                return
            print(f"   cursos configurados a probar: {candidatos}")

        enrolled = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            for cid in candidatos:
                try:
                    enrolled = await moodle.get_enrolled_users_full(token, host, int(cid), client=client)
                    print(f"   ✅ curso accesible: course_id={cid}")
                    break
                except Exception as e:  # noqa: BLE001
                    print(f"   ⚠️  course_id={cid} no accesible con este usuario: {str(e)[:90]}")
        if enrolled is None:
            print(
                "⚠️  Ningún curso configurado es accesible con el usuario del cron. "
                "Probá con  -e MOODLE_COURSE_ID=38  (un curso al que el usuario tenga acceso)."
            )
            return

        students = [
            u for u in enrolled
            if isinstance(u, dict)
            and any(r.get("shortname") == "student" for r in (u.get("roles") or []))
        ]

        # 3) Parseo de regional + comisión por alumno.
        por_regional: dict[str, int] = {}
        sin_regional = 0
        con_comision = 0
        for u in students:
            grupos = [g.get("name") for g in (u.get("groups") or []) if g.get("name")]
            regional = next((r for r in (parse_regional(g) for g in grupos) if r), None)
            comision = next((c for c in (parse_comision(g) for g in grupos) if c), None)
            if regional:
                por_regional[regional] = por_regional.get(regional, 0) + 1
            else:
                sin_regional += 1
            if comision:
                con_comision += 1

        print(f"\n   alumnos (student)         : {len(students)}")
        print(f"   con comisión parseada     : {con_comision}")
        print(f"   regionales distintas (R-) : {len(por_regional)}")
        print(f"   sin regional              : {sin_regional}\n")
        for reg, n in sorted(por_regional.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"     · {reg:<30} {n} alumno(s)")
        print(
            "\n📌 B: confirmá que las regionales listadas son las reales y que 'sin regional' "
            "es bajo. Cada regional será destinatario de un tutor nexo (tabla TutorNexo)."
        )


async def main() -> None:
    print("🔎 Spike T0 — Notificaciones por email")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        await parte_a_resend(client)
    await parte_b_regionales()
    _section("RESUMEN SPIKE T0")
    print("A=Resend (canal de envío) · B=Regionales (parseo). Volcá conclusiones al plan.")


if __name__ == "__main__":
    asyncio.run(main())
