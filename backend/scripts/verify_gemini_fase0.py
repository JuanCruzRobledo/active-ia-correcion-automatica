#!/usr/bin/env python3
"""Fase 0 — Verificación de modelos Gemini (A2 + T0.3).

Verifica DOS cosas contra la API real de Gemini, SIN escribir nada y SIN imprimir la key:

  T0.3  ¿Qué nombres de modelo soporta realmente esta API key? (ListModels)
        Los alias del prompt original (gemini-pro-latest, gemini-flash-lite-latest)
        NO son canónicos según la doc de mayo 2026. Defaults reales abajo.

  A2    ¿La heurística "Pro responde ⇒ key PAGA" sirve para esta key?
        OJO: el free tier permite llamar modelos Pro con rate limits bajos,
        así que esta clasificación es APROXIMADA. El script lo deja en evidencia.

──────────────────────────────────────────────────────────────────────────────
USO (PowerShell):

    $env:GEMINI_API_KEY = "AIza..."
    # opcionales (defaults reales abajo):
    $env:GEMINI_MODEL_PRO   = "gemini-2.5-pro"
    $env:GEMINI_MODEL_FLASH = "gemini-2.5-flash-lite"
    python backend/scripts/verify_gemini_fase0.py

Dependencia: httpx (ya está en requirements.txt).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

API_KEY = os.environ.get("GEMINI_API_KEY") or ""
MODEL_PRO = os.environ.get("GEMINI_MODEL_PRO") or "gemini-2.5-pro"
MODEL_FLASH = os.environ.get("GEMINI_MODEL_FLASH") or "gemini-2.5-flash-lite"
BASE = "https://generativelanguage.googleapis.com/v1beta"


def _section(title: str) -> None:
    print(f"\n{'─' * 70}\n{title}\n{'─' * 70}")


async def list_models(client: httpx.AsyncClient) -> set[str]:
    _section("T0.3 — Modelos disponibles para esta key (ListModels)")
    r = await client.get(f"{BASE}/models", params={"key": API_KEY})
    if r.status_code != 200:
        print(f"⚠️  ListModels devolvió {r.status_code}: {r.text[:300]}")
        return set()

    names: set[str] = set()
    rows: list[tuple[str, bool]] = []
    for m in r.json().get("models", []):
        name = (m.get("name") or "").removeprefix("models/")
        methods = m.get("supportedGenerationMethods", [])
        supports = "generateContent" in methods
        names.add(name)
        if supports:
            rows.append((name, supports))

    rows.sort()
    print(f"Modelos que soportan generateContent ({len(rows)}):\n")
    for name, _ in rows:
        flag = ""
        if name == MODEL_PRO:
            flag = "  ← GEMINI_MODEL_PRO"
        elif name == MODEL_FLASH:
            flag = "  ← GEMINI_MODEL_FLASH"
        print(f"  {name}{flag}")

    for label, model in (("PRO", MODEL_PRO), ("FLASH", MODEL_FLASH)):
        if model not in names:
            print(f"\n⚠️  El modelo {label}='{model}' NO está en la lista. "
                  f"Elegí uno de los de arriba y reexportá GEMINI_MODEL_{label}.")
    return names


async def try_generate(client: httpx.AsyncClient, model: str) -> tuple[bool, int, float]:
    url = f"{BASE}/models/{model}:generateContent"
    payload = {"contents": [{"parts": [{"text": "Responde solo: OK"}]}]}
    t0 = time.monotonic()
    try:
        r = await client.post(url, params={"key": API_KEY}, json=payload, timeout=30.0)
    except httpx.HTTPError as e:
        print(f"  {model:<28} ERROR de red: {e}")
        return False, 0, time.monotonic() - t0
    dt = time.monotonic() - t0
    ok = r.status_code == 200
    detail = ""
    if not ok:
        try:
            detail = r.json().get("error", {}).get("status", "") or r.text[:120]
        except Exception:
            detail = r.text[:120]
    print(f"  {model:<28} HTTP {r.status_code}  {dt:0.2f}s  {detail}")
    return ok, r.status_code, dt


async def classify(client: httpx.AsyncClient) -> None:
    _section("A2 — Clasificación de tier (Pro → Flash)")
    pro_ok, pro_status, _ = await try_generate(client, MODEL_PRO)
    flash_ok, flash_status, _ = await try_generate(client, MODEL_FLASH)

    if pro_ok:
        tier = "PAGA (según la heurística del prompt)"
    elif flash_ok:
        tier = "GRATUITA (Pro falló, Flash respondió)"
    else:
        tier = "INVÁLIDA (ambos fallaron)"

    print(f"\n📌 Resultado heurístico: tier = {tier}")
    print(
        "\n⚠️  ADVERTENCIA (A2): el free tier de Gemini SÍ permite llamar modelos Pro "
        "(con rate limits bajos). Que Pro responda NO garantiza que la key sea paga. "
        f"Si Pro respondió 429 (status={pro_status}) eso es rate-limit, no 'sin acceso'. "
        "Por eso el plan trata esta clasificación como aproximada y hace 'Corregir todo' "
        "resiliente a 429."
    )


async def main() -> None:
    if not API_KEY:
        print("❌ Falta GEMINI_API_KEY. Ver el docstring del script.")
        sys.exit(1)
    print(f"🔎 Verificando Gemini (PRO='{MODEL_PRO}', FLASH='{MODEL_FLASH}')")
    async with httpx.AsyncClient() as client:
        await list_models(client)
        await classify(client)

    _section("RESUMEN FASE 0 — Gemini")
    print("1. Anotá en PLAN_FEAT.md los nombres reales de modelo para GEMINI_MODEL_PRO/FLASH.")
    print("2. Confirmá la advertencia A2 antes de atar 'Corregir todo' sólo a tier=PAGA.")


if __name__ == "__main__":
    asyncio.run(main())
