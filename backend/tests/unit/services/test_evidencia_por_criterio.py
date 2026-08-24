"""
motor-anti-falsos-positivos, bloque 2: evidencia citable por criterio.

**Por qué esto es el corazón del change.** Los bugs 4 y 5 son el mismo mecanismo:
el criterio se cierra por reconocimiento léxico, no por verificación.

- 100/100 a una entrega con "3 categorías OK" y "10 productos OK" donde ningún
  producto quedaba vinculado a ninguna categoría — *vio* las piezas.
- Puntaje completo a una "búsqueda" que era `if puntajes[i] == 990` — *leyó* una
  búsqueda.

Hoy nada obliga al motor a decir DÓNDE vio lo que dice que vio, así que afirmarlo
no tiene costo. Pedir la cita textual se lo pone: es mucho más difícil inventar
una línea de código que exista literalmente en la entrega que afirmar que el
vínculo está.

Este bloque agrega el campo al contrato en los dos sentidos (lo que se le pide al
modelo y lo que se parsea de vuelta). La VERIFICACIÓN de que la cita exista de
verdad es el bloque 3.

El campo es opcional en todo el camino: las correcciones viejas no lo tienen y
tienen que seguir leyéndose sin romper.
"""

import pytest

from app.schemas.correccion import (
    CriterioEvaluado,
    CriterioGeminiSchema,
    GeminiResponse,
    SubcriterioEvaluado,
    SubcriterioGeminiSchema,
)


def _criterio_gemini(**over):
    base = {
        "id": "C1",
        "nombre": "Excepción propia verificada",
        "puntaje_obtenido": 20,
        "puntaje_maximo": 20,
        "estado": "OK",
        "feedback": "Cumple.",
    }
    base.update(over)
    return base


def _respuesta_gemini(criterios):
    return {
        "nota": 100,
        "criterios": criterios,
        "fortalezas": ["a"],
        "recomendaciones": ["b"],
        "comentario_general": "ok",
    }


class TestContratoDeParseo:
    def test_criterio_de_la_ia_acepta_evidencia(self):
        c = CriterioGeminiSchema(
            **_criterio_gemini(evidencia="class CupoExcedidoException extends Exception {")
        )
        assert c.evidencia == "class CupoExcedidoException extends Exception {"

    def test_criterio_de_la_ia_sin_evidencia_parsea_igual(self):
        """Correcciones viejas y modelos que omitan el campo no pueden romper."""
        c = CriterioGeminiSchema(**_criterio_gemini())
        assert c.evidencia is None

    def test_subcriterio_de_la_ia_acepta_evidencia(self):
        s = SubcriterioGeminiSchema(
            id="C1.1",
            puntaje_obtenido=10,
            puntaje_maximo=10,
            estado="OK",
            feedback="ok",
            evidencia="throw new CupoExcedidoException();",
        )
        assert s.evidencia == "throw new CupoExcedidoException();"

    def test_subcriterio_de_la_ia_sin_evidencia_parsea_igual(self):
        s = SubcriterioGeminiSchema(
            id="C1.1", puntaje_obtenido=10, puntaje_maximo=10, estado="OK", feedback="ok"
        )
        assert s.evidencia is None

    def test_respuesta_completa_con_evidencia_parsea(self):
        r = GeminiResponse(
            **_respuesta_gemini([_criterio_gemini(evidencia="int x = buscar(lista);")])
        )
        assert r.criterios[0].evidencia == "int x = buscar(lista);"

    def test_respuesta_completa_sin_evidencia_parsea(self):
        """Caracterización: el camino de hoy sigue funcionando idéntico."""
        r = GeminiResponse(**_respuesta_gemini([_criterio_gemini()]))
        assert r.criterios[0].evidencia is None


class TestContratoDePersistencia:
    def test_criterio_evaluado_acepta_evidencia(self):
        c = CriterioEvaluado(
            id="C1",
            nombre="Criterio",
            puntaje_obtenido=20,
            puntaje_maximo=20,
            estado="OK",
            feedback="ok",
            evidencia="if (cupo == 0) throw ...",
        )
        assert c.evidencia == "if (cupo == 0) throw ..."

    def test_criterio_evaluado_sin_evidencia_es_valido(self):
        c = CriterioEvaluado(
            id="C1", nombre="C", puntaje_obtenido=20, puntaje_maximo=20,
            estado="OK", feedback="ok",
        )
        assert c.evidencia is None

    def test_subcriterio_evaluado_acepta_evidencia(self):
        s = SubcriterioEvaluado(
            id="C1.1", puntaje_obtenido=10, puntaje_maximo=10,
            estado="OK", feedback="ok", evidencia="throw new X();",
        )
        assert s.evidencia == "throw new X();"


class TestResponseSchemasDelProveedor:
    """Los cuatro esquemas que se le mandan al modelo tienen que pedirla."""

    @pytest.mark.parametrize(
        "nombre_schema",
        [
            "_SCHEMA_CORRECCION_CODIGO",
            "_SCHEMA_CORRECCION_PDF",
            "_SCHEMA_CORRECCION_CODIGO_V2",
            "_SCHEMA_CORRECCION_PDF_V2",
        ],
    )
    def test_el_criterio_del_schema_pide_evidencia(self, nombre_schema):
        import app.integrations.gemini_correction_client as cli

        schema = getattr(cli, nombre_schema)
        criterio = schema["properties"]["criterios"]["items"]["properties"]
        assert "evidencia" in criterio

    @pytest.mark.parametrize(
        "nombre_schema", ["_SCHEMA_CORRECCION_CODIGO_V2", "_SCHEMA_CORRECCION_PDF_V2"]
    )
    def test_el_subcriterio_v2_tambien_pide_evidencia(self, nombre_schema):
        import app.integrations.gemini_correction_client as cli

        schema = getattr(cli, nombre_schema)
        criterio = schema["properties"]["criterios"]["items"]["properties"]
        sub = criterio["subcriterios_evaluados"]["items"]["properties"]
        assert "evidencia" in sub

    @pytest.mark.parametrize(
        "nombre_schema",
        [
            "_SCHEMA_CORRECCION_CODIGO",
            "_SCHEMA_CORRECCION_PDF",
            "_SCHEMA_CORRECCION_CODIGO_V2",
            "_SCHEMA_CORRECCION_PDF_V2",
        ],
    )
    def test_la_evidencia_no_es_obligatoria_en_el_schema(self, nombre_schema):
        """Exigirla rompería la corrección cuando el modelo no pueda citar —
        por ejemplo un criterio que se cierra en 0 porque no hay nada."""
        import app.integrations.gemini_correction_client as cli

        schema = getattr(cli, nombre_schema)
        requeridos = schema["properties"]["criterios"]["items"].get("required") or []
        assert "evidencia" not in requeridos


class TestInstruccionEnElPrompt:
    def test_el_prompt_pide_citar_codigo_literal(self):
        from app.integrations.gemini_correction_client import _build_evidencia_texto

        texto = _build_evidencia_texto().lower()

        assert "evidencia" in texto
        assert "literal" in texto or "textual" in texto

    def test_el_prompt_aclara_que_no_se_inventa_la_cita(self):
        from app.integrations.gemini_correction_client import _build_evidencia_texto

        texto = _build_evidencia_texto().lower()

        assert "no inventes" in texto or "no la inventes" in texto


class TestPersistencia:
    def test_la_evidencia_se_persiste_dentro_del_criterio(self):
        """Va en `criterios_json` (JSONB) — sin migración."""
        from app.services.correccion_service import _criterio_a_dict

        c = CriterioEvaluado(
            id="C1", nombre="C", puntaje_obtenido=20, puntaje_maximo=20,
            estado="OK", feedback="ok", evidencia="línea citada",
        )

        assert _criterio_a_dict(c)["evidencia"] == "línea citada"

    def test_criterio_sin_evidencia_no_ensucia_el_json(self):
        from app.services.correccion_service import _criterio_a_dict

        c = CriterioEvaluado(
            id="C1", nombre="C", puntaje_obtenido=20, puntaje_maximo=20,
            estado="OK", feedback="ok",
        )
        salida = _criterio_a_dict(c)

        assert salida.get("evidencia") is None
