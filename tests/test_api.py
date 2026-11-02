import shutil

import pytest
from fastapi.testclient import TestClient

from bookorbit_tts.config import Settings
from bookorbit_tts.server import create_app

pytestmark = pytest.mark.skipif(
    shutil.which("espeak-ng") is None and shutil.which("espeak") is None,
    reason="espeak-ng is required for the fast API tests",
)


@pytest.fixture()
def client(tmp_path):
    settings = Settings(engine="espeak", data_dir=tmp_path)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["engine"] == "espeak"
    assert body["voices"] > 0


def test_models_endpoint_used_by_bookorbit(client):
    body = client.get("/v1/models").json()
    ids = {entry["id"] for entry in body["data"]}
    assert "tts-1" in ids


def test_voice_listing_shape(client):
    body = client.get("/v1/audio/voices").json()
    assert body["voices"]
    voice = body["voices"][0]
    for key in ("id", "name", "short_name", "language", "locale", "gender"):
        assert key in voice
    assert voice["voice_id"] == voice["id"]


def test_speech_wav(client):
    response = client.post(
        "/v1/audio/speech",
        json={"model": "tts-1", "input": "Hello from the test.", "voice": None, "speed": 1.0, "response_format": "wav"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"


def test_speech_mp3(client):
    response = client.post(
        "/v1/audio/speech",
        json={"input": "Hello again.", "voice": "en-us", "response_format": "mp3"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content[:3] == b"ID3" or response.content[0] == 0xFF


def test_unknown_voice_is_rejected(client):
    response = client.post(
        "/v1/audio/speech",
        json={"input": "Hello.", "voice": "does-not-exist", "response_format": "wav"},
    )
    assert response.status_code == 400


def test_unknown_format_is_rejected(client):
    response = client.post(
        "/v1/audio/speech",
        json={"input": "Hello.", "voice": None, "response_format": "midi"},
    )
    assert response.status_code == 400


def test_empty_input_is_rejected(client):
    response = client.post(
        "/v1/audio/speech",
        json={"input": "   ", "voice": None, "response_format": "wav"},
    )
    assert response.status_code == 400


def test_api_key_is_enforced(tmp_path):
    settings = Settings(engine="espeak", data_dir=tmp_path, api_key="s3cret")
    with TestClient(create_app(settings)) as client:
        assert client.get("/v1/models").status_code == 401
        huge = client.get("/v1/models", headers={"Authorization": "Bearer " + ("a" * 5000)})
        assert huge.status_code == 401
        ok = client.get("/v1/models", headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 200
        assert client.get("/health").status_code == 200


def test_docs_are_off_unless_requested(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_oversized_body_is_rejected(client):
    response = client.post(
        "/v1/audio/speech",
        content=b"{" + b"x" * 80_000,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_engine_failures_do_not_echo_paths(client):
    def boom(*args, **kwargs):
        raise RuntimeError("failed at /opt/secret/voices/model.onnx")

    client.app.state.synth.speak = boom
    response = client.post(
        "/v1/audio/speech",
        json={"input": "Hello.", "response_format": "wav"},
    )
    assert response.status_code == 503
    assert b"/opt/secret" not in response.content
    assert b"model.onnx" not in response.content
    assert response.json()["detail"] == "synthesis failed"
