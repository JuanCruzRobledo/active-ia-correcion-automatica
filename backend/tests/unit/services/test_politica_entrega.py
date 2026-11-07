"""La selección de evidencia y el tope son independientes de la IA."""

import io
import zipfile
from decimal import Decimal

import pytest

from app.services.consolidacion_service import ConsolidacionService


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_dist_no_desplaza_fuente_y_properties_se_lee():
    archive = zip_bytes({
        "tp/dist/assets/index.js": "bundle" * 60_000,
        "tp/src/api/client.js": 'fetch("/api")',
        "tp/backend/application.properties": "server.port=8080",
    })
    content, files = ConsolidacionService().consolidar_zip(io.BytesIO(archive))
    assert "bundle" not in content
    assert 'fetch("/api")' in content
    assert "tp/backend/application.properties" in files


def test_lockfiles_no_entran_y_package_json_si():
    archive = zip_bytes({"package.json": '{"name":"tp"}',
                         "package-lock.json": "lock", "pnpm-lock.yaml": "lock"})
    content, files = ConsolidacionService().consolidar_zip(io.BytesIO(archive), modo="proyecto_completo")
    assert files == ["package.json"]
    assert "lock" not in content


def test_analisis_detecta_antes_de_filtrar_y_no_penaliza_residuos():
    from app.services.politica_entrega import analizar_archivo
    archive = zip_bytes({"TP\\NODE_MODULES\\lib\\index.js": "dependency",
                         "tp/dist/index.js": "bundle", "tp/.DS_Store": "metadata",
                         "tp/__pycache__/main.pyc": "cache", "tp/src/main.js": "source"})
    result = analizar_archivo(archive, "tp.zip", ["tp/src/main.js"])
    assert result["version"] == 1
    assert result["limite_nota"] is None
    assert result["rutas_penalizables"] == ["TP/NODE_MODULES/", "tp/dist/"]
    assert len(result["archivos_ignorados"]) == 4


def test_residuos_y_nombres_parecidos_no_activan_tope():
    from app.services.politica_entrega import analizar_archivo
    archive = zip_bytes({"src/distribucion/index.js": "source", ".git/config": "git",
                         "__pycache__/x.pyc": "cache", "dist/": ""})
    result = analizar_archivo(archive, "tp.zip", ["src/distribucion/index.js"])
    assert result["limite_nota"] is None
    assert result["rutas_penalizables"] == []


def test_excepcion_explicita_permite_dist_sin_penalizar():
    from app.services.politica_entrega import analizar_archivo
    archive = zip_bytes({"tp/dist/index.js": "bundle", "src/main.js": "source"})
    content, files = ConsolidacionService().consolidar_zip(
        io.BytesIO(archive), directorios_permitidos=["dist"])
    result = analizar_archivo(archive, "tp.zip", files, ["dist"])
    assert "bundle" in content
    assert result["limite_nota"] is None


@pytest.mark.parametrize("enabled,tipo,academic,expected,limit", [
    (False, "TP", 82, 82, None),
    (False, "PARCIAL_2", 82, 82, None),
    (True, "TP", 82, 50, 50),
    (True, "TP", 35, 35, 50),
    (True, "TPI", 82, 82, None),
    (True, "PARCIAL_2", 82, 82, None),
])
def test_tope_solo_para_tp_si_se_activa(monkeypatch, enabled, tipo, academic, expected, limit):
    from app.services import politica_entrega
    analysis = {"version": 1, "rutas_penalizables": ["tp/node_modules/"], "limite_nota": 50}
    monkeypatch.setattr(politica_entrega, "APLICAR_TOPE_TP", enabled)
    result = politica_entrega.aplicar_tope(Decimal(academic), analysis, tipo)
    assert result["nota"] == Decimal(expected)
    assert result["nota_academica"] == academic
    assert result["limite_nota"] == limit
    assert result["rutas_penalizables"] == ["tp/node_modules/"]


@pytest.mark.parametrize("analysis", [None, {"version": 1, "rutas_penalizables": [], "limite_nota": None}])
def test_entregas_antiguas_y_limpias_no_reciben_tope(analysis):
    from app.services.politica_entrega import aplicar_tope
    result = aplicar_tope(Decimal(82), analysis)
    assert result["nota"] == 82
    assert result["limite_nota"] is None


def test_pdf_generado_no_se_evalua_por_fallback():
    archive = zip_bytes({"tp/DIST/reporte.pdf": b"%PDF-1.4"})
    assert ConsolidacionService().extraer_pdf_de_zip(archive) is None


def test_rutas_relativas_se_normalizan_igual_en_analisis_y_consolidado():
    from app.services.politica_entrega import analizar_archivo
    archive = zip_bytes({"./src/main.py": "print(1)"})
    content, files = ConsolidacionService().consolidar_zip(io.BytesIO(archive))
    analysis = analizar_archivo(archive, "tp.zip", files)
    assert files == ["src/main.py"]
    assert analysis["archivos_ignorados"] == []


@pytest.mark.parametrize("value", [["node_modules/"], ["src"], "dist", ["../dist"]])
def test_rubrica_rechaza_excepciones_no_validas(value):
    from app.schemas.rubrica import RubricaUpdate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RubricaUpdate(metadata_json={"politica_entrega": {"directorios_permitidos": value}})


def test_rubrica_normaliza_excepcion_y_preserva_otra_metadata():
    from app.schemas.rubrica import RubricaUpdate
    data = RubricaUpdate(metadata_json={"lenguaje": "Java", "politica_entrega": {"directorios_permitidos": ["DIST", "dist"]}})
    assert data.metadata_json["lenguaje"] == "Java"
    assert data.metadata_json["politica_entrega"]["directorios_permitidos"] == ["dist"]


@pytest.mark.parametrize("path", ["docs/informe.pdf", "./docs/informe.pdf", "docs\\informe.pdf"])
def test_pdf_anidado_conserva_ruta_normalizada_en_analisis(path):
    from app.services.politica_entrega import analizar_archivo
    data = zip_bytes({path: b"%PDF-1.4 fake"})
    payload, included = ConsolidacionService().extraer_pdf_de_zip(data)
    assert included == "docs/informe.pdf"
    analysis = analizar_archivo(data, "tp.zip", [included])
    assert analysis["archivos_ignorados"] == []
