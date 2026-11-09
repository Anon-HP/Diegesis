"""Browser test of the full stack: web frontend (:3000) -> Next.js proxy -> FastAPI backend (:8000) -> model.

Requires both servers to be running (see README "Web app") and Playwright's Chromium:
    PLAYWRIGHT_BROWSERS_PATH=... .venv/bin/python -m playwright install chromium-headless-shell
Run with:  .venv/bin/python -m pytest -m ui tests/test_ui.py
Skipped automatically if the frontend is not reachable.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FRONTEND = os.environ.get("CPT_FRONTEND_URL", "http://127.0.0.1:3000")
SIX = ["Moment-to-Moment", "Action-to-Action", "Subject-to-Subject", "Scene-to-Scene", "Aspect-to-Aspect",
       "Non-Sequitur"]

pytestmark = pytest.mark.ui


def _up(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def page():
    if not _up(FRONTEND) or not _up(FRONTEND + "/api/health"):
        pytest.skip("frontend/backend not running")
    from transition.paths import WORKSPACE
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(WORKSPACE / "ms-playwright"))
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except pw.Error as e:
            pytest.skip(f"Playwright Chromium not installed: {str(e).splitlines()[0]}")
        pg = browser.new_page(viewport={"width": 1280, "height": 1800})
        yield pg
        browser.close()


def panels():
    from transition.paths import PANELS_DIR
    a, b = PANELS_DIR / "1094/35_0.jpg", PANELS_DIR / "1094/35_1.jpg"
    if not (a.exists() and b.exists()):
        pytest.skip("COMICS panels not available")
    return a, b


def upload(pg, a, b):
    inputs = pg.locator("input[type=file]")
    inputs.nth(0).set_input_files(str(a))
    inputs.nth(1).set_input_files(str(b))


def test_no_dummy_content_on_page(page):
    page.goto(FRONTEND)
    html = page.content()
    assert "Optional question" not in html
    assert "Both panels follow the same character" not in html  # old hard-coded result text
    assert "91%" not in html  # old fake per-class percentages


def test_invalid_file_type_rejected(page, tmp_path):
    page.goto(FRONTEND)
    bad = tmp_path / "panel.gif"
    bad.write_bytes(b"GIF89a")
    page.locator("input[type=file]").nth(0).set_input_files(str(bad))
    page.get_by_role("alert").filter(has_text="Unsupported file type").wait_for(timeout=5000)


def test_real_prediction_flow(page, tmp_path):
    a, b = panels()
    page.goto(FRONTEND)
    upload(page, a, b)
    page.get_by_text("2 / 2 PANELS ADDED").wait_for(timeout=5000)
    page.get_by_role("button", name="Analyze transition").click()
    page.get_by_text("Analyzing panels...").wait_for(timeout=5000)  # loading state
    page.get_by_text("MODEL PROBABILITIES").wait_for(timeout=120_000)
    text = page.locator("section[aria-labelledby=analysis-heading]").inner_text()
    shown = [n for n in SIX if n in text.split("MODEL PROBABILITIES")[0]]
    assert len(shown) == 1, f"exactly one predicted type must be shown before the breakdown: {shown}"
    assert "CONFIDENCE" in text
    page.screenshot(path=str(tmp_path / "result.png"), full_page=True)
    # The displayed type must equal the backend's own prediction for the same two files.
    r = page.request.post(FRONTEND + "/api/analyze", multipart={
        "first": {"name": a.name, "mimeType": "image/jpeg", "buffer": a.read_bytes()},
        "second": {"name": b.name, "mimeType": "image/jpeg", "buffer": b.read_bytes()}})
    assert r.ok
    label = r.json()["label"]
    assert shown[0].lower() == label, (shown[0], label)


def test_backend_error_is_shown(page):
    a, b = panels()
    page.goto(FRONTEND)
    page.route("**/api/analyze", lambda route: route.fulfill(
        status=503, content_type="application/json",
        body=json.dumps({"error": {"code": "model_unavailable", "message": "The model is still loading; try again."}})))
    upload(page, a, b)
    page.get_by_role("button", name="Analyze transition").click()
    page.get_by_role("alert").filter(has_text="The model is still loading").wait_for(timeout=10_000)
    page.unroute("**/api/analyze")


def test_backend_unreachable_is_shown(page):
    a, b = panels()
    page.goto(FRONTEND)
    page.route("**/api/analyze", lambda route: route.abort("connectionrefused"))
    upload(page, a, b)
    page.get_by_role("button", name="Analyze transition").click()
    page.get_by_role("alert").filter(has_text="Could not reach the analysis server").wait_for(timeout=10_000)
    page.unroute("**/api/analyze")
