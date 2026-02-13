"""
Script para crear un usuario administrador en la base de datos.

Uso:
    python scripts/create_admin.py

Crea un usuario admin si no existe.
NO borra datos existentes.
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.models.usuario import Usuario
from app.models.enums import RolEnum


async def create_admin():
    """Crea un usuario administrador."""

    print("🚀 Creando usuario administrador...")

    # Crear engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Sin logs SQL
    )

    # Crear sesión
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Verificar si ya existe un admin
        result = await session.execute(
            select(Usuario).where(Usuario.username == "admin")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("⚠️  El usuario 'admin' ya existe en la base de datos.")
            print(f"    Nombre: {existing.nombre}")
            print(f"    Rol: {existing.rol.value}")
            print(f"    Activo: {existing.activo}")
            print("\n💡 Si necesitas resetear la contraseña, elimina el usuario primero.")
        else:
            # Crear usuario admin
            print("👤 Creando usuario administrador...")
            admin = Usuario(
                username="admin",
                nombre="Administrador del Sistema",
                password_hash=hash_password("admin123"),
                rol=RolEnum.ADMIN,
                primer_login=True,  # Forzar cambio de contraseña en primer login
                activo=True,
            )

            session.add(admin)
            await session.commit()

            print("\n✅ Usuario administrador creado exitosamente")
            print("\n" + "="*70)
            print("📝 CREDENCIALES DE ACCESO")
            print("="*70)
            print("\n  [ADMIN]")
            print("  Username: admin")
            print("  Password: admin123")
            print("  Nombre:   Administrador del Sistema")
            print("\n⚠️  IMPORTANTE: Cambia la contraseña en el primer login")
            print("="*70 + "\n")

    await engine.dispose()
    print("✨ Proceso completado")


if __name__ == "__main__":
    asyncio.run(create_admin())
