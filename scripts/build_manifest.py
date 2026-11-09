"""Merge sampled pairs with annotation files into data/manifest.csv.

Every row carries the provenance of its label:
  label_source = human | llm | synthetic
When both a human label and an llm label exist for a pair, the human label is used as `label`
and the llm label is kept in `llm_label`.

Synthetic non-sequiturs: panel A from one book and panel B from a different book in the
SAME split, so the split stays clean. These are weak supervision only.
"""
import argparse
import csv
import glob
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition.labels import LABELS, validate_label  # noqa: E402
from transition.paths import ANN_DIR, DATA_DIR  # noqa: E402
from transition.runctl import atomic_open  # noqa: E402

FIELDS = ["pair_id", "book", "split", "panel_a", "panel_b", "cross_page", "stratum", "valid", "label",
          "label_source", "annotator", "confidence", "second_choice", "rationale", "llm_label", "human_label"]


def read_labels(pattern):
    out = {}
    for p in sorted(glob.glob(pattern)):
        for r in csv.DictReader(open(p)):
            out[r["pair_id"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-synthetic", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    samples = {}
    for p in sorted(glob.glob(str(ANN_DIR / "sample_*.csv"))):
        for r in csv.DictReader(open(p)):
            samples[r["pair_id"]] = r
    llm = read_labels(str(ANN_DIR / "batches" / "*_labels.csv"))
    human = read_labels(str(ANN_DIR / "human" / "*.csv"))

    rows = []
    for pid, s in samples.items():
        L, H = llm.get(pid), human.get(pid)
        if not L and not H:
            continue
        src = H or L
        valid = str(src.get("valid", "1")).strip()
        label = src.get("label", "").strip() if valid == "1" else ""
        if label:
            validate_label(label)
        sc = (src.get("second_choice") or "").strip()
        if sc and sc not in LABELS:
            sc = ""
        rows.append({
            "pair_id": pid, "book": s["book"], "split": s["split"], "panel_a": s["panel_a"], "panel_b": s["panel_b"],
            "cross_page": s["cross_page"], "stratum": s["stratum"], "valid": valid if label else "0", "label": label,
            "label_source": "human" if H else "llm", "annotator": src.get("annotator", "claude" if not H else "human"),
            "confidence": src.get("confidence", ""), "second_choice": sc, "rationale": src.get("rationale", ""),
            "llm_label": (L or {}).get("label", "") if L and str(L.get("valid", "1")) == "1" else "",
            "human_label": (H or {}).get("label", "") if H else "",
        })

    # Synthetic cross-book non-sequiturs (same split for both panels).
    by_split = {}
    for r in rows:
        if r["valid"] == "1":
            by_split.setdefault(r["split"], []).append(r)
    syn = []
    for split, rs in by_split.items():
        k = max(4, int(args.n_synthetic * len(rs) / max(1, len(rows))))
        for i in range(k):
            for _ in range(50):
                a, b = rng.sample(rs, 2)
                if a["book"] != b["book"]:
                    break
            syn.append({"pair_id": f"SYN_{a['panel_a'].replace('/', '-')}__{b['panel_b'].replace('/', '-')}",
                        "book": a["book"], "split": split, "panel_a": a["panel_a"],
                        "panel_b": b["panel_b"], "cross_page": "", "stratum": "synthetic", "valid": "1",
                        "label": "non-sequitur", "label_source": "synthetic", "annotator": "constructed",
                        "confidence": "", "second_choice": "", "rationale": "panels from two different books",
                        "llm_label": "", "human_label": ""})
    rows += syn
    with atomic_open(DATA_DIR / "manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print("rows", len(rows), "valid", sum(r["valid"] == "1" for r in rows))
    print(Counter((r["label_source"], r["split"], r["label"]) for r in rows if r["valid"] == "1"))


if __name__ == "__main__":
    main()
