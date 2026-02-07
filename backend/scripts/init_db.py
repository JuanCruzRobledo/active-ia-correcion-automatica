"""
Script para inicializar la base de datos con datos mínimos.

Crea:
- Usuario administrador inicial
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models.base import Base
from app.models.usuario import Usuario
from app.models.enums import RolEnum

# Importar TODOS los modelos para que SQLAlchemy los registre
from app.models.materia import Materia, CoordinadorMateria
from app.models.comision import Comision, ComisionTutor
from app.models.rubrica import Rubrica
from app.models.entrega import Entrega, EntregaHistorial
from app.models.correccion import Correccion


async def init_db():
    """Inicializa la base de datos con datos mínimos."""

    print("🚀 Iniciando configuración de base de datos...")

    # Crear engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True,
    )

    # RECREAR TODAS LAS TABLAS desde cero con el esquema actualizado
    print("⚠️  BORRANDO todas las tablas existentes...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    print("✨ Creando tablas con esquema V2 actualizado...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Crear sesión
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        from sqlalchemy import select

        # Definir usuarios de prueba
        usuarios_prueba = [
            {
                "username": "admin",
                "nombre": "Administrador del Sistema",
                "password": "admin123",
                "rol": RolEnum.ADMIN,
            },
            {
                "username": "coord1",
                "nombre": "María García",
                "password": "coord123",
                "rol": RolEnum.COORDINADOR,
            },
            {
                "username": "tutor1",
                "nombre": "Carlos Rodríguez",
                "password": "tutor123",
                "rol": RolEnum.TUTOR,
            },
        ]

        usuarios_creados = []
        usuarios_existentes = []

        for usuario_data in usuarios_prueba:
            # Verificar si ya existe
            result = await session.execute(
                select(Usuario).where(Usuario.username == usuario_data["username"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                usuarios_existentes.append(usuario_data["username"])
            else:
                # Crear usuario
                print(f"👤 Creando usuario: {usuario_data['nombre']} ({usuario_data['rol'].value})...")
                usuario = Usuario(
                    username=usuario_data["username"],
                    nombre=usuario_data["nombre"],
                    password_hash=hash_password(usuario_data["password"]),
                    rol=usuario_data["rol"],
                    primer_login=True,  # Forzar cambio de contraseña en primer login
                    activo=True,
                )

                session.add(usuario)
                usuarios_creados.append(usuario_data)

        if usuarios_creados:
            await session.commit()
            print(f"\n✅ {len(usuarios_creados)} usuario(s) creado(s) exitosamente")

            print("\n" + "="*70)
            print("📝 CREDENCIALES DE ACCESO - USUARIOS DE PRUEBA")
            print("="*70)
            for user_data in usuarios_creados:
                print(f"\n  [{user_data['rol'].value.upper()}]")
                print(f"  Username: {user_data['username']}")
                print(f"  Password: {user_data['password']}")
                print(f"  Nombre:   {user_data['nombre']}")
                print("  " + "-"*66)
            print("\n⚠️  IMPORTANTE: Cambia las contraseñas en el primer login")
            print("="*70 + "\n")

        if usuarios_existentes:
            print(f"\n⚠️  {len(usuarios_existentes)} usuario(s) ya existe(n): {', '.join(usuarios_existentes)}")

    await engine.dispose()
    print("✨ Inicialización completada")


if __name__ == "__main__":
    asyncio.run(init_db())
