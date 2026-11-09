"""Graceful shutdown, atomic writes and cache validation shared by all long-running scripts.

Conventions used by every script:
  * install_stop_handler() turns SIGINT/SIGTERM into a flag. The work loop checks
    `stop.requested` between safe units of work (a book, panel, fold...). Each finished unit is
    persisted, and the script then exits with EXIT_INTERRUPTED (130). Further signals do not
    force-quit. Use SIGKILL if a hard stop is ever genuinely needed.
  * Every output file is written by atomic_open(): it writes a temp file in the same
    directory, fsyncs it, then os.replace()s it into place. A file at its final path is
    therefore always complete. Temp files (".<name>.tmp-*") are never mistaken for outputs.
  * Cached artifacts are validated (load_valid_*) before being skipped. Invalid ones are
    recomputed and overwritten.
  * Final aggregate outputs are written only once all units are done, so an interrupted
    run never leaves a final output that looks complete but isn't.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import pickle
import signal
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np

EXIT_INTERRUPTED = 130


class StopFlag:
    def __init__(self):
        self.requested = False
        self.signals = 0

    def _handle(self, signum, frame):
        self.signals += 1
        self.requested = True
        name = signal.Signals(signum).name
        if self.signals == 1:
            print(f"\n[{name}] stop requested: finishing the current unit, saving progress, then exiting.",
                  file=sys.stderr, flush=True)
        else:
            print(f"[{name}] still finishing the current unit (signal #{self.signals}); not force-quitting.",
                  file=sys.stderr, flush=True)


def install_stop_handler() -> StopFlag:
    flag = StopFlag()
    signal.signal(signal.SIGINT, flag._handle)
    signal.signal(signal.SIGTERM, flag._handle)
    return flag


def exit_interrupted(msg: str = "") -> None:
    print(f"interrupted cleanly{': ' + msg if msg else ''}. Re-run the same command to resume.",
          file=sys.stderr, flush=True)
    sys.exit(EXIT_INTERRUPTED)


def test_unit_delay() -> None:
    """Testing hook: CPT_TEST_UNIT_DELAY=<seconds> slows each unit so tests can interrupt mid-run."""
    d = os.environ.get("CPT_TEST_UNIT_DELAY")
    if d:
        time.sleep(float(d))


@contextlib.contextmanager
def atomic_open(path: str | Path, mode: str = "w", **kw):
    """Open a temp file next to `path`, then fsync and os.replace it into place on success."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    os.close(fd)
    try:
        with open(tmp, mode, **kw) as fh:
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def atomic_write_text(path, text: str) -> None:
    with atomic_open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def atomic_pickle(path, obj) -> None:
    with atomic_open(path, "wb") as fh:
        pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)


def atomic_savez(path, **arrays) -> None:
    with atomic_open(path, "wb") as fh:  # file object: numpy won't append ".npz"
        np.savez(fh, **arrays)


def atomic_json(path, obj) -> None:
    with atomic_open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)


def load_valid_npz(path, required: dict[str, tuple | None]) -> dict | None:
    """Return the arrays if `path` is a readable npz holding every required key, with the given
    leading shape (None = any) and finite floats. Otherwise return None (treat as missing)."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as z:
            out = {k: z[k] for k in required}
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, EOFError):
        return None
    for k, shape in required.items():
        a = out[k]
        if shape is not None and tuple(a.shape[:len(shape)]) != tuple(shape):
            return None
        if a.dtype.kind == "f" and not np.isfinite(a).all():
            return None
    return out


def load_valid_pickle(path, check=None):
    """Unpickle `path`. Returns None if it is missing, unreadable or fails check(obj)."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as fh:
            obj = pickle.load(fh)
    except (OSError, EOFError, pickle.UnpicklingError, AttributeError, ValueError, ImportError, IndexError):
        return None
    if check is not None:
        try:
            if not check(obj):
                return None
        except Exception:
            return None
    return obj


def fingerprint(*parts) -> str:
    """A short, stable hash of the configuration/data a checkpoint depends on."""
    h = hashlib.sha1()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


class JsonlCheckpoint:
    """Append-only, line-per-unit progress log. Each record is flushed and fsynced. A torn final
    line (from a crash mid-write) or a record from a different configuration is ignored."""

    def __init__(self, path, key: str):
        self.path, self.key = Path(path), key
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, object]:
        done = {}
        if self.path.is_file():
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(rec, dict) and rec.get("_key") == self.key and "unit" in rec:
                        done[rec["unit"]] = rec.get("data")
        return done

    def append(self, unit: str, data) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"_key": self.key, "unit": unit, "data": data}) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def remove(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()
