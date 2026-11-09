"""Untrained heuristic baseline. Thresholds were set by hand before any labels were looked at.

It is used as a comparison baseline and as the fallback when no trained head is available.
"""
from __future__ import annotations

from .features import PanelRecord, lowlevel_pair
from .ocr import SCENE_CUES

STRONG_CUES = ("later", "meanwhile", "next day", "next morning", "that night", "that evening",
               "elsewhere", "back at", "hours", "days", "weeks", "months", "years", "miles")


def rule_predict(a: PanelRecord, b: PanelRecord) -> tuple[str, float]:
    cos = float(a.img_emb @ b.img_emb)
    corr = float(lowlevel_pair(a.low, b.low)[0])
    tb = b.text.lower()
    if any(c in tb for c in STRONG_CUES):
        return "scene-to-scene", 0.6
    if cos < 0.45:
        return "non-sequitur", 0.3
    if cos < 0.62:
        return "scene-to-scene", 0.35
    if cos > 0.93 and corr > 0.75:
        return "moment-to-moment", 0.4
    if cos > 0.82:
        return "action-to-action", 0.4
    return "subject-to-subject", 0.35


__all__ = ["rule_predict", "SCENE_CUES"]
