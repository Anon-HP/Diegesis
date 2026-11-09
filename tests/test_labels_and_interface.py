"""Tests for the six-class contract and the two-image interface.

The heavy end-to-end test (which loads the CLIP model) runs only when the encoder weights and
sample panels are available. Run it with: pytest -m e2e
"""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transition.labels import LABELS, NUM_CLASSES, validate_label  # noqa: E402

EXPECTED = ("moment-to-moment", "action-to-action", "subject-to-subject", "scene-to-scene",
            "aspect-to-aspect", "non-sequitur")


def test_exactly_six_mccloud_labels():
    assert LABELS == EXPECTED
    assert NUM_CLASSES == 6


@pytest.mark.parametrize("bad", ["continued conversation", "Continued-Conversation", "other", ""])
def test_rejects_non_mccloud_labels(bad):
    with pytest.raises(ValueError):
        validate_label(bad)


def test_manifest_labels_are_valid():
    m = ROOT / "data" / "manifest.csv"
    if not m.exists():
        pytest.skip("no manifest yet")
    rows = list(csv.DictReader(open(m)))
    for r in rows:
        assert r["label_source"] in {"human", "llm", "synthetic"}
        if r["valid"] == "1":
            assert r["label"] in EXPECTED
        else:
            assert r["label"] == ""
    # A book never appears in two splits (natural pairs).
    split_of = {}
    for r in rows:
        if r["label_source"] == "synthetic":
            continue
        assert split_of.setdefault(r["book"], r["split"]) == r["split"]


def test_cli_rejects_missing_file(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "predict.py"), str(tmp_path / "a.png"), str(tmp_path / "b.png")],
                         capture_output=True, text=True)
    assert out.returncode == 2
    assert "not a file" in out.stderr


def test_cli_rejects_non_image(tmp_path):
    a = tmp_path / "a.png"
    a.write_text("not an image")
    out = subprocess.run([sys.executable, str(ROOT / "predict.py"), str(a), str(a)], capture_output=True, text=True)
    assert out.returncode == 2


def test_cli_requires_exactly_two_images():
    out = subprocess.run([sys.executable, str(ROOT / "predict.py"), "only_one.png"], capture_output=True, text=True)
    assert out.returncode != 0


@pytest.mark.e2e
def test_end_to_end_prediction_on_real_panels():
    sample = ROOT / "tests" / "sample_pairs.csv"
    if not sample.exists():
        pytest.skip("no sample pairs file")
    from transition.paths import PANELS_DIR
    from transition.predictor import TransitionPredictor

    pred = TransitionPredictor()
    n = 0
    for r in csv.DictReader(open(sample)):
        a, b = PANELS_DIR / r["panel_a"], PANELS_DIR / r["panel_b"]
        if not (a.exists() and b.exists()):
            continue
        out = pred.predict(a, b)
        assert out["label"] in EXPECTED
        assert 0.0 <= out["confidence"] <= 1.0
        assert set(out["probabilities"]) == set(EXPECTED)
        assert abs(sum(out["probabilities"].values()) - 1.0) < 1e-2
        n += 1
    assert n > 0
