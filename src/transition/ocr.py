"""Internal OCR on a single panel image using Tesseract (English), plus text features.

OCR runs only on the supplied panel images. No transcript is ever supplied from outside.
Golden Age lettering is all-caps hand lettering, so Tesseract is noisy. The text features
below are deliberately simple and tolerant of noise.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

TESSERACT = shutil.which("tesseract")

# Caption cues that usually signal a time/space jump (scene-to-scene).
SCENE_CUES = [
    "later", "meanwhile", "next day", "next morning", "that night", "that evening", "tonight",
    "morning", "evening", "hours", "days", "weeks", "months", "years", "elsewhere", "back at",
    "miles", "soon", "the next", "following", "at the", "in the", "arrive", "arrives", "after",
]
# Cues that the text continues the same moment/exchange.
CONT_CUES = ["...", "--", "and", "but", "so", "then"]

WORD = re.compile(r"[a-z]{2,}")
STOP = set("the a an and or but to of in on at is it i you he she we they me my his her was be "
           "for with as that this are not no so do did dat de".split())


def ocr_image(img: Image.Image, timeout: int = 20, strict: bool = False) -> str:
    """Return the OCR text of a panel ('' if tesseract is unavailable).

    strict=True (used when caching): a timeout raises instead of returning '', so a timeout is
    never cached as "no text". At inference a timeout degrades to '' (text features absent)."""
    if TESSERACT is None:
        if strict:
            raise RuntimeError("tesseract not found; refusing to cache empty OCR")
        return ""
    g = ImageOps.grayscale(img)
    # Upscale small panels; Tesseract wants roughly 30px-tall glyphs.
    scale = 1600 / max(g.size)
    if scale > 1:
        g = g.resize((int(g.width * scale), int(g.height * scale)), Image.LANCZOS)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "p.png"
        g.save(p)
        try:
            # start_new_session: a terminal Ctrl-C must not kill tesseract mid-panel (the caller
            # handles shutdown between panels); a failed run raises instead of yielding "" text.
            res = subprocess.run(
                [TESSERACT, str(p), "stdout", "-l", "eng", "--psm", "11"],
                capture_output=True, text=True, timeout=timeout, start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            if strict:
                raise
            return ""
        if res.returncode != 0:
            raise RuntimeError(f"tesseract failed ({res.returncode}): {res.stderr.strip()[:200]}")
        out = res.stdout
    # Keep tokens that look like words (filters halftone noise).
    toks = [t for t in re.split(r"\s+", out) if re.fullmatch(r"[A-Za-z'!?.,\-]{2,}", t)]
    return " ".join(toks)


def words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 2}


TEXT_FEATURE_NAMES = (
    ["len_a", "len_b", "has_a", "has_b", "jaccard"]
    + [f"cue_b_{c.replace(' ', '_')}" for c in SCENE_CUES]
    + [f"cue_a_{c.replace(' ', '_')}" for c in SCENE_CUES[:6]]
    + ["b_startslower_cont", "a_ends_cont"]
)


def text_features(ta: str, tb: str) -> np.ndarray:
    la, lb = ta.lower(), tb.lower()
    wa, wb = words(ta), words(tb)
    jac = len(wa & wb) / max(1, len(wa | wb))
    f = [np.log1p(len(wa)), np.log1p(len(wb)), float(bool(wa)), float(bool(wb)), jac]
    f += [float(c in lb) for c in SCENE_CUES]
    f += [float(c in la) for c in SCENE_CUES[:6]]
    f += [float(lb.lstrip().startswith(("...", "--", "and ", "but "))),
          float(la.rstrip().endswith(("...", "--", ",")))]
    return np.asarray(f, dtype=np.float32)


# Lexicon families for the compact "cue2" feature group, built from how Golden Age captions are actually
# phrased (see the scene-to-scene annotator rationales). Matching uses whole words or phrases.
CUE_FAMILIES = {
    "time_jump": ["later", "next day", "next morning", "the next", "that night", "that evening", "that afternoon",
                  "tonight", "dawn", "dusk", "midnight", "noon", "morning", "evening", "afternoon", "hours",
                  "hour", "days", "weeks", "months", "years", "soon", "shortly", "presently", "before long",
                  "rest of the day", "following", "after", "earlier", "ago", "before dawn"],
    "place_jump": ["elsewhere", "back at", "back in", "far away", "miles", "across town", "arriving",
                   "arrive", "arrives", "reach", "reaches", "at the", "in the", "headquarters", "hideout"],
    "simultaneity": ["meanwhile", "at that moment", "at that very moment", "while", "same time", "at the same"],
    "story_start": ["the end", "presents", "featuring", "starring", "in the adventure of", "chapter", "part"],
}
_CUE_RES = {k: [re.compile(r"\b" + re.escape(p) + r"\b") for p in v] for k, v in CUE_FAMILIES.items()}
CUE2_NAMES = [f"b_{k}" for k in CUE_FAMILIES] + ["a_time_jump", "b_any", "a_any_story_end"]


def cue2_features(ta: str, tb: str) -> np.ndarray:
    la, lb = ta.lower(), tb.lower()
    cnt = lambda txt, fam: sum(bool(r.search(txt)) for r in _CUE_RES[fam])  # noqa: E731
    fb = [min(cnt(lb, k), 3) / 3 for k in CUE_FAMILIES]
    return np.asarray(fb + [min(cnt(la, "time_jump"), 3) / 3, float(any(fb)),
                            float(bool(re.search(r"\bthe end\b", la)))], dtype=np.float32)
