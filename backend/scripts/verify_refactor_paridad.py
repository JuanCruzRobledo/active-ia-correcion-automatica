#!/usr/bin/env python3
"""Verificación de PARIDAD del refactor (PLAN_REFACTOR_MOODLE_BULK.md §R5).

Prueba de fuego contra el Moodle REAL: baja los datos del modo NUEVO (2 descargas
masivas por sesión) y, para una muestra de alumnos, también del modo VIEJO (per-alumno),
y verifica que `calcular_avance_alumno` dé EXACTAMENTE lo mismo. NO escribe en la DB.

Seguro: ~10 requests one-shot (login + enrolled + contents + 2 CSV + 2×muestra). User-Agent
identificable. Enmascara PII en la salida.

USO:
    docker compose -f docker-compose.local.yml exec \
      -e MOODLE_COURSE_ID=38 -e MUESTRA=5 \
      backend python scripts/verify_refactor_paridad.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

COURSE_ID = os.environ.get("MOODLE_COURSE_ID") or ""
MUESTRA = int(os.environ.get("MUESTRA") or "5")


def _mask(s) -> str:
    s = str(s or "").strip()
    return f"{s[:2]}…({len(s)})" if s else "∅"


async def main() -> None:
    print("🔎 Verificación de paridad — refactor Moodle bulk\n")
    from sqlalchemy import select

    from app.models.avance import SnapshotCronConfig
    from app.repositories.materia_repository import MateriaRepository
    from app.repositories.usuario_repository import UsuarioRepository
    from app.services.avance_mapper import calcular_avance_alumno
    from app.services.moodle_bulk_parser import (
        construir_indice_nombre_cmid,
        parsear_csv_finalizacion,
        parsear_export_calificador,
    )
    from app.services.moodle_service import MoodleService
    from app.services.snapshot_service import SnapshotService
    from app.models.base import async_session_maker

    async with async_session_maker() as db:
        cfg = (
            await db.execute(select(SnapshotCronConfig).where(SnapshotCronConfig.id == 1))
        ).scalar_one_or_none()
        usuario = await UsuarioRepository(db).get_by_id(cfg.usuario_id) if cfg else None
        if usuario is None or not usuario.moodle_username:
            print("⚠️  Sin usuario con credenciales de Moodle. Abortando.")
            return

        snap = SnapshotService(db)
        token, host = await snap.token_de_usuario(usuario)
        moodle = MoodleService(db)

        # Materia configurada: la del curso pedido, o la 1ra accesible.
        materias = await MateriaRepository(db).get_configuradas_dashboard()
        if COURSE_ID:
            materia = next((m for m in materias if m.moodle_course_id == int(COURSE_ID)), None)
        else:
            materia = materias[0] if materias else None
        if materia is None:
            print(f"⚠️  No hay materia configurada para course_id={COURSE_ID or '(1ra)'}.")
            return
        course_id = materia.moodle_course_id
        unidad_actual = materia.unidad_actual
        unidades_config = [
            {"numero": u.numero, "componentes": [
                {"tipo": c.tipo.value, "cmid": c.moodle_cmid, "fuente": c.fuente.value}
                for c in u.componentes]} for u in materia.unidades
        ]
        n_comp = sum(len(u["componentes"]) for u in unidades_config)
        print(f"   materia={materia.id} course_id={course_id} unidad_actual={unidad_actual} "
              f"unidades={len(unidades_config)} componentes={n_comp}\n")

        # ───────── modo NUEVO (masivo) — cronometrado por paso ─────────
        import time

        def _t():
            return time.monotonic()

        tiempos = {}
        t_total0 = _t()
        sesion = moodle.crear_cliente_sesion()
        try:
            t0 = _t()
            await moodle.login_sesion(sesion, host, usuario.moodle_username, usuario.moodle_password_encrypted)
            tiempos["login"] = _t() - t0
            t0 = _t()
            enrolled = await moodle.get_enrolled_users_full(token, host, course_id, client=sesion)
            tiempos["enrolled"] = _t() - t0
            students = [u for u in enrolled if isinstance(u, dict) and SnapshotService._es_student(u)]
            t0 = _t()
            secciones = await moodle.get_course_contents(token, host, course_id, client=sesion)
            tiempos["course_contents"] = _t() - t0
            nombre_a_cmid = construir_indice_nombre_cmid(secciones)
            email_a_uid = {(u.get("email") or "").strip().lower(): u.get("id")
                           for u in students if u.get("email")}
            t0 = _t()
            export_txt = await moodle.descargar_export_calificador(sesion, host, course_id)
            tiempos["export_calificador"] = _t() - t0
            t0 = _t()
            notas_new = parsear_export_calificador(export_txt, nombre_a_cmid, email_a_uid)
            tiempos["parse_notas"] = _t() - t0
            t0 = _t()
            csv_fin = await moodle.descargar_reporte_finalizacion_csv(sesion, host, course_id)
            tiempos["csv_finalizacion"] = _t() - t0
            t0 = _t()
            comp_new = parsear_csv_finalizacion(csv_fin, nombre_a_cmid, email_a_uid)
            tiempos["parse_completion"] = _t() - t0
        finally:
            await sesion.aclose()
        tiempos["TOTAL"] = _t() - t_total0

        print(f"   NUEVO: {len(students)} students · {len(nombre_a_cmid)} actividades mapeadas · "
              f"notas para {len(notas_new)} uids · completion para {len(comp_new)} uids")
        print("   ⏱  tiempos por paso (s):")
        for k, v in tiempos.items():
            print(f"        {k:<20} {v:7.2f}")
        print()

        # ───────── muestra: comparar contra modo VIEJO (per-alumno) ─────────
        muestra = students[:MUESTRA]
        ok = 0
        diffs = 0
        async with moodle_cliente() as c:
            for u in muestra:
                uid = u.get("id")
                # VIEJO (per-alumno)
                statuses_old = await moodle.get_activities_completion(token, host, course_id, uid, client=c)
                notas_old = await moodle.get_grade_items(token, host, course_id, uid, client=c)
                r_old = calcular_avance_alumno(statuses_old, notas_old, unidades_config, unidad_actual=unidad_actual)
                # NUEVO (de los CSV masivos)
                r_new = calcular_avance_alumno(comp_new.get(uid, []), notas_new.get(uid, {}),
                                               unidades_config, unidad_actual=unidad_actual)
                igual = (
                    r_old["unidad_alcanzada"] == r_new["unidad_alcanzada"]
                    and r_old["estado"] == r_new["estado"]
                    and r_old["actividades_faltantes"] == r_new["actividades_faltantes"]
                )
                if igual:
                    ok += 1
                else:
                    diffs += 1
                marca = "✅" if igual else "❌"
                print(f"   {marca} uid={uid} email={_mask(u.get('email'))} | "
                      f"viejo: alc={r_old['unidad_alcanzada']} est={r_old['estado'].value} | "
                      f"nuevo: alc={r_new['unidad_alcanzada']} est={r_new['estado'].value}")
                if not igual:
                    print(f"        deudas viejo={r_old['actividades_faltantes']}")
                    print(f"        deudas nuevo={r_new['actividades_faltantes']}")

        print(f"\n   PARIDAD: {ok}/{len(muestra)} idénticos · {diffs} diferencias")
        print("   ✅ Si todos coinciden, el refactor preserva el cálculo." if diffs == 0
              else "   ⚠️ Revisar diferencias (probable: match nombre→cmid o estados de completion).")


def moodle_cliente():
    import httpx
    from app.services.moodle_service import MOODLE_USER_AGENT
    return httpx.AsyncClient(headers={"User-Agent": MOODLE_USER_AGENT}, timeout=60.0)


if __name__ == "__main__":
    asyncio.run(main())
