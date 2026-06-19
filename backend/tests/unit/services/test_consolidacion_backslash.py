"""
Tests para ConsolidacionService — ZIPs con separador Windows + mensaje diagnóstico.

Bug de producción (solo Linux/Docker): un alumno arma el ZIP en Windows con una
herramienta que guarda las entradas con backslash (`carpeta\\archivo.ext`). En
Linux, `zipfile` conserva el `\` literal al leer; el servicio normalizaba el path
a `/` para mostrarlo pero luego LEÍA con ese string normalizado →
`KeyError "There is no item named '.../build.gradle' in the archive"` → 502.

En Windows (Python dev) el bug NO se reproduce porque `zipfile` normaliza el `\`
al leer. Por eso estos tests INYECTAN el estado de "clave con backslash" en un
ZipFile ya abierto (replicando la lectura de Linux) y ejercitan el helper
`_consolidar_desde_zipfile`, que debe leer vía el objeto `ZipInfo`.
"""

import io
import zipfile

import pytest
from fastapi import HTTPException

from app.services.consolidacion_service import ConsolidacionService


@pytest.fixture
def service() -> ConsolidacionService:
    return ConsolidacionService()


def _zip_bytes(entradas: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in entradas.items():
            zf.writestr(nombre, contenido)
    return buffer.getvalue()


def _abrir_con_backslash(entradas: dict[str, str]) -> zipfile.ZipFile:
    """Abre un ZIP y fuerza las claves a backslash, replicando la lectura en Linux."""
    zf = zipfile.ZipFile(io.BytesIO(_zip_bytes(entradas)), "r")
    nuevos: dict[str, zipfile.ZipInfo] = {}
    for info in zf.filelist:
        info.filename = info.filename.replace("/", "\\")
        nuevos[info.filename] = info
    zf.NameToInfo = nuevos
    return zf


class TestBackslashLinux:
    def test_helper_lee_via_zipinfo_con_backslash(self, service: ConsolidacionService):
        """Caso Malpassi: entradas con `\\` se leen e incluyen sin romper."""
        zf = _abrir_con_backslash(
            {
                "TP_SistemaGestionDePedidos/build.gradle": "plugins { id 'java' }\n",
                "TP_SistemaGestionDePedidos/src/Main.java": "class Main {}\n",
            }
        )
        extensiones = service._resolve_extensiones("proyecto_completo", None)

        contenido, archivos = service._consolidar_desde_zipfile(
            zf, extensiones, "proyecto_completo"
        )

        assert any("build.gradle" in a for a in archivos)
        assert any("Main.java" in a for a in archivos)
        assert "plugins { id 'java' }" in contenido
        assert "class Main {}" in contenido
        # los paths se muestran normalizados (sin backslash)
        assert all("\\" not in a for a in archivos)

    def test_scan_zip_devuelve_zipinfo_y_path(self, service: ConsolidacionService):
        """_scan_zip devuelve (ZipInfo, path_normalizado) para leer por objeto."""
        zf = zipfile.ZipFile(io.BytesIO(_zip_bytes({"src/main.py": "x = 1\n"})), "r")
        extensiones = service._resolve_extensiones("solo_codigo", None)

        resultado = service._scan_zip(zf, extensiones)

        assert len(resultado) == 1
        info, path = resultado[0]
        assert isinstance(info, zipfile.ZipInfo)
        assert path == "src/main.py"


class TestMensajeDiagnostico:
    def test_sin_archivos_validos_lista_lo_encontrado(self, service: ConsolidacionService):
        """Caso Sabina: ZIP sin código → 400 que indica qué SÍ había (diagnóstico)."""
        zip_obj = io.BytesIO(_zip_bytes({"informe.pdf": "x", "captura.png": "y"}))

        with pytest.raises(HTTPException) as exc:
            service.consolidar_zip(zip_obj, modo="solo_codigo")

        assert exc.value.status_code == 400
        # el mensaje debe ayudar a diagnosticar: menciona las extensiones presentes
        detalle = exc.value.detail.lower()
        assert ".pdf" in detalle or ".png" in detalle


class TestNoRegresion:
    """El comportamiento normal (sin backslash) no cambia."""

    def test_solo_codigo_excluye_no_codigo(self, service: ConsolidacionService):
        zip_obj = io.BytesIO(
            _zip_bytes(
                {
                    "main.py": "print('hello')\n",
                    "README.md": "readme",
                    "data.json": "{}",
                }
            )
        )
        contenido, archivos = service.consolidar_zip(zip_obj, modo="solo_codigo")
        assert "main.py" in archivos
        assert "README.md" not in archivos
        assert "print('hello')" in contenido

    def test_estructura_directorios(self, service: ConsolidacionService):
        zip_obj = io.BytesIO(
            _zip_bytes(
                {"src/main.py": "a = 1\n", "src/utils/helper.py": "b = 2\n"}
            )
        )
        contenido, archivos = service.consolidar_zip(zip_obj, modo="solo_codigo")
        assert "src/main.py" in archivos
        assert "src/utils/helper.py" in archivos
        assert "a = 1" in contenido and "b = 2" in contenido
