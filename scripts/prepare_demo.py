"""Copy the examiner-demo panel pairs into demo/ (git-ignored) and run the real model on each.

For every pair it runs the full two-image pipeline (live Tesseract OCR + CLIP + DINOv2 + head) twice:
  * models/head.joblib      the deployed head the web app and predict.py use (refit on ALL labels, incl. test)
  * models/head_dev.joblib  the same configuration fitted on dev books only (test books never seen)
Results go to demo/demo_predictions.csv; docs/DEMO_GUIDE.md quotes them.

usage: .venv/bin/python scripts/prepare_demo.py
"""
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from transition.paths import DATA_DIR, MODELS_DIR, PANELS_DIR  # noqa: E402
from transition.predictor import TransitionPredictor  # noqa: E402
from transition.runctl import atomic_open  # noqa: E402

# (step, pair_id, role). Order = presentation order in docs/DEMO_GUIDE.md.
DEMO = [
    (1, "1094_35_0__35_1", "held-out, correct"),
    (2, "2438_26_2__26_3", "held-out, correct"),
    (3, "262_6_4__6_5", "held-out, correct"),
    (4, "1094_24_1__24_2", "held-out, correct"),
    (5, "2206_63_6__63_7", "held-out, correct"),
    (6, "1943_3_3__3_4", "held-out book, rare class (held-out head is wrong)"),
    (7, "3637_31_2__31_3", "TRAINING book, rare class (in-sample only)"),
    (8, "282_7_7__8_0", "held-out, known failure"),
]


def main():
    man = {r["pair_id"]: r for r in csv.DictReader(open(DATA_DIR / "manifest.csv"))}
    out_dir = ROOT / "demo"
    out_dir.mkdir(exist_ok=True)
    deployed = TransitionPredictor(MODELS_DIR / "head.joblib")
    heldout = TransitionPredictor(MODELS_DIR / "head_dev.joblib")
    rows = []
    for step, pid, role in DEMO:
        r = man[pid]
        a, b = PANELS_DIR / r["panel_a"], PANELS_DIR / r["panel_b"]
        da = out_dir / f"{step:02d}_{pid}_A.jpg"
        db = out_dir / f"{step:02d}_{pid}_B.jpg"
        shutil.copyfile(a, da)
        shutil.copyfile(b, db)
        d = deployed.predict(a, b)
        h = heldout.predict(a, b)
        rows.append({"step": step, "pair_id": pid, "book": r["book"], "split": r["split"], "role": role,
                     "label_llm": r["label"], "annotator_confidence": r["confidence"],
                     "deployed_pred": d["label"], "deployed_conf": d["confidence"],
                     "heldout_pred": h["label"], "heldout_conf": h["confidence"],
                     "panel_a": str(a), "panel_b": str(b), "demo_a": str(da), "demo_b": str(db)})
        print(f"{step}. {pid:18s} [{r['split']}] llm={r['label']:19s} deployed={d['label']} ({d['confidence']:.2f}) "
              f"held-out={h['label']} ({h['confidence']:.2f})", flush=True)
    with atomic_open(out_dir / "demo_predictions.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote", out_dir / "demo_predictions.csv")


if __name__ == "__main__":
    main()
