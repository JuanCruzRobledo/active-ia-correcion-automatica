"""Unit tests for MoodleService.get_token."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.moodle_service import MoodleService, MoodleAuthError, MoodleConnectionError


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def service(db):
    svc = MoodleService(db)
    # Clear token cache between tests
    svc._token_cache.clear()
    return svc


@pytest.mark.asyncio
async def test_get_token_success(service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.moodle_service.decrypt_api_key", return_value="password"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        token = await service.get_token(
            user_id=1,
            moodle_host="https://moodle.example.com",
            username="user",
            password_encrypted="encrypted",
        )

    assert token == "abc123"
    assert 1 in service._token_cache


@pytest.mark.asyncio
async def test_get_token_uses_cache(service):
    future = datetime.utcnow() + timedelta(minutes=30)
    service._token_cache[1] = ("cached_token", future)

    with patch("app.services.moodle_service.decrypt_api_key") as mock_decrypt:
        token = await service.get_token(
            user_id=1,
            moodle_host="https://moodle.example.com",
            username="user",
            password_encrypted="encrypted",
        )
        mock_decrypt.assert_not_called()

    assert token == "cached_token"


@pytest.mark.asyncio
async def test_get_token_invalid_login_raises_auth_error(service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "Invalid login, please try again"}
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.moodle_service.decrypt_api_key", return_value="wrongpassword"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(MoodleAuthError):
            await service.get_token(
                user_id=2,
                moodle_host="https://moodle.example.com",
                username="user",
                password_encrypted="encrypted",
            )


@pytest.mark.asyncio
async def test_get_token_timeout_raises_connection_error(service):
    import httpx

    with patch("app.services.moodle_service.decrypt_api_key", return_value="password"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(MoodleConnectionError):
            await service.get_token(
                user_id=3,
                moodle_host="https://moodle.example.com",
                username="user",
                password_encrypted="encrypted",
            )


# =========================================================================
# get_submissions_with_files (Fase 2 — importación de entregas desde Moodle)
# =========================================================================

# Estructura real confirmada en Fase 0 contra tup.sied.utn.edu.ar:
# una submission expone los archivos en plugins[type=file].fileareas[].files[].fileurl
def _submissions_payload(submissions: list[dict]) -> dict:
    return {"assignments": [{"assignmentid": 478, "submissions": submissions}]}


def _file_plugin(filename: str, fileurl: str, filesize: int = 100, mimetype: str = "application/zip") -> dict:
    return {
        "type": "file",
        "fileareas": [
            {"area": "submission_files", "files": [
                {"filename": filename, "fileurl": fileurl, "filesize": filesize, "mimetype": mimetype}
            ]}
        ],
    }


@pytest.mark.asyncio
async def test_get_submissions_with_files_extracts_fileurls(service):
    payload = _submissions_payload([
        {
            "userid": 101, "status": "submitted", "gradingstatus": "notgraded",
            "timemodified": 1700000000, "attemptnumber": 0,
            "plugins": [
                {"type": "onlinetext", "fileareas": []},
                _file_plugin("tp.zip", "https://m/pluginfile.php/1/assignsubmission_file/x/tp.zip"),
            ],
        },
    ])
    with patch.object(service, "_fetch_submissions", AsyncMock(return_value=payload)),          patch.object(service, "_fetch_grades_map", AsyncMock(return_value={})):
        subs = await service.get_submissions_with_files(
            token="t", moodle_host="https://m", assignment_instance_id=478,
            group_member_ids={101},
        )

    assert len(subs) == 1
    assert subs[0].userid == 101
    assert subs[0].timemodified == 1700000000
    assert len(subs[0].files) == 1
    assert subs[0].files[0].filename == "tp.zip"
    assert subs[0].files[0].fileurl.endswith("/tp.zip")


@pytest.mark.asyncio
async def test_get_submissions_with_files_filters_by_group(service):
    payload = _submissions_payload([
        {"userid": 101, "status": "submitted", "gradingstatus": "notgraded",
         "timemodified": 1, "attemptnumber": 0,
         "plugins": [_file_plugin("a.zip", "https://m/a.zip")]},
        {"userid": 999, "status": "submitted", "gradingstatus": "notgraded",
         "timemodified": 1, "attemptnumber": 0,
         "plugins": [_file_plugin("b.zip", "https://m/b.zip")]},
    ])
    with patch.object(service, "_fetch_submissions", AsyncMock(return_value=payload)),          patch.object(service, "_fetch_grades_map", AsyncMock(return_value={})):
        subs = await service.get_submissions_with_files(
            token="t", moodle_host="https://m", assignment_instance_id=478,
            group_member_ids={101},  # 999 no pertenece al grupo
        )

    assert [s.userid for s in subs] == [101]


@pytest.mark.asyncio
async def test_get_submissions_with_files_skips_non_submitted(service):
    payload = _submissions_payload([
        {"userid": 101, "status": "draft", "gradingstatus": "notgraded",
         "timemodified": 1, "attemptnumber": 0,
         "plugins": [_file_plugin("a.zip", "https://m/a.zip")]},
        {"userid": 102, "status": "new", "gradingstatus": "notgraded",
         "timemodified": 1, "attemptnumber": 0, "plugins": []},
    ])
    with patch.object(service, "_fetch_submissions", AsyncMock(return_value=payload)),          patch.object(service, "_fetch_grades_map", AsyncMock(return_value={})):
        subs = await service.get_submissions_with_files(
            token="t", moodle_host="https://m", assignment_instance_id=478,
            group_member_ids={101, 102},
        )

    assert subs == []


@pytest.mark.asyncio
async def test_get_submissions_with_files_excluye_ya_corregidas(service):
    # 101 sin calificar → pendiente; 102 corregida (grade posterior a la entrega) → excluida
    payload = _submissions_payload([
        {"userid": 101, "status": "submitted", "gradingstatus": "notgraded",
         "timemodified": 100, "attemptnumber": 0,
         "plugins": [_file_plugin("a.zip", "https://m/a.zip")]},
        {"userid": 102, "status": "submitted", "gradingstatus": "graded",
         "timemodified": 100, "attemptnumber": 0,
         "plugins": [_file_plugin("b.zip", "https://m/b.zip")]},
    ])
    with patch.object(service, "_fetch_submissions", AsyncMock(return_value=payload)), patch.object(service, "_fetch_grades_map", AsyncMock(return_value={102: 200})):
        subs = await service.get_submissions_with_files(
            token="t", moodle_host="https://m", assignment_instance_id=478,
            group_member_ids={101, 102},
        )

    assert [s.userid for s in subs] == [101]


@pytest.mark.asyncio
async def test_get_submissions_with_files_incluye_reentrega(service):
    # Corregida pero re-entregada después (sub_tm 300 > grade_tm 200) → vuelve a "espera"
    payload = _submissions_payload([
        {"userid": 102, "status": "submitted", "gradingstatus": "graded",
         "timemodified": 300, "attemptnumber": 1,
         "plugins": [_file_plugin("b.zip", "https://m/b.zip")]},
    ])
    with patch.object(service, "_fetch_submissions", AsyncMock(return_value=payload)), patch.object(service, "_fetch_grades_map", AsyncMock(return_value={102: 200})):
        subs = await service.get_submissions_with_files(
            token="t", moodle_host="https://m", assignment_instance_id=478,
            group_member_ids={102},
        )

    assert [s.userid for s in subs] == [102]


# =========================================================================
# download_submission_file
# =========================================================================

@pytest.mark.asyncio
async def test_download_submission_file_appends_token_and_returns_bytes(service):
    mock_response = MagicMock()
    mock_response.content = b"PK\x03\x04zipbytes"
    mock_response.raise_for_status = MagicMock()

    captured = {}

    async def fake_get(url, *args, **kwargs):
        captured["url"] = url
        return mock_response

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=fake_get)
        mock_client_cls.return_value = mock_client

        content = await service.download_submission_file(
            token="tok123",
            fileurl="https://m/pluginfile.php/1/assignsubmission_file/x/tp.zip",
        )

    assert content == b"PK\x03\x04zipbytes"
    assert "token=tok123" in captured["url"]


@pytest.mark.asyncio
async def test_download_submission_file_timeout_raises_connection_error(service):
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(MoodleConnectionError):
            await service.download_submission_file(token="t", fileurl="https://m/x.zip")


# =========================================================================
# get_assignment_grade_config  (Fase 3 — detección de escala del assignment)
# =========================================================================

def _assignments_payload(assignments: list[dict]) -> dict:
    return {"courses": [{"id": 38, "assignments": assignments}]}


@pytest.mark.asyncio
async def test_grade_config_numerica(service):
    data = _assignments_payload([{"cmid": 11369, "id": 484, "name": "Parcial", "grade": 100}])
    with patch.object(service, "_fetch_assignments", AsyncMock(return_value=data)):
        cfg = await service.get_assignment_grade_config("t", "https://m", 38, 11369)
    assert cfg.instance_id == 484
    assert cfg.tipo == "numerica"
    assert cfg.grade_max == 100
    assert cfg.scale_id is None


@pytest.mark.asyncio
async def test_grade_config_escala(service):
    # grade negativo → escala cualitativa; scale_id = abs(grade) (confirmado Fase 0: scale 5)
    data = _assignments_payload([{"cmid": 11237, "id": 478, "name": "TP", "grade": -5}])
    with patch.object(service, "_fetch_assignments", AsyncMock(return_value=data)):
        cfg = await service.get_assignment_grade_config("t", "https://m", 38, 11237)
    assert cfg.instance_id == 478
    assert cfg.tipo == "escala"
    assert cfg.scale_id == 5
    assert cfg.grade_max is None


@pytest.mark.asyncio
async def test_grade_config_cmid_no_encontrado(service):
    data = _assignments_payload([{"cmid": 999, "id": 1, "name": "Otro", "grade": 100}])
    with patch.object(service, "_fetch_assignments", AsyncMock(return_value=data)):
        cfg = await service.get_assignment_grade_config("t", "https://m", 38, 11237)
    assert cfg is None


# =========================================================================
# save_grade  (Fase 3 — mod_assign_save_grade)
# =========================================================================

@pytest.mark.asyncio
async def test_save_grade_envia_payload_correcto(service):
    captured = {}
    mock_response = MagicMock()
    mock_response.json.return_value = None  # save_grade exitoso devuelve null
    mock_response.raise_for_status = MagicMock()

    async def fake_post(url, *args, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        return mock_response

    with patch("httpx.AsyncClient") as cls:
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=None)
        mc.post = AsyncMock(side_effect=fake_post)
        cls.return_value = mc

        await service.save_grade(
            token="tok", moodle_host="https://m", assignment_instance_id=478,
            moodle_user_id=101, grade=1.0, feedback_comment="Aprobado!",
        )

    d = captured["data"]
    assert d["wsfunction"] == "mod_assign_save_grade"
    assert d["wstoken"] == "tok"
    assert int(d["assignmentid"]) == 478
    assert int(d["userid"]) == 101
    assert float(d["grade"]) == 1.0
    # feedback en plugindata (assignfeedbackcomments)
    assert d["plugindata[assignfeedbackcomments_editor][text]"] == "Aprobado!"
    assert str(d["plugindata[assignfeedbackcomments_editor][format]"]) == "1"


@pytest.mark.asyncio
async def test_save_grade_exception_de_moodle_lanza_error(service):
    mock_response = MagicMock()
    mock_response.json.return_value = {"exception": "moodle_exception", "message": "No permission"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as cls:
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=None)
        mc.post = AsyncMock(return_value=mock_response)
        cls.return_value = mc

        with pytest.raises(MoodleConnectionError):
            await service.save_grade(
                token="t", moodle_host="https://m", assignment_instance_id=478,
                moodle_user_id=101, grade=1.0, feedback_comment="x",
            )
