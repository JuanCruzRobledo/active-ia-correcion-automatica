"""
Tests for EntregaService.

Tests cover:
- Creating individual entregas
- Creating entregas from ZIP (masiva)
- Handling duplicates (overwrite vs error)
- Soft deleting entregas
- Validation of required fields

Nota de mantenimiento: este archivo venía del commit inicial del repo y nunca
llegó a ejecutarse — importaba `CargaMasivaRequest`, un símbolo que jamás
existió, así que pytest cortaba en la colección. Se reescribió contra la API
real conservando la intención de los 11 tests originales. La API había
derivado en: `EntregaCreate` se redujo a `alumno_nombre`/`comision_id`/
`rubrica_id` y el archivo pasó a viajar como `UploadFile` aparte;
`crear_entrega_masiva` recibe argumentos planos en vez de un schema;
`eliminar_entrega` pide `actor_id`; y `universidad_id` entró con
multi-tenant-scoping-queries (Fase 4), donde el service lo propaga desde el
padre ya cargado.

Es el único lugar de la suite que ejercita `crear_entrega_individual` y
`crear_entrega_masiva` de verdad: el resto de los tests los mockea.
"""

import io
import json
import zipfile
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comision import Comision
from app.models.materia import Materia
from app.models.rubrica import Rubrica, TipoRubricaEnum
from app.models.enums import RolEnum
from app.models.usuario import Usuario
from app.schemas.entrega import EntregaCreate
from app.services.entrega_service import EntregaService

# multi-tenant-scoping-queries (Fase 4): universidad_id es NOT NULL en toda la
# rama Materia -> Comision -> Rubrica -> Entrega.
UNIV_ID = 1


def crear_zip_simple(contenido: str = "print('hello')") -> bytes:
    """Create a simple ZIP file with one Python file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", contenido)
    return buffer.getvalue()


def crear_zip_proyecto_spring() -> bytes:
    """ZIP con la forma real de una entrega Spring Boot.

    Mezcla a propósito archivos de los tres modos: `.java` (solo_codigo),
    `.css` (web_completo) y `.gradle`/`.properties` (proyecto_completo), para
    que el modo aplicado se lea en qué archivos entraron.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("gestion-pedidos/build.gradle", "dependencies { implementation 'org.projectlombok:lombok' }")
        zf.writestr("gestion-pedidos/src/main/resources/application.properties", "server.port=8080")
        zf.writestr("gestion-pedidos/src/main/java/App.java", "class App {}")
        zf.writestr("gestion-pedidos/src/main/resources/static/estilos.css", "body { margin: 0; }")
    return buffer.getvalue()


async def _archivos_incluidos(
    service: EntregaService, rubrica_id: int, alumno_nombre: str
) -> list[str]:
    """Archivos que efectivamente quedaron consolidados para el corrector."""
    entrega = await service.entrega_repo.get_by_rubrica_alumno(
        rubrica_id=rubrica_id,
        alumno_nombre=alumno_nombre,
    )
    assert entrega is not None, f"No se encontró la entrega de {alumno_nombre}"
    incluidos = entrega.archivos_incluidos or []
    # En SQLite la columna JSON puede volver como str; en Postgres ya es lista.
    if isinstance(incluidos, str):
        incluidos = json.loads(incluidos)
    return list(incluidos)


def _upload(contenido: bytes, filename: str) -> UploadFile:
    """UploadFile en memoria: el service usa .size, .filename y await .read()."""
    return UploadFile(
        file=io.BytesIO(contenido),
        filename=filename,
        size=len(contenido),
    )


@pytest_asyncio.fixture
async def materia(db_session: AsyncSession) -> Materia:
    """Create a test materia."""
    materia = Materia(
        universidad_id=UNIV_ID,
        codigo="PROG1",
        nombre="Programación 1",
        activa=True,
    )
    db_session.add(materia)
    await db_session.commit()
    await db_session.refresh(materia)
    return materia


@pytest_asyncio.fixture
async def comision(db_session: AsyncSession, materia: Materia) -> Comision:
    """Create a test comision."""
    comision = Comision(
        universidad_id=UNIV_ID,
        materia_id=materia.id,
        nombre="Comisión A",
        anio=2026,
        activa=True,
    )
    db_session.add(comision)
    await db_session.commit()
    await db_session.refresh(comision)
    return comision


@pytest_asyncio.fixture
async def rubrica(db_session: AsyncSession, materia: Materia) -> Rubrica:
    """Create a test rubrica."""
    criterios: list[dict[str, Any]] = [
        {
            "id": "C1",
            "nombre": "Funcionalidad",
            "descripcion": "Código funciona",
            "peso": 100,
            "subcriterios": [
                {
                    "id": "C1.1",
                    "descripcion": "El código corre sin errores",
                    "evidencias": ["Se ejecuta sin excepciones"],
                }
            ],
        }
    ]
    rubrica = Rubrica(
        universidad_id=UNIV_ID,
        materia_id=materia.id,
        tipo=TipoRubricaEnum.TP,
        titulo="TP1 - Listas",
        descripcion="Evalúa el manejo de listas.",
        puntaje_maximo=100,
        numero=1,
        anio=2026,
        criterios_json=criterios,
        activa=True,
    )
    db_session.add(rubrica)
    await db_session.commit()
    await db_session.refresh(rubrica)
    return rubrica


@pytest_asyncio.fixture
async def subidor(db_session: AsyncSession) -> Usuario:
    """Usuario que sube las entregas y actúa de actor en el borrado.

    `password_hash` se setea literal a propósito: `hash_password()` depende de
    passlib+bcrypt y estos tests no ejercitan autenticación.
    """
    usuario = Usuario(
        username="subidor_test",
        nombre="Subidor Test",
        password_hash="no-usado-en-estos-tests",
    )
    db_session.add(usuario)
    await db_session.commit()
    await db_session.refresh(usuario)
    return usuario


@pytest.mark.asyncio
class TestEntregaService:
    """Tests for EntregaService."""

    async def test_crear_entrega_individual_success(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating individual entrega successfully."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )

        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple("print('hello world')"), "tp1.zip"),
            subido_por_id=subidor.id,
        )

        assert entrega.id is not None
        assert entrega.alumno_nombre == "Pérez, Juan"
        assert entrega.comision_id == comision.id
        assert entrega.rubrica_id == rubrica.id
        assert entrega.archivo_nombre == "tp1.zip"
        assert entrega.archivado is False

    async def test_crear_entrega_individual_comision_not_found(
        self,
        db_session: AsyncSession,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating entrega with non-existent comision fails."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=9999,  # Non-existent
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), "test.zip"),
                subido_por_id=subidor.id,
            )

        assert exc_info.value.status_code == 404

    async def test_crear_entrega_individual_rubrica_not_found(
        self,
        db_session: AsyncSession,
        comision: Comision,
        subidor: Usuario,
    ):
        """Test creating entrega with non-existent rubrica fails."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=9999,  # Non-existent
            alumno_nombre="Test Student",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), "test.zip"),
                subido_por_id=subidor.id,
            )

        assert exc_info.value.status_code == 404

    async def test_crear_entrega_individual_pdf(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating an individual PDF entrega."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )

        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(b"%PDF-1.4 mock pdf content", "documento.pdf"),
            subido_por_id=subidor.id,
            modo_consolidacion="solo_codigo",  # se ignora para PDF
        )

        # `contenido_consolidado` no viaja en EntregaResponse (PERF-006: es una
        # columna deferred); el marcador de PDF se ve en el preview.
        assert entrega.id is not None
        assert entrega.archivo_tipo == "pdf"
        assert "[Entrega en formato PDF]" in entrega.contenido_preview

    async def test_crear_entrega_duplicada_sin_sobrescribir(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating duplicate entrega without overwrite fails."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )
        await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple(), "tp1_v1.zip"),
            subido_por_id=subidor.id,
        )

        # Mismo alumno + misma rúbrica, sin sobrescribir -> conflicto
        with pytest.raises(HTTPException) as exc_info:
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), "tp1_v2.zip"),
                subido_por_id=subidor.id,
            )

        assert exc_info.value.status_code == 409
        assert "ya existe" in exc_info.value.detail.lower()

    async def test_crear_entrega_duplicada_con_sobrescribir(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test creating duplicate entrega with overwrite succeeds."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Pérez, Juan",
        )

        entrega_v1 = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple("print('version 1')"), "tp1_v1.zip"),
            subido_por_id=subidor.id,
        )

        entrega_v2 = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple("print('version 2')"), "tp1_v2.zip"),
            subido_por_id=subidor.id,
            sobrescribir=True,
        )

        # Se pisa la misma fila, no se crea una nueva
        assert entrega_v2.id == entrega_v1.id
        assert entrega_v2.archivo_nombre == "tp1_v2.zip"

    async def test_crear_entrega_masiva_pdf(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Masiva con dos alumnos: uno entrega código y el otro un PDF."""
        service = EntregaService(db_session)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("García, Ana/main.py", "print('codigo')")
            zf.writestr("Pérez, Juan/documento.pdf", b"%PDF-1.4 mock pdf")

        resultado = await service.crear_entrega_masiva(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            archivo_zip=_upload(buffer.getvalue(), "entregas.zip"),
            subido_por_id=subidor.id,
        )

        assert resultado.total_procesadas == 2
        assert resultado.total_exitosas == 2

        resultado_db = await service.listar_entregas(comision_id=comision.id)
        assert resultado_db.total == 2

        entregas_pdf = [
            e for e in resultado_db.items if e.alumno_nombre == "Pérez, Juan"
        ]
        entregas_codigo = [
            e for e in resultado_db.items if e.alumno_nombre == "García, Ana"
        ]

        assert len(entregas_pdf) == 1
        assert len(entregas_codigo) == 1
        assert entregas_pdf[0].archivo_tipo == "pdf"

    async def test_listar_entregas_por_comision(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test listing entregas by comision."""
        service = EntregaService(db_session)

        for i in range(3):
            data = EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=f"Alumno {i}",
            )
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(f"print('student {i}')"), f"tp{i}.zip"),
                subido_por_id=subidor.id,
            )

        result = await service.listar_entregas(comision_id=comision.id)

        assert result.total == 3
        assert len(result.items) == 3

    async def test_listar_entregas_por_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test listing entregas by rubrica."""
        service = EntregaService(db_session)

        for i in range(2):
            data = EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=f"Alumno {i}",
            )
            await service.crear_entrega_individual(
                data=data,
                archivo=_upload(crear_zip_simple(), f"tp{i}.zip"),
                subido_por_id=subidor.id,
            )

        result = await service.listar_entregas(rubrica_id=rubrica.id)

        assert result.total == 2

    async def test_eliminar_entrega_soft_delete(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test soft deleting entrega."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
        )
        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple(), "test.zip"),
            subido_por_id=subidor.id,
        )

        await service.eliminar_entrega(entrega.id, actor_id=subidor.id)

        # Baja lógica: desaparece del listado activo
        result = await service.listar_entregas(comision_id=comision.id)
        assert result.total == 0

    async def test_listar_entregas_papelera_muestra_las_eliminadas(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """
        CRUD-011: sin esto una entrega borrada es inalcanzable — no se puede
        listar, así que nadie conoce su id y el endpoint de restore queda muerto.
        """
        service = EntregaService(db_session)
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
        )
        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple(), "test.zip"),
            subido_por_id=subidor.id,
        )
        await service.eliminar_entrega(entrega.id, actor_id=subidor.id)

        papelera = await service.listar_entregas(
            comision_id=comision.id, solo_eliminadas=True
        )
        assert papelera.total == 1
        assert papelera.items[0].id == entrega.id
        # el listado tiene que decir CUÁL está borrada, si no la papelera es ciega
        assert papelera.items[0].deleted_at is not None

    async def test_listar_entregas_incluir_eliminadas_trae_vivas_y_borradas(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Triangulación: incluir != solo."""
        service = EntregaService(db_session)
        creadas = []
        for nombre in ("Alumno Vivo", "Alumno Borrado"):
            data = EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre=nombre,
            )
            creadas.append(
                await service.crear_entrega_individual(
                    data=data,
                    archivo=_upload(crear_zip_simple(), f"{nombre}.zip"),
                    subido_por_id=subidor.id,
                )
            )
        await service.eliminar_entrega(creadas[1].id, actor_id=subidor.id)

        todas = await service.listar_entregas(
            comision_id=comision.id, incluir_eliminadas=True
        )
        assert todas.total == 2
        por_id = {i.id: i for i in todas.items}
        assert por_id[creadas[0].id].deleted_at is None
        assert por_id[creadas[1].id].deleted_at is not None

    async def test_obtener_entrega_con_correccion(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Test getting entrega with correction included."""
        service = EntregaService(db_session)

        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Test Student",
        )
        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_simple(), "test.zip"),
            subido_por_id=subidor.id,
        )

        detail = await service.obtener_entrega(entrega.id)

        assert detail.id == entrega.id
        assert detail.alumno_nombre == "Test Student"
        assert detail.tiene_correccion is False  # todavía no se corrigió
        # Regresión: `obtener_entrega` arma un HistorialResponse para contar
        # versiones. Construirlo con los nombres de campo equivocados hacía
        # explotar el endpoint entero con 500.
        assert detail.num_versiones_anteriores == 0

    # ------------------------------------------------------------------
    # Regresión BUG-CONSOLIDACION: el modo lo manda el cliente, no la rúbrica.
    #
    # `crear_entrega_individual` / `crear_entrega_masiva` recibían
    # `modo_consolidacion` con default "solo_codigo" y NUNCA consultaban la
    # rúbrica ya cargada. Cualquier cliente que no mandara el campo (la skill
    # de Moodle, un script, curl) consolidaba en "solo_codigo" aunque la
    # rúbrica pidiera "proyecto_completo": los .gradle/.properties/.xml no
    # llegaban al corrector y el modelo informaba "no se entregó el archivo
    # de build". Confirmado en producción sobre la rúbrica 188 (PROG4A26):
    # 3 entregas consolidadas en "Solo código" con la rúbrica en
    # "proyecto_completo" -> C2 2/10, y una alumna desaprobada.
    # ------------------------------------------------------------------

    async def test_entrega_individual_usa_el_modo_de_la_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Sin modo explícito, se consolida con el modo que declara la rúbrica."""
        rubrica.modo_consolidacion = "proyecto_completo"
        await db_session.commit()

        service = EntregaService(db_session)
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Herrera, Jazmin",
        )

        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_proyecto_spring(), "gestion-pedidos.zip"),
            subido_por_id=subidor.id,
        )

        incluidos = await _archivos_incluidos(service, rubrica.id, "Herrera, Jazmin")
        assert any(a.endswith("build.gradle") for a in incluidos), (
            f"build.gradle no llegó al corrector. Incluidos: {incluidos}"
        )
        assert any(a.endswith("application.properties") for a in incluidos), (
            f"application.properties no llegó al corrector. Incluidos: {incluidos}"
        )
        assert "Proyecto completo" in (entrega.contenido_preview or "")

    async def test_entrega_individual_modo_explicito_gana_sobre_la_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Un modo explícito del caller sigue teniendo precedencia (override)."""
        rubrica.modo_consolidacion = "proyecto_completo"
        await db_session.commit()

        service = EntregaService(db_session)
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Override, Test",
        )

        await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_proyecto_spring(), "tp.zip"),
            subido_por_id=subidor.id,
            modo_consolidacion="solo_codigo",
        )

        incluidos = await _archivos_incluidos(service, rubrica.id, "Override, Test")
        assert not any(a.endswith("build.gradle") for a in incluidos)
        assert any(a.endswith(".java") for a in incluidos)

    async def test_entrega_individual_web_completo_de_la_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Triangulación: `web_completo` trae el .css pero no el .gradle."""
        rubrica.modo_consolidacion = "web_completo"
        await db_session.commit()

        service = EntregaService(db_session)
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Web, Alumno",
        )

        await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_proyecto_spring(), "tp.zip"),
            subido_por_id=subidor.id,
        )

        incluidos = await _archivos_incluidos(service, rubrica.id, "Web, Alumno")
        assert any(a.endswith("estilos.css") for a in incluidos)
        assert not any(a.endswith("build.gradle") for a in incluidos)

    async def test_entrega_masiva_usa_el_modo_de_la_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """La carga masiva también toma el modo de la rúbrica."""
        rubrica.modo_consolidacion = "proyecto_completo"
        await db_session.commit()

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Galarza Manuel_925405_assignsubmission_file/build.gradle", "dependencies { }")
            zf.writestr("Galarza Manuel_925405_assignsubmission_file/App.java", "class App {}")

        service = EntregaService(db_session)
        await service.crear_entrega_masiva(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            archivo_zip=_upload(buffer.getvalue(), "entregas.zip"),
            subido_por_id=subidor.id,
        )

        incluidos = await _archivos_incluidos(service, rubrica.id, "Galarza Manuel")
        assert any(a.endswith("build.gradle") for a in incluidos), (
            f"build.gradle no llegó al corrector. Incluidos: {incluidos}"
        )

    # ------------------------------------------------------------------
    # reconsolidar_entrega: reprocesa el contenido de una entrega existente
    # con el modo actual de la rúbrica, SIN destruir su corrección.
    #
    # La consolidación ocurre al subir, no al corregir: `corregir` arma el
    # payload con `entrega.contenido_consolidado` ya guardado. Cuando una
    # entrega se consolidó con el modo equivocado (BUG-CONSOLIDACION), el
    # único camino era borrar la corrección para poder sobrescribir —
    # destructivo, y sobre notas ya comunicadas a los alumnos.
    # ------------------------------------------------------------------

    async def test_reconsolidar_reprocesa_con_el_modo_actual_de_la_rubrica(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """Una entrega consolidada con el modo viejo se reprocesa con el nuevo."""
        rubrica.modo_consolidacion = "solo_codigo"
        await db_session.commit()

        service = EntregaService(db_session)
        data = EntregaCreate(
            comision_id=comision.id,
            rubrica_id=rubrica.id,
            alumno_nombre="Herrera, Jazmin",
        )
        entrega = await service.crear_entrega_individual(
            data=data,
            archivo=_upload(crear_zip_proyecto_spring(), "gestion-pedidos.zip"),
            subido_por_id=subidor.id,
        )

        # Se consolidó mal: el build.gradle nunca llegó al corrector.
        incluidos = await _archivos_incluidos(service, rubrica.id, "Herrera, Jazmin")
        assert not any(a.endswith("build.gradle") for a in incluidos)

        # La rúbrica se corrige y la entrega se reprocesa con el mismo ZIP.
        rubrica.modo_consolidacion = "proyecto_completo"
        await db_session.commit()

        resultado = await service.reconsolidar_entrega(
            entrega_id=entrega.id,
            archivo=_upload(crear_zip_proyecto_spring(), "gestion-pedidos.zip"),
            actor_id=subidor.id,
        )

        incluidos = await _archivos_incluidos(service, rubrica.id, "Herrera, Jazmin")
        assert any(a.endswith("build.gradle") for a in incluidos), (
            f"build.gradle sigue sin llegar. Incluidos: {incluidos}"
        )
        assert any(a.endswith("application.properties") for a in incluidos)
        assert "Proyecto completo" in (resultado.contenido_preview or "")

    async def test_reconsolidar_conserva_la_correccion_existente(
        self,
        db_session: AsyncSession,
        comision: Comision,
        rubrica: Rubrica,
        subidor: Usuario,
    ):
        """No se pierde la corrección: es lo que separa esto de sobrescribir."""
        from app.models.correccion import Correccion

        rubrica.modo_consolidacion = "solo_codigo"
        await db_session.commit()

        service = EntregaService(db_session)
        entrega = await service.crear_entrega_individual(
            data=EntregaCreate(
                comision_id=comision.id,
                rubrica_id=rubrica.id,
                alumno_nombre="Con, Correccion",
            ),
            archivo=_upload(crear_zip_proyecto_spring(), "tp.zip"),
            subido_por_id=subidor.id,
        )

        correccion = Correccion(
            universidad_id=UNIV_ID,
            entrega_id=entrega.id,
            nota=Decimal("52"),
            criterios_json={"criterios": []},
            fortalezas=[],
            recomendaciones=[],
            corregido_por_id=subidor.id,
        )
        db_session.add(correccion)
        await db_session.commit()

        rubrica.modo_consolidacion = "proyecto_completo"
        await db_session.commit()

        await service.reconsolidar_entrega(
            entrega_id=entrega.id,
            archivo=_upload(crear_zip_proyecto_spring(), "tp.zip"),
            actor_id=subidor.id,
        )

        detalle = await service.obtener_entrega(entrega.id)
        assert detalle.tiene_correccion is True, (
            "reconsolidar borró la corrección — es justo lo que debe evitar"
        )

    async def test_reconsolidar_entrega_inexistente_da_404(
        self,
        db_session: AsyncSession,
        subidor: Usuario,
    ):
        """Una entrega que no existe no se reprocesa en silencio."""
        service = EntregaService(db_session)

        with pytest.raises(HTTPException) as exc:
            await service.reconsolidar_entrega(
                entrega_id=999999,
                archivo=_upload(crear_zip_simple(), "tp.zip"),
                actor_id=subidor.id,
            )

        assert exc.value.status_code == 404
