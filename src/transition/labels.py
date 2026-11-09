"""The fixed McCloud six-class label set. This module is the only place labels are defined."""

LABELS: tuple[str, ...] = (
    "moment-to-moment",
    "action-to-action",
    "subject-to-subject",
    "scene-to-scene",
    "aspect-to-aspect",
    "non-sequitur",
)
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
NUM_CLASSES = len(LABELS)

DISPLAY = {
    "moment-to-moment": "Moment-to-moment",
    "action-to-action": "Action-to-action",
    "subject-to-subject": "Subject-to-subject",
    "scene-to-scene": "Scene-to-scene",
    "aspect-to-aspect": "Aspect-to-aspect",
    "non-sequitur": "Non-sequitur",
}

assert NUM_CLASSES == 6


def validate_label(label: str) -> str:
    """Return the canonical label or raise. Never remaps from another taxonomy."""
    if label not in LABEL2ID:
        raise ValueError(f"{label!r} is not one of the six McCloud labels {LABELS}")
    return label
