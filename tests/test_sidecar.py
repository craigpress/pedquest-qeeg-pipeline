"""Tests for qeeg.ingestion.sidecar — write, read, invalidation."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

import qeeg.ingestion.sidecar as sidecar_mod
from qeeg.ingestion.sidecar import SidecarMeta, read_sidecar, write_sidecar


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Redirect sidecar and parquet cache dirs to a temp location for test isolation."""
    sidecar_dir = tmp_path / ".qeeg_cache" / "sidecars"
    parquet_dir = tmp_path / ".qeeg_cache" / "parquet"
    monkeypatch.setattr(sidecar_mod, "_SIDECAR_DIR", sidecar_dir)
    monkeypatch.setattr(sidecar_mod, "_PARQUET_DIR", parquet_dir)


def _make_scan_sidecar(csv_path: Path, **overrides) -> SidecarMeta:
    defaults = dict(
        source_csv=str(csv_path),
        source_mtime=csv_path.stat().st_mtime,
        file_type="persyst_csv",
        csv_panel_type="trends",
        patient_id="SYNTH001",
        test_date="03/15/2025",
        test_time="10:00:00",
        encoding="utf-8-sig",
        n_columns=33,
        n_data_rows=50,
        phase="scan",
    )
    defaults.update(overrides)
    return SidecarMeta(**defaults)


class TestWriteAndReadSidecar:
    def test_round_trip_scan_phase(self, synthetic_csv: Path):
        meta = _make_scan_sidecar(synthetic_csv)
        write_sidecar(synthetic_csv, meta)
        loaded = read_sidecar(synthetic_csv)
        assert loaded is not None
        assert loaded.file_type == "persyst_csv"
        assert loaded.csv_panel_type == "trends"
        assert loaded.patient_id == "SYNTH001"
        assert loaded.phase == "scan"

    def test_round_trip_full_phase(self, synthetic_csv: Path):
        meta = _make_scan_sidecar(
            synthetic_csv,
            phase="full",
            code_row_index=7,
            trend_row_index=6,
            persyst_version="Persyst 14",
            code_to_description={"I1_1": "Artifact Intensity"},
            description_to_codes={"Artifact Intensity": ["I1_1"]},
        )
        write_sidecar(synthetic_csv, meta)
        loaded = read_sidecar(synthetic_csv)
        assert loaded is not None
        assert loaded.phase == "full"
        assert loaded.code_row_index == 7
        assert loaded.trend_row_index == 6
        assert loaded.persyst_version == "Persyst 14"
        assert loaded.code_to_description == {"I1_1": "Artifact Intensity"}
        assert loaded.description_to_codes == {"Artifact Intensity": ["I1_1"]}


class TestReadSidecarMiss:
    def test_returns_none_when_no_sidecar(self, synthetic_csv: Path):
        assert read_sidecar(synthetic_csv) is None

    def test_returns_none_on_mtime_mismatch(self, synthetic_csv: Path):
        meta = _make_scan_sidecar(synthetic_csv, source_mtime=0.0)
        write_sidecar(synthetic_csv, meta)
        assert read_sidecar(synthetic_csv) is None

    def test_returns_none_after_csv_touch(self, synthetic_csv: Path):
        import os
        meta = _make_scan_sidecar(synthetic_csv)
        write_sidecar(synthetic_csv, meta)
        assert read_sidecar(synthetic_csv) is not None

        # Move the CSV mtime forward by 2s (> 1s tolerance in read_sidecar)
        new_mtime = synthetic_csv.stat().st_mtime + 2.0
        os.utime(synthetic_csv, (new_mtime, new_mtime))
        assert read_sidecar(synthetic_csv) is None

    def test_returns_none_on_corrupt_json(self, synthetic_csv: Path):
        from qeeg.ingestion.sidecar import sidecar_path
        sidecar_path(synthetic_csv).parent.mkdir(parents=True, exist_ok=True)
        sidecar_path(synthetic_csv).write_text("not valid json", encoding="utf-8")
        assert read_sidecar(synthetic_csv) is None


class TestWriteSidecarRobustness:
    def test_write_failure_does_not_raise(self, synthetic_csv: Path, monkeypatch):
        """write_sidecar silently ignores PermissionError."""
        import qeeg.ingestion.sidecar as sm

        def _bad_mkdir(*a, **kw):
            raise PermissionError("read-only")

        monkeypatch.setattr(Path, "mkdir", _bad_mkdir)
        write_sidecar(synthetic_csv, _make_scan_sidecar(synthetic_csv))  # must not raise

    def test_unknown_fields_ignored_on_read(self, synthetic_csv: Path):
        """Future sidecar versions with extra fields should still load."""
        import json
        from qeeg.ingestion.sidecar import sidecar_path

        meta = _make_scan_sidecar(synthetic_csv)
        data = {f.name: getattr(meta, f.name) for f in meta.__dataclass_fields__.values()}
        data["future_field"] = "ignored"
        sidecar_path(synthetic_csv).parent.mkdir(parents=True, exist_ok=True)
        sidecar_path(synthetic_csv).write_text(json.dumps(data), encoding="utf-8")
        loaded = read_sidecar(synthetic_csv)
        assert loaded is not None
        assert loaded.patient_id == "SYNTH001"


class TestParquetCachePath:
    def test_different_paths_different_hashes(self, tmp_path: Path):
        from qeeg.ingestion.sidecar import parquet_cache_path
        p1 = tmp_path / "a.csv"
        p2 = tmp_path / "b.csv"
        p1.touch()
        p2.touch()
        assert parquet_cache_path(p1) != parquet_cache_path(p2)

    def test_same_path_same_hash(self, synthetic_csv: Path):
        from qeeg.ingestion.sidecar import parquet_cache_path
        assert parquet_cache_path(synthetic_csv) == parquet_cache_path(synthetic_csv)
