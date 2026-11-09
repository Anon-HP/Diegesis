"""Inter-annotator agreement between primary llm labels and the second pass (or human labels).

usage: python scripts/agreement.py [--other 'annotations/second_pass/*.csv'] [--out experiments/agreement_r1.json]
"""
import argparse
import csv
import glob
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition.labels import LABELS  # noqa: E402
from transition.paths import ANN_DIR  # noqa: E402


def read(pattern):
    out = {}
    for p in sorted(glob.glob(pattern)):
        for r in csv.DictReader(open(p)):
            out[r["pair_id"]] = r
    return out


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in set(a) | set(b)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary", default=str(ANN_DIR / "batches" / "*_labels.csv"))
    ap.add_argument("--other", default=str(ANN_DIR / "second_pass" / "*.csv"))
    ap.add_argument("--out", default="experiments/agreement_r1.json")
    args = ap.parse_args()
    P, O = read(args.primary), read(args.other)
    both = [k for k in O if k in P]
    valid_agree = sum(P[k]["valid"] == O[k]["valid"] for k in both)
    pairs = [(P[k]["label"], O[k]["label"]) for k in both if P[k]["valid"] == "1" and O[k]["valid"] == "1"]
    a, b = zip(*pairs)
    k, po = kappa(a, b)
    conf = {la: {lb: 0 for lb in LABELS} for la in LABELS}
    for x, y in pairs:
        conf[x][y] += 1
    res = {"n_overlap": len(both), "validity_agreement": valid_agree / len(both), "n_both_valid": len(pairs),
           "percent_agreement": po, "cohen_kappa": k, "confusion_primary_rows_vs_other_cols": conf}
    Path(args.out).parent.mkdir(exist_ok=True)
    json.dump(res, open(args.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "confusion_primary_rows_vs_other_cols"}, indent=1))
    for la in LABELS:
        print(f"{la:20s}", [conf[la][lb] for lb in LABELS])


if __name__ == "__main__":
    main()
