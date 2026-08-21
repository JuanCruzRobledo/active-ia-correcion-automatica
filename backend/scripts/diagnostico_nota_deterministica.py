#!/usr/bin/env python
"""
Diagnóstico de impacto del change `nota-deterministica-penalizaciones`.

**SOLO LECTURA. Este script no escribe una sola fila.** Es el insumo del gate de
gobernanza ALTA: antes de cambiar cómo se calcula una nota hay que saber a
cuántas correcciones ya emitidas les habría dado un número distinto, y cuánto.

Qué responde:

1. Cuántas correcciones cambiarían de nota, y cuánto baja en promedio y en el
   peor caso (bugs 2 y 3 del pedido de AI-Native).
2. Qué rúbricas de producción tienen penalizaciones declaradas y con qué
   porcentaje — para revisar si alguna fue escrita asumiendo "% del criterio"
   en vez de "% del total" (design D1).
3. Cuánto cambiaría el resultado si los descuentos se aplicaran EN CASCADA en
   vez de sobre la misma base. Es la Open Question del design, y se contesta
   mejor con dos columnas que con una opinión.

Uso:

    python scripts/diagnostico_nota_deterministica.py
    python scripts/diagnostico_nota_deterministica.py --limit 200
    python scripts/diagnostico_nota_deterministica.py --csv impacto.csv
    python scripts/diagnostico_nota_deterministica.py --universidad 1

El cálculo lo hace `app/services/correccion_nota.py`, el mismo módulo que va a
usar el service cuando el gate dé el OK. No se reescribe la fórmula acá a
propósito: un diagnóstico que calcula distinto que la implementación miente.
"""

import argparse
import asyncio
import csv
import sys
from decimal import Decimal
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, selectinload

from app.core.config import settings
from app.models.correccion import Correccion
from app.models.entrega import Entrega
from app.models.rubrica import Rubrica
from app.services.correccion_nota import calcular_nota, calcular_nota_actual


def _criterios_de(correccion: Correccion) -> list[dict]:
    """Los criterios evaluados viven en `criterios_json` como {"criterios": [...]}."""
    datos = correccion.criterios_json or {}
    if isinstance(datos, dict):
        return datos.get("criterios") or []
    if isinstance(datos, list):  # tolerancia a correcciones muy viejas
        return datos
    return []


def _pesos_de(rubrica: Rubrica) -> dict[str, Decimal]:
    pesos: dict[str, Decimal] = {}
    for criterio in rubrica.criterios_json or []:
        cid = criterio.get("id")
        peso = criterio.get("peso")
        if cid and peso is not None:
            pesos[cid] = Decimal(str(peso))
    return pesos


def _descuento_en_cascada(
    penalizaciones_rubrica: list[dict], ids: list[str], suma: Decimal
) -> Decimal:
    """Variante para contestar la Open Question. NO es la fórmula propuesta.

    En cascada cada descuento se aplica sobre lo que quedó del anterior: dos
    penalizaciones del 30% dejan 49% de la nota, no 40%.
    """
    por_id = {p.get("id"): p for p in (penalizaciones_rubrica or []) if p.get("id")}
    restante = suma
    for pen_id in ids or []:
        pen = por_id.get(pen_id)
        if pen is None:
            continue
        pct = Decimal(str(pen.get("descuento_porcentaje", 0) or 0))
        restante = restante - (restante * pct / Decimal(100))
    return suma - restante


async def _analizar(session: AsyncSession, limite: int | None, universidad_id: int | None):
    stmt = (
        select(Correccion)
        .join(Entrega, Correccion.entrega_id == Entrega.id)
        .options(selectinload(Correccion.entrega).selectinload(Entrega.rubrica))
        .order_by(Correccion.id)
    )
    if universidad_id is not None:
        stmt = stmt.where(Correccion.universidad_id == universidad_id)
    if limite is not None:
        stmt = stmt.limit(limite)

    correcciones = (await session.execute(stmt)).scalars().all()

    filas = []
    for c in correcciones:
        entrega = c.entrega
        rubrica = entrega.rubrica if entrega else None
        if rubrica is None:
            continue

        criterios = _criterios_de(c)
        if not criterios:
            continue

        penalizaciones = rubrica.penalizaciones_json or []
        condiciones = rubrica.condiciones_desaprobacion_json or []
        ids_pen = list(c.penalizaciones_aplicadas or [])

        nota_actual_recalculada = calcular_nota_actual(
            criterios_evaluados=criterios,
            condiciones_rubrica=condiciones,
            id_condicion_declarada=c.condicion_desaprobacion_aplicada,
        )

        r = calcular_nota(
            criterios_evaluados=criterios,
            penalizaciones_rubrica=penalizaciones,
            condiciones_rubrica=condiciones,
            ids_penalizaciones_declaradas=ids_pen,
            id_condicion_declarada=c.condicion_desaprobacion_aplicada,
            schema_version=rubrica.schema_version,
            pesos_por_criterio=_pesos_de(rubrica),
        )

        cascada = _descuento_en_cascada(penalizaciones, ids_pen, r.suma_criterios)
        nota_cascada = max(Decimal("0"), r.suma_criterios - cascada)
        if r.condicion_aplicada:
            techo = next(
                (
                    Decimal(str(cd.get("nota_maxima")))
                    for cd in condiciones
                    if cd.get("id") == r.condicion_aplicada
                    and cd.get("nota_maxima") is not None
                ),
                None,
            )
            if techo is not None:
                nota_cascada = min(nota_cascada, techo)

        filas.append(
            {
                "correccion_id": c.id,
                "entrega_id": c.entrega_id,
                "alumno": entrega.alumno_nombre,
                "rubrica_id": rubrica.id,
                "rubrica": rubrica.titulo,
                "schema_version": rubrica.schema_version,
                "editada_a_mano": c.editado_manualmente,
                "nota_persistida": Decimal(str(c.nota)),
                "nota_actual_recalculada": nota_actual_recalculada,
                "nota_nueva": r.nota_final,
                "diferencia": r.nota_final - nota_actual_recalculada,
                "descuento": r.descuento_total,
                "penalizaciones": ",".join(r.penalizaciones_aplicadas),
                "criterios_con_discrepancia": ",".join(r.criterios_con_discrepancia),
                "nota_nueva_en_cascada": nota_cascada,
            }
        )

    return filas


async def _rubricas_con_penalizaciones(session: AsyncSession, universidad_id: int | None):
    stmt = select(Rubrica).order_by(Rubrica.id)
    if universidad_id is not None:
        stmt = stmt.where(Rubrica.universidad_id == universidad_id)
    rubricas = (await session.execute(stmt)).scalars().all()

    salida = []
    for r in rubricas:
        penalizaciones = r.penalizaciones_json or []
        if not penalizaciones:
            continue
        salida.append(
            {
                "rubrica_id": r.id,
                "titulo": r.titulo,
                "materia_id": r.materia_id,
                "penalizaciones": [
                    (
                        p.get("id"),
                        p.get("descuento_porcentaje"),
                        (p.get("descripcion") or "")[:70],
                    )
                    for p in penalizaciones
                ],
            }
        )
    return salida


def _reportar(filas: list[dict], rubricas: list[dict]) -> None:
    print("=" * 78)
    print("DIAGNÓSTICO — nota-deterministica-penalizaciones (SOLO LECTURA)")
    print("=" * 78)

    print(f"\nCorrecciones analizadas: {len(filas)}")

    cambian = [f for f in filas if f["diferencia"] != 0]
    print(f"Correcciones que cambiarían de nota: {len(cambian)}")

    if not cambian:
        print("\n  Ninguna corrección existente cambiaría de nota.")
    else:
        difs = [f["diferencia"] for f in cambian]
        peor = min(difs)
        promedio = sum(difs, Decimal("0")) / Decimal(len(difs))
        print(f"  Diferencia promedio: {promedio.quantize(Decimal('0.01'))} puntos")
        print(f"  Peor caso:           {peor} puntos")

        por_penalizacion = [f for f in cambian if f["descuento"] > 0]
        por_desglose = [f for f in cambian if f["criterios_con_discrepancia"]]
        print(f"  Cambian por penalización (bug 2): {len(por_penalizacion)}")
        print(f"  Cambian por desglose (bug 3):     {len(por_desglose)}")

        cruzan = [
            f
            for f in cambian
            if f["nota_actual_recalculada"] >= 60 and f["nota_nueva"] < 60
        ]
        if cruzan:
            print(
                f"\n  !! {len(cruzan)} corrección(es) pasarían de aprobado a desaprobado."
            )
            print("     Estas son las que hay que mirar de a una con el coordinador:")
            for f in cruzan[:20]:
                print(
                    f"       correccion {f['correccion_id']:>6}  {f['alumno'][:28]:<28} "
                    f"{f['nota_actual_recalculada']:>6} → {f['nota_nueva']:>6}  "
                    f"({f['rubrica'][:30]})"
                )
            if len(cruzan) > 20:
                print(f"       ... y {len(cruzan) - 20} más (ver el CSV)")

        editadas = [f for f in cambian if f["editada_a_mano"]]
        if editadas:
            print(
                f"\n  Nota: {len(editadas)} de las que cambian fueron editadas a mano."
                " El recálculo NO las pisa (el change no recalcula nada existente),"
                " pero conviene saber que están."
            )

        desfasadas = [
            f
            for f in filas
            if not f["editada_a_mano"]
            and f["nota_persistida"] != f["nota_actual_recalculada"]
        ]
        if desfasadas:
            print(
                f"\n  Atención: {len(desfasadas)} corrección(es) NO editadas a mano tienen"
                " una nota persistida distinta de la que da la fórmula actual."
                " Eso es un hallazgo aparte y merece mirarse."
            )

        distintos = [
            f for f in cambian if f["nota_nueva"] != f["nota_nueva_en_cascada"]
        ]
        print(
            f"\n  Open Question (base única vs. cascada): {len(distintos)} corrección(es)"
            " darían distinto según cuál se elija."
        )
        if distintos:
            print("     Ejemplos:")
            for f in distintos[:5]:
                print(
                    f"       correccion {f['correccion_id']:>6}  "
                    f"base única {f['nota_nueva']:>6}  |  cascada {f['nota_nueva_en_cascada']:>6}"
                )

    print("\n" + "-" * 78)
    print(f"RÚBRICAS CON PENALIZACIONES DECLARADAS: {len(rubricas)}")
    print("-" * 78)
    if not rubricas:
        print("  Ninguna. El bug 2 no tiene efecto sobre los datos actuales.")
    else:
        print(
            "  Revisar si alguna fue escrita asumiendo '% del criterio' en vez de"
            "\n  '% del total'. La propuesta interpreta % del total (design D1).\n"
        )
        for r in rubricas:
            print(f"  [{r['rubrica_id']:>4}] {r['titulo'][:52]}")
            for pid, pct, desc in r["penalizaciones"]:
                print(f"          {pid}  {pct:>3}%  {desc}")

    print("\n" + "=" * 78)
    print("Este script no modificó ninguna fila.")
    print("=" * 78)


def _escribir_csv(filas: list[dict], destino: str) -> None:
    if not filas:
        print(f"\nSin filas para escribir en {destino}.")
        return
    with open(destino, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    print(f"\nCSV escrito: {destino} ({len(filas)} filas)")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Máximo de correcciones")
    parser.add_argument("--universidad", type=int, default=None, help="Filtrar por universidad")
    parser.add_argument("--csv", type=str, default=None, help="Volcar el detalle a un CSV")
    args = parser.parse_args()

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with maker() as session:
            filas = await _analizar(session, args.limit, args.universidad)
            rubricas = await _rubricas_con_penalizaciones(session, args.universidad)
        _reportar(filas, rubricas)
        if args.csv:
            _escribir_csv(filas, args.csv)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
