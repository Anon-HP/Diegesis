"""Unit tests for graceful shutdown, atomic writes and cache validation (src/transition/runctl.py)."""
import os
import pickle
import signal
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition import runctl  # noqa: E402


def test_atomic_open_success_and_no_temp_left(tmp_path):
    p = tmp_path / "out.txt"
    runctl.atomic_write_text(p, "hello")
    assert p.read_text() == "hello"
    assert [f.name for f in tmp_path.iterdir()] == ["out.txt"]


def test_atomic_open_failure_keeps_previous_version(tmp_path):
    p = tmp_path / "out.txt"
    p.write_text("old complete version")
    with pytest.raises(RuntimeError):
        with runctl.atomic_open(p, "w") as fh:
            fh.write("half of the new ver")
            raise RuntimeError("crash mid-write")
    assert p.read_text() == "old complete version"
    assert [f.name for f in tmp_path.iterdir()] == ["out.txt"]  # temp file cleaned up


def test_atomic_savez_keeps_exact_name(tmp_path):
    p = tmp_path / "book.npz"
    runctl.atomic_savez(p, emb=np.ones((3, 4), np.float32))
    assert p.is_file() and not (tmp_path / "book.npz.npz").exists()


def test_load_valid_npz(tmp_path):
    good = tmp_path / "good.npz"
    runctl.atomic_savez(good, panels=np.array(["a", "b"]), emb=np.ones((2, 4), np.float32))
    req = {"panels": (2,), "emb": (2,)}
    assert runctl.load_valid_npz(good, req) is not None
    assert runctl.load_valid_npz(good, {"panels": (3,), "emb": (3,)}) is None  # wrong shape
    assert runctl.load_valid_npz(good, {"missing": None}) is None  # missing key
    assert runctl.load_valid_npz(tmp_path / "nope.npz", req) is None  # missing file
    trunc = tmp_path / "trunc.npz"
    trunc.write_bytes(good.read_bytes()[:-20])  # simulated torn write
    assert runctl.load_valid_npz(trunc, req) is None
    nan = tmp_path / "nan.npz"
    runctl.atomic_savez(nan, panels=np.array(["a", "b"]), emb=np.full((2, 4), np.nan, np.float32))
    assert runctl.load_valid_npz(nan, req) is None


def test_load_valid_pickle(tmp_path):
    p = tmp_path / "r.pkl"
    runctl.atomic_pickle(p, {"x": 1})
    assert runctl.load_valid_pickle(p) == {"x": 1}
    assert runctl.load_valid_pickle(p, check=lambda o: "y" in o) is None
    data = pickle.dumps({"x": list(range(1000))})
    p.write_bytes(data[: len(data) // 2])
    assert runctl.load_valid_pickle(p) is None


def test_jsonl_checkpoint_ignores_torn_line_and_foreign_key(tmp_path):
    f = tmp_path / "state.jsonl"
    ck = runctl.JsonlCheckpoint(f, key="k1")
    ck.append("book1", {"rows": [1]})
    ck.append("book2", {"rows": [2]})
    runctl.JsonlCheckpoint(f, key="other").append("book3", {"rows": [3]})
    with open(f, "a") as fh:
        fh.write('{"_key": "k1", "unit": "book4", "da')  # crash mid-line
    assert runctl.JsonlCheckpoint(f, key="k1").load() == {"book1": {"rows": [1]}, "book2": {"rows": [2]}}


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_stop_flag_sets_flag_instead_of_terminating(sig):
    old_int, old_term = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
    try:
        flag = runctl.install_stop_handler()
        assert not flag.requested
        os.kill(os.getpid(), sig)
        os.kill(os.getpid(), sig)  # a second signal must not force-quit either
        assert flag.requested and flag.signals == 2
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)


def test_fingerprint_is_stable_and_sensitive():
    assert runctl.fingerprint([1, 2], "a") == runctl.fingerprint([1, 2], "a")
    assert runctl.fingerprint([1, 2], "a") != runctl.fingerprint([1, 3], "a")
