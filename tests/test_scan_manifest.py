"""Tests for POST /api/scan/folder and POST /api/manifest/build endpoints."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers to create test files
# ---------------------------------------------------------------------------

def _write_clinical_csv(path: Path) -> Path:
    path.write_text(
        "patient_id,age_days,rosc_datetime,notes\n"
        "SYNTH001,4380,2024-01-15 08:30,\n",
        encoding="utf-8",
    )
    return path


def _write_corrections_csv(path: Path) -> Path:
    path.write_text(
        "new_name,age_in_days_at_time_of_eeg,eeg_start_time,eeg_duration\n"
        "SYNTH001_1,4380,07:00:00,08:00:00\n",
        encoding="utf-8",
    )
    return path


def _to_excel_serial(dt) -> float:
    from datetime import datetime
    return (dt - datetime(1899, 12, 30)).total_seconds() / 86400.0


def _write_deidentified_persyst_csv(path: Path, synthetic_csv: Path) -> Path:
    """Copy the synthetic CSV but replace ClockDateTime values with pre-2000 dates."""
    from datetime import datetime

    content = synthetic_csv.read_text(encoding="utf-8-sig")
    lines = content.splitlines()

    # Find the code row (has ClockDateTime)
    code_row_idx = next(i for i, l in enumerate(lines) if "ClockDateTime" in l)
    clock_col = lines[code_row_idx].split(",").index("ClockDateTime")

    # Replace ClockDateTime values in data rows with a pre-2000 date serial
    old_serial = _to_excel_serial(datetime(2025, 3, 15, 10, 0, 0))
    new_serial = _to_excel_serial(datetime(1995, 1, 1, 0, 0, 0))

    new_lines = []
    for i, line in enumerate(lines):
        if i <= code_row_idx:
            new_lines.append(line)
            continue
        parts = line.split(",")
        if len(parts) > clock_col and parts[clock_col].strip():
            # Offset by the difference so relative spacing is preserved
            try:
                orig = float(parts[clock_col])
                offset = orig - old_serial
                parts[clock_col] = f"{new_serial + offset:.10f}"
            except ValueError:
                pass
        new_lines.append(",".join(parts))

    path.write_text("\n".join(new_lines), encoding="utf-8-sig")
    return path


# ---------------------------------------------------------------------------
# Scan endpoint tests
# ---------------------------------------------------------------------------


class TestScanFolder:
    def test_classifies_persyst_csv(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        resp = client.post("/api/scan/folder", json={"folder_path": str(tmp_path)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["counts"].get("persyst_csv", 0) == 1
        files = {f["filename"]: f for f in data["files"]}
        assert files[synthetic_csv.name]["file_type"] == "persyst_csv"

    def test_classifies_clinical_csv(self, client: TestClient, tmp_path: Path):
        _write_clinical_csv(tmp_path / "clinical.csv")
        resp = client.post("/api/scan/folder", json={"folder_path": str(tmp_path)})
        assert resp.status_code == 200
        files = {f["filename"]: f for f in resp.json()["files"]}
        assert files["clinical.csv"]["file_type"] == "clinical_csv"

    def test_classifies_corrections_csv(self, client: TestClient, tmp_path: Path):
        _write_corrections_csv(tmp_path / "corrections.csv")
        resp = client.post("/api/scan/folder", json={"folder_path": str(tmp_path)})
        assert resp.status_code == 200
        files = {f["filename"]: f for f in resp.json()["files"]}
        assert files["corrections.csv"]["file_type"] == "corrections_csv"

    def test_mmx_not_classified(self, client: TestClient, tmp_path: Path):
        """MMX files are excluded from folder scan — users upload them manually via /upload/mmx."""
        (tmp_path / "study.mmx").write_bytes(b"MMX")
        resp = client.post("/api/scan/folder", json={"folder_path": str(tmp_path)})
        assert resp.status_code == 200
        filenames = {f["filename"] for f in resp.json()["files"]}
        assert "study.mmx" not in filenames

    def test_classifies_raw_eeg(self, client: TestClient, tmp_path: Path):
        # .dat/.lay are excluded from CSV-only scan; they're handled via MMX/upload flow
        (tmp_path / "study.dat").write_bytes(b"EEG")
        (tmp_path / "study.lay").write_bytes(b"LAY")
        resp = client.post("/api/scan/folder", json={"folder_path": str(tmp_path)})
        assert resp.status_code == 200
        filenames = {f["filename"] for f in resp.json()["files"]}
        assert "study.dat" not in filenames
        assert "study.lay" not in filenames

    def test_recursive_scan_finds_nested_files(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        subdir = tmp_path / "patient_001"
        subdir.mkdir()
        nested = subdir / "SYNTH001_2.csv"
        nested.write_bytes(synthetic_csv.read_bytes())

        resp = client.post(
            "/api/scan/folder",
            json={"folder_path": str(tmp_path), "recursive": True},
        )
        assert resp.status_code == 200
        filenames = {f["filename"] for f in resp.json()["files"]}
        assert "SYNTH001_2.csv" in filenames

    def test_non_recursive_skips_subdirs(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        subdir = tmp_path / "nested"
        subdir.mkdir()
        (subdir / "SYNTH001_2.csv").write_bytes(synthetic_csv.read_bytes())

        resp = client.post(
            "/api/scan/folder",
            json={"folder_path": str(tmp_path), "recursive": False},
        )
        assert resp.status_code == 200
        filenames = {f["filename"] for f in resp.json()["files"]}
        assert "SYNTH001_2.csv" not in filenames

    def test_rejects_path_traversal(self, client: TestClient):
        resp = client.post(
            "/api/scan/folder",
            json={"folder_path": "C:\\Users\\..\\Windows"},
        )
        assert resp.status_code == 400
        assert "traversal" in resp.json()["detail"].lower()

    def test_rejects_unc_path(self, client: TestClient):
        resp = client.post(
            "/api/scan/folder",
            json={"folder_path": "\\\\server\\share"},
        )
        assert resp.status_code in (400, 404)

    def test_missing_folder_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/scan/folder",
            json={"folder_path": "C:\\nonexistent_qeeg_test_dir_xyz"},
        )
        assert resp.status_code == 404

    def test_counts_match_files(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        _write_clinical_csv(tmp_path / "clinical.csv")
        _write_corrections_csv(tmp_path / "corrections.csv")
        # MMX files are excluded from scan — should not appear in counts

        resp = client.post("/api/scan/folder", json={"folder_path": str(tmp_path)})
        data = resp.json()
        assert data["counts"]["persyst_csv"] == 1
        assert data["counts"]["clinical_csv"] == 1
        assert data["counts"]["corrections_csv"] == 1
        total_from_counts = sum(data["counts"].values())
        assert total_from_counts == len(data["files"])


# ---------------------------------------------------------------------------
# Manifest endpoint tests
# ---------------------------------------------------------------------------


def _scan_result(tmp_path: Path, synthetic_csv: Path, client: TestClient) -> dict:
    """Run a folder scan and return the response JSON."""
    resp = client.post("/api/scan/folder", json={"folder_path": str(tmp_path)})
    assert resp.status_code == 200
    return resp.json()


class TestManifestBuild:
    def test_groups_single_patient(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        scan = _scan_result(tmp_path, synthetic_csv, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 1
        patient = data["patients"][0]
        assert patient["patient_id"] == "SYNTH001"
        assert len(patient["persyst_files"]) == 1

    def test_groups_two_files_same_patient(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        second = tmp_path / "SYNTH001_2.csv"
        second.write_bytes(synthetic_csv.read_bytes())

        scan = _scan_result(tmp_path, synthetic_csv, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_patients"] == 1
        assert len(data["patients"][0]["persyst_files"]) == 2

    def test_attaches_clinical_csv(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        _write_clinical_csv(tmp_path / "clinical.csv")
        scan = _scan_result(tmp_path, synthetic_csv, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        data = resp.json()
        assert data["global_clinical_csv"] is not None
        assert data["patients"][0]["clinical_csv"] is not None

    def test_attaches_corrections_csv(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        _write_corrections_csv(tmp_path / "corrections.csv")
        scan = _scan_result(tmp_path, synthetic_csv, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        data = resp.json()
        assert data["global_corrections_csv"] is not None
        assert data["patients"][0]["corrections_csv"] is not None

    def test_mmx_not_attached_via_manifest(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        """MMX files are uploaded separately via /upload/mmx, not via manifest."""
        (tmp_path / "study.mmx").write_bytes(b"MMX")
        scan = _scan_result(tmp_path, synthetic_csv, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        data = resp.json()
        # Manifest entries no longer have mmx_files field
        assert "mmx_files" not in data["patients"][0]

    def test_validation_passes_for_clean_folder(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        _write_clinical_csv(tmp_path / "clinical.csv")
        scan = _scan_result(tmp_path, synthetic_csv, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        data = resp.json()
        patient = data["patients"][0]
        assert patient["validation_errors"] == []
        assert data["validation_summary"]["errors"] == 0
        assert data["validation_summary"]["valid"] == 1

    def test_validation_error_missing_corrections(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        """De-identified dates without a corrections CSV → validation error."""
        deid = tmp_path / "SYNTH001_deid.csv"
        _write_deidentified_persyst_csv(deid, synthetic_csv)
        # Remove the original (has real dates) so only the de-id file is scanned
        synthetic_csv.unlink()

        scan = _scan_result(tmp_path, deid, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        data = resp.json()
        patient = data["patients"][0]
        assert patient["requires_corrections"] is True
        assert any("corrections" in e.lower() for e in patient["validation_errors"])

    def test_validation_passes_deidentified_with_corrections(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        deid = tmp_path / "SYNTH001_deid.csv"
        _write_deidentified_persyst_csv(deid, synthetic_csv)
        synthetic_csv.unlink()
        _write_corrections_csv(tmp_path / "corrections.csv")

        scan = _scan_result(tmp_path, deid, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        data = resp.json()
        patient = data["patients"][0]
        assert patient["requires_corrections"] is True
        assert patient["validation_errors"] == []  # corrections present — no error

    def test_no_persyst_files_returns_400(self, client: TestClient, tmp_path: Path):
        _write_clinical_csv(tmp_path / "clinical.csv")
        scan = _scan_result(tmp_path, tmp_path / "clinical.csv", client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        assert resp.status_code == 400

    def test_montage_mismatch_no_error(
        self, client: TestClient, tmp_path: Path, synthetic_csv: Path
    ):
        """Two CSVs with different column counts are outer-joined — no hard error."""
        content = synthetic_csv.read_text(encoding="utf-8-sig").splitlines()
        code_row_idx = next(i for i, l in enumerate(content) if "ClockDateTime" in l)

        trimmed_lines = []
        for i, line in enumerate(content):
            if i < code_row_idx:
                trimmed_lines.append(line)
            elif i == code_row_idx:
                parts = line.split(",")
                trimmed_lines.append(",".join(parts[:-5]))
            else:
                parts = line.split(",")
                trimmed_lines.append(",".join(parts[:-5]))

        mismatch = tmp_path / "SYNTH001_2.csv"
        mismatch.write_text("\n".join(trimmed_lines), encoding="utf-8-sig")

        scan = _scan_result(tmp_path, synthetic_csv, client)
        resp = client.post("/api/manifest/build", json={"scanned_files": scan["files"]})
        data = resp.json()
        patient = data["patients"][0]
        # Column-count differences are outer-joined — no validation error
        assert not any("mismatch" in e.lower() for e in patient["validation_errors"])
