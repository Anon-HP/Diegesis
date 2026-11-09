"""Interrupt-and-resume tests for the long-running scripts, run against a throwaway workspace.

Each test starts a script as a subprocess, slowed per unit with CPT_TEST_UNIT_DELAY, and sends
SIGINT or SIGTERM once the first unit is done. It then checks four things: exit code 130, no
final output, and only complete artifacts on disk. The same command is re-run to check that it
resumes without redoing finished units and produces the same result as an uninterrupted run.
Tests that load CLIP/DINOv2 are marked e2e (they need the cached weights; GPU optional).
"""
import csv
import gzip
import http.server
import os
import pickle
import signal
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
sys.path.insert(0, str(ROOT / "src"))
from transition.paths import PANELS_DIR as REAL_PANELS, WORKSPACE as REAL_WS  # noqa: E402

REAL_HF = str(REAL_WS / "hf_cache")


def make_workspace(tmp: Path, n_books=8, n_pages=3, n_panels=4, text=False):
    panels = tmp / "ws" / "data" / "comics" / "panels_dl" / "raw_panel_images"
    rng = np.random.default_rng(0)
    for b in range(100, 100 + n_books):
        d = panels / str(b)
        d.mkdir(parents=True)
        for p in range(n_pages + 1):  # page 0 = cover (excluded by the indexer)
            for k in range(n_panels):
                im = Image.new("RGB", (220, 180), tuple(int(x) for x in rng.integers(0, 255, 3)))
                dr = ImageDraw.Draw(im)
                dr.ellipse([20 + k * 10, 20, 120 + k * 10, 140], fill=tuple(int(x) for x in rng.integers(0, 255, 3)))
                if text:
                    dr.rectangle([5, 5, 215, 45], fill="white")
                    dr.text((10, 10), "LATER THAT NIGHT", fill="black", font_size=22)
                im.save(d / f"{p}_{k}.jpg")
    comics = tmp / "ws" / "data" / "comics"
    (comics / "predadpages.txt").write_text("")
    (comics / "COMICS_ocr_file.csv").write_text(
        "comic_no,page_no,panel_no,textbox_no,dialog_or_narration,text,x1,y1,x2,y2\n100,1,1,0,1,later that day,0,0,1,1\n")
    env = dict(os.environ, CPT_WORKSPACE=str(tmp / "ws"), CPT_DATA_DIR=str(tmp / "data"),
               CPT_ANN_DIR=str(tmp / "ann"), CPT_EXP_DIR=str(tmp / "exp"), CPT_MODELS_DIR=str(tmp / "models"),
               HF_HOME=REAL_HF, PYTHONUNBUFFERED="1")
    for k in ("data", "ann/batches", "exp", "models"):
        (tmp / k).mkdir(parents=True, exist_ok=True)
    return env


def run(cmd, env, **kw):
    return subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=ROOT, timeout=600, **kw)


def run_and_interrupt(cmd, env, ready, sig=signal.SIGINT, delay="0.4"):
    """Start cmd, wait until ready(line) is true for a stdout line, send `sig`, wait for exit."""
    e = dict(env, CPT_TEST_UNIT_DELAY=delay)
    p = subprocess.Popen(cmd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
    lines = []
    for line in p.stdout:
        lines.append(line)
        if ready(line):
            p.send_signal(sig)
            break
    out, err = p.communicate(timeout=600)
    return p.returncode, "".join(lines) + out, err


def read_index(path):
    with gzip.open(path, "rt") as fh:
        return list(csv.reader(fh))


# ---------------------------------------------------------------- build_pair_index (unit: book)
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_build_pair_index_interrupt_resume(tmp_path, sig):
    env = make_workspace(tmp_path)
    out = tmp_path / "data" / "pair_index.csv.gz"
    cmd = [PY, "scripts/build_pair_index.py"]
    rc, so, se = run_and_interrupt(cmd, env, lambda l: l.startswith("book "), sig)
    assert rc == 130, se
    assert "stop requested" in se and "interrupted cleanly" in se
    assert not out.exists(), "final index must not exist after an interrupted run"
    state = list((tmp_path / "ws" / "cache" / "state").glob("pair_index.*.jsonl"))
    assert len(state) == 1
    n_done = sum(1 for _ in open(state[0]))
    assert 1 <= n_done < 8

    r = run(cmd, env)
    assert r.returncode == 0, r.stderr
    assert f"{n_done} already done" in r.stdout
    assert r.stdout.count("\nbook ") + r.stdout.startswith("book ") == 8 - n_done  # no book redone
    assert not state[0].exists(), "progress log is removed after successful completion"
    resumed = read_index(out)

    out.unlink()
    r = run(cmd, env)  # fresh uninterrupted run for comparison
    assert r.returncode == 0
    assert read_index(out) == resumed
    assert len(resumed) == 1 + 8 * (3 * 3 + 2)  # header + per book: 3 pages x 3 within + 2 cross-page


def test_build_pair_index_ignores_torn_progress_line(tmp_path):
    env = make_workspace(tmp_path, n_books=3)
    cmd = [PY, "scripts/build_pair_index.py"]
    rc, _, _ = run_and_interrupt(cmd, env, lambda l: l.startswith("book "))
    assert rc == 130
    state = next((tmp_path / "ws" / "cache" / "state").glob("pair_index.*.jsonl"))
    with open(state, "a") as fh:
        fh.write('{"_key": "x", "unit": "102", "data": {"rows": [[')  # simulated crash mid-append
    r = run(cmd, env)
    assert r.returncode == 0, r.stderr
    assert len(read_index(tmp_path / "data" / "pair_index.csv.gz")) == 1 + 3 * 11


# ---------------------------------------------------------------- ocr_cache (unit: panel chunk)
def test_ocr_cache_interrupt_resume(tmp_path):
    """OCR'd text cached during an interrupted run must equal an uninterrupted OCR of the same panel
    (a terminal SIGINT must not kill tesseract mid-panel and leave empty/partial text behind)."""
    import shutil

    from transition.ocr import ocr_image

    real = REAL_PANELS / "1406"
    if not real.is_dir():
        pytest.skip("real lettered panels needed (synthetic captions are not read reliably by tesseract)")
    env = make_workspace(tmp_path, n_books=2, n_pages=2, n_panels=4)
    src = sorted(real.glob("*.jpg"))[10:26]  # read-only copy of 16 real panels
    dst = sorted((tmp_path / "ws" / "data" / "comics" / "panels_dl" / "raw_panel_images").glob("*/[12]_*.jpg"))
    for a, b in zip(src, dst):
        shutil.copy(a, b)
    assert run([PY, "scripts/build_pair_index.py"], env).returncode == 0
    rows = read_index(tmp_path / "data" / "pair_index.csv.gz")
    man = tmp_path / "data" / "m.csv"
    with open(man, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["panel_a", "panel_b"])
        w.writerows([r[3], r[4]] for r in rows[1:])
    cmd = [PY, "scripts/ocr_cache.py", str(man), "--workers", "2"]
    rc, so, se = run_and_interrupt(cmd, env, lambda l: "/" in l and l[0].isdigit(), signal.SIGINT, delay="0.5")
    assert rc == 130, se
    ocr_dir = tmp_path / "ws" / "cache" / "ocr"
    done = sorted(ocr_dir.glob("*.txt"))
    assert 0 < len(done) < 16
    assert not list(ocr_dir.glob(".*tmp*")), "no temp files left behind"
    panels_root = tmp_path / "ws" / "data" / "comics" / "panels_dl" / "raw_panel_images"
    for f in done:
        book, fname = f.name[:-4].split("_", 1)
        fresh = ocr_image(Image.open(panels_root / book / fname).convert("RGB"), strict=True)
        assert f.read_text() == fresh, f"cached OCR for {f.name} differs from an uninterrupted run"
    assert any(f.read_text().strip() for f in done), "fixture should contain lettering"
    r = run(cmd, env)
    assert r.returncode == 0, r.stderr
    assert f"{16 - len(done)} to OCR" in r.stdout
    assert len(list(ocr_dir.glob("*.txt"))) == 16


# ---------------------------------------------------------------- train.py (unit: CV fold)
def _fake_records(tmp_path, env, n_pairs=60):
    from transition.features import PanelRecord
    from transition.labels import LABELS

    rng = np.random.default_rng(1)
    cache = tmp_path / "ws" / "cache" / "panels"
    cache.mkdir(parents=True)
    rows = []
    for i in range(n_pairs):
        book = str(100 + i % 12)
        split = "test" if i % 12 in (0, 1) else "train"
        label = LABELS[i % 4]
        pa, pb = f"{book}/{i}_0.jpg", f"{book}/{i}_1.jpg"
        for p in (pa, pb):
            rec = PanelRecord(rng.normal(size=16).astype(np.float32), rng.normal(size=16).astype(np.float32),
                              "LATER" if label == "scene-to-scene" else "", {
                                  "thumb": rng.normal(size=1024).astype(np.float32),
                                  "hist": np.abs(rng.normal(size=24)).astype(np.float32),
                                  "edge": 0.1, "aspect": 0.0, "area": 10.0},
                              rng.normal(size=8).astype(np.float32), rng.normal(size=(16, 8)).astype(np.float16))
            rec.img_emb /= np.linalg.norm(rec.img_emb)
            rec.txt_emb /= np.linalg.norm(rec.txt_emb)
            with open(cache / (p.replace("/", "_") + ".pkl"), "wb") as fh:
                pickle.dump(rec, fh)
        rows.append({"pair_id": f"p{i}", "book": book, "split": split, "panel_a": pa, "panel_b": pb,
                     "stratum": "random", "valid": "1", "label": label, "label_source": "llm",
                     "confidence": "high"})
    man = tmp_path / "data" / "manifest.csv"
    with open(man, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return man


def test_train_interrupt_resume_and_corrupt_checkpoint(tmp_path):
    env = make_workspace(tmp_path, n_books=1, n_pages=1, n_panels=2)
    man = _fake_records(tmp_path, env)
    cmd = [PY, "scripts/train.py", "--manifest", str(man), "--exp", "t", "--folds", "3",
           "--subsets", "match+low+cue,clipdiff+low+cue", "--models", "logreg,logreg_strong", "--final-test"]
    e = dict(env, CPT_TEST_UNIT_DELAY="0.5")
    p = subprocess.Popen(cmd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
    ck_root = tmp_path / "exp" / "t_ckpt"
    t0 = time.time()
    while not list(ck_root.glob("*/*.npz")) and time.time() - t0 < 120:
        time.sleep(0.05)
    p.send_signal(signal.SIGTERM)
    _, se = p.communicate(timeout=300)
    assert p.returncode == 130, se
    assert not (tmp_path / "exp" / "t.json").exists() and not (tmp_path / "models" / "head_dev.joblib").exists()
    ck = sorted(ck_root.glob("*/*.npz"))
    assert 1 <= len(ck) < 12
    # Corrupt one checkpoint: it must be detected and recomputed, not trusted.
    ck[0].write_bytes(ck[0].read_bytes()[:-30])
    r = run(cmd, env)
    assert r.returncode == 0, r.stderr
    assert f"CV folds: {len(ck) - 1} reused from checkpoints, {12 - len(ck) + 1} computed" in r.stdout
    resumed = r.stdout
    # A second identical run reuses everything and gives identical CV/test numbers.
    r2 = run(cmd, env)
    assert "CV folds: 12 reused from checkpoints, 0 computed" in r2.stdout
    strip = lambda s: [l for l in s.splitlines() if "macroF1" in l]  # noqa: E731
    assert strip(r2.stdout) == strip(resumed)
    assert (tmp_path / "exp" / "t.json").exists() and (tmp_path / "models" / "head_dev.joblib").exists()


# ---------------------------------------------------------------- sample_for_annotation (unit: composite)
def test_sampler_interrupt_resume(tmp_path):
    env = make_workspace(tmp_path, n_books=6, n_pages=3, n_panels=4)
    assert run([PY, "scripts/build_pair_index.py"], env).returncode == 0
    cmd = [PY, "scripts/sample_for_annotation.py", "--n", "20", "--per-book", "6", "--batch-size", "10",
           "--tag", "t"]
    e = dict(env, CPT_TEST_UNIT_DELAY="0.3")
    p = subprocess.Popen(cmd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
    comp = tmp_path / "ws" / "composites"
    t0 = time.time()
    while len(list(comp.glob("*.jpg"))) < 2 and time.time() - t0 < 120:
        time.sleep(0.05)
    p.send_signal(signal.SIGINT)
    _, se = p.communicate(timeout=120)
    assert p.returncode == 130, se
    assert not (tmp_path / "ann" / "sample_t.csv").exists()
    assert not list((tmp_path / "ann" / "batches").glob("t_*.csv"))
    n_first = len(list(comp.glob("*.jpg")))
    # Corrupt one composite: it must be regenerated.
    victim = sorted(comp.glob("*.jpg"))[0]
    victim.write_bytes(victim.read_bytes()[:200])
    r = run(cmd, env)
    assert r.returncode == 0, r.stderr
    rows = list(csv.DictReader(open(tmp_path / "ann" / "sample_t.csv")))
    assert len(rows) >= n_first
    for row in rows:
        assert not Path(row["composite"]).is_absolute()
        with Image.open(tmp_path / "ws" / row["composite"]) as im:
            im.load()


# ---------------------------------------------------------------- fetch_comics_part.sh (unit: verified chunk)
class _RangeHandler(http.server.BaseHTTPRequestHandler):
    data = b""

    def log_message(self, *a):
        pass

    def do_GET(self):
        rng = self.headers.get("Range", "")
        start, end = rng.replace("bytes=", "").split("-")
        start, end = int(start), min(int(end), len(self.data) - 1)
        self.send_response(206)
        self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.data)}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        try:
            for i in range(start, end + 1, 4096):  # throttled so the test can interrupt mid-chunk
                self.wfile.write(self.data[i:min(i + 4096, end + 1)])
                self.wfile.flush()
                time.sleep(0.01)
        except (BrokenPipeError, ConnectionResetError):
            pass


def test_fetch_script_interrupt_resume_gives_exact_prefix(tmp_path):
    data = np.random.default_rng(3).integers(0, 256, 600_000, dtype=np.uint8).tobytes()
    _RangeHandler.data = data
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _RangeHandler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/a.tar.gz"
    out = tmp_path / "part.bin"
    target = 500_000
    try:
        p = subprocess.Popen(["bash", str(ROOT / "scripts" / "fetch_comics_part.sh"), str(target), str(out), url],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        chunk = Path(str(out) + ".chunk")
        t0 = time.time()
        while (not chunk.exists() or chunk.stat().st_size < 50_000) and time.time() - t0 < 60:
            time.sleep(0.02)
        p.send_signal(signal.SIGINT)
        so, se = p.communicate(timeout=60)
        assert p.returncode == 130, se
        got = out.read_bytes()
        assert 0 < len(got) < target
        assert got == data[:len(got)], "interrupted output must be an exact prefix"
        assert not chunk.exists()
        r = subprocess.run(["bash", str(ROOT / "scripts" / "fetch_comics_part.sh"), str(target), str(out), url],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        assert out.read_bytes() == data[:target]
    finally:
        srv.shutdown()


# ---------------------------------------------------------------- encoders (heavy, e2e)
@pytest.mark.e2e
def test_mine_clip_similarity_interrupt_resume(tmp_path):
    env = make_workspace(tmp_path, n_books=4, n_pages=1, n_panels=3)
    assert run([PY, "scripts/build_pair_index.py"], env).returncode == 0
    cmd = [PY, "scripts/mine_clip_similarity.py"]
    rc, so, se = run_and_interrupt(cmd, env, lambda l: l.startswith("book "), signal.SIGINT, delay="2")
    assert rc == 130, se
    out = tmp_path / "ws" / "cache" / "pair_clipcos.csv"
    assert not out.exists()
    npz = sorted((tmp_path / "ws" / "cache" / "clip_img").glob("*.npz"))
    assert 1 <= len(npz) < 4
    npz[0].write_bytes(npz[0].read_bytes()[:100])  # torn file -> must be recomputed
    r = run(cmd, env)
    assert r.returncode == 0, r.stderr
    assert f"{len(npz) - 1} valid in cache, {4 - len(npz) + 1} to compute" in r.stdout
    assert len(list(csv.reader(open(out)))) == 1 + 4 * 2


@pytest.mark.e2e
def test_extract_features_interrupt_resume(tmp_path):
    env = make_workspace(tmp_path, n_books=2, n_pages=1, n_panels=4, text=True)
    assert run([PY, "scripts/build_pair_index.py"], env).returncode == 0
    rows = read_index(tmp_path / "data" / "pair_index.csv.gz")
    man = tmp_path / "data" / "m.csv"
    with open(man, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["panel_a", "panel_b"])
        w.writerows([r[3], r[4]] for r in rows[1:])
    cmd = [PY, "scripts/extract_features.py", "--manifest", str(man), "--chunk", "2", "--workers", "2"]
    rc, so, se = run_and_interrupt(cmd, env, lambda l: l.startswith("new "), signal.SIGTERM, delay="1")
    assert rc == 130, se
    pk = sorted((tmp_path / "ws" / "cache" / "panels").glob("*.pkl"))
    assert 2 <= len(pk) < 8
    pk[0].write_bytes(pk[0].read_bytes()[:50])
    r = run(cmd, env)
    assert r.returncode == 0, r.stderr
    assert f"{8 - len(pk) + 1} to compute, 0 need DINO features, {len(pk) - 1} valid in cache" in r.stdout


# ---------------------------------------------------------------- OCR failures are reported, never cached
def test_ocr_failures_are_not_cached(tmp_path):
    env = make_workspace(tmp_path, n_books=1, n_pages=1, n_panels=3)
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "tesseract").write_text("#!/bin/sh\necho 'simulated failure' >&2\nexit 1\n")
    (fake / "tesseract").chmod(0o755)
    env["PATH"] = f"{fake}:{env['PATH']}"
    man = tmp_path / "data" / "m.csv"
    man.write_text("panel_a,panel_b\n100/1_0.jpg,100/1_1.jpg\n100/1_1.jpg,100/1_2.jpg\n")
    r = run([PY, "scripts/ocr_cache.py", str(man), "--workers", "2"], env)
    assert r.returncode == 1, r.stderr
    assert r.stderr.count("FAILED ") == 3 and "re-run to retry" in r.stderr
    assert not list((tmp_path / "ws" / "cache" / "ocr").glob("*.txt")), "failed OCR must never be cached"
