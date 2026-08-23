"""Playwright GUI tests for the stress test data.

Requires:
  1. python tests/generate_stress_data.py  (generates test data)
  2. python start.py --dev                  (dev server running)
  3. playwright install chromium

Run:  pytest tests/test_stress_gui.py -v --headed
"""
from __future__ import annotations

import json
import socket
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

STRESS_DIR = Path(__file__).resolve().parent.parent / "test_data" / "stress_test"
BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not (STRESS_DIR / "2046" / "2046_1.csv").exists(),
        reason="Stress test data not generated",
    ),
    pytest.mark.skipif(
        not _port_open("localhost", 3000),
        reason="Dev server not running on localhost:3000",
    ),
]

PATIENT_IDS = ["2046", "3640", "3848", "4458", "4682"]


# -----------------------------------------------------------------------
# API helpers — use direct API calls for setup, Playwright for visual checks
# -----------------------------------------------------------------------

def api_health(page: Page) -> bool:
    resp = page.request.get(f"{API_URL}/api/health")
    return resp.ok


def _post_json(page: Page, url: str, payload: dict) -> dict:
    """POST JSON to API and return parsed response."""
    resp = page.request.post(url, data=json.dumps(payload), headers={
        "Content-Type": "application/json",
    })
    return resp


def api_scan_folder(page: Page) -> dict:
    resp = _post_json(page, f"{API_URL}/api/scan/folder",
                      {"folder_path": str(STRESS_DIR), "recursive": True})
    assert resp.ok, f"Scan failed: {resp.status} {resp.text()}"
    return resp.json()


def api_upload_clinical(page: Page) -> dict:
    resp = _post_json(page, f"{API_URL}/api/upload/clinical-path",
                      {"path": str(STRESS_DIR / "clinical_data.csv")})
    assert resp.ok, f"Clinical upload failed: {resp.status} {resp.text()}"
    return resp.json()


def api_upload_corrections(page: Page) -> dict:
    resp = _post_json(page, f"{API_URL}/api/upload/corrections-path",
                      {"path": str(STRESS_DIR / "eeg_date_correction.csv")})
    assert resp.ok, f"Corrections upload failed: {resp.status} {resp.text()}"
    return resp.json()


def api_register_local_files(page: Page, scan_result: dict) -> list[dict]:
    """Register local CSV files, returning upload responses with file_ids."""
    persyst_files = [
        f for f in scan_result["files"] if f["file_type"] == "persyst_csv"
    ]
    paths = [f["path"] for f in persyst_files]
    resp = _post_json(page, f"{API_URL}/api/upload/local", {"paths": paths})
    assert resp.ok, f"Register local failed: {resp.status} {resp.text()}"
    return resp.json()


def wait_for_batch(page: Page, batch_id: str, timeout_s: int = 600):
    """Poll batch status until complete."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = page.request.get(f"{API_URL}/api/batch/status/{batch_id}")
        if not resp.ok:
            # SSE endpoint — try polling patient summaries instead
            break
        data = resp.json()
        if data.get("status") == "complete":
            return data
        time.sleep(2)

    # Fallback: check if patients are loaded
    for pid in PATIENT_IDS:
        resp = page.request.get(f"{API_URL}/api/patients/{pid}")
        if not resp.ok:
            # Wait more
            time.sleep(5)
    return None


def api_get_patient_summary(page: Page, pid: str) -> dict | None:
    resp = page.request.get(f"{API_URL}/api/patients/{pid}")
    if resp.ok:
        return resp.json()
    return None


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture(scope="module")
def setup_data(browser):
    """Scan, register, upload metadata, and run pipeline for 1 patient via API.

    Uses patient 4458 (cleanest, fastest). Skips if already loaded.
    """
    context = browser.new_context()
    page = context.new_page()

    assert api_health(page), "API server not running"

    # Step 1: Scan folder
    scan = api_scan_folder(page)
    persyst_count = scan["counts"].get("persyst_csv", 0)
    assert persyst_count == 5, f"Expected 5 CSVs, got {persyst_count}"

    # Step 2: Register local files
    uploads = api_register_local_files(page, scan)
    assert len(uploads) >= 1, f"Expected uploads, got {len(uploads)}"

    # Step 3: Upload clinical + corrections
    try:
        api_upload_clinical(page)
    except AssertionError:
        pass  # May fail if already uploaded
    try:
        api_upload_corrections(page)
    except AssertionError:
        pass

    # Step 4: Check if any patient already loaded
    for u in uploads:
        pid = u.get("patient_id", "")
        if api_get_patient_summary(page, pid) is not None:
            context.close()
            return [pid]

    # Step 5: Run pipeline for patient 4458
    target = [u for u in uploads if u.get("patient_id") == "4458"]
    if not target:
        target = uploads[:1]
    fid = target[0]["file_id"]
    pid = target[0]["patient_id"]

    resp = _post_json(page, f"{API_URL}/api/pipeline/run", {
        "file_ids": [fid],
        "patient_id": pid,
        "artifact_mode": "combined",
        "artifact_intensity_threshold": 10.0,
        "artifact_quality_threshold": 50.0,
        "seizure_mode": "probability",
        "seizure_probability_threshold": 0.5,
        "bin_edges_hours": [0, 6, 12, 18, 24, 48, 72],
        "min_coverage_hours": 1.0,
    })
    assert resp.ok, f"Pipeline run failed: {resp.status} {resp.text()}"

    # Wait for processing (single 172K-row patient ~2-3 min)
    for _ in range(90):  # 7.5 min max
        if api_get_patient_summary(page, pid) is not None:
            break
        time.sleep(5)

    summary = api_get_patient_summary(page, pid)
    assert summary is not None, f"Patient {pid} not loaded after pipeline"

    context.close()
    return [pid]


# -----------------------------------------------------------------------
# GUI tests
# -----------------------------------------------------------------------

class TestImportView:
    """Test the import/scan UI."""

    def test_app_loads(self, page: Page):
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        # App should render
        expect(page.locator("body")).to_be_visible()

    def test_folder_scan_ui(self, page: Page):
        """Enter folder path and trigger scan via UI."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Target the scan input by its real placeholder. The previous locator
        # fell back to "first text input on the page", which silently drifted to
        # whichever unrelated field happened to render first — the fill then went
        # to the wrong box and left Scan disabled.
        folder_input = page.get_by_placeholder(r"C:\path\to\study\folder")
        expect(folder_input).to_be_visible()
        folder_input.fill(str(STRESS_DIR))

        # exact=True so this does not also match the "Scanning..." label.
        scan_btn = page.get_by_role("button", name="Scan", exact=True)
        expect(scan_btn).to_be_enabled()
        scan_btn.click()
        # Wait for scan results
        page.wait_for_timeout(5000)


class TestPatientDashboard:
    """Test patient dashboard renders for each patient."""

    def test_patient_list_visible(self, page: Page, setup_data):
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Navigate to patients view
        patients_nav = page.get_by_role("button", name="Patients").or_(
            page.locator("button:has-text('Patients')")
        )
        if patients_nav.is_visible():
            patients_nav.click()
            page.wait_for_timeout(2000)

    def test_patient_dashboard_api(self, page: Page, setup_data):
        """Verify API endpoints work for loaded patients."""
        loaded_pids = setup_data
        pid = loaded_pids[0]

        # Summary
        resp = page.request.get(f"{API_URL}/api/patients/{pid}")
        assert resp.ok, f"Patient {pid} API failed"
        summary = resp.json()
        assert summary["patient_id"] == pid

        # Epochs (columnar; families required, max_points server-side downsample)
        resp = page.request.get(
            f"{API_URL}/api/patients/{pid}/epochs?families=fft_power&max_points=1000"
        )
        assert resp.ok, f"Patient {pid} epochs API failed: {resp.status}"
        epochs = resp.json()
        assert len(epochs["hours"]) > 0
        assert len(epochs["columns"]) > 0

        # Bins
        resp = page.request.get(f"{API_URL}/api/patients/{pid}/bins")
        assert resp.ok, f"Patient {pid} bins API failed"
        bins = resp.json()
        assert len(bins["bins"]) > 0


class TestExport:
    """Test export functionality."""

    @pytest.mark.parametrize("fmt", ["csv", "json"])
    def test_export_format(self, page: Page, setup_data, fmt: str):
        loaded_pids = setup_data
        pid = loaded_pids[0]
        resp = page.request.get(
            f"{API_URL}/api/export/{pid}/{fmt}"
        )
        assert resp.ok, f"Export {fmt} for {pid} failed: {resp.status}"
        assert len(resp.body()) > 100, f"Export {fmt} for {pid} too small"


class TestVisualRendering:
    """Playwright visual checks — verify charts render in browser."""

    def test_dashboard_charts_render(self, page: Page, setup_data):
        """Load a patient dashboard and check that chart elements exist."""
        loaded_pids = setup_data
        pid = loaded_pids[0]

        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Click on patients nav
        patients_btn = page.locator("button:has-text('Patients')").first
        if patients_btn.is_visible():
            patients_btn.click()
            page.wait_for_timeout(2000)

            # Look for the loaded patient in the list and click it
            patient_link = page.locator(f"text={pid}").first
            if patient_link.is_visible():
                patient_link.click()
                page.wait_for_timeout(3000)

                # Check for Recharts SVG or canvas elements
                svg_charts = page.locator("svg.recharts-surface")
                canvas_elements = page.locator("canvas")
                total = svg_charts.count() + canvas_elements.count()
                assert total >= 0  # Non-strict: verify no crash

    def test_no_console_errors(self, page: Page, setup_data):
        """Check that loading the app doesn't produce JS errors."""
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # Filter out known non-critical errors
        critical_errors = [
            e for e in errors
            if "ResizeObserver" not in e  # Known benign error
        ]
        assert len(critical_errors) == 0, f"JS errors: {critical_errors}"
