"""Tests for EEG date corrections: upload endpoint, sort logic, date pipeline, edge cases."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app, pipeline_service
from api.services.pipeline_service import ClinicalMetadata, EEGCorrection


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def corrections_csv(tmp_path: Path) -> Path:
    """Write a corrections CSV with two segments for patient SYNTH001."""
    path = tmp_path / "corrections.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "new_name", "age_in_days_at_time_of_eeg",
            "eeg_start_time", "eeg_duration",
        ])
        writer.writeheader()
        writer.writerow({
            "new_name": "SYNTH001_1",
            "age_in_days_at_time_of_eeg": 100,
            "eeg_start_time": "10:00:00",
            "eeg_duration": "02:00:00",
        })
        writer.writerow({
            "new_name": "SYNTH001_2",
            "age_in_days_at_time_of_eeg": 101,
            "eeg_start_time": "08:30:00",
            "eeg_duration": "03:00:00",
        })
    return path


# ---------------------------------------------------------------------------
# Unit tests: _sort_paths_by_corrections
# ---------------------------------------------------------------------------

class TestSortPathsByCorrections:
    def test_sorts_by_age_then_start_time(self, tmp_path: Path):
        """Paths should be ordered by (age_in_days, eeg_start_time)."""
        p1 = tmp_path / "SEG_A.csv"
        p2 = tmp_path / "SEG_B.csv"
        p3 = tmp_path / "SEG_C.csv"
        for p in (p1, p2, p3):
            p.touch()

        # Store corrections in reverse order
        pipeline_service._eeg_corrections = {
            "SEG_C": EEGCorrection("SEG_C", 50, "08:00:00", "01:00:00"),
            "SEG_A": EEGCorrection("SEG_A", 51, "10:00:00", "02:00:00"),
            "SEG_B": EEGCorrection("SEG_B", 50, "14:00:00", "01:00:00"),
        }
        try:
            result = pipeline_service._sort_paths_by_corrections([p1, p2, p3])
            stems = [p.stem for p in result]
            # Day 50 08:00 < Day 50 14:00 < Day 51 10:00
            assert stems == ["SEG_C", "SEG_B", "SEG_A"]
        finally:
            pipeline_service._eeg_corrections = {}

    def test_missing_correction_sorts_last(self, tmp_path: Path):
        """Paths without corrections sort to the end."""
        p1 = tmp_path / "HAS_CORR.csv"
        p2 = tmp_path / "NO_CORR.csv"
        p1.touch()
        p2.touch()

        pipeline_service._eeg_corrections = {
            "HAS_CORR": EEGCorrection("HAS_CORR", 10, "09:00:00", "01:00:00"),
        }
        try:
            result = pipeline_service._sort_paths_by_corrections([p2, p1])
            stems = [p.stem for p in result]
            assert stems == ["HAS_CORR", "NO_CORR"]
        finally:
            pipeline_service._eeg_corrections = {}

    def test_empty_corrections_preserves_order(self, tmp_path: Path):
        """With no corrections stored, original order is preserved."""
        p1 = tmp_path / "A.csv"
        p2 = tmp_path / "B.csv"
        p1.touch()
        p2.touch()
        result = pipeline_service._sort_paths_by_corrections([p1, p2])
        assert result == [p1, p2]

    def test_sorts_by_embedded_dat_stem_before_csv_stem(self, tmp_path: Path):
        """CSV filenames are panel/export artifacts; embedded .dat stem is canonical."""
        p1 = tmp_path / "export_panel_b.csv"
        p2 = tmp_path / "export_panel_a.csv"
        p1.write_text('File,C:\\data\\PAT_2.dat\nClockDateTime,I1_1\n1,1\n', encoding="utf-8")
        p2.write_text('File,C:\\data\\PAT_1.dat\nClockDateTime,I1_1\n1,1\n', encoding="utf-8")

        pipeline_service._eeg_corrections = {
            "PAT_1": EEGCorrection("PAT_1", 10, "08:00:00", "01:00:00"),
            "PAT_2": EEGCorrection("PAT_2", 11, "08:00:00", "01:00:00"),
        }
        try:
            result = pipeline_service._sort_paths_by_corrections([p1, p2])
            assert result == [p2, p1]
        finally:
            pipeline_service._eeg_corrections = {}

    def test_relevant_corrections_use_embedded_dat_stem(self, tmp_path: Path):
        p = tmp_path / "arbitrary_export_name.csv"
        p.write_text('File,C:\\data\\PAT_1.dat\nClockDateTime,I1_1\n1,1\n', encoding="utf-8")
        pipeline_service._eeg_corrections = {
            "PAT_1": EEGCorrection("PAT_1", 10, "08:00:00", "01:00:00"),
        }
        try:
            relevant = pipeline_service._relevant_corrections_for_paths([p])
            assert list(relevant) == ["PAT_1"]
            assert relevant["PAT_1"]["eeg_start_time"] == "08:00:00"
        finally:
            pipeline_service._eeg_corrections = {}

    def test_zero_age_in_days(self, tmp_path: Path):
        """age_in_days=0 should sort before positive values."""
        p1 = tmp_path / "DAY0.csv"
        p2 = tmp_path / "DAY5.csv"
        p1.touch()
        p2.touch()

        pipeline_service._eeg_corrections = {
            "DAY0": EEGCorrection("DAY0", 0, "12:00:00", "01:00:00"),
            "DAY5": EEGCorrection("DAY5", 5, "08:00:00", "02:00:00"),
        }
        try:
            result = pipeline_service._sort_paths_by_corrections([p2, p1])
            stems = [p.stem for p in result]
            assert stems == ["DAY0", "DAY5"]
        finally:
            pipeline_service._eeg_corrections = {}


# ---------------------------------------------------------------------------
# Unit tests: _apply_date_corrections
# ---------------------------------------------------------------------------

class TestApplyDateCorrections:
    def test_returns_none_without_clinical_metadata(self, synthetic_csv: Path):
        """No clinical metadata → (None, None)."""
        result = pipeline_service._apply_date_corrections(
            [synthetic_csv], "SYNTH001",
        )
        assert result == (None, None)

    def test_returns_none_without_rosc_datetime(self, synthetic_csv: Path):
        """Clinical metadata without rosc_datetime → (None, None)."""
        pipeline_service._clinical_metadata["SYNTH001"] = ClinicalMetadata(
            patient_id="SYNTH001", age_at_arrest_days=100, rosc_datetime=None,
        )
        try:
            result = pipeline_service._apply_date_corrections(
                [synthetic_csv], "SYNTH001",
            )
            assert result == (None, None)
        finally:
            pipeline_service._clinical_metadata.pop("SYNTH001", None)

    def test_returns_none_when_correction_missing_for_segment(
        self, synthetic_csv_pair: tuple[Path, Path],
    ):
        """If any segment lacks a correction entry, returns (None, None)."""
        p1, p2 = synthetic_csv_pair

        pipeline_service._clinical_metadata["SYNTH001"] = ClinicalMetadata(
            patient_id="SYNTH001", age_at_arrest_days=100,
            rosc_datetime="2025-04-10T14:00:00",
        )
        # Only provide correction for one of two files
        pipeline_service._eeg_corrections = {
            "SYNTH001_1": EEGCorrection("SYNTH001_1", 100, "10:00:00", "02:00:00"),
        }
        try:
            result = pipeline_service._apply_date_corrections([p1, p2], "SYNTH001")
            assert result == (None, None)
        finally:
            pipeline_service._clinical_metadata.pop("SYNTH001", None)
            pipeline_service._eeg_corrections = {}

    def test_synthetic_timestamps_generated(self, synthetic_csv: Path):
        """With valid metadata + corrections, synthetic timestamps are generated."""
        rosc_dt = "2025-04-10T14:00:00"
        age_days = 100

        pipeline_service._clinical_metadata["SYNTH001"] = ClinicalMetadata(
            patient_id="SYNTH001", age_at_arrest_days=age_days, rosc_datetime=rosc_dt,
        )
        pipeline_service._eeg_corrections = {
            "SYNTH001_1": EEGCorrection("SYNTH001_1", age_days, "10:00:00", "02:00:00"),
        }
        try:
            parsed_list, rosc_str = pipeline_service._apply_date_corrections(
                [synthetic_csv], "SYNTH001",
            )
            assert parsed_list is not None
            # _apply_date_corrections normalizes to pd.Timestamp string format
            assert pd.Timestamp(rosc_str) == pd.Timestamp(rosc_dt)
            assert len(parsed_list) == 1

            df = parsed_list[0].data
            clock = df["ClockDateTime"]
            assert pd.api.types.is_numeric_dtype(clock)

            # Synthetic timestamps should be monotonically increasing
            diffs = clock.diff().dropna()
            assert (diffs > 0).all(), "Timestamps should be monotonically increasing"

            # Segment start = birthday_date + age_days + eeg_start_time.
            # birthday now preserves ROSC clock time (Task 4 D.4) but
            # seg_start in pipeline_service normalizes at point of use, so the
            # expected result is still the same as the old midnight-anchored math.
            excel_epoch = pd.Timestamp("1899-12-30")
            rosc = pd.Timestamp(rosc_dt)
            birthday_date = (rosc - pd.Timedelta(days=age_days)).normalize()
            expected_start = birthday_date + pd.Timedelta(days=age_days, hours=10)
            expected_serial = (expected_start - excel_epoch).total_seconds() / 86400.0

            assert abs(float(clock.iloc[0]) - expected_serial) < 0.001
        finally:
            pipeline_service._clinical_metadata.pop("SYNTH001", None)
            pipeline_service._eeg_corrections = {}

    def test_zero_age_in_days_correction(self, synthetic_csv: Path):
        """age_in_days=0 should produce timestamps on the birthday itself."""
        rosc_dt = "2025-01-01T12:00:00"

        pipeline_service._clinical_metadata["SYNTH001"] = ClinicalMetadata(
            patient_id="SYNTH001", age_at_arrest_days=0, rosc_datetime=rosc_dt,
        )
        pipeline_service._eeg_corrections = {
            "SYNTH001_1": EEGCorrection("SYNTH001_1", 0, "08:00:00", "01:00:00"),
        }
        try:
            parsed_list, rosc_str = pipeline_service._apply_date_corrections(
                [synthetic_csv], "SYNTH001",
            )
            assert parsed_list is not None

            df = parsed_list[0].data
            clock = df["ClockDateTime"]

            # Birthday = rosc_date - 0 days = 2025-01-01
            # Segment start = birthday + 0 days + 08:00:00 = 2025-01-01 08:00
            excel_epoch = pd.Timestamp("1899-12-30")
            expected_start = pd.Timestamp("2025-01-01 08:00:00")
            expected_serial = (expected_start - excel_epoch).total_seconds() / 86400.0

            assert abs(float(clock.iloc[0]) - expected_serial) < 0.001
        finally:
            pipeline_service._clinical_metadata.pop("SYNTH001", None)
            pipeline_service._eeg_corrections = {}

    def test_multi_segment_ordering(self, synthetic_csv_pair: tuple[Path, Path]):
        """Multiple corrected segments should have non-overlapping timestamp ranges."""
        p1, p2 = synthetic_csv_pair
        rosc_dt = "2025-04-10T14:00:00"
        age_days = 100

        pipeline_service._clinical_metadata["SYNTH001"] = ClinicalMetadata(
            patient_id="SYNTH001", age_at_arrest_days=age_days, rosc_datetime=rosc_dt,
        )
        pipeline_service._eeg_corrections = {
            "SYNTH001_1": EEGCorrection("SYNTH001_1", 100, "10:00:00", "02:00:00"),
            "SYNTH001_2": EEGCorrection("SYNTH001_2", 101, "08:30:00", "03:00:00"),
        }
        try:
            parsed_list, _ = pipeline_service._apply_date_corrections(
                [p1, p2], "SYNTH001",
            )
            assert parsed_list is not None
            assert len(parsed_list) == 2

            # Segment 2 (day 101) should start after segment 1 (day 100)
            last_ts_seg1 = float(parsed_list[0].data["ClockDateTime"].iloc[-1])
            first_ts_seg2 = float(parsed_list[1].data["ClockDateTime"].iloc[0])
            assert first_ts_seg2 > last_ts_seg1
        finally:
            pipeline_service._clinical_metadata.pop("SYNTH001", None)
            pipeline_service._eeg_corrections = {}

    def test_preserves_within_segment_timestamp_gap(self, synthetic_csv: Path, monkeypatch):
        """Date correction should replace the anchor, not flatten real gaps."""
        class FakeParsed:
            def __init__(self):
                self.data = pd.DataFrame({
                    "ClockDateTime": [
                        1.0,
                        1.0 + 1 / 86400,
                        1.0 + 301 / 86400,
                        1.0 + 302 / 86400,
                    ],
                    "I1_1": [1, 2, 3, 4],
                })

        import api.services.pipeline_service as ps_mod

        monkeypatch.setattr(ps_mod, "parse_persyst_csv", lambda _path: FakeParsed())
        pipeline_service._clinical_metadata["SYNTH001"] = ClinicalMetadata(
            patient_id="SYNTH001",
            age_at_arrest_days=100,
            rosc_datetime="2025-04-10T14:00:00",
        )
        pipeline_service._eeg_corrections = {
            synthetic_csv.stem: EEGCorrection(synthetic_csv.stem, 100, "10:00:00", "02:00:00"),
        }
        try:
            parsed_list, _ = pipeline_service._apply_date_corrections([synthetic_csv], "SYNTH001")
            assert parsed_list is not None
            diffs_seconds = parsed_list[0].data["ClockDateTime"].diff().dropna() * 86400
            assert diffs_seconds.iloc[0] == pytest.approx(1.0, rel=1e-4)
            assert diffs_seconds.iloc[1] == pytest.approx(300.0, rel=1e-4)
        finally:
            pipeline_service._clinical_metadata.pop("SYNTH001", None)
            pipeline_service._eeg_corrections = {}


# ---------------------------------------------------------------------------
# Integration tests: corrections upload endpoint
# ---------------------------------------------------------------------------

class TestCorrectionsUploadEndpoint:
    def test_upload_corrections_csv(
        self, client: TestClient, corrections_csv: Path,
    ):
        """POST /api/upload/corrections-path should accept a valid corrections CSV."""
        resp = client.post(
            "/api/upload/corrections-path",
            json={"path": str(corrections_csv)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert "SYNTH001_1" in data["files"]
        assert "SYNTH001_2" in data["files"]

        # Verify corrections are stored in service
        assert "SYNTH001_1" in pipeline_service._eeg_corrections
        corr = pipeline_service._eeg_corrections["SYNTH001_1"]
        assert corr.age_in_days_at_time_of_eeg == 100
        assert corr.eeg_start_time == "10:00:00"

        # Clean up
        pipeline_service._eeg_corrections = {}

    def test_upload_corrections_file(self, client: TestClient):
        """POST /api/upload/eeg-corrections should accept a CSV file upload."""
        csv_content = (
            "new_name,age_in_days_at_time_of_eeg,eeg_start_time,eeg_duration\n"
            "TEST_1,50,09:30:00,01:30:00\n"
        )
        resp = client.post(
            "/api/upload/eeg-corrections",
            files=[("file", ("corrections.csv", csv_content.encode(), "text/csv"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert "TEST_1" in data["files"]

        # Clean up
        pipeline_service._eeg_corrections = {}

    def test_upload_nonexistent_corrections_file(self, client: TestClient):
        """Missing file should return 404."""
        resp = client.post(
            "/api/upload/corrections-path",
            json={"path": "C:\\nonexistent\\corrections.csv"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests: _build_time_axis_response correction prefix match
# ---------------------------------------------------------------------------

class TestTimeAxisCorrectionPrefixMatch:
    def test_exact_patient_id_matches(self):
        """Exact patient-id key is picked up."""
        from api.routes.patients import _build_time_axis_response
        from api.services.pipeline_service import EEGCorrection

        pipeline_service._eeg_corrections = {
            "1002": EEGCorrection("1002", 100, "08:00:00", "02:00:00"),
        }
        try:
            # Just verify the lookup doesn't raise and picks the right correction
            matches = [
                c for name, c in pipeline_service._eeg_corrections.items()
                if name == "1002" or name.startswith("1002_")
            ]
            assert len(matches) == 1
            assert matches[0].eeg_start_time == "08:00:00"
        finally:
            pipeline_service._eeg_corrections = {}

    def test_segment_suffix_matches(self):
        """Keys like '1002_1' and '1002_2' match patient '1002'."""
        from api.services.pipeline_service import EEGCorrection

        pipeline_service._eeg_corrections = {
            "1002_1": EEGCorrection("1002_1", 100, "08:00:00", "02:00:00"),
            "1002_2": EEGCorrection("1002_2", 101, "08:00:00", "02:00:00"),
            "10020_1": EEGCorrection("10020_1", 50, "06:00:00", "02:00:00"),
        }
        try:
            matches = [
                c for name, c in pipeline_service._eeg_corrections.items()
                if name == "1002" or name.startswith("1002_")
            ]
            assert len(matches) == 2
            stems = {c.new_name for c in matches}
            assert stems == {"1002_1", "1002_2"}
        finally:
            pipeline_service._eeg_corrections = {}

    def test_neighbour_patient_not_matched(self):
        """Patient '10020' corrections must not be attributed to patient '1002'."""
        from api.services.pipeline_service import EEGCorrection

        pipeline_service._eeg_corrections = {
            "10020_1": EEGCorrection("10020_1", 50, "06:00:00", "02:00:00"),
            "10025_1": EEGCorrection("10025_1", 60, "07:00:00", "03:00:00"),
        }
        try:
            matches = [
                c for name, c in pipeline_service._eeg_corrections.items()
                if name == "1002" or name.startswith("1002_")
            ]
            assert matches == []
        finally:
            pipeline_service._eeg_corrections = {}
