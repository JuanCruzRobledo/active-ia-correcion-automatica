"""
Tests del script de configuración de producción para AI-Native.

**Por qué un script de operaciones tiene tests.** Este script escribe en la base
de PRODUCCIÓN y lo corre una persona una vez, a mano, probablemente de noche y
con el cliente esperando. No hay una segunda oportunidad de descubrir que la
consulta usaba una columna que no existe.

Y no es hipotético: la primera versión filtraba por `Materia.deleted_at`, que en
este modelo **no existe** (Materia y Comision usan `activa`, no soft delete), y
leía `membresia.activa` con un `getattr(..., True)` de default — o sea que una
membresía dada de baja habría pasado como activa, en silencio, que es
exactamente el modo de falla que este proyecto viene persiguiendo.

Lo que se prueba acá es la parte que decide y escribe. Lo que NO se prueba es el
`argparse` ni la impresión con colores: ahí no hay nada que pueda salir mal de
forma cara.
"""

import importlib.util
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.comision import Comision
from app.models.materia import CoordinadorMateria, Materia
from app.models.universidad import Universidad
from app.models.usuario import Usuario
from app.models.usuario_universidad import UsuarioUniversidad
from app.models.enums import RolEnum


def _cargar_script():
    """Importa el script por ruta: `scripts/` no es un paquete."""
    ruta = Path(__file__).parents[3] / "scripts" / "configurar_integracion_ai_native.py"
    spec = importlib.util.spec_from_file_location("cfg_ai_native", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


cfg = _cargar_script()


@pytest_asyncio.fixture
async def escenario(db_session):
    """Una universidad con su cuenta de AI-Native y nada más configurado."""
    uni = Universidad(nombre="TUPaD", activa=True)
    otra = Universidad(nombre="FRM", activa=True)
    db_session.add_all([uni, otra])
    await db_session.flush()

    # `Usuario` no tiene columna `rol`: el rol vive en la membresía, que es lo
    # que hace posible que la misma persona sea coordinadora en una universidad
    # y tutora en otra.
    usuario = Usuario(
        username="ai-native-tupad",
        email="ai-native-tupad@example.test",
        nombre="Integración AI-Native",
        password_hash="x",
        activo=True,
    )
    db_session.add(usuario)
    await db_session.flush()

    db_session.add(UsuarioUniversidad(
        usuario_id=usuario.id, universidad_id=uni.id,
        rol=RolEnum.COORDINADOR, activo=True,
    ))
    await db_session.flush()

    return {"db": db_session, "uni": uni, "otra": otra, "usuario": usuario}


class TestGuardas:
    """Lo que tiene que ABORTAR antes de escribir una sola fila."""

    @pytest.mark.asyncio
    async def test_universidad_inexistente(self, escenario):
        with pytest.raises(cfg.Aborta, match="No existe la universidad"):
            await cfg._cargar_universidad(escenario["db"], 9999)

    @pytest.mark.asyncio
    async def test_universidad_inactiva(self, escenario):
        escenario["uni"].activa = False
        await escenario["db"].flush()
        with pytest.raises(cfg.Aborta, match="INACTIVA"):
            await cfg._cargar_universidad(escenario["db"], escenario["uni"].id)

    @pytest.mark.asyncio
    async def test_usuario_inexistente(self, escenario):
        with pytest.raises(cfg.Aborta, match="No existe el usuario"):
            await cfg._cargar_usuario(escenario["db"], "no-existe")

    @pytest.mark.asyncio
    async def test_la_cuenta_de_otra_universidad_aborta(self, escenario):
        """El error más caro del script, y el único que el operador no ve venir.

        Vincular la cuenta de la TUPaD a una materia de la FRM le daría a
        AI-Native acceso cruzado, permanente y silencioso.
        """
        with pytest.raises(cfg.Aborta, match="NO tiene membresía"):
            await cfg._validar_membresia(
                escenario["db"], escenario["usuario"], escenario["otra"]
            )

    @pytest.mark.asyncio
    async def test_membresia_dada_de_baja_aborta(self, escenario):
        res = await escenario["db"].execute(select(UsuarioUniversidad))
        membresia = res.scalar_one()
        membresia.activo = False
        await escenario["db"].flush()

        with pytest.raises(cfg.Aborta, match="dada de baja"):
            await cfg._validar_membresia(
                escenario["db"], escenario["usuario"], escenario["uni"]
            )

    @pytest.mark.asyncio
    async def test_no_puede_crear_la_materia_sin_codigo_ni_nombre(self, escenario):
        """Adivinar el nombre de una materia de producción no es una opción."""
        with pytest.raises(cfg.Aborta, match="no puedo crearla"):
            await cfg._resolver_materia(
                escenario["db"], escenario["uni"],
                external_ref="uuid-nuevo", codigo=None, nombre=None, aplicar=True,
            )

    @pytest.mark.asyncio
    async def test_no_pisa_un_external_ref_distinto_ya_existente(self, escenario):
        """Pisarlo desconectaría lo que el cliente ya publicó contra el ref viejo."""
        escenario["db"].add(Materia(
            universidad_id=escenario["uni"].id, codigo="PARAD",
            nombre="Paradigmas", external_ref="uuid-VIEJO", activa=True,
        ))
        await escenario["db"].flush()

        with pytest.raises(cfg.Aborta, match="distinto del que"):
            await cfg._resolver_materia(
                escenario["db"], escenario["uni"],
                external_ref="uuid-NUEVO", codigo="PARAD",
                nombre="Paradigmas", aplicar=True,
            )


class TestDryRun:
    """Un dry-run que deja algo escrito no es un dry-run."""

    @pytest.mark.asyncio
    async def test_no_crea_la_materia(self, escenario):
        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=False,
        )
        assert materia is None

        res = await escenario["db"].execute(select(Materia))
        assert res.scalars().all() == []

    @pytest.mark.asyncio
    async def test_no_vincula_al_coordinador(self, escenario):
        escenario["db"].add(Materia(
            universidad_id=escenario["uni"].id, codigo="PARAD",
            nombre="Paradigmas", external_ref="uuid-1", activa=True,
        ))
        await escenario["db"].flush()
        res = await escenario["db"].execute(select(Materia))
        materia = res.scalar_one()

        await cfg._vincular_coordinador(
            escenario["db"], escenario["usuario"], materia, aplicar=False
        )

        res = await escenario["db"].execute(select(CoordinadorMateria))
        assert res.scalars().all() == []

    @pytest.mark.asyncio
    async def test_no_crea_la_comision_ni_apunta_la_materia(self, escenario):
        escenario["db"].add(Materia(
            universidad_id=escenario["uni"].id, codigo="PARAD",
            nombre="Paradigmas", external_ref="uuid-1", activa=True,
        ))
        await escenario["db"].flush()
        res = await escenario["db"].execute(select(Materia))
        materia = res.scalar_one()

        await cfg._asegurar_comision_integracion(
            escenario["db"], materia,
            nombre_comision="Integración AI-Native", anio=2026, aplicar=False,
        )

        res = await escenario["db"].execute(select(Comision))
        assert res.scalars().all() == []
        assert materia.comision_integracion_id is None


class TestAplicar:
    """Los cuatro eslabones, cada uno con el error que evita."""

    @pytest.mark.asyncio
    async def test_crea_la_materia_con_el_external_ref(self, escenario):
        """Sin esto, su PUT de trabajos prácticos devuelve 404."""
        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=True,
        )

        assert materia is not None
        assert materia.external_ref == "uuid-1"
        assert materia.universidad_id == escenario["uni"].id

    @pytest.mark.asyncio
    async def test_completa_el_ref_de_una_materia_que_ya_existia(self, escenario):
        """El caso normal si la materia vino de Moodle.

        Crear una segunda materia duplicaría la misma cursada, y el docente
        terminaría viendo dos.
        """
        escenario["db"].add(Materia(
            universidad_id=escenario["uni"].id, codigo="PARAD",
            nombre="Paradigmas", external_ref=None, activa=True,
        ))
        await escenario["db"].flush()

        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=True,
        )

        res = await escenario["db"].execute(select(Materia))
        assert len(res.scalars().all()) == 1
        assert materia.external_ref == "uuid-1"

    @pytest.mark.asyncio
    async def test_vincula_al_coordinador(self, escenario):
        """Sin esta fila, el rol COORDINADOR recibe 403 en todos los endpoints."""
        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=True,
        )
        await cfg._vincular_coordinador(
            escenario["db"], escenario["usuario"], materia, aplicar=True
        )

        res = await escenario["db"].execute(select(CoordinadorMateria))
        vinculos = res.scalars().all()
        assert len(vinculos) == 1
        assert vinculos[0].coordinador_id == escenario["usuario"].id

    @pytest.mark.asyncio
    async def test_crea_la_comision_y_deja_la_materia_apuntando(self, escenario):
        """Sin esto, TODA corrección de AI-Native devuelve 409."""
        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=True,
        )
        comision = await cfg._asegurar_comision_integracion(
            escenario["db"], materia,
            nombre_comision="Integración AI-Native", anio=2026, aplicar=True,
        )

        assert comision is not None
        assert comision.materia_id == materia.id
        assert comision.universidad_id == escenario["uni"].id
        assert materia.comision_integracion_id == comision.id


class TestIdempotencia:
    """Correrlo dos veces tiene que dar lo mismo que correrlo una.

    Va a pasar: el operador lo corre, algo falla más adelante, y lo vuelve a
    correr. Si la segunda vez duplica la comisión, las entregas quedan repartidas
    entre dos y nadie entiende por qué faltan la mitad.
    """

    @pytest.mark.asyncio
    async def test_dos_corridas_no_duplican_nada(self, escenario):
        for _ in range(2):
            materia = await cfg._resolver_materia(
                escenario["db"], escenario["uni"],
                external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
                aplicar=True,
            )
            await cfg._vincular_coordinador(
                escenario["db"], escenario["usuario"], materia, aplicar=True
            )
            await cfg._asegurar_comision_integracion(
                escenario["db"], materia,
                nombre_comision="Integración AI-Native", anio=2026, aplicar=True,
            )

        res = await escenario["db"].execute(select(Materia))
        assert len(res.scalars().all()) == 1
        res = await escenario["db"].execute(select(Comision))
        assert len(res.scalars().all()) == 1
        res = await escenario["db"].execute(select(CoordinadorMateria))
        assert len(res.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_reapunta_si_la_comision_quedo_colgada(self, escenario):
        """`comision_integracion_id` apuntando a una comisión dada de baja."""
        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=True,
        )
        muerta = Comision(
            materia_id=materia.id, universidad_id=escenario["uni"].id,
            nombre="Vieja", anio=2025, activa=False,
        )
        escenario["db"].add(muerta)
        await escenario["db"].flush()
        materia.comision_integracion_id = muerta.id
        await escenario["db"].flush()

        comision = await cfg._asegurar_comision_integracion(
            escenario["db"], materia,
            nombre_comision="Integración AI-Native", anio=2026, aplicar=True,
        )

        assert comision.id != muerta.id
        assert materia.comision_integracion_id == comision.id


class TestVerificacion:
    """El `--verificar` relee de la base; no confía en lo que acaba de escribir."""

    @pytest.mark.asyncio
    async def test_sin_configurar_da_falso(self, escenario):
        assert await cfg._verificar(
            escenario["db"], escenario["uni"], escenario["usuario"]
        ) is False

    @pytest.mark.asyncio
    async def test_configurado_completo_da_verdadero(self, escenario):
        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=True,
        )
        await cfg._vincular_coordinador(
            escenario["db"], escenario["usuario"], materia, aplicar=True
        )
        await cfg._asegurar_comision_integracion(
            escenario["db"], materia,
            nombre_comision="Integración AI-Native", anio=2026, aplicar=True,
        )

        assert await cfg._verificar(
            escenario["db"], escenario["uni"], escenario["usuario"]
        ) is True

    @pytest.mark.asyncio
    async def test_materia_sin_comision_da_falso(self, escenario):
        """Publicar sí, corregir no: el 409 que hay que detectar ANTES."""
        materia = await cfg._resolver_materia(
            escenario["db"], escenario["uni"],
            external_ref="uuid-1", codigo="PARAD", nombre="Paradigmas",
            aplicar=True,
        )
        await cfg._vincular_coordinador(
            escenario["db"], escenario["usuario"], materia, aplicar=True
        )

        assert await cfg._verificar(
            escenario["db"], escenario["uni"], escenario["usuario"]
        ) is False
