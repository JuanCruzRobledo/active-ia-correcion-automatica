#!/usr/bin/env python3
"""Inspecciona las secciones de un curso de Moodle (para decidir el mapeo de unidades).

Read-only, 1-2 requests. Lista cada sección: orden, id, nombre, nº de módulos y qué
actividades EVALUABLES tiene (assign/quiz/feedback/workshop/lesson). Muestra también
qué detecta el patrón "N- Tema" (detectar_cabeceras).

USO:
    docker compose -f docker-compose.local.yml exec -e CURSO=43 \
      backend python scripts/inspect_secciones.py
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

CURSO = int(os.environ.get("CURSO") or "43")
_EVALUABLES = {"assign", "quiz", "feedback", "workshop", "lesson"}


async def main() -> None:
    from sqlalchemy import select

    from app.models.avance import SnapshotCronConfig
    from app.repositories.usuario_repository import UsuarioRepository
    from app.services.avance_mapper import detectar_cabeceras
    from app.services.moodle_service import MoodleService
    from app.services.snapshot_service import SnapshotService
    from app.models.base import async_session_maker

    async with async_session_maker() as db:
        cfg = (
            await db.execute(select(SnapshotCronConfig).where(SnapshotCronConfig.id == 1))
        ).scalar_one_or_none()
        usuario = await UsuarioRepository(db).get_by_id(cfg.usuario_id) if cfg else None
        if usuario is None or not usuario.moodle_username:
            print("⚠️  Sin usuario con credenciales de Moodle.")
            return
        snap = SnapshotService(db)
        token, host = await snap.token_de_usuario(usuario)
        secciones = await MoodleService(db).get_course_contents(token, host, CURSO)

    print(f"\n📚 Curso {CURSO}: {len(secciones)} secciones\n")
    con_evaluables = 0
    for sec in secciones:
        mods = sec.get("modules", []) or []
        evaluables = [m for m in mods if m.get("modname") in _EVALUABLES]
        if evaluables:
            con_evaluables += 1
        tipos = {}
        for m in evaluables:
            tipos[m["modname"]] = tipos.get(m["modname"], 0) + 1
        resumen = ", ".join(f"{n}×{t}" for t, n in tipos.items()) or "—"
        print(f"  #{sec.get('section'):>2} (id={sec.get('id')}) "
              f"{(sec.get('name') or '').strip()[:55]:<55} "
              f"| {len(mods):>2} mods | evaluables: {resumen}")

    cabeceras = detectar_cabeceras(secciones)
    print(f"\n🔎 Patrón 'N- Tema' detecta {len(cabeceras)} cabeceras: "
          f"{[c['numero'] for c in cabeceras]}")
    print(f"📊 Secciones con ≥1 actividad evaluable: {con_evaluables}/{len(secciones)}")


if __name__ == "__main__":
    asyncio.run(main())
