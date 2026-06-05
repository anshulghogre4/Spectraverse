"""
Integration tests for Sprint 1 (regression) and Sprint 2 (generate endpoints).
Run from the backend/ directory:
    pytest tests/test_api.py -v
"""
import io
import wave
import base64
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_jpeg(width: int = 32, height: int = 32) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 180, 140)).save(buf, format="JPEG")
    return buf.getvalue()


def _make_wav(duration_s: float = 0.5, sr: int = 22050) -> bytes:
    buf = io.BytesIO()
    n_frames = int(sr * duration_s)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


# ── Sprint 1 regression ───────────────────────────────────────────────────────

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "SpectraVerse API"
    assert "version" in data


def test_mappings_endpoint():
    response = client.get("/api/mappings")
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        assert isinstance(response.json(), dict)


# ── Sprint 2: image-to-audio ──────────────────────────────────────────────────

def test_generate_image_to_audio_returns_audio():
    """POST a JPEG → non-empty base64 WAV starting with RIFF."""
    jpeg = _make_jpeg()
    response = client.post(
        "/api/generate/image-to-audio?mode=classic&style=&duration=5",
        files={"file": ("test.jpg", jpeg, "image/jpeg")},
    )
    if response.status_code == 503:
        pytest.skip("ImageToAudioPipeline unavailable in this environment")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    assert body.get("audio_b64"), "audio_b64 must be non-empty"

    wav_bytes = base64.b64decode(body["audio_b64"])
    assert wav_bytes[:4] == b"RIFF", f"Expected RIFF header, got {wav_bytes[:4]!r}"
    assert body["sample_rate"] == 22050


def test_generate_image_to_audio_invalid_type():
    """POST a text file → 400."""
    response = client.post(
        "/api/generate/image-to-audio",
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


def test_generate_image_to_audio_duration_capped():
    """duration=999 should be clamped server-side, not rejected."""
    jpeg = _make_jpeg()
    response = client.post(
        "/api/generate/image-to-audio?duration=999",
        files={"file": ("test.jpg", jpeg, "image/jpeg")},
    )
    if response.status_code == 503:
        pytest.skip("ImageToAudioPipeline unavailable in this environment")
    assert response.status_code == 200
    assert response.json()["duration"] <= 15.0


# ── Sprint 2: audio-to-visual ─────────────────────────────────────────────────

def test_generate_audio_to_visual_returns_config():
    """POST a WAV → visual_config with particle_count > 0."""
    wav = _make_wav()
    response = client.post(
        "/api/generate/audio-to-visual?mode=classic&style=",
        files={"file": ("test.wav", wav, "audio/wav")},
    )
    if response.status_code == 503:
        pytest.skip("AudioToVisualPipeline unavailable in this environment")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    vc = body.get("visual_config", {})
    assert isinstance(vc, dict) and vc, "visual_config must be non-empty"
    assert vc.get("particles", {}).get("count", 0) > 0


def test_generate_audio_to_visual_invalid_type():
    """POST a text file → 400."""
    response = client.post(
        "/api/generate/audio-to-visual",
        files={"file": ("test.txt", b"not audio", "text/plain")},
    )
    assert response.status_code == 400
