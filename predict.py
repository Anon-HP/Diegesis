#!/usr/bin/env python3
"""Classify the McCloud transition between two consecutive comic panels.

usage: python predict.py PANEL_A PANEL_B [--json] [--head models/head.joblib] [--cpu]

Prints exactly one of: moment-to-moment, action-to-action, subject-to-subject, scene-to-scene,
aspect-to-aspect, non-sequitur (plus a confidence score).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("panel_a", help="first (earlier) panel image")
    ap.add_argument("panel_b", help="second (next) panel image")
    ap.add_argument("--json", action="store_true", help="print full JSON (probabilities, OCR text)")
    ap.add_argument("--head", default=None, help="path to trained classifier head")
    ap.add_argument("--cpu", action="store_true", help="force CPU")
    args = ap.parse_args(argv)

    from transition.predictor import InputError, TransitionPredictor, load_panel

    try:
        load_panel(args.panel_a)
        load_panel(args.panel_b)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    pred = TransitionPredictor(head_path=args.head, device="cpu" if args.cpu else None)
    out = pred.predict(args.panel_a, args.panel_b)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"{out['label']}\t{out['confidence']:.3f}")
        for w in out.get("warnings", []):
            print(f"warning: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
