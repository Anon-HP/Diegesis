"""Compute the CLIP image cosine for every pair in data/pair_index.csv.gz (used only for sampling strata).

Output: <workspace>/cache/pair_clipcos.csv (pair_id, cos). Panel embeddings are cached per book in
<workspace>/cache/clip_img/<book>.npz.

Graceful stop / resume: the unit of work is one book. Each book's npz is written atomically. A cached
npz is reused only if it loads, holds exactly this book's panel list and has finite embeddings of the
right shape. Otherwise it is recomputed. On SIGINT/SIGTERM the current book finishes and the script
exits with code 130, without writing pair_clipcos.csv. That file is written atomically once every
book is done.
"""
import argparse
import csv
import gzip
import io
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition.features import ClipEncoder  # noqa: E402
from transition.paths import CACHE_DIR, DATA_DIR, PANELS_DIR  # noqa: E402
from transition.runctl import (atomic_savez, atomic_write_text, exit_interrupted, install_stop_handler,  # noqa: E402
                               load_valid_npz, test_unit_delay)


def valid_book_cache(f: Path, panels: list[str]):
    z = load_valid_npz(f, {"panels": (len(panels),), "emb": (len(panels),)})
    if z is None or z["emb"].ndim != 2 or list(z["panels"]) != panels:
        return None
    return z["emb"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=str(DATA_DIR / "pair_index.csv.gz"))
    ap.add_argument("--out", default=str(CACHE_DIR / "pair_clipcos.csv"))
    args = ap.parse_args()
    stop = install_stop_handler()

    rows = list(csv.DictReader(gzip.open(args.index, "rt")))
    by_book = defaultdict(set)
    for r in rows:
        by_book[r["book"]].update([r["panel_a"], r["panel_b"]])
    out_dir = CACHE_DIR / "clip_img"
    out_dir.mkdir(parents=True, exist_ok=True)

    emb, todo = {}, []
    for book, panels in sorted(by_book.items()):
        panels = sorted(panels)
        E = valid_book_cache(out_dir / f"{book}.npz", panels)
        if E is None:
            todo.append((book, panels))
        else:
            emb.update(zip(panels, E))
    print(f"{len(by_book)} books: {len(by_book) - len(todo)} valid in cache, {len(todo)} to compute", flush=True)

    if todo:
        enc = ClipEncoder()
        load = lambda p: Image.open(PANELS_DIR / p).convert("RGB")  # noqa: E731
        with ThreadPoolExecutor(8) as ex:
            for bi, (book, panels) in enumerate(todo):
                if stop.requested:
                    exit_interrupted(f"{bi}/{len(todo)} remaining books computed")
                imgs = list(ex.map(load, panels))
                E = np.concatenate([enc.encode_images(imgs[i:i + 32]) for i in range(0, len(imgs), 32)])
                test_unit_delay()
                atomic_savez(out_dir / f"{book}.npz", panels=np.array(panels), emb=E)
                emb.update(zip(panels, E))
                print(f"book {bi + 1}/{len(todo)} {book}: {len(panels)} panels", flush=True)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["pair_id", "cos"])
    for r in rows:
        w.writerow([r["pair_id"], f"{float(emb[r['panel_a']] @ emb[r['panel_b']]):.4f}"])
    atomic_write_text(args.out, buf.getvalue())
    print("done", len(rows), "->", args.out)


if __name__ == "__main__":
    main()
