"""Tests for the HTTP API (src/transition/api.py).

Validation tests use a stub predictor (fast, no model). The e2e test loads the real model and sends
two real COMICS panels through /api/analyze.
"""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fastapi.testclient import TestClient  # noqa: E402

from transition import api  # noqa: E402
from transition.labels import LABELS  # noqa: E402


def png(w=200, h=150, color=(200, 30, 30), fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format=fmt)
    return buf.getvalue()


class StubPredictor:
    head = object()
    head_path = Path("head.joblib")

    def __init__(self, label="action-to-action", conf=0.8):
        self.label, self.conf = label, conf
        self.calls = 0

    def predict_images(self, a, b):
        self.calls += 1
        probs = {l: (self.conf if l == self.label else (1 - self.conf) / 5) for l in LABELS}
        return {"label": self.label, "confidence": self.conf, "probabilities": probs, "method": "stub",
                "ocr_a": "LATER", "ocr_b": ""}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CPT_API_LAZY", "1")
    stub = StubPredictor()
    monkeypatch.setattr(api.state, "predictor", stub)
    monkeypatch.setattr(api.state, "status", "ok")
    with TestClient(api.app) as c:
        c.stub = stub
        yield c


def post(c, a=None, b=None, **files):
    f = {}
    if a is not None:
        f["first"] = ("a.png", a, "image/png")
    if b is not None:
        f["second"] = ("b.png", b, "image/png")
    f.update(files)
    return c.post("/api/analyze", files=f)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["labels"] == list(LABELS)


def test_success_returns_one_of_six_labels(client):
    r = post(client, png(), png(fmt="JPEG"))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["label"] in LABELS and set(j["probabilities"]) == set(LABELS)
    assert 0 <= j["confidence"] <= 1 and j["warnings"] == []


def test_missing_second_panel(client):
    r = post(client, png())
    assert r.status_code == 400 and r.json()["error"]["code"] == "missing_panel"
    assert client.stub.calls == 0


def test_non_image_rejected(client):
    r = post(client, b"not an image at all", png())
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_image"


def test_unsupported_format_rejected(client):
    r = post(client, png(), png(fmt="GIF"))
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_type"


def test_tiny_image_rejected(client):
    r = post(client, png(20, 20), png())
    assert r.status_code == 400 and r.json()["error"]["code"] == "image_too_small"


def test_empty_file_rejected(client):
    r = post(client, b"", png())
    assert r.status_code == 400 and r.json()["error"]["code"] == "empty_file"


def test_too_large_rejected(client, monkeypatch):
    monkeypatch.setattr(api, "MAX_BYTES", 1000)
    r = post(client, png(400, 400, (1, 2, 3)) + b"\0" * 2000, png())
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_model_not_ready_gives_503(client, monkeypatch):
    monkeypatch.setattr(api.state, "status", "loading")
    r = post(client, png(), png())
    assert r.status_code == 503 and r.json()["error"]["code"] == "model_unavailable"


def test_inference_failure_gives_500(client):
    def boom(a, b):
        raise RuntimeError("cuda exploded")
    client.stub.predict_images = boom
    r = post(client, png(), png())
    assert r.status_code == 500 and r.json()["error"]["code"] == "inference_failed"


def test_warnings_for_low_confidence_and_non_sequitur(client, monkeypatch):
    monkeypatch.setattr(api.state, "predictor", StubPredictor("non-sequitur", 0.3))
    j = post(client, png(), png()).json()
    assert len(j["warnings"]) == 2


def test_predictor_warnings_are_passed_through(client, monkeypatch):
    stub = StubPredictor()
    stub.predict_images = lambda a, b: dict(StubPredictor.predict_images(stub, a, b), warnings=["no OCR"])
    monkeypatch.setattr(api.state, "predictor", stub)
    assert post(client, png(), png()).json()["warnings"] == ["no OCR"]


@pytest.mark.e2e
def test_api_end_to_end_real_model(monkeypatch):
    from transition.paths import PANELS_DIR
    a, b = PANELS_DIR / "1094/35_0.jpg", PANELS_DIR / "1094/35_1.jpg"
    if not (a.exists() and b.exists()):
        pytest.skip("COMICS panels not available")
    monkeypatch.delenv("CPT_API_LAZY", raising=False)
    monkeypatch.setattr(api.state, "predictor", None)
    monkeypatch.setattr(api.state, "status", "loading")
    with TestClient(api.app) as c:  # lifespan loads the real model
        assert c.get("/api/health").json()["status"] == "ok"
        r = c.post("/api/analyze", files={"first": ("a.jpg", a.read_bytes(), "image/jpeg"),
                                          "second": ("b.jpg", b.read_bytes(), "image/jpeg")})
        assert r.status_code == 200, r.text
        assert r.json()["label"] in LABELS
