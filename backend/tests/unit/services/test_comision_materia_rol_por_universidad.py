"""Fase 6 multi-tenant (multi-tenant-cleanup-rol-global, D3, hallazgo tarea 3.5).

`comision_service`/`materia_service` validaban "¿este candidato tiene rol
TUTOR/COORDINADOR?" contra `usuario.rol` GLOBAL — un lector del rol global
que el grep de design.md no había anticipado (esos servicios no están en la
lista de "últimos lectores" de la Parte 3). Con dos universidades, una
persona TUTOR en A y COORDINADOR en B (o viceversa) se validaba mal: el rol
correcto es el de la membresía en la universidad DE LA MATERIA/COMISIÓN.
"""

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.models.materia import Materia
from app.models.usuario_universidad import UsuarioUniversidad
from app.schemas.comision import ComisionCreate
from app.schemas.materia import CoordinadoresAssign
from app.services.comision_service import ComisionService
from app.services.materia_service import MateriaService
from tests.helpers.usuario_membresia import crear_universidad, crear_usuario_con_membresia


@pytest.mark.asyncio
async def test_crear_comision_rechaza_tutor_de_otra_universidad(db_session):
    """Persona TUTOR en A, COORDINADOR en B. Crear una comisión de una
    materia de B pasándola como tutor debe fallar (no es TUTOR en B)."""
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    db_session.add(
        UsuarioUniversidad(usuario_id=persona.id, universidad_id=uni_b.id, rol=RolEnum.COORDINADOR, activo=True)
    )
    materia_b = Materia(universidad_id=uni_b.id, codigo="PROG1", nombre="Programación 1", activa=True)
    db_session.add(materia_b)
    await db_session.commit()

    service = ComisionService(db_session)
    data = ComisionCreate(nombre="Comisión 1", anio=2026, materia_id=materia_b.id, tutor_ids=[persona.id])

    with pytest.raises(HTTPException) as exc_info:
        await service.crear_comision(data, universidad_id=uni_b.id)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_comision_acepta_tutor_de_la_misma_universidad(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.TUTOR, universidad=uni_a)
    materia_a = Materia(universidad_id=uni_a.id, codigo="PROG2", nombre="Programación 2", activa=True)
    db_session.add(materia_a)
    await db_session.commit()

    service = ComisionService(db_session)
    data = ComisionCreate(nombre="Comisión 1", anio=2026, materia_id=materia_a.id, tutor_ids=[persona.id])

    # No debe lanzar (rol correcto en la universidad de la materia).
    resultado = await service.crear_comision(data, universidad_id=uni_a.id)

    tutores_asignados = await service.comision_tutor_repo.get_tutores_for_comision(resultado.id)
    assert [t.tutor_id for t in tutores_asignados] == [persona.id]


@pytest.mark.asyncio
async def test_asignar_coordinadores_rechaza_coordinador_de_otra_universidad(db_session):
    uni_a = await crear_universidad(db_session, "Universidad A")
    uni_b = await crear_universidad(db_session, "Universidad B")
    persona, _, _ = await crear_usuario_con_membresia(db_session, rol=RolEnum.COORDINADOR, universidad=uni_a)
    db_session.add(
        UsuarioUniversidad(usuario_id=persona.id, universidad_id=uni_b.id, rol=RolEnum.TUTOR, activo=True)
    )
    materia_b = Materia(universidad_id=uni_b.id, codigo="PROG3", nombre="Programación 3", activa=True)
    db_session.add(materia_b)
    await db_session.commit()

    service = MateriaService(db_session)
    data = CoordinadoresAssign(coordinador_ids=[persona.id])

    with pytest.raises(HTTPException) as exc_info:
        await service.asignar_coordinadores(materia_b.id, data, universidad_id=uni_b.id)

    assert exc_info.value.status_code == 400
