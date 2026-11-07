"""Restaura notas académicas afectadas por el antiguo tope de archivos.

Desde backend: python -m scripts.reparar_tope_entregas --universidad-id ID
Agregá --aplicar para guardar los cambios en Active-IA.
"""

import argparse
import asyncio
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import async_session_maker
from app.models.correccion import Correccion
from app.models.entrega import Entrega
from app.services.politica_entrega import VERSION_POLITICA, aplicar_politica_correccion


async def reparar_correcciones(
    db: AsyncSession, *, universidad_id: int, aplicar: bool,
) -> int:
    politica = Correccion.criterios_json["politica_entrega"]
    consulta = (
        select(Entrega, Correccion)
        .join(Correccion, Correccion.entrega_id == Entrega.id)
        .where(
            Entrega.universidad_id == universidad_id,
            Correccion.universidad_id == universidad_id,
            Entrega.deleted_at.is_(None),
            politica["version"].as_integer() == VERSION_POLITICA,
            politica["limite_nota"].as_integer() == 50,
        )
        .order_by(Entrega.id)
    )
    if aplicar:
        consulta = consulta.with_for_update(of=(Entrega, Correccion))

    reparables = 0
    for entrega, correccion in (await db.execute(consulta)).all():
        anterior = correccion.criterios_json["politica_entrega"]
        analisis = entrega.analisis_archivos or {}
        rutas = anterior.get("rutas_penalizables")
        if not rutas and analisis.get("version") == VERSION_POLITICA:
            rutas = analisis.get("rutas_penalizables")
        try:
            academica = Decimal(str(anterior.get("nota_academica")))
        except InvalidOperation:
            academica = Decimal("NaN")
        if (
            not academica.is_finite()
            or not 0 <= academica <= 100
            or correccion.nota != min(academica, Decimal(50)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
            or not isinstance(rutas, list)
            or not rutas
            or not all(isinstance(ruta, str) for ruta in rutas)
        ):
            print(f"Corrección {correccion.id}: omitida por datos inconsistentes.")
            continue

        print(f"Corrección {correccion.id}: {correccion.nota:.2f} -> {academica:.2f}")
        reparables += 1
        if aplicar:
            # La evidencia guardada con la corrección identifica la versión evaluada.
            aplicar_politica_correccion(
                correccion, {**anterior, "rutas_penalizables": rutas}, nota_academica=academica,
            )
            if analisis.get("limite_nota") == 50:
                entrega.analisis_archivos = {**analisis, "limite_nota": None}
    return reparables


async def main(universidad_id: int, aplicar: bool) -> None:
    if not aplicar:
        print("Vista previa: los cambios se guardan al agregar --aplicar.")
    async with async_session_maker() as db, db.begin():
        total = await reparar_correcciones(db, universidad_id=universidad_id, aplicar=aplicar)
    modo = "Aplicadas" if aplicar else "Detectadas en vista previa"
    print(f"{modo}: {total} correcciones.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universidad-id", required=True, type=int)
    parser.add_argument("--aplicar", action="store_true", help="Guarda las correcciones en la base de datos.")
    args = parser.parse_args()
    asyncio.run(main(args.universidad_id, args.aplicar))
