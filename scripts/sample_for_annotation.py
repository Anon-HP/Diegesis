"""Choose panel pairs to annotate, using stratified sampling to enrich the rare classes.

Each sampled pair records the stratum it came from. Results on the `random` stratum are
reported separately, because that stratum follows the natural class distribution.

Strata:
  random       uniform over consecutive pairs on the same page
  crosspage    the last panel of page p followed by the first panel of page p+1
  cue          COMICS-provided OCR of panel B contains a time/place caption cue (candidate metadata only)
  lowsim       low thumbnail correlation and a large colour change (scene/subject candidates)
  highsim      very high thumbnail correlation (moment/aspect candidates)
Also writes composite images (A | B) for annotators to view.

Graceful stop / resume: sampling is deterministic (seeded), so a re-run picks the same pairs. The unit
of work is one composite image, written atomically and reused only if it decodes. On SIGINT/SIGTERM the
current composite finishes and the script exits with code 130 before writing any sample/batch CSV. The
CSVs are written atomically once every composite exists.
"""
import argparse
import csv
import gzip
import random
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition.features import lowlevel_pair, lowlevel_single  # noqa: E402
from transition.paths import ANN_DIR, CACHE_DIR, COMICS_DIR, DATA_DIR, PANELS_DIR, WORKSPACE  # noqa: E402
from transition.runctl import atomic_open, exit_interrupted, install_stop_handler, test_unit_delay  # noqa: E402

CUES = ("later", "meanwhile", "next day", "next morning", "that night", "that evening", "elsewhere",
        "back at", "hours", "the next", "soon", "miles")


def load_cue_pairs(ocr_csv: Path, books: set[str]) -> set[tuple[str, int, int]]:
    """(book, page, panel) whose COMICS OCR text contains a cue."""
    hits = set()
    with open(ocr_csv, newline="", encoding="utf-8", errors="ignore") as fh:
        r = csv.reader(fh)
        next(r)
        for row in r:
            if row[0] not in books or len(row) < 6:
                continue
            t = row[5].lower()
            if any(c in t for c in CUES):
                hits.add((row[0], int(row[1]), int(row[2])))
    return hits


def composite(a: Path, b: Path, out: Path, h: int = 520):
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    ia = ia.resize((max(1, int(ia.width * h / ia.height)), h))
    ib = ib.resize((max(1, int(ib.width * h / ib.height)), h))
    gap, top = 40, 34
    W = ia.width + ib.width + gap
    canvas = Image.new("RGB", (W, h + top), (255, 255, 255))
    canvas.paste(ia, (0, top))
    canvas.paste(ib, (ia.width + gap, top))
    d = ImageDraw.Draw(canvas)
    d.text((6, 4), "PANEL A (first)", fill=(200, 0, 0), font_size=24)
    d.text((ia.width + gap + 6, 4), "PANEL B (next)", fill=(0, 0, 200), font_size=24)
    d.line([(ia.width + gap // 2, 0), (ia.width + gap // 2, h + top)], fill=(0, 0, 0), width=3)
    if W > 1400:
        canvas = canvas.resize((1400, int(canvas.height * 1400 / W)))
    with atomic_open(out, "wb") as fh:
        canvas.save(fh, format="JPEG", quality=88)


def composite_ok(path: Path) -> bool:
    try:
        with Image.open(path) as im:
            im.load()  # full decode: catches truncated files
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=480)
    ap.add_argument("--per-book", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=40)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--exclude", default="", help="csv with pair_id column to skip (already sampled)")
    ap.add_argument("--tag", default="r1")
    ap.add_argument("--quota", default="0.45,0.15,0.15,0.12,0.13", help="random,crosspage,cue,lowsim,highsim")
    ap.add_argument("--use-clip", action="store_true", help="use cache/pair_clipcos.csv for sim strata")
    ap.add_argument("--tail", type=float, default=0.1, help="fraction defining low/high sim strata")
    args = ap.parse_args()
    stop = install_stop_handler()
    rng = random.Random(args.seed)

    rows = list(csv.DictReader(gzip.open(DATA_DIR / "pair_index.csv.gz", "rt")))
    skip = set()
    if args.exclude:
        for p in args.exclude.split(","):
            skip |= {r["pair_id"] for r in csv.DictReader(open(p))}
    rows = [r for r in rows if r["pair_id"] not in skip]
    books = {r["book"] for r in rows}
    cue = load_cue_pairs(COMICS_DIR / "COMICS_ocr_file.csv", books)

    within = [r for r in rows if r["cross_page"] == "0"]
    cross = [r for r in rows if r["cross_page"] == "1"]
    cue_rows = [r for r in rows if (r["book"], int(r["page_b"]), int(r["panel_b"].split("_")[-1].split(".")[0])) in cue]

    clipcos = CACHE_DIR / "pair_clipcos.csv"
    if args.use_clip and clipcos.exists():
        cos = {r["pair_id"]: float(r["cos"]) for r in csv.DictReader(open(clipcos))}
        sims = sorted(((cos[r["pair_id"]], r) for r in within if r["pair_id"] in cos), key=lambda x: x[0])
        print("using CLIP cosine strata over", len(sims), "pairs")
    else:
        # Low-level similarity on a random subset (cheap) for lowsim/highsim strata.
        probe = rng.sample(within, min(3000, len(within)))
        sims = []
        for r in probe:
            if stop.requested:
                exit_interrupted("during similarity probe; nothing written")
            a = lowlevel_single(Image.open(PANELS_DIR / r["panel_a"]))
            b = lowlevel_single(Image.open(PANELS_DIR / r["panel_b"]))
            v = lowlevel_pair(a, b)
            sims.append((v[0] - v[1], r))  # corr minus hist distance
        sims.sort(key=lambda x: x[0])
    k = max(1, int(len(sims) * args.tail))
    lowsim = [r for _, r in sims[:k]]
    highsim = [r for _, r in sims[-k:]]

    quota = dict(zip(["random", "crosspage", "cue", "lowsim", "highsim"], map(float, args.quota.split(","))))
    pools = {"random": within, "crosspage": cross, "cue": cue_rows, "lowsim": lowsim, "highsim": highsim}
    per_book = defaultdict(int)
    chosen, seen = [], set()
    for s, frac in quota.items():
        pool = pools[s][:]
        rng.shuffle(pool)
        want = int(round(frac * args.n))
        got = 0
        for r in pool:
            if got >= want:
                break
            if r["pair_id"] in seen or per_book[r["book"]] >= args.per_book:
                continue
            seen.add(r["pair_id"])
            per_book[r["book"]] += 1
            chosen.append({**r, "stratum": s})
            got += 1
        print(f"{s}: {got}/{want} (pool {len(pool)})")
    rng.shuffle(chosen)

    comp_dir = WORKSPACE / "composites"
    comp_dir.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for i, r in enumerate(chosen):
        cp = comp_dir / f"{r['pair_id']}.jpg"
        if not composite_ok(cp):
            if stop.requested:
                exit_interrupted(f"{i}/{len(chosen)} composites ready; no CSVs written yet")
            composite(PANELS_DIR / r["panel_a"], PANELS_DIR / r["panel_b"], cp)
            test_unit_delay()
        out_rows.append({"pair_id": r["pair_id"], "book": r["book"], "split": r["split"],
                         "panel_a": r["panel_a"], "panel_b": r["panel_b"], "cross_page": r["cross_page"],
                         "stratum": r["stratum"], "composite": cp.relative_to(WORKSPACE).as_posix(),
                         "batch": f"{args.tag}_{i // args.batch_size:02d}"})
    out = ANN_DIR / f"sample_{args.tag}.csv"
    for b in sorted({r["batch"] for r in out_rows}):  # batches first; the sample CSV marks completion
        with atomic_open(ANN_DIR / "batches" / f"{b}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["pair_id", "composite"])
            w.writeheader()
            w.writerows({"pair_id": r["pair_id"], "composite": r["composite"]} for r in out_rows if r["batch"] == b)
    with atomic_open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    print(f"{len(out_rows)} pairs, books={len(per_book)} -> {out}")


if __name__ == "__main__":
    main()
