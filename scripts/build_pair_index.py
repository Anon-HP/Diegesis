"""Build the index of consecutive panel pairs from the extracted COMICS panels.

Reading order: COMICS stores panels as raw_panel_images/<book>/<page>_<panel>.jpg. Within a book
we sort by the integers (page, panel). Panel order inside a page comes from the COMICS
authors' own ordering (not independently verified; annotators flag broken pairs as valid=0).

Exclusions: the archive's last, truncated book folder (--partial-book), pages listed in
predadpages.txt (predicted ads), page 0 (usually the cover), and tiny crops.

Split: deterministic by book id (hash), so no book appears in more than one split.

Graceful stop / resume: the unit of work is one book. Each finished book's pairs are appended to a
progress log (cache/state/pair_index.<fingerprint>.jsonl). On SIGINT/SIGTERM the current book
finishes and the script exits with code 130. Re-running the same command skips logged books. The
final index is written atomically, only when every book is done, and the log is then deleted.
"""
import argparse
import csv
import gzip
import hashlib
import io
import os
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition.paths import COMICS_DIR, DATA_DIR, PANELS_DIR, STATE_DIR  # noqa: E402
from transition.runctl import (JsonlCheckpoint, atomic_open, exit_interrupted, fingerprint,  # noqa: E402
                               install_stop_handler, test_unit_delay)

FNAME = re.compile(r"^(\d+)_(\d+)\.jpg$")
HEADER = ["pair_id", "book", "split", "panel_a", "panel_b", "page_a", "page_b", "cross_page"]


def book_split(book: str) -> str:
    h = int(hashlib.sha1(f"cpt-split-v1:{book}".encode()).hexdigest(), 16) % 100
    if h < 20:
        return "test"
    if h < 30:
        return "val"
    return "train"


def book_pairs(bdir: Path, ads: set, min_side: int) -> tuple[list[list], dict]:
    book = bdir.name
    stats = {"tiny": 0, "ads": 0, "cover": 0}
    panels, maxpan = [], {}
    for f in os.listdir(bdir):
        m = FNAME.match(f)
        if not m:
            continue
        page, pan = int(m.group(1)), int(m.group(2))
        maxpan[page] = max(maxpan.get(page, -1), pan)
        if page == 0:
            stats["cover"] += 1
            continue
        if (book, page) in ads:
            stats["ads"] += 1
            continue
        try:
            with Image.open(bdir / f) as im:
                if min(im.size) < min_side:
                    stats["tiny"] += 1
                    continue
        except Exception:
            continue
        panels.append((page, pan, f))
    panels.sort()
    out = []
    for (pa, na, fa), (pb, nb, fb) in zip(panels, panels[1:]):
        if pb - pa > 1:
            continue  # skip across removed pages
        if pb == pa and nb != na + 1:
            continue  # a panel in between was filtered out -> not consecutive
        if pb == pa + 1 and (nb != 0 or na != maxpan[pa]):
            continue
        out.append([f"{book}_{pa}_{na}__{pb}_{nb}", book, book_split(book), f"{book}/{fa}", f"{book}/{fb}",
                    pa, pb, int(pb != pa)])
    return out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panels", default=str(PANELS_DIR))
    ap.add_argument("--ads", default=str(COMICS_DIR / "predadpages.txt"))
    ap.add_argument("--out", default=str(DATA_DIR / "pair_index.csv.gz"))
    ap.add_argument("--min-side", type=int, default=120)
    ap.add_argument("--partial-book", default="",
                    help="book id of the archive's last (truncated) folder; find it with: tar -tzf part.tar.gz | tail -1")
    args = ap.parse_args()
    stop = install_stop_handler()

    ads = set()
    if Path(args.ads).is_file():
        for line in open(args.ads):
            line = line.strip()
            if "---" in line:
                b, p = line.split("---")
                ads.add((b, int(p)))
    books = sorted((d for d in Path(args.panels).iterdir() if d.is_dir() and d.name != args.partial_book),
                   key=lambda d: (0, int(d.name), "") if d.name.isdigit() else (1, 0, d.name))
    if args.partial_book:
        print(f"excluding partial book {args.partial_book}")

    key = fingerprint(os.path.abspath(args.panels), args.min_side, args.partial_book, len(ads), "v2")
    ckpt = JsonlCheckpoint(STATE_DIR / f"pair_index.{key}.jsonl", key)
    done = ckpt.load()

    def is_done(bdir):  # a book's file count is checked so that re-extracted / grown books are redone
        rec = done.get(bdir.name)
        return (isinstance(rec, dict) and isinstance(rec.get("rows"), list)
                and rec.get("nfiles") == len(os.listdir(bdir)))

    print(f"{len(books)} books; {sum(map(is_done, books))} already done (resuming)", flush=True)
    for i, bdir in enumerate(books):
        if stop.requested:
            exit_interrupted(f"{sum(map(is_done, books))}/{len(books)} books done")
        if is_done(bdir):
            continue
        nfiles = len(os.listdir(bdir))
        rows, stats = book_pairs(bdir, ads, args.min_side)
        test_unit_delay()
        rec = {"nfiles": nfiles, "rows": rows, "stats": stats}
        ckpt.append(bdir.name, rec)
        done[bdir.name] = rec
        print(f"book {i + 1}/{len(books)} {bdir.name}: {len(rows)} pairs", flush=True)

    totals = {"tiny": 0, "ads": 0, "cover": 0}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    n_pairs = 0
    for bdir in books:
        rec = done[bdir.name]
        w.writerows(rec["rows"])
        n_pairs += len(rec["rows"])
        for k in totals:
            totals[k] += rec["stats"].get(k, 0)
    with atomic_open(args.out, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(buf.getvalue().encode())
    ckpt.remove()
    print(f"books={len(books)} pairs={n_pairs} filtered={totals} -> {args.out}")


if __name__ == "__main__":
    main()
