"""
Tests de dedup_ultimo_intento (item #3, causa raíz del "detecta el primer archivo").

Moodle devuelve un registro de submission por intento (attemptnumber). Si un alumno
reentrega, hay que quedarse con el intento MÁS RECIENTE (mayor attemptnumber; desempate
por timemodified), no con el primero.
"""

from app.services.moodle_service import MoodleSubmission, dedup_ultimo_intento


def _sub(userid, attempt, tm, files=("a.py",)):
    return MoodleSubmission(
        userid=userid,
        status="submitted",
        gradingstatus="notgraded",
        timemodified=tm,
        attemptnumber=attempt,
        files=list(files),
    )


def test_se_queda_con_el_mayor_attemptnumber():
    subs = [_sub(1, 0, 100, files=("viejo.py",)), _sub(1, 1, 200, files=("nuevo.py",))]
    res = dedup_ultimo_intento(subs)
    assert len(res) == 1
    assert res[0].attemptnumber == 1
    assert res[0].files == ["nuevo.py"]


def test_desempata_por_timemodified_si_igual_attempt():
    subs = [_sub(1, 0, 100), _sub(1, 0, 300)]
    res = dedup_ultimo_intento(subs)
    assert len(res) == 1
    assert res[0].timemodified == 300


def test_usuarios_distintos_se_conservan():
    subs = [_sub(1, 0, 100), _sub(2, 0, 100)]
    res = dedup_ultimo_intento(subs)
    assert {s.userid for s in res} == {1, 2}


def test_orden_de_entrada_no_importa():
    # El intento nuevo viene PRIMERO en la lista (el bug agarraba este orden mal).
    subs = [_sub(1, 1, 200, files=("nuevo.py",)), _sub(1, 0, 100, files=("viejo.py",))]
    res = dedup_ultimo_intento(subs)
    assert len(res) == 1
    assert res[0].attemptnumber == 1


def test_lista_vacia():
    assert dedup_ultimo_intento([]) == []
