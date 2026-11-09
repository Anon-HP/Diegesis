"""Active mining: rank unlabelled consecutive pairs by predicted probability of the rare classes
(moment-to-moment, aspect-to-aspect by default), so that the next annotation round includes more of them.

The ranking model is a class-balanced logistic regression on CLIP pair features (clipdiff:
eA*eB, |eA-eB|, cos). It is trained on the currently labelled natural pairs and uses the cached
per-book embeddings in cache/clip_img/ (from mine_clip_similarity.py). It ONLY chooses which pairs
to show annotators. Annotators never see its prediction, and its scores are never used as labels.

Writes annotations/sample_<tag>.csv + batch files (same format as sample_for_annotation.py),
stratum = "active:<class>", with composites.
"""
import argparse
import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mine_clip_similarity import valid_book_cache  # noqa: E402
from sample_for_annotation import composite, composite_ok  # noqa: E402
from transition.labels import LABEL2ID  # noqa: E402
from transition.paths import ANN_DIR, CACHE_DIR, DATA_DIR, PANELS_DIR, WORKSPACE  # noqa: E402
from transition.runctl import atomic_open, exit_interrupted, install_stop_handler  # noqa: E402


def feat(ea, eb):
    return np.concatenate([ea * eb, np.abs(ea - eb), [float(ea @ eb)]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="moment-to-moment,aspect-to-aspect")
    ap.add_argument("--n", type=int, default=160)
    ap.add_argument("--per-book", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=40)
    ap.add_argument("--tag", default="r3")
    args = ap.parse_args()
    stop = install_stop_handler()

    rows = list(csv.DictReader(gzip.open(DATA_DIR / "pair_index.csv.gz", "rt")))
    by_book = defaultdict(set)
    for r in rows:
        by_book[r["book"]].update([r["panel_a"], r["panel_b"]])
    emb = {}
    for book, panels in by_book.items():
        E = valid_book_cache(CACHE_DIR / "clip_img" / f"{book}.npz", sorted(panels))
        if E is not None:
            emb.update(zip(sorted(panels), E))
    print(f"CLIP embeddings available for {len(emb)} panels")

    sampled = set()
    for p in ANN_DIR.glob("sample_*.csv"):
        sampled |= {r["pair_id"] for r in csv.DictReader(open(p))}
    lab = [r for r in csv.DictReader(open(DATA_DIR / "manifest.csv"))
           if r["valid"] == "1" and r["label_source"] in ("llm", "human")
           and r["panel_a"] in emb and r["panel_b"] in emb]
    X = np.stack([feat(emb[r["panel_a"]], emb[r["panel_b"]]) for r in lab])
    y = np.array([LABEL2ID[r["label"]] for r in lab])
    print("ranking model trained on", len(lab), "labelled pairs:", np.bincount(y, minlength=6).tolist())
    mdl = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=5000, class_weight="balanced")).fit(X, y)

    pool = [r for r in rows if r["pair_id"] not in sampled and r["panel_a"] in emb and r["panel_b"] in emb
            and r["cross_page"] == "0"]
    P = mdl.predict_proba(np.stack([feat(emb[r["panel_a"]], emb[r["panel_b"]]) for r in pool]))
    cls = list(mdl.classes_)
    targets = [t for t in args.targets.split(",") if LABEL2ID[t] in cls]
    print("targets present in training labels:", targets)
    per_target = args.n // max(1, len(targets))
    chosen, per_book, seen = [], defaultdict(int), set()
    for t in targets:
        order = np.argsort(-P[:, cls.index(LABEL2ID[t])])
        got = 0
        for i in order:
            r = pool[i]
            if got >= per_target:
                break
            if r["pair_id"] in seen or per_book[r["book"]] >= args.per_book:
                continue
            seen.add(r["pair_id"])
            per_book[r["book"]] += 1
            chosen.append({**r, "stratum": f"active:{t}"})
            got += 1
        print(f"{t}: {got} candidates")
    # Interleave classes so batches are mixed (annotators must not infer the target class from position).
    rng = np.random.default_rng(5)
    rng.shuffle(chosen)

    comp_dir = WORKSPACE / "composites"
    out_rows = []
    for i, r in enumerate(chosen):
        cp = comp_dir / f"{r['pair_id']}.jpg"
        if not composite_ok(cp):
            if stop.requested:
                exit_interrupted(f"{i}/{len(chosen)} composites ready; no CSVs written")
            composite(PANELS_DIR / r["panel_a"], PANELS_DIR / r["panel_b"], cp)
        out_rows.append({"pair_id": r["pair_id"], "book": r["book"], "split": r["split"], "panel_a": r["panel_a"],
                         "panel_b": r["panel_b"], "cross_page": r["cross_page"], "stratum": r["stratum"],
                         "composite": str(cp), "batch": f"{args.tag}_{i // args.batch_size:02d}"})
    for b in sorted({r["batch"] for r in out_rows}):
        with atomic_open(ANN_DIR / "batches" / f"{b}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["pair_id", "composite"])
            w.writeheader()
            w.writerows({"pair_id": r["pair_id"], "composite": r["composite"]} for r in out_rows if r["batch"] == b)
    with atomic_open(ANN_DIR / f"sample_{args.tag}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    print(f"{len(out_rows)} pairs from {len(per_book)} books -> sample_{args.tag}.csv")


if __name__ == "__main__":
    main()
