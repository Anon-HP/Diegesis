"""Train and evaluate the transition classifier head on cached panel records.

Protocol (no leakage):
  * Splits are per book (scripts/build_pair_index.py), so no book appears in two splits.
  * Model selection uses StratifiedGroupKFold over books, on dev pairs (train+val) only.
  * Final test: fit the selected configuration on dev, then evaluate ONCE on the test books
    (--final-test). Headline metrics use natural pairs only. Synthetic non-sequiturs are
    reported separately.
  * The provenance of every evaluated label is reported. At present the labels come from
    Claude ('llm'), so the metrics measure agreement with the LLM annotator, not with humans.
  * --deploy refits the selected configuration on ALL labelled pairs (dev+test) and writes
    models/head.joblib. Do this only after the test numbers have been recorded.

Graceful stop / resume: the unit of work is one CV fold of one (model, feature-subset)
configuration. Its out-of-fold probabilities are saved atomically to
experiments/<exp>_ckpt/<fingerprint>/. The fingerprint covers the labelled rows, the fold seed and
the training options, so a checkpoint is only reused for identical data and settings. On SIGINT/SIGTERM
the current fold finishes and the script exits with code 130. Re-running the same command (same --exp)
resumes. All result files (json, csv, joblib) are written atomically, only after the CV is complete.
"""
import argparse
import csv
import io
import sys
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_features import load_record  # noqa: E402
from transition.features import FEATURE_SUBSETS, needs_centers, pair_vector  # noqa: E402
from transition.labels import LABEL2ID, LABELS, NUM_CLASSES  # noqa: E402
from transition.paths import DATA_DIR, EXP_DIR, MODELS_DIR  # noqa: E402
from transition.runctl import (atomic_json, atomic_open, atomic_savez, atomic_write_text,  # noqa: E402
                               exit_interrupted, fingerprint, install_stop_handler, load_valid_npz,
                               test_unit_delay)
from transition.rules import rule_predict  # noqa: E402

MODELS = ("logreg", "logreg_strong", "logreg_pca", "hgb")


def make_model(name, n_train, n_feat=10**9):
    if name == "logreg":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=5000, class_weight="balanced"))
    if name == "logreg_strong":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.005, max_iter=5000, class_weight="balanced"))
    if name == "logreg_pca":
        return make_pipeline(StandardScaler(), PCA(n_components=min(64, n_train // 4, n_feat - 1), random_state=0),
                             LogisticRegression(C=0.5, max_iter=5000, class_weight="balanced"))
    if name == "hgb":
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                              class_weight="balanced", random_state=0)
    raise ValueError(name)


def full_proba(model, X):
    p = model.predict_proba(X)
    out = np.zeros((len(X), NUM_CLASSES))
    out[:, model.classes_] = p
    return out


def metrics(y, pred):
    labels = list(range(NUM_CLASSES))
    present = sorted(set(y.tolist()))
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=labels, zero_division=0)
    return {
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1_present_classes": float(f1_score(y, pred, labels=present, average="macro", zero_division=0)),
        "macro_f1_all6": float(f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
        # Classes with >=10 examples in this evaluation set: a less noisy selection criterion than
        # present-class macro-F1, which swings wildly on classes with 1-4 examples.
        "macro_f1_supported": float(f1_score(y, pred, labels=[c for c in present if (y == c).sum() >= 10],
                                             average="macro", zero_division=0)),
        "supported_classes": [LABELS[c] for c in present if (y == c).sum() >= 10],
        "classes_present": [LABELS[i] for i in present],
        "per_class": {LABELS[i]: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i in labels},
        "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist(),
    }


def fmt(m):
    return (f"macroF1={m['macro_f1_present_classes']:.3f} macroF1_sup={m['macro_f1_supported']:.3f} "
            f"balAcc={m['balanced_accuracy']:.3f} acc={m['accuracy']:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DATA_DIR / "manifest.csv"))
    ap.add_argument("--train-sources", default="llm,human,synthetic")
    ap.add_argument("--subsets", default=",".join(FEATURE_SUBSETS))
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--min-confidence", default="low", choices=["low", "medium", "high"],
                    help="drop llm-labelled TRAINING pairs below this confidence (evaluation keeps all)")
    ap.add_argument("--exp", default=time.strftime("exp_%Y%m%d_%H%M%S"))
    ap.add_argument("--final-test", action="store_true")
    ap.add_argument("--deploy", action="store_true", help="refit on all labelled pairs -> models/head.joblib")
    args = ap.parse_args()
    stop = install_stop_handler()

    rows = [r for r in csv.DictReader(open(args.manifest))
            if r["valid"] == "1" and r["label_source"] in set(args.train_sources.split(","))]
    recs = {}
    for r in rows:
        for k in ("panel_a", "panel_b"):
            if r[k] not in recs:
                recs[r[k]] = load_record(r[k])
    y = np.array([LABEL2ID[r["label"]] for r in rows])
    split = np.array([r["split"] for r in rows])
    src = np.array([r["label_source"] for r in rows])
    groups = np.array([r["book"] for r in rows])
    rank = {"low": 0, "medium": 1, "high": 2}
    conf_ok = np.array([r["label_source"] != "llm" or rank.get(r["confidence"], 0) >= rank[args.min_confidence]
                        for r in rows])
    natural, dev = src != "synthetic", split != "test"
    print(f"pairs total={len(rows)} dev={dev.sum()} test={(~dev).sum()} natural={natural.sum()}")
    print("dev counts:", {LABELS[i]: int(((y == i) & dev).sum()) for i in range(NUM_CLASSES)})
    print("test counts (natural):", {LABELS[i]: int(((y == i) & ~dev & natural).sum()) for i in range(NUM_CLASSES)})

    # Corpus-mean centres for the cos_c group: a label-free image statistic over DEV panels only (never test).
    dev_panels = sorted({r[k] for r, d in zip(rows, dev) if d for k in ("panel_a", "panel_b")})
    centers = {"clip": np.mean([recs[p].img_emb for p in dev_panels], 0)}
    if all(recs[p].dino_cls is not None for p in dev_panels):
        centers["dino"] = np.mean([recs[p].dino_cls for p in dev_panels], 0)
    if any("zs" in sub.split("+") for sub in args.subsets.split(",")):
        from transition.features import ZS_PROMPTS, ClipEncoder
        centers["zs"] = ClipEncoder(device="cpu").encode_texts(ZS_PROMPTS)
    feats = {s: np.stack([pair_vector(recs[r["panel_a"]], recs[r["panel_b"]], s, centers) for r in rows])
             for s in args.subsets.split(",")}
    res = {"exp": args.exp, "args": vars(args), "cv": {}}
    di = np.where(dev)[0]
    yd, gd, nd = y[di], groups[di], natural[di]
    folds = list(StratifiedGroupKFold(n_splits=args.folds, shuffle=True, random_state=0).split(di, yd, gd))

    maj = int(np.bincount(yd[nd]).argmax())
    res["cv"]["baseline:majority"] = metrics(yd[nd], np.full(nd.sum(), maj))
    rule = np.array([LABEL2ID[rule_predict(recs[r["panel_a"]], recs[r["panel_b"]])[0]] for r in rows])
    res["cv"]["baseline:rules"] = metrics(yd[nd], rule[di][nd])
    key_fp = fingerprint([(r["pair_id"], r["label"], r["split"], r["book"]) for r in rows], conf_ok.tolist(),
                         args.folds, args.train_sources, args.min_confidence, "cv-v1")
    ckpt_dir = EXP_DIR / f"{args.exp}_ckpt" / key_fp
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    n_units = len(feats) * len(args.models.split(",")) * len(folds)
    n_done = n_reused = 0
    oof_store = {}
    for s, X in feats.items():
        Xd = X[di]
        for m in args.models.split(","):
            oof = np.zeros((len(di), NUM_CLASSES))
            for k, (tr, va) in enumerate(folds):
                f = ckpt_dir / f"{m}__{s.replace('+', '-')}__fold{k}.npz"
                z = load_valid_npz(f, {"va": (len(va),), "proba": (len(va), NUM_CLASSES)})
                if z is not None and np.array_equal(z["va"], va):
                    oof[va] = z["proba"]
                    n_done += 1
                    n_reused += 1
                    continue
                if stop.requested:
                    exit_interrupted(f"{n_done}/{n_units} CV folds done; checkpoints in {ckpt_dir}")
                tr = tr[conf_ok[di][tr]]
                mdl = make_model(m, len(tr), Xd.shape[1]).fit(Xd[tr], yd[tr])
                oof[va] = full_proba(mdl, Xd[va])
                test_unit_delay()
                atomic_savez(f, va=va, proba=oof[va])
                n_done += 1
            key = f"{m}|{s}"
            pred = oof.argmax(1)
            res["cv"][key] = metrics(yd[nd], pred[nd])
            if (~nd).any():
                res["cv"][key]["synthetic_nonseq_recall"] = float((pred[~nd] == LABEL2ID["non-sequitur"]).mean())
            oof_store[key] = pred
            print(f"{key:40s} {fmt(res['cv'][key])}", flush=True)
    for b in ("baseline:majority", "baseline:rules"):
        print(f"{b:40s} {fmt(res['cv'][b])}")
    print(f"CV folds: {n_reused} reused from checkpoints, {n_units - n_reused} computed", flush=True)

    learned = {k: v for k, v in res["cv"].items() if "|" in k}
    best = max(learned, key=lambda k: (learned[k]["macro_f1_supported"], learned[k]["balanced_accuracy"]))
    res["selected"] = best
    print("selected:", best, fmt(learned[best]))
    m, s = best.split("|")
    if stop.requested:  # CV is complete and checkpointed; the remaining fits are the next unit
        exit_interrupted("CV complete; final fit/test not started")
    out_dir = EXP_DIR
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["pair_id", "label_source", "stratum", "confidence", "true", "pred"])
    for j, i in enumerate(di):
        r = rows[i]
        w.writerow([r["pair_id"], r["label_source"], r["stratum"], r["confidence"], LABELS[y[i]],
                    LABELS[oof_store[best][j]]])
    atomic_write_text(out_dir / f"{args.exp}_cv_oof.csv", buf.getvalue())

    fit_idx = di[conf_ok[di]]
    final = make_model(m, len(fit_idx), feats[s].shape[1]).fit(feats[s][fit_idx], y[fit_idx])
    if args.final_test and (~dev).any():
        ti = np.where(~dev)[0]
        nt = natural[ti]
        pt = full_proba(final, feats[s][ti]).argmax(1)
        res["test"] = metrics(y[ti][nt], pt[nt])
        res["test"]["label_sources"] = sorted(set(src[ti][nt].tolist()))
        res["test"]["n_books"] = len(set(groups[ti][nt].tolist()))
        if (~nt).any():
            res["test"]["synthetic_nonseq_recall"] = float((pt[~nt] == LABEL2ID["non-sequitur"]).mean())
        strat = np.array([rows[i]["stratum"] for i in ti])[nt]
        if (strat == "random").sum() >= 10:  # natural class distribution only
            res["test_random_stratum"] = metrics(y[ti][nt][strat == "random"], pt[nt][strat == "random"])
            print(f"TEST random stratum ({res['test_random_stratum']['n']} pairs): {fmt(res['test_random_stratum'])}")
        res["test_baselines"] = {"majority_from_dev": metrics(y[ti][nt], np.full(nt.sum(), maj)),
                                 "rules": metrics(y[ti][nt], rule[ti][nt])}
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["pair_id", "label_source", "stratum", "confidence", "true", "pred"])
        for i, p in zip(ti, pt):
            r = rows[i]
            w.writerow([r["pair_id"], r["label_source"], r["stratum"], r["confidence"], LABELS[y[i]], LABELS[p]])
        atomic_write_text(out_dir / f"{args.exp}_test_predictions.csv", buf.getvalue())
        print(f"TEST ({res['test']['n']} natural pairs, {res['test']['n_books']} books): {fmt(res['test'])}")
        print(f"TEST rules baseline: {fmt(res['test_baselines']['rules'])}")
        print(f"TEST majority baseline: {fmt(res['test_baselines']['majority_from_dev'])}")

    MODELS_DIR.mkdir(exist_ok=True)
    meta = {"features": s, "model_name": m, "labels": LABELS, "exp": args.exp,
            "needs_dino": any(g in s.split("+") for g in ("dino", "match")) or ("cos_c" in s.split("+") and "dino" in centers),
            "centers": centers if needs_centers(s) else None}
    with atomic_open(MODELS_DIR / "head_dev.joblib", "wb") as fh:
        joblib.dump({**meta, "model": final, "trained_on": "dev (train+val books)"}, fh)
    if args.deploy:
        all_idx = np.where(conf_ok)[0]
        dep = make_model(m, len(all_idx), feats[s].shape[1]).fit(feats[s][all_idx], y[all_idx])
        with atomic_open(MODELS_DIR / "head.joblib", "wb") as fh:
            joblib.dump({**meta, "model": dep, "trained_on": f"all labelled pairs ({len(all_idx)})"}, fh)
        print("deployed head ->", MODELS_DIR / "head.joblib")
    atomic_json(out_dir / f"{args.exp}.json", res)
    print("wrote", out_dir / f"{args.exp}.json")


if __name__ == "__main__":
    main()
