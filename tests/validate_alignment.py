"""
Playwright alignment validation for workbench v2 fixes.
Run: python tests/validate_alignment.py
Requires dev server running on http://localhost:3000 and http://localhost:8000
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"
SCREENSHOT_PATH = Path(__file__).resolve().parent.parent / "alignment_check.png"
TOLERANCE_PX = 3


def main():
    # Fetch patient 1002 summary from the API
    resp = requests.get(f"{API_URL}/api/patients")
    patients = resp.json()
    patient_1002 = next((p for p in patients if p["patient_id"] == "1002"), None)
    if not patient_1002:
        print("ERROR: patient 1002 not found in API")
        return False

    print(f"Patient 1002: totalHours={patient_1002['qc']['recording_duration_hours']:.20f}h, "
          f"roscOffset={patient_1002['time_axis'].get('hours_rosc_to_eeg')}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(BASE_URL)
        page.wait_for_load_state("load", timeout=15000)
        page.wait_for_selector("button[title='Patients']", timeout=15000)

        # Inject patient state directly into the Zustand store
        patient_json = json.dumps(patient_1002)
        page.evaluate(f"""() => {{
            // Find the Zustand store via the global store key
            const storeKey = Object.keys(window).find(k =>
                window[k] && typeof window[k].getState === 'function'
                && window[k].getState().patientId !== undefined
            );
            if (!storeKey) {{
                // Try accessing via module system
                return 'store not found';
            }}
            const store = window[storeKey];
            store.getState().setPatient("1002", {patient_json});
            store.getState().setView("dashboard");
            return 'ok';
        }}""")

        # Alternatively, navigate via UI — try clicking patients and then the patient row
        page.locator("button[title='Patients']").click()
        time.sleep(2)

        # Check if 1002 is visible
        count = page.locator("text=1002").count()
        print(f"Patient 1002 rows found: {count}")

        if count > 0:
            page.locator("text=1002").first.click()
            page.wait_for_selector("[data-testid='time-axis-track']", timeout=15000)
        else:
            # Fallback: navigate to dashboard directly and inject state
            page.evaluate("""() => {
                // Try React state injection via global app store
                const keys = Object.keys(window.__ZUSTAND_DEVTOOLS_STORES__ || {});
                return keys;
            }""")
            print("Could not find patient 1002 in list — check if patients loaded in API")
            page.screenshot(path=str(SCREENSHOT_PATH))
            browser.close()
            return False

        # Wait for Recharts grids (up to 40s — API can take 5+ seconds for large panels)
        grids_found = 0
        for _ in range(40):
            grids_found = page.locator(".recharts-cartesian-grid").count()
            if grids_found > 0:
                break
            time.sleep(1)

        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOT_PATH))
        print(f"Screenshot: {SCREENSHOT_PATH}  |  Recharts grids: {grids_found}")

        result = page.evaluate("""() => {
            const track = document.querySelector('[data-testid="time-axis-track"]');
            if (!track) return { error: 'time-axis-track not found' };

            const grids = [...document.querySelectorAll('.recharts-cartesian-grid')];
            const spans = [...track.querySelectorAll('span')];
            const tr = track.getBoundingClientRect();

            return {
                trackLeft: tr.left,
                trackRight: tr.right,
                gridCount: grids.length,
                gridRects: grids.map(g => {
                    const r = g.getBoundingClientRect();
                    return { left: r.left, right: r.right };
                }),
                tickCount: spans.length,
                firstTickText: spans[0] ? spans[0].textContent : null,
                lastTickText: spans[spans.length-1] ? spans[spans.length-1].textContent : null,
                lastTickRight: spans[spans.length-1]
                    ? spans[spans.length-1].getBoundingClientRect().right : null,
            };
        }""")

        if "error" in result:
            print(f"ERROR: {result}")
            browser.close()
            return False

        print(f"\nTime Axis: left={result['trackLeft']:.1f}  right={result['trackRight']:.1f}")
        print(f"Ticks: {result['tickCount']}  first={result['firstTickText']}  last={result['lastTickText']}")

        failures = []

        if result['lastTickRight'] is not None:
            diff = abs(result['lastTickRight'] - result['trackRight'])
            ok = diff <= TOLERANCE_PX
            print(f"Last-tick right-align: delta={diff:.1f}px  [{'PASS' if ok else 'FAIL'}]")
            if not ok:
                failures.append(f"last-tick-alignment: {diff:.1f}px off")

        if result['firstTickText'] == "0h":
            print("First tick = 0h  [PASS]")
        else:
            print(f"First tick is '{result['firstTickText']}'  [FAIL]")
            failures.append(f"first-tick: {result['firstTickText']}")

        print(f"\nChart alignment ({result['gridCount']} Recharts grids):")
        for i, gr in enumerate(result['gridRects']):
            ld = abs(gr['left'] - result['trackLeft'])
            rd = abs(gr['right'] - result['trackRight'])
            ok = ld <= TOLERANCE_PX and rd <= TOLERANCE_PX
            print(f"  Chart {i+1}: left_delta={ld:.1f}  right_delta={rd:.1f}  [{'PASS' if ok else 'FAIL'}]")
            if not ok:
                failures.append(f"chart-{i+1}: Ld={ld:.1f} Rd={rd:.1f}")

        if result['gridCount'] == 0:
            print("  No grids found — data may still be loading")

        print(f"\n{'PASS' if not failures else 'FAIL'}: {len(failures)} issues: {failures}")
        browser.close()
        return len(failures) == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
