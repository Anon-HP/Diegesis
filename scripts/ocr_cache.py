"""Pre-compute Tesseract OCR text for every panel in data/manifest.csv (cache: <workspace>/cache/ocr/).

Graceful stop / resume: the unit of work is one panel, processed in small parallel chunks. Each
panel's text is written atomically. On SIGINT/SIGTERM the chunk in flight finishes and the script
exits with code 130. A re-run skips panels that already have a cache file. Empty text is a valid
result (a panel without lettering). A failed or timed-out tesseract run (120 s, one retry at 240 s) is never
cached: it is listed at the end, the script exits 1, and a re-run retries it.
"""
import argparse
import csv
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition.ocr import ocr_image  # noqa: E402
from transition.paths import CACHE_DIR, DATA_DIR, PANELS_DIR  # noqa: E402
from transition.runctl import atomic_write_text, exit_interrupted, install_stop_handler, test_unit_delay  # noqa: E402


CACHE_TIMEOUT = 120  # seconds; generous because batch jobs share the CPU


def ocr_path(panel: str) -> Path:
    return CACHE_DIR / "ocr" / (panel.replace("/", "_") + ".txt")


def cached_ocr(panel: str, img=None) -> str:
    p = ocr_path(panel)
    if p.is_file():  # written atomically, so presence means complete
        return p.read_text(encoding="utf-8")
    img = img if img is not None else Image.open(PANELS_DIR / panel).convert("RGB")
    try:
        t = ocr_image(img, timeout=CACHE_TIMEOUT, strict=True)
    except subprocess.TimeoutExpired:  # usually CPU contention: retry once before giving up
        t = ocr_image(img, timeout=CACHE_TIMEOUT * 2, strict=True)
    atomic_write_text(p, t)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="?", default=str(DATA_DIR / "manifest.csv"))
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    stop = install_stop_handler()
    panels = sorted({r[k] for r in csv.DictReader(open(args.manifest)) for k in ("panel_a", "panel_b")})
    todo = [p for p in panels if not ocr_path(p).is_file()]
    print(len(panels), "panels;", len(todo), "to OCR", flush=True)

    failures = []

    def work(p):
        try:
            cached_ocr(p)
        except Exception as e:  # never cached; reported at the end, retried on the next run
            failures.append((p, f"{type(e).__name__}: {str(e)[:120]}"))
        test_unit_delay()

    chunk = args.workers * 2
    with ThreadPoolExecutor(args.workers) as ex:
        for i in range(0, len(todo), chunk):
            if stop.requested:
                exit_interrupted(f"{i}/{len(todo)} panels OCR'd")
            list(ex.map(work, todo[i:i + chunk]))  # whole chunk completes before the next stop check
            print(f"{min(i + chunk, len(todo))}/{len(todo)}", flush=True)
    if failures:
        for p, e in failures:
            print(f"FAILED {p}: {e}", file=sys.stderr)
        print(f"{len(failures)} panels failed (not cached); re-run to retry", file=sys.stderr)
        sys.exit(1)
    print("done")


if __name__ == "__main__":
    main()
