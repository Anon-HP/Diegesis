"""HTTP API around TransitionPredictor, used by the local web frontend (frontend/).

Run:  .venv/bin/python serve.py            (http://127.0.0.1:8000)

Endpoints
  GET  /api/health   -> {"status": "ok"|"loading"|"error", "labels": [...6...], "method": ..., "detail": ...}
  POST /api/analyze  multipart/form-data with exactly two image files: `first` (Panel A), `second` (Panel B)
                     -> {"label", "confidence", "probabilities", "method", "warnings", "ocr", "elapsed_ms"}
Errors are JSON: {"error": {"code": ..., "message": ...}} with HTTP 400 (bad input), 413 (too large),
503 (model not ready) or 500 (inference failure).
"""
from __future__ import annotations

import io
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageFile, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from .labels import LABELS, validate_label
from .predictor import MIN_SIDE

ImageFile.LOAD_TRUNCATED_IMAGES = True
MAX_BYTES = int(os.environ.get("CPT_MAX_UPLOAD_MB", "15")) * 1024 * 1024
MAX_PIXELS = 40_000_000  # decompression-bomb guard
LOW_CONFIDENCE = 0.45
ALLOWED_FORMATS = {"PNG", "JPEG"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


class _State:
    predictor = None
    status = "loading"
    detail = ""
    lock = threading.Lock()  # one inference at a time (single GPU / CPU-heavy OCR)


state = _State()


def _load_predictor():
    try:
        from .predictor import TransitionPredictor

        state.predictor = TransitionPredictor(device=os.environ.get("CPT_DEVICE") or None)
        state.status = "ok"
    except Exception as e:  # reported by /api/health and 503 on /api/analyze
        state.status, state.detail = "error", f"{type(e).__name__}: {e}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("CPT_API_LAZY") != "1":
        await run_in_threadpool(_load_predictor)
    yield


app = FastAPI(title="Comic panel transition API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("CPT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    missing = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("type") == "missing"})
    if missing:
        return _error(400, "missing_panel", f"Both panels are required (missing: {', '.join(missing)}).")
    return _error(400, "invalid_request", "Send two image files as multipart fields 'first' and 'second'.")


async def _read_image(upload: UploadFile, which: str) -> Image.Image:
    data = await upload.read(MAX_BYTES + 1)
    if not data:
        raise ApiError(400, "empty_file", f"The {which} panel file is empty.")
    if len(data) > MAX_BYTES:
        raise ApiError(413, "file_too_large", f"The {which} panel is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ALLOWED_FORMATS:
                raise ApiError(400, "unsupported_type",
                               f"The {which} panel is {im.format or 'an unknown format'}; please upload a PNG or JPEG image.")
            if im.width * im.height > MAX_PIXELS:
                raise ApiError(400, "image_too_large", f"The {which} panel has too many pixels.")
            im.load()
            img = im.convert("RGB")
    except ApiError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise ApiError(400, "invalid_image", f"The {which} panel could not be read as an image.")
    if min(img.size) < MIN_SIDE:
        raise ApiError(400, "image_too_small", f"The {which} panel is too small ({img.width}×{img.height}); "
                                               f"each side must be at least {MIN_SIDE} px.")
    return img


@app.get("/api/health")
def health():
    p = state.predictor
    return {"status": state.status, "labels": list(LABELS), "detail": state.detail,
            "head": None if p is None or p.head is None else str(p.head_path.name),
            "fallback_heuristic": bool(p is not None and p.head is None)}


@app.post("/api/analyze")
async def analyze(first: UploadFile, second: UploadFile):
    img_a = await _read_image(first, "first")
    img_b = await _read_image(second, "second")
    if state.status != "ok" or state.predictor is None:
        msg = "The model is still loading; try again in a few seconds." if state.status == "loading" else \
            f"The model failed to load: {state.detail}"
        raise ApiError(503, "model_unavailable", msg)

    def run():
        with state.lock:
            t0 = time.perf_counter()
            out = state.predictor.predict_images(img_a, img_b)
            return out, time.perf_counter() - t0

    try:
        out, dt = await run_in_threadpool(run)
    except Exception as e:
        raise ApiError(500, "inference_failed", f"Inference failed: {type(e).__name__}")
    label = validate_label(out["label"])
    warnings = []
    if state.predictor.head is None:
        warnings.append("No trained classifier head was found; this is an untrained heuristic fallback.")
    if out["confidence"] < LOW_CONFIDENCE:
        warnings.append("Low confidence: the model is uncertain between several transition types.")
    if label == "non-sequitur":
        warnings.append("Non-sequitur predictions are unreliable: the model learned this class mostly from "
                        "synthetic pairs and over-predicts it for visually very different panels.")
    return {"label": label, "confidence": out["confidence"], "probabilities": out["probabilities"],
            "method": out["method"], "warnings": warnings, "ocr": {"first": out["ocr_a"], "second": out["ocr_b"]},
            "elapsed_ms": round(dt * 1000)}
