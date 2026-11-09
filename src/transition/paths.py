"""Filesystem locations. Large data lives outside the repo; every location can be overridden with env vars
(the tests use this to run scripts against a throwaway workspace)."""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = Path(os.environ.get("CPT_WORKSPACE", "/home/anonhp/Hard-Drive/comic-transition-workspace"))
COMICS_DIR = Path(os.environ.get("CPT_COMICS_DIR", WORKSPACE / "data" / "comics"))
PANELS_DIR = Path(os.environ.get("CPT_PANELS_DIR", COMICS_DIR / "panels_dl" / "raw_panel_images"))
CACHE_DIR = Path(os.environ.get("CPT_CACHE_DIR", WORKSPACE / "cache"))
STATE_DIR = CACHE_DIR / "state"  # resumable progress logs
MODELS_DIR = Path(os.environ.get("CPT_MODELS_DIR", REPO / "models"))  # small trained heads
DATA_DIR = Path(os.environ.get("CPT_DATA_DIR", REPO / "data"))
ANN_DIR = Path(os.environ.get("CPT_ANN_DIR", REPO / "annotations"))
EXP_DIR = Path(os.environ.get("CPT_EXP_DIR", REPO / "experiments"))

# Keep downloaded encoder weights off the small root disk.
os.environ.setdefault("HF_HOME", str(WORKSPACE / "hf_cache"))
