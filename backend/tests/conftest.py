"""
Pytest configuration and fixtures for Active-IA tests.

Provides database session fixtures and common test utilities.
"""

import asyncio
import os
from typing import AsyncGenerator

# La suite corre sin .env. Sin esto, el validador de arranque de Settings
# (SEC-003) aborta el import de app.core.config: DEBUG default es False
# (= producción) y los secretos son los defaults del repo. Los tests son
# entorno de desarrollo, así que DEBUG=True.
os.environ.setdefault("DEBUG", "True")

import json
import sqlite3

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models.base import Base


# Database URL for testing (SQLite in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# El esquema usa JSONB y ARRAY (Postgres) en varias tablas; SQLite no sabe
# renderizarlos y `Base.metadata.create_all` revienta con CompileError.
#
# Varios módulos de test ya registraban esto por su cuenta, pero @compiles y
# register_adapter son GLOBALES AL PROCESO: si el registro vive en un módulo
# suelto, que funcione o no depende del orden de importación de pytest. Vive
# acá para que sea determinístico y una sola vez.


@compiles(JSONB, "sqlite")
def _compilar_jsonb_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _compilar_array_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an instance of the default event loop for the test session.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh database session for each test.

    Yields:
        AsyncSession: Database session for testing.
    """
    # Create async engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
