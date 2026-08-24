"""Tests for FastAPI endpoints — health, upload, patients, export."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app, pipeline_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def loaded_patient(synthetic_csv: Path):
    """Process a synthetic CSV and load it into the pipeline service."""
    import shutil
    from qeeg.pipeline import process_patient
    from qeeg.storage.result_cache import save_result, content_hash_files
    from qeeg.config import PipelineConfig

    result = process_patient(synthetic_csv)
    config = PipelineConfig()
    content_hash = content_hash_files([synthetic_csv])
    save_result(
        result,
        config.model_dump(),
        content_hash,
        [str(synthetic_csv)],
        pipeline_service.cache_dir,
    )
    pipeline_service._build_patient_index()
    yield result

    pipeline_service._patient_index.pop(result.patient_id, None)
    with pipeline_service._lock:
        pipeline_service._hot_cache.pop(result.patient_id, None)
    patient_dir = pipeline_service.cache_dir / result.patient_id
    if patient_dir.exists():
        shutil.rmtree(patient_dir)


class TestHealthCheck:
    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "patients_loaded" in data


class TestUploadLocal:
    def test_register_local_csv(self, client: TestClient, synthetic_csv: Path):
        resp = client.post(
            "/api/upload/local",
            json={"paths": [str(synthetic_csv)]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "file_id" in data[0]
        assert data[0]["filename"] == synthetic_csv.name
        assert data[0]["size_bytes"] > 0

    def test_nonexistent_file_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/upload/local",
            json={"paths": ["C:\\nonexistent\\file.csv"]},
        )
        assert resp.status_code == 404

    def test_non_csv_returns_400(self, client: TestClient, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a csv")
        resp = client.post(
            "/api/upload/local",
            json={"paths": [str(txt_file)]},
        )
        assert resp.status_code == 400

    def test_re_register_does_not_overwrite_original(
        self, client: TestClient, synthetic_csv: Path
    ):
        """Regression: re-registering an already-registered file must not
        overwrite or rename the original CSV via a stale ptr resolved by
        get_upload_path (the bug that destroyed a 1 GB EEG file in prod)."""
        original_content = synthetic_csv.read_bytes()
        original_size = synthetic_csv.stat().st_size

        # First registration
        resp1 = client.post("/api/upload/local", json={"paths": [str(synthetic_csv)]})
        assert resp1.status_code == 200

        # Second registration — same file, should not corrupt the original
        resp2 = client.post("/api/upload/local", json={"paths": [str(synthetic_csv)]})
        assert resp2.status_code == 200

        # Original CSV must be untouched
        assert synthetic_csv.exists(), "Original CSV was deleted or renamed"
        assert synthetic_csv.stat().st_size == original_size, (
            f"Original CSV size changed: {synthetic_csv.stat().st_size} != {original_size}"
        )
        assert synthetic_csv.read_bytes() == original_content, (
            "Original CSV contents were overwritten"
        )

    def test_colliding_filenames_get_distinct_file_ids(
        self, client: TestClient, tmp_path: Path
    ):
        """Regression: two patients can export trend CSVs with the SAME filename
        (Persyst names exports by timestamp, e.g. 20260611_1323_.csv). They must
        get distinct file_ids so their .ptr files don't collide and resolve to
        each other's data — the bug that made one patient's segment resolve to a
        different patient's recording (a 3,553h timeline artifact)."""
        a = tmp_path / "patA" / "20260611_1323_.csv"
        b = tmp_path / "patB" / "20260611_1323_.csv"
        a.parent.mkdir(parents=True)
        b.parent.mkdir(parents=True)
        a.write_text("File,Z:/A/subject-3_x.dat\nheader\n1,2,3\n", encoding="utf-8")
        b.write_text("File,Z:/B/subject-13_y.dat\nheader\nx,y\n", encoding="utf-8")

        fid_a = client.post("/api/upload/local", json={"paths": [str(a)]}).json()[0]["file_id"]
        fid_b = client.post("/api/upload/local", json={"paths": [str(b)]}).json()[0]["file_id"]

        # Distinct file_ids despite identical filename
        assert fid_a != fid_b, f"colliding filenames produced same file_id: {fid_a}"
        # Each file_id resolves back to its OWN file (no cross-patient .ptr overwrite)
        assert pipeline_service.get_upload_path(fid_a).resolve() == a.resolve()
        assert pipeline_service.get_upload_path(fid_b).resolve() == b.resolve()


class TestUploadMultipart:
    def test_upload_csv(self, client: TestClient, synthetic_csv: Path):
        with open(synthetic_csv, "rb") as f:
            resp = client.post(
                "/api/upload",
                files=[("files", ("test.csv", f, "text/csv"))],
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["size_bytes"] > 0

    def test_reject_non_csv(self, client: TestClient, tmp_path: Path):
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        with open(txt, "rb") as f:
            resp = client.post(
                "/api/upload",
                files=[("files", ("test.txt", f, "text/plain"))],
            )
        assert resp.status_code == 400


class TestPatientEndpoints:
    def test_list_patients_empty(self, client: TestClient):
        resp = client.get("/api/patients")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_patients_with_data(self, client: TestClient, loaded_patient):
        resp = client.get("/api/patients")
        assert resp.status_code == 200
        data = resp.json()
        ids = [p["patient_id"] for p in data]
        assert loaded_patient.patient_id in ids

    def test_get_patient(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/patients/{pid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == pid

    def test_get_patient_not_found(self, client: TestClient):
        resp = client.get("/api/patients/nonexistent")
        assert resp.status_code == 404

    def test_get_schema(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/patients/{pid}/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "code" in data[0]
        assert "family" in data[0]

    def test_get_chart_metadata(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/patients/{pid}/chart-metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert "panels" in data
        panels = data["panels"]
        assert len(panels) == 20
        ids = {p["panel_id"] for p in panels}
        assert "band_power_anterior" in ids
        assert "seizure_probability" in ids
        # Each panel has required fields
        for p in panels:
            assert "display_name" in p
            assert "variables" in p
            assert "cadence_seconds" in p
            assert "units" in p

    def test_get_chart_metadata_not_found(self, client: TestClient):
        resp = client.get("/api/patients/nonexistent/chart-metadata")
        assert resp.status_code == 404

    def test_get_epochs(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/patients/{pid}/epochs?families=aeeg")
        assert resp.status_code == 200
        data = resp.json()
        assert "hours" in data
        assert "columns" in data
        assert len(data["hours"]) == 50

    def test_get_bins(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/patients/{pid}/bins")
        assert resp.status_code == 200
        data = resp.json()
        assert "bins" in data
        assert "bin_edges" in data

    def test_get_overlay(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/patients/{pid}/overlay")
        assert resp.status_code == 200
        data = resp.json()
        assert "artifact_regions" in data
        assert "bin_boundaries" in data


class TestExportEndpoints:
    def test_export_csv(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/export/{pid}/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_export_json(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/export/{pid}/json")
        assert resp.status_code == 200
        data = resp.json()
        assert "patient_id" in data

    def test_export_codebook_includes_categorical_metadata(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/export/{pid}/codebook")
        assert resp.status_code == 200
        data = resp.json()

        missingness = next(row for row in data if row["variable_name"] == "missingness_flag")
        assert missingness["data_type"] == "string"
        assert missingness["is_categorical"] is True
        codes = {item["code"] for item in missingness["categories"]}
        assert {"complete", "high_artifact", "moderate_artifact", "low_data", "no_data"} <= codes

        n_observed = next(row for row in data if row["variable_name"] == "n_observed")
        assert n_observed["data_type"] == "integer"
        assert "row count" in n_observed["label"].lower() or "row count" in n_observed["notes"].lower()

    def test_export_invalid_format(self, client: TestClient, loaded_patient):
        pid = loaded_patient.patient_id
        resp = client.get(f"/api/export/{pid}/invalid_format")
        assert resp.status_code in (400, 422)

    def test_export_nonexistent_patient(self, client: TestClient):
        resp = client.get("/api/export/nonexistent/csv")
        assert resp.status_code == 404
