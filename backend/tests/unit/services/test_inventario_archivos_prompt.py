"""
motor-anti-falsos-positivos, bloque 1: el inventario de archivos llega al motor.

**El bug 1 del pedido de AI-Native, con víctima concreta.** El 2026-08-04 el
motor descontó puntos por archivos que SÍ estaban en la entrega y dejó a una
alumna desaprobada (materia 22, rúbrica 188).

La causa es de una línea: `Entrega.archivos_incluidos` existe en la base, se
puebla en la consolidación (`entrega_service.py:171,331,445,1124`) y se expone en
la API (`schemas/entrega.py:284`) — pero **nunca llegaba al prompt**. `grep
archivos_incluidos` sobre `correccion_service.py` y `app/integrations/` daba
CERO. El modelo recibía un blob de texto concatenado y tenía que inferir qué
había entregado el alumno.

Y cuando además el código venía recortado por `_truncar_codigo` (IA-015), veía
literalmente menos de lo que había, sin ninguna señal estructurada de que faltaba
algo: el marcador de corte va DENTRO del propio blob, mezclado con el código.

Dos datos, entonces:

1. **El inventario**: qué archivos entregó el alumno, como hecho, no como
   inferencia. Con la regla dura de que nada listado ahí puede considerarse
   ausente.
2. **El truncado**: si el código está incompleto y en qué medida, en un campo
   propio, para que el motor no lea una ausencia donde hay un corte.
"""

from types import SimpleNamespace

import pytest

from app.services.correccion_service import CorreccionService, _truncar_codigo


def _entrega(**over):
    base = SimpleNamespace(
        id=1,
        alumno_nombre="Alumna Test",
        archivo_nombre="entrega.zip",
        archivo_tipo="zip",
        archivos_incluidos=["Main.java", "Evento.java", "CupoExcedidoException.java"],
        contenido_consolidado="class Main {}",
        contenido_preview=None,
        pdf_contenido_b64=None,
        comision=SimpleNamespace(materia=SimpleNamespace(nombre="Programación 2")),
    )
    for k, v in over.items():
        setattr(base, k, v)
    return base


def _rubrica(**over):
    base = SimpleNamespace(
        titulo="TP2",
        descripcion="Evalúa POO",
        tipo=SimpleNamespace(value="TP"),
        puntaje_maximo=100,
        metadata_json={},
        criterios_json=[],
        penalizaciones_json=[],
        condiciones_desaprobacion_json=[],
        schema_version=1,
    )
    for k, v in over.items():
        setattr(base, k, v)
    return base


def _payload(entrega=None, rubrica=None):
    svc = CorreccionService.__new__(CorreccionService)
    return svc._build_correction_payload(
        entrega or _entrega(), rubrica or _rubrica(), "api-key-falsa"
    )


class TestInventarioEnElPayload:
    def test_el_payload_incluye_los_archivos_consolidados(self):
        payload = _payload()

        assert payload["entrega"]["archivos_incluidos"] == [
            "Main.java",
            "Evento.java",
            "CupoExcedidoException.java",
        ]

    def test_el_payload_incluye_nombre_y_tipo_del_archivo_original(self):
        payload = _payload()

        assert payload["entrega"]["archivo_nombre"] == "entrega.zip"
        assert payload["entrega"]["archivo_tipo"] == "zip"

    def test_entrega_sin_archivos_consolidados_cae_al_nombre_del_archivo(self):
        """Entrega de archivo único: el inventario no puede quedar vacío."""
        payload = _payload(_entrega(archivos_incluidos=None))

        assert payload["entrega"]["archivos_incluidos"] == ["entrega.zip"]

    def test_lista_vacia_tambien_cae_al_nombre_del_archivo(self):
        payload = _payload(_entrega(archivos_incluidos=[]))

        assert payload["entrega"]["archivos_incluidos"] == ["entrega.zip"]


class TestEstadoDeTruncado:
    def test_codigo_completo_se_informa_como_no_truncado(self):
        payload = _payload(_entrega(contenido_consolidado="class Main {}"))

        assert payload["entrega"]["codigo_truncado"] is False

    def test_codigo_truncado_se_informa_con_los_dos_tamanios(self):
        # Por encima de MAX_CODIGO_CORRECCION_CHARS (200_000). Justo EN el limite
        # no trunca (`<= limite`), asi que hay que pasarse de verdad.
        largo = "x" * 250_000
        payload = _payload(_entrega(contenido_consolidado=largo))

        entrega_info = payload["entrega"]
        assert entrega_info["codigo_truncado"] is True
        assert entrega_info["caracteres_originales"] == 250_000
        assert entrega_info["caracteres_enviados"] < 250_000

    def test_truncar_codigo_devuelve_el_estado_ademas_del_texto(self):
        """El marcador de corte va dentro del blob; el estado, aparte."""
        recortado, truncado, originales = _truncar_codigo("x" * 500, 100)

        assert truncado is True
        assert originales == 500
        assert recortado.startswith("x" * 100)
        assert "truncado" in recortado

    def test_truncar_codigo_no_toca_lo_que_entra_en_el_limite(self):
        recortado, truncado, originales = _truncar_codigo("hola", 100)

        assert recortado == "hola"
        assert truncado is False
        assert originales == 4

    def test_truncar_codigo_tolera_none(self):
        recortado, truncado, originales = _truncar_codigo(None, 100)

        assert recortado is None
        assert truncado is False
        assert originales == 0


class TestPayloadDePdf:
    def test_el_camino_pdf_tambien_lleva_inventario(self):
        svc = CorreccionService.__new__(CorreccionService)
        entrega = _entrega(pdf_contenido_b64="JVBERi0=", archivo_tipo="pdf",
                           archivo_nombre="entrega.pdf", archivos_incluidos=None)

        payload = svc._build_pdf_correction_payload(entrega, _rubrica(), "api-key-falsa")

        assert payload["entrega"]["archivos_incluidos"] == ["entrega.pdf"]
        assert payload["entrega"]["archivo_tipo"] == "pdf"


class TestSeccionDelPrompt:
    """La regla dura: nada listado en el inventario puede darse por ausente."""

    def test_el_prompt_lista_los_archivos_entregados(self):
        from app.integrations.gemini_correction_client import _build_inventario_texto

        texto = _build_inventario_texto(
            {
                "archivos_incluidos": ["Main.java", "Evento.java"],
                "archivo_nombre": "entrega.zip",
                "archivo_tipo": "zip",
                "codigo_truncado": False,
            }
        )

        assert "Main.java" in texto
        assert "Evento.java" in texto

    def test_el_prompt_prohibe_descontar_por_archivos_listados(self):
        from app.integrations.gemini_correction_client import _build_inventario_texto

        texto = _build_inventario_texto(
            {"archivos_incluidos": ["Main.java"], "codigo_truncado": False}
        ).lower()

        assert "no descuentes" in texto
        assert "ausente" in texto

    def test_el_prompt_advierte_cuando_el_codigo_viene_recortado(self):
        from app.integrations.gemini_correction_client import _build_inventario_texto

        texto = _build_inventario_texto(
            {
                "archivos_incluidos": ["Main.java"],
                "codigo_truncado": True,
                "caracteres_originales": 200_000,
                "caracteres_enviados": 120_000,
            }
        ).lower()

        assert "incompleto" in texto or "truncad" in texto

    def test_sin_truncado_no_aparece_la_advertencia(self):
        from app.integrations.gemini_correction_client import _build_inventario_texto

        texto = _build_inventario_texto(
            {"archivos_incluidos": ["Main.java"], "codigo_truncado": False}
        ).lower()

        assert "incompleto" not in texto

    def test_sin_inventario_la_seccion_no_se_arma(self):
        """Correcciones viejas o payloads sin el bloque: no debe romper."""
        from app.integrations.gemini_correction_client import _build_inventario_texto

        assert _build_inventario_texto(None) == ""
        assert _build_inventario_texto({}) == ""


class TestDegradacionSinDatos:
    """Sin con que armar el inventario, se omite — nunca se manda basura.

    Un inventario con `None` adentro seria peor que no tenerlo: el motor lo
    leeria como un archivo llamado "None" y el bug 1 volveria por otra puerta.
    """

    def test_entrega_sin_archivo_nombre_no_arma_inventario(self):
        payload = _payload(_entrega(archivos_incluidos=None, archivo_nombre=None))

        assert payload["entrega"]["archivos_incluidos"] == []

    def test_y_esa_seccion_del_prompt_queda_vacia(self):
        from app.integrations.gemini_correction_client import _build_inventario_texto

        payload = _payload(_entrega(archivos_incluidos=None, archivo_nombre=None))

        assert _build_inventario_texto(payload["entrega"]) == ""

    def test_ningun_nombre_nulo_se_cuela_en_la_lista(self):
        payload = _payload(_entrega(archivos_incluidos=None, archivo_nombre=None))

        assert None not in payload["entrega"]["archivos_incluidos"]
