#!/usr/bin/env python3
"""Start the local inference API used by the web frontend.

usage: python serve.py [--host 127.0.0.1] [--port 8000]
The model (CLIP + DINOv2 + trained head) loads at startup; /api/health reports "ok" once ready.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    import uvicorn

    uvicorn.run("transition.api:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
