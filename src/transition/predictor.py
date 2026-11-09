"""Two-image inference: Panel A + Panel B -> exactly one of the six McCloud labels."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from .features import PanelFeaturizer, pair_vector
from .labels import LABELS, NUM_CLASSES, validate_label
from .paths import MODELS_DIR
from .rules import rule_predict

MIN_SIDE = 32


class InputError(ValueError):
    pass


def load_panel(path: str | Path) -> Image.Image:
    p = Path(path)
    if not p.is_file():
        raise InputError(f"not a file: {p}")
    try:
        with Image.open(p) as im:
            im.load()
            img = im.convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise InputError(f"cannot read image {p}: {e}") from e
    if min(img.size) < MIN_SIDE:
        raise InputError(f"image too small ({img.size}): {p}")
    return img


class TransitionPredictor:
    def __init__(self, head_path: str | Path | None = None, device: str | None = None):
        import joblib

        head_path = Path(head_path) if head_path else MODELS_DIR / "head.joblib"
        self.head = None
        if head_path.exists():
            self.head = joblib.load(head_path)
            assert tuple(self.head["labels"]) == LABELS, "head label set differs from the six McCloud labels"
        self.head_path = head_path
        need_dino = bool(self.head and self.head.get("needs_dino"))
        self.feat = PanelFeaturizer(device=device, use_dino=need_dino)

    def predict_images(self, img_a: Image.Image, img_b: Image.Image) -> dict:
        a = self.feat.record(img_a)
        b = self.feat.record(img_b)
        if self.head is None:
            label, conf = rule_predict(a, b)
            probs = {l: (conf if l == label else (1 - conf) / (NUM_CLASSES - 1)) for l in LABELS}
            method = "heuristic-fallback (no trained head found)"
        else:
            x = pair_vector(a, b, self.head["features"], self.head.get("centers"))[None, :]
            m = self.head["model"]
            p = np.zeros(NUM_CLASSES)
            p[m.classes_] = m.predict_proba(x)[0]
            label = LABELS[int(p.argmax())]
            conf = float(p.max())
            probs = {l: float(p[i]) for i, l in enumerate(LABELS)}
            method = f"trained head {self.head_path.name} ({self.head['model_name']}|{self.head['features']})"
        return {"label": validate_label(label), "confidence": round(float(conf), 4),
                "probabilities": {k: round(v, 4) for k, v in probs.items()}, "method": method,
                "ocr_a": a.text, "ocr_b": b.text}

    def predict(self, path_a: str | Path, path_b: str | Path) -> dict:
        return self.predict_images(load_panel(path_a), load_panel(path_b))
