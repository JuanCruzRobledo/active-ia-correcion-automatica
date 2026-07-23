"""Helper compartido de tests: Usuario + membresía activa en una Universidad.

Fase 6 multi-tenant (multi-tenant-cleanup-rol-global, D7). Reemplaza el patrón
viejo `Usuario(rol=RolEnum.X)` a secas: el rol deja de vivir en `usuarios.rol`
(columna eliminada en el Grupo 5 de esta fase) y pasa a vivir ÚNICAMENTE en
`UsuarioUniversidad.rol` (la membresía).

Por qué un helper único y no borrar `rol=` sin más: muchos tests dependen de
que el usuario TENGA ese rol para que el escenario tenga sentido (ej.
"un TUTOR no puede..."). Sacar el kwarg sin crear la membresía equivalente
deja tests que pasan sin verificar nada — exactamente lo que D7 quiere evitar.

Uso:
    usuario, membresia, universidad = await crear_usuario_con_membresia(
        db_session, rol=RolEnum.TUTOR
    )
    await db_session.commit()

Si ya existe una `Universidad` (para escenarios multi-universidad), se pasa
explícitamente y el helper NO crea una nueva:
    usuario_b, membresia_b, _ = await crear_usuario_con_membresia(
        db_session, rol=RolEnum.COORDINADOR, universidad=universidad_b
    )
"""

import itertools

from app.models.enums import RolEnum
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad

_contador = itertools.count(1)


async def crear_universidad(db, nombre: str | None = None, *, activa: bool = True) -> Universidad:
    """Crea una `Universidad` de test (flush, sin commit)."""
    n = next(_contador)
    universidad = Universidad(nombre=nombre or f"Universidad Test {n}", activa=activa)
    db.add(universidad)
    await db.flush()
    return universidad


async def crear_usuario_con_membresia(
    db,
    *,
    rol: RolEnum = RolEnum.TUTOR,
    universidad: Universidad | None = None,
    username: str | None = None,
    nombre: str | None = None,
    email: str | None = None,
    activo: bool = True,
    membresia_activa: bool = True,
    es_superadmin: bool = False,
    password_hash: str = "x",
) -> tuple[Usuario, UsuarioUniversidad, Universidad]:
    """Crea `Usuario` + (si no se pasa) `Universidad` + `UsuarioUniversidad`.

    Hace `flush()` pero NO `commit()` — el caller decide cuándo commitear,
    igual que el resto de los tests del repo (ver
    `test_usuario_repository_membresias.py`).

    Devuelve `(usuario, membresia, universidad)`.
    """
    n = next(_contador)
    if universidad is None:
        universidad = await crear_universidad(db)

    usuario = Usuario(
        username=username or f"usuario_test_{n}",
        nombre=nombre or f"Usuario Test {n}",
        email=email,
        password_hash=password_hash,
        activo=activo,
        es_superadmin=es_superadmin,
    )
    db.add(usuario)
    await db.flush()

    membresia = UsuarioUniversidad(
        usuario_id=usuario.id,
        universidad_id=universidad.id,
        rol=rol,
        activo=membresia_activa,
    )
    db.add(membresia)
    await db.flush()

    return usuario, membresia, universidad
