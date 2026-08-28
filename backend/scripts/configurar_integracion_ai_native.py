#!/usr/bin/env python
"""
Configura en producción lo que la integración con AI-Native necesita para
funcionar, por universidad.

**DRY-RUN POR DEFECTO. No escribe nada salvo que le pases `--aplicar`.**

Por qué existe
--------------
AI-Native ya tiene credenciales, pero credenciales no alcanzan. Su primer
`PUT /trabajos-practicos/by-ref/{ref}` y su primera corrección chocan contra
cuatro cosas que sólo un administrador puede dejar puestas, y cada una devuelve
un error distinto:

    Falta                                    Ellos reciben
    ---------------------------------------  --------------------------------
    La materia con SU external_ref            404 al publicar el TP
    El vínculo coordinador <-> materia        403 (rol COORDINADOR exige
                                              CoordinadorMateria)
    La comisión de integración                409 al corregir
    materia.comision_integracion_id           409 al corregir

Los cuatro se configuran una vez y quedan. El script los deja consistentes o no
toca nada: es todo o nada dentro de una transacción.

Por qué la comisión de integración
----------------------------------
`entregas.comision_id` es NOT NULL y AI-Native no tiene comisiones — no modela
cohortes. La comisión de integración es el destino por defecto de sus entregas.
Su cliente NUNCA manda `comision_external_ref` (decisión de ellos: "mandarlo con
un id que ellos no conocen sería peor que no mandarlo"), así que TODA corrección
suya cae acá.

`correccion_ejercicio_service` se niega a crear una comisión por efecto colateral
de una corrección — dar de alta entidades de costado es la clase de magia que
después nadie puede explicar. Este script es la contracara deliberada de esa
regla: la crea de frente, una vez, con nombre propio y auditable.

Lo que NO hace, a propósito
---------------------------
- **No marca `depende_de_ejecucion` en ninguna rúbrica.** AI-Native confirmó el
  27/08 que nunca sincronizaron una rúbrica con nosotros: no hay nada viejo que
  corregir, y su primera sincronización ya llega con las 34 marcas puestas. Un
  script que "arregle" rúbricas que no existen sólo puede pisar algo bueno.
- **No crea usuarios ni membresías.** Eso ya está hecho y por otra vía.
- **No borra ni desactiva nada.** Sólo crea lo que falta y completa el puntero.

Uso
---
    # 1. Ver qué falta, sin tocar nada (por defecto)
    python scripts/configurar_integracion_ai_native.py \
        --universidad 1 \
        --usuario ai-native-tupad \
        --materia-external-ref 7f3a9c21-... \
        --materia-codigo PARAD \
        --materia-nombre "Paradigmas de Programación"

    # 2. Aplicar, cuando la salida del dry-run sea la esperada
    python scripts/configurar_integracion_ai_native.py ... --aplicar

    # 3. Verificar después (sólo lectura, no necesita el resto de los datos)
    python scripts/configurar_integracion_ai_native.py \
        --universidad 1 --usuario ai-native-tupad --verificar

Se corre UNA VEZ POR UNIVERSIDAD, con la cuenta que le corresponde a esa
universidad. Si le pasás una cuenta que no tiene membresía activa en la
universidad indicada, se planta antes de escribir: es el error más caro de este
script (dejar a AI-Native con acceso a la universidad equivocada) y no depende
de que el operador esté atento.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.models.comision import Comision  # noqa: E402
from app.models.materia import CoordinadorMateria, Materia  # noqa: E402
from app.models.universidad import Universidad  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.models.usuario_universidad import UsuarioUniversidad  # noqa: E402


# El nombre por defecto dice qué es y por qué existe. Un "COM-1" acá haría que
# dentro de seis meses alguien la confunda con una comisión real y le asigne
# tutores o alumnos.
NOMBRE_COMISION_DEFECTO = "Integración AI-Native"

VERDE = "\033[92m"
AMARILLO = "\033[93m"
ROJO = "\033[91m"
GRIS = "\033[90m"
FIN = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {VERDE}✓{FIN} {msg}")


def falta(msg: str) -> None:
    print(f"  {AMARILLO}·{FIN} {msg}")


def error(msg: str) -> None:
    print(f"  {ROJO}✗{FIN} {msg}")


def nota(msg: str) -> None:
    print(f"    {GRIS}{msg}{FIN}")


class Aborta(Exception):
    """Condición que hace inseguro seguir. Corta antes de escribir nada."""


async def _cargar_universidad(db: AsyncSession, universidad_id: int) -> Universidad:
    uni = await db.get(Universidad, universidad_id)
    if uni is None:
        raise Aborta(f"No existe la universidad con id {universidad_id}.")
    if not uni.activa:
        raise Aborta(
            f"La universidad '{uni.nombre}' está INACTIVA. Configurar la "
            "integración sobre una universidad apagada deja una bomba para el "
            "día que se encienda."
        )
    return uni


async def _cargar_usuario(db: AsyncSession, username: str) -> Usuario:
    res = await db.execute(select(Usuario).where(Usuario.username == username))
    usuario = res.scalar_one_or_none()
    if usuario is None:
        raise Aborta(f"No existe el usuario '{username}'.")
    return usuario


async def _validar_membresia(
    db: AsyncSession, usuario: Usuario, uni: Universidad
) -> None:
    """El chequeo que evita el error más caro: la cuenta equivocada.

    Vincular la cuenta de una universidad a la materia de OTRA le daría a
    AI-Native acceso cruzado, en silencio y de forma permanente. Se valida acá y
    no se confía en que el operador pegó bien el `--usuario`.
    """
    res = await db.execute(
        select(UsuarioUniversidad).where(
            UsuarioUniversidad.usuario_id == usuario.id,
            UsuarioUniversidad.universidad_id == uni.id,
        )
    )
    membresia = res.scalar_one_or_none()
    if membresia is None:
        raise Aborta(
            f"El usuario '{usuario.username}' NO tiene membresía en "
            f"'{uni.nombre}'. Estás por vincular la cuenta de una universidad a "
            "la materia de otra."
        )
    if not membresia.activo:
        raise Aborta(
            f"La membresía de '{usuario.username}' en '{uni.nombre}' está dada "
            "de baja."
        )

    # Dos membresías activas rompen el login del cliente: con 2+, /auth/login
    # devuelve `SeleccionUniversidadRequerida` (sin `access_token`) y el cliente
    # de AI-Native lo clasifica como falla de INFRAESTRUCTURA, o sea reintenta
    # para siempre contra algo que nunca se va a recuperar. No aborta el script
    # —no es lo que este script configura— pero se avisa fuerte.
    res = await db.execute(
        select(UsuarioUniversidad).where(UsuarioUniversidad.usuario_id == usuario.id)
    )
    activas = [m for m in res.scalars().all() if m.activo]
    if len(activas) > 1:
        error(
            f"'{usuario.username}' tiene {len(activas)} membresías activas. "
            "Su cliente NO va a poder loguearse."
        )
        nota("Con 2+ membresías, /auth/login devuelve la selección de universidad")
        nota("sin `access_token`. Su cliente lo toma como falla de infraestructura")
        nota("y reintenta indefinidamente. Una cuenta por universidad.")
    else:
        ok(f"'{usuario.username}' tiene exactamente 1 membresía activa")


async def _resolver_materia(
    db: AsyncSession,
    uni: Universidad,
    *,
    external_ref: str,
    codigo: str | None,
    nombre: str | None,
    aplicar: bool,
) -> Materia | None:
    """Ubica la materia por el external_ref que AI-Native va a mandar, o la crea."""
    res = await db.execute(
        select(Materia).where(
            Materia.universidad_id == uni.id,
            Materia.external_ref == external_ref,
            Materia.activa.is_(True),
        )
    )
    materia = res.scalar_one_or_none()
    if materia is not None:
        ok(f"Materia '{materia.nombre}' (id={materia.id}) ya tiene ese external_ref")
        return materia

    # Puede existir la materia pero SIN el external_ref: es el caso normal si la
    # materia vino de Moodle. Completarle el ref es preferible a crear una
    # segunda materia que duplique la misma cursada.
    if codigo:
        res = await db.execute(
            select(Materia).where(
                Materia.universidad_id == uni.id,
                Materia.codigo == codigo,
                Materia.activa.is_(True),
            )
        )
        existente = res.scalar_one_or_none()
        if existente is not None:
            if existente.external_ref and existente.external_ref != external_ref:
                raise Aborta(
                    f"La materia '{existente.nombre}' (código {codigo}) ya tiene "
                    f"external_ref '{existente.external_ref}', distinto del que "
                    f"pediste ('{external_ref}'). Pisarlo desconectaría lo que "
                    "AI-Native ya haya publicado contra el ref viejo."
                )
            falta(f"Materia '{existente.nombre}' existe SIN external_ref")
            nota(f"se le asignaría external_ref = {external_ref}")
            if aplicar:
                existente.external_ref = external_ref
                await db.flush()
            return existente

    if not (codigo and nombre):
        raise Aborta(
            f"No hay materia con external_ref '{external_ref}' en '{uni.nombre}', "
            "y no puedo crearla sin --materia-codigo y --materia-nombre. "
            "Confirmá con AI-Native qué external_ref van a mandar antes de crear "
            "una materia nueva: si no coincide, su PUT sigue dando 404."
        )

    falta(f"No existe la materia. Se crearía '{nombre}' (código {codigo})")
    nota(f"external_ref = {external_ref}")
    if not aplicar:
        return None

    materia = Materia(
        universidad_id=uni.id,
        codigo=codigo,
        nombre=nombre,
        external_ref=external_ref,
        activa=True,
    )
    db.add(materia)
    await db.flush()
    return materia


async def _vincular_coordinador(
    db: AsyncSession, usuario: Usuario, materia: Materia, *, aplicar: bool
) -> None:
    """Sin esta fila, el rol COORDINADOR recibe 403 en todos los endpoints."""
    res = await db.execute(
        select(CoordinadorMateria).where(
            CoordinadorMateria.materia_id == materia.id,
            CoordinadorMateria.coordinador_id == usuario.id,
        )
    )
    if res.scalar_one_or_none() is not None:
        ok(f"'{usuario.username}' ya es coordinador de '{materia.nombre}'")
        return

    falta(f"Se vincularía '{usuario.username}' como coordinador de '{materia.nombre}'")
    nota("sin esto, todos los endpoints le devuelven 403")
    if aplicar:
        # `asignado_en` lo pone el default del modelo: repetirlo aca seria una
        # segunda fuente de verdad para la misma marca de tiempo.
        db.add(
            CoordinadorMateria(
                materia_id=materia.id,
                coordinador_id=usuario.id,
            )
        )
        await db.flush()


async def _asegurar_comision_integracion(
    db: AsyncSession,
    materia: Materia,
    *,
    nombre_comision: str,
    anio: int,
    aplicar: bool,
) -> Comision | None:
    """Crea la comisión de integración y la deja apuntada desde la materia."""
    if materia.comision_integracion_id:
        comision = await db.get(Comision, materia.comision_integracion_id)
        if comision is not None and comision.activa:
            ok(
                f"Comisión de integración ya configurada: "
                f"'{comision.nombre}' (id={comision.id})"
            )
            return comision
        error(
            f"materia.comision_integracion_id={materia.comision_integracion_id} "
            "apunta a una comisión inexistente o dada de baja. Se reapunta."
        )

    res = await db.execute(
        select(Comision).where(
            Comision.materia_id == materia.id,
            Comision.nombre == nombre_comision,
            Comision.activa.is_(True),
        )
    )
    comision = res.scalar_one_or_none()

    if comision is None:
        falta(f"Se crearía la comisión '{nombre_comision}' ({anio})")
        nota("es el destino de TODA entrega de AI-Native: su cliente no manda")
        nota("comision_external_ref, así que sin esto toda corrección da 409")
        if not aplicar:
            return None
        comision = Comision(
            materia_id=materia.id,
            universidad_id=materia.universidad_id,
            nombre=nombre_comision,
            anio=anio,
            activa=True,
        )
        db.add(comision)
        await db.flush()
    else:
        ok(f"La comisión '{nombre_comision}' ya existe (id={comision.id})")

    if materia.comision_integracion_id != comision.id:
        falta(f"Se apuntaría materia.comision_integracion_id -> {comision.id}")
        if aplicar:
            materia.comision_integracion_id = comision.id
            await db.flush()

    return comision


async def _verificar(db: AsyncSession, uni: Universidad, usuario: Usuario) -> bool:
    """Relee el estado final desde la base. No confía en lo que acaba de escribir."""
    print(f"\n{'=' * 62}\nVERIFICACIÓN — {uni.nombre}\n{'=' * 62}")

    res = await db.execute(
        select(Materia)
        .join(CoordinadorMateria, CoordinadorMateria.materia_id == Materia.id)
        .where(
            CoordinadorMateria.coordinador_id == usuario.id,
            Materia.universidad_id == uni.id,
            Materia.activa.is_(True),
        )
    )
    materias = list(res.scalars().all())

    if not materias:
        error(f"'{usuario.username}' no coordina ninguna materia en '{uni.nombre}'")
        nota("su PUT de trabajos prácticos va a devolver 403")
        return False

    todo_ok = True
    for m in materias:
        print(f"\n  Materia '{m.nombre}' (id={m.id})")
        if m.external_ref:
            ok(f"external_ref = {m.external_ref}")
        else:
            error("sin external_ref -> su PUT devuelve 404")
            todo_ok = False

        if m.comision_integracion_id:
            c = await db.get(Comision, m.comision_integracion_id)
            if c is not None and c.activa:
                ok(f"comisión de integración: '{c.nombre}' (id={c.id})")
            else:
                error("comision_integracion_id apunta a algo que no existe -> 409")
                todo_ok = False
        else:
            error("sin comisión de integración -> toda corrección devuelve 409")
            todo_ok = False

    return todo_ok


async def main() -> int:
    ap = argparse.ArgumentParser(
        description="Deja lista la integración con AI-Native en una universidad.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--universidad", type=int, required=True, help="id de la universidad")
    ap.add_argument("--usuario", required=True, help="username de la cuenta de AI-Native")
    ap.add_argument("--materia-external-ref", help="el ref que AI-Native va a mandar")
    ap.add_argument("--materia-codigo", help="código, si hay que crear la materia")
    ap.add_argument("--materia-nombre", help="nombre, si hay que crear la materia")
    ap.add_argument("--comision-nombre", default=NOMBRE_COMISION_DEFECTO)
    ap.add_argument("--anio", type=int, default=datetime.now(timezone.utc).year)
    ap.add_argument(
        "--aplicar",
        action="store_true",
        help="ESCRIBE en la base. Sin esto es dry-run y no toca nada.",
    )
    ap.add_argument(
        "--verificar",
        action="store_true",
        help="Sólo lee y reporta el estado final. No escribe nunca.",
    )
    args = ap.parse_args()

    from app.models.base import async_session_maker

    async with async_session_maker() as db:
        try:
            uni = await _cargar_universidad(db, args.universidad)
            usuario = await _cargar_usuario(db, args.usuario)

            if args.verificar:
                return 0 if await _verificar(db, uni, usuario) else 1

            if not args.materia_external_ref:
                raise Aborta("Falta --materia-external-ref (o usá --verificar).")

            modo = "APLICANDO" if args.aplicar else "DRY-RUN (no escribe nada)"
            print(f"\n{'=' * 62}")
            print(f"{uni.nombre} — {modo}")
            print(f"{'=' * 62}\n")

            await _validar_membresia(db, usuario, uni)

            materia = await _resolver_materia(
                db, uni,
                external_ref=args.materia_external_ref,
                codigo=args.materia_codigo,
                nombre=args.materia_nombre,
                aplicar=args.aplicar,
            )
            if materia is None:
                print(f"\n{AMARILLO}Dry-run: falta crear la materia. "
                      f"Repetí con --aplicar.{FIN}\n")
                await db.rollback()
                return 0

            await _vincular_coordinador(db, usuario, materia, aplicar=args.aplicar)
            await _asegurar_comision_integracion(
                db, materia,
                nombre_comision=args.comision_nombre,
                anio=args.anio,
                aplicar=args.aplicar,
            )

            if args.aplicar:
                await db.commit()
                print(f"\n{VERDE}Aplicado.{FIN}")
                await _verificar(db, uni, usuario)
            else:
                # Todo lo tentativo se descarta. Un dry-run que deja algo
                # escrito no es un dry-run.
                await db.rollback()
                print(f"\n{AMARILLO}Dry-run terminado. Nada se escribió.{FIN}")
                print("Repetí el mismo comando con --aplicar cuando esto sea lo "
                      "que esperabas.\n")
            return 0

        except Aborta as e:
            await db.rollback()
            print(f"\n{ROJO}ABORTADO:{FIN} {e}\n")
            return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
