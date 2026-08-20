"""Las escalas de Moodle se resuelven POR CAMPUS, no globalmente.

**El bug que esto cierra.** `MOODLE_SCALE_MAP` era un diccionario global
indexado solo por `scale_id`, cargado en Fase 0 con la escala de TUPaD. Pero los
`scale_id` son **por instancia de Moodle**, y `Universidad.moodle_host` confirma
que cada universidad tiene la suya. Verificado el 2026-08-20 en los dos campus:

    tup.sied.utn.edu.ar        scale_id=5  →  Aprobado (1), Desaprobado (2)
    campustest.frm.utn.edu.ar  scale_id=5  →  No satisfactorio (1),
                                              Satisfactorio (2),
                                              Supera lo esperado (3)

El mismo número, dos escalas incompatibles. Con el mapa global, un TP de FRM
calificado contra la escala 5 mandaba **índice 1 para el que aprobaba**, que en
ese campus es "No satisfactorio". Invertido y en silencio.

Y lo peor: **el guard no saltaba**, porque el 5 SÍ estaba en el mapa. El error
que reportó el tutor (scale_id=3 no mapeada) era el guard funcionando bien; la
escala 5 era el caso donde no podía funcionar.

`moodle_host` es obligatorio a propósito: con un default, un call site que se
olvide de pasarlo volvería a resolver contra un mapa que no le corresponde, que
es exactamente el bug.
"""

import pytest

from app.core.moodle_config import escala_de, normalizar_host
from app.services.moodle_grade_service import GradeMapError, MoodleGradeService
from app.services.moodle_service import AssignmentGradeConfig

TUPAD = "https://tup.sied.utn.edu.ar"
FRM = "https://campustest.frm.utn.edu.ar"


def _escala(scale_id: int):
    return AssignmentGradeConfig(instance_id=478, tipo="escala", scale_id=scale_id)


class TestTupadNoCambia:
    """Red de seguridad: la universidad que ya funcionaba tiene que seguir igual."""

    @pytest.mark.parametrize(
        "nota,indice_esperado", [(100, 1.0), (60, 1.0), (59, 2.0), (0, 2.0)]
    )
    def test_tp_de_tupad_mapea_exactamente_como_antes(self, nota, indice_esperado):
        grade = MoodleGradeService._mapear_nota(
            "TP", nota, _escala(5), moodle_host=TUPAD
        )
        assert grade == indice_esperado

    def test_el_texto_de_la_nota_de_tupad_sale_de_su_propia_escala(self):
        texto = MoodleGradeService._nota_texto(1.0, _escala(5), moodle_host=TUPAD)
        assert texto == "Aprobado"


class TestFrmDesbloqueado:
    """La escala 3 de FRM: Aprobado (1), Desaprobado (2)."""

    @pytest.mark.parametrize(
        "nota,indice_esperado", [(100, 1.0), (60, 1.0), (59, 2.0), (0, 2.0)]
    )
    def test_tp_de_frm_mapea_con_su_escala_3(self, nota, indice_esperado):
        grade = MoodleGradeService._mapear_nota(
            "TP", nota, _escala(3), moodle_host=FRM
        )
        assert grade == indice_esperado

    def test_el_texto_de_la_nota_de_frm_sale_de_su_propia_escala(self):
        texto = MoodleGradeService._nota_texto(1.0, _escala(3), moodle_host=FRM)
        assert texto == "Aprobado"


class TestLaMinaDesarmada:
    """El caso que calificaba invertido y nadie veía."""

    def test_la_escala_5_de_frm_no_se_califica_con_el_mapa_de_tupad(self):
        with pytest.raises(GradeMapError) as exc:
            MoodleGradeService._mapear_nota("TP", 85, _escala(5), moodle_host=FRM)

        # El mensaje tiene que nombrar el campus: quien configure necesita saber
        # DÓNDE mirar la escala, no solo que falta.
        assert "campustest.frm.utn.edu.ar" in str(exc.value)

    def test_la_escala_3_de_tupad_tampoco_se_califica_con_el_mapa_de_frm(self):
        """Simétrico: la contaminación no puede ir en ninguna dirección."""
        with pytest.raises(GradeMapError):
            MoodleGradeService._mapear_nota("TP", 85, _escala(3), moodle_host=TUPAD)

    def test_un_campus_desconocido_no_califica_nada(self):
        with pytest.raises(GradeMapError):
            MoodleGradeService._mapear_nota(
                "TP", 85, _escala(5), moodle_host="https://otro.campus.edu.ar"
            )

    def test_host_vacio_no_califica_nada(self):
        with pytest.raises(GradeMapError):
            MoodleGradeService._mapear_nota("TP", 85, _escala(5), moodle_host="")


class TestNormalizacionDelHost:
    """El host viene de la base y puede tener variaciones inofensivas."""

    @pytest.mark.parametrize(
        "host",
        [
            "https://tup.sied.utn.edu.ar",
            "https://tup.sied.utn.edu.ar/",
            "http://tup.sied.utn.edu.ar",
            "tup.sied.utn.edu.ar",
            "  https://TUP.SIED.UTN.EDU.AR/  ",
        ],
    )
    def test_variaciones_del_mismo_host_resuelven_igual(self, host):
        assert normalizar_host(host) == "tup.sied.utn.edu.ar"
        assert escala_de(host, 5) is not None

    def test_dos_campus_distintos_no_colisionan(self):
        assert escala_de(TUPAD, 5) is not None
        assert escala_de(FRM, 5) is None
        assert escala_de(FRM, 3) is not None
        assert escala_de(TUPAD, 3) is None
