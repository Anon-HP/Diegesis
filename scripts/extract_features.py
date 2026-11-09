"""Compute and cache per-panel records (CLIP image/text embeddings, DINOv2 CLS+patches, OCR text,
low-level stats) for every panel referenced in data/manifest.csv.
Cache: <workspace>/cache/panels/<book>_<file>.pkl

Graceful stop / resume: the unit of work is one panel record, processed in small chunks. Each
record is written atomically. A cached record is reused only if it unpickles and every field is
present, finite and correctly shaped. Older records that lack DINO features are upgraded in place.
On SIGINT/SIGTERM the chunk in flight finishes and the script exits with code 130.
"""
import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ocr_cache import cached_ocr  # noqa: E402
from transition.features import ClipEncoder, DinoEncoder, PanelRecord, lowlevel_single  # noqa: E402
from transition.paths import CACHE_DIR, DATA_DIR, PANELS_DIR  # noqa: E402
from transition.runctl import (atomic_pickle, exit_interrupted, install_stop_handler, load_valid_pickle,  # noqa: E402
                               test_unit_delay)


def cache_path(panel: str) -> Path:
    return CACHE_DIR / "panels" / (panel.replace("/", "_") + ".pkl")


def _finite_vec(a) -> bool:
    return isinstance(a, np.ndarray) and a.ndim == 1 and a.size > 0 and bool(np.isfinite(a).all())


def record_ok(rec, need_dino: bool = True) -> bool:
    if not isinstance(rec, PanelRecord) or not isinstance(rec.text, str) or not isinstance(rec.low, dict):
        return False
    if not (_finite_vec(rec.img_emb) and _finite_vec(rec.txt_emb)):
        return False
    if need_dino:
        p = getattr(rec, "dino_patches", None)
        if not _finite_vec(getattr(rec, "dino_cls", None)) or not isinstance(p, np.ndarray) or p.ndim != 2:
            return False
        if not np.isfinite(p.astype(np.float32)).all():
            return False
    return True


def load_record(panel: str) -> PanelRecord:
    rec = load_valid_pickle(cache_path(panel), lambda r: record_ok(r, need_dino=False))
    if rec is None:
        raise FileNotFoundError(f"no valid cached record for {panel}; run scripts/extract_features.py")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DATA_DIR / "manifest.csv"))
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--chunk", type=int, default=32)
    args = ap.parse_args()
    stop = install_stop_handler()
    (CACHE_DIR / "panels").mkdir(parents=True, exist_ok=True)
    panels = sorted({r[k] for r in csv.DictReader(open(args.manifest)) for k in ("panel_a", "panel_b")})

    new, upgrade = [], []
    for p in panels:
        rec = load_valid_pickle(cache_path(p), lambda r: record_ok(r, need_dino=False))
        if rec is None:
            new.append(p)  # missing or invalid -> recompute
        elif not record_ok(rec, need_dino=True):
            upgrade.append(p)  # valid but lacks DINO features
    print(f"{len(panels)} panels: {len(new)} to compute, {len(upgrade)} need DINO features, "
          f"{len(panels) - len(new) - len(upgrade)} valid in cache", flush=True)
    if not new and not upgrade:
        return
    dino = DinoEncoder()
    enc = ClipEncoder() if new else None

    failures = []

    def prep(p):
        img = Image.open(PANELS_DIR / p).convert("RGB")
        try:
            text = cached_ocr(p, img)
        except Exception as e:  # OCR failure: skip this panel (no partial record), report at the end
            failures.append((p, f"{type(e).__name__}: {str(e)[:120]}"))
            return p, None, None, None
        return p, img, text, lowlevel_single(img)

    done = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for i in range(0, len(new), args.chunk):
            if stop.requested:
                exit_interrupted(f"{done}/{len(new) + len(upgrade)} panels done")
            for p, img, text, low in ex.map(prep, new[i:i + args.chunk]):
                if img is None:
                    continue
                rec = PanelRecord(enc.encode_images([img])[0], enc.encode_texts([text])[0], text, low)
                c, pt = dino.encode([img])
                rec.dino_cls, rec.dino_patches = c[0], pt[0]
                atomic_pickle(cache_path(p), rec)
                done += 1
                test_unit_delay()
            print(f"new {min(i + args.chunk, len(new))}/{len(new)}", flush=True)
    for i, p in enumerate(upgrade):
        if stop.requested:
            exit_interrupted(f"{done}/{len(new) + len(upgrade)} panels done")
        rec = load_record(p)
        c, pt = dino.encode([Image.open(PANELS_DIR / p).convert("RGB")])
        rec.dino_cls, rec.dino_patches = c[0], pt[0]
        atomic_pickle(cache_path(p), rec)
        done += 1
        test_unit_delay()
    if failures:
        for p, e in failures:
            print(f"FAILED {p}: {e}", file=sys.stderr)
        print(f"{len(failures)} panels failed (no record written); re-run to retry", file=sys.stderr)
        sys.exit(1)
    print("done")


if __name__ == "__main__":
    main()
