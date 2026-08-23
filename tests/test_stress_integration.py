"""Integration tests — run the full pipeline on stress test data.

Requires: python tests/generate_stress_data.py to have been run first.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

STRESS_DIR = Path(__file__).resolve().parent.parent / "test_data" / "stress_test"

# Skip all tests if stress data hasn't been generated
pytestmark = pytest.mark.skipif(
    not (STRESS_DIR / "2046" / "2046_1.csv").exists(),
    reason="Stress test data not generated. Run: python tests/generate_stress_data.py",
)


@pytest.fixture(scope="module")
def pipeline_config():
    from qeeg.config import PipelineConfig
    return PipelineConfig()


def _run_patient(pid: str, rosc_time_str: str | None = None, config=None):
    """Helper to run pipeline for a single patient."""
    from qeeg.pipeline import process_patient
    from qeeg.config import PipelineConfig

    csv_path = STRESS_DIR / pid / f"{pid}_1.csv"
    assert csv_path.exists(), f"Missing: {csv_path}"

    return process_patient(
        csv_path,
        patient_id=pid,
        rosc_time_str=rosc_time_str,
        config=config or PipelineConfig(),
    )


# -----------------------------------------------------------------------
# Per-patient pipeline tests
# -----------------------------------------------------------------------

class TestPatient2046:
    """Seizure evolution: SE at 12-18h, resolution by 24h."""

    @pytest.fixture(scope="class")
    def result(self):
        from qeeg.config import PipelineConfig, SeizureConfig
        config = PipelineConfig(seizure=SeizureConfig(exclusion_mode="probability"))
        return _run_patient("2046", rosc_time_str="2025-01-10 09:30:00", config=config)

    def test_parses(self, result):
        assert result.epochs.shape[0] == 172800

    def test_has_seizures(self, result):
        assert result.seizure_report.seizure_burden_pct > 0

    def test_status_epilepticus(self, result):
        # SE criteria: >30 min continuous OR >50% hourly burden
        assert result.seizure_report.has_status_epilepticus is True

    def test_time_axis_rosc_aligned(self, result):
        assert result.time_info.reference == "rosc"

    def test_bin_summary_populated(self, result):
        assert result.bin_summary is not None
        assert len(result.bin_summary) > 0

    def test_qc_report(self, result):
        assert result.qc is not None


class TestPatient3640:
    """Burst-suppression → flat/isoelectric."""

    @pytest.fixture(scope="class")
    def result(self):
        return _run_patient("3640", rosc_time_str="2025-02-15 06:30:00")

    def test_parses(self, result):
        assert result.epochs.shape[0] == 172800

    def test_no_status_epilepticus(self, result):
        assert result.seizure_report.has_status_epilepticus is False

    def test_low_seizure_burden(self, result):
        assert result.seizure_report.seizure_burden_pct < 5.0

    def test_high_suppression_late(self, result):
        # Last bin should show high suppression ratio
        bins = result.bin_summary
        if bins is not None and len(bins) > 0:
            last_bin = bins.iloc[-1]
            # Look for suppression columns
            supp_cols = [c for c in bins.columns if "suppression" in c.lower() and "median" in c.lower()]
            if supp_cols:
                assert last_bin[supp_cols[0]] > 0.5, f"Expected high suppression in last bin"


class TestPatient3848:
    """Slow disorganized → recovery, brief early seizures."""

    @pytest.fixture(scope="class")
    def result(self):
        from qeeg.config import PipelineConfig, SeizureConfig
        config = PipelineConfig(seizure=SeizureConfig(exclusion_mode="probability"))
        return _run_patient("3848", rosc_time_str="2025-03-20 05:00:00", config=config)

    def test_parses(self, result):
        assert result.epochs.shape[0] == 172800

    def test_seizures_detected(self, result):
        # Brief early seizures detected — noise adds extra threshold crossings
        # SE may be triggered by "repeated seizures without 5 min recovery" criterion
        assert result.seizure_report.seizure_events > 0
        assert result.seizure_report.seizure_burden_pct > 0

    def test_rosc_alignment(self, result):
        assert result.time_info.reference == "rosc"


class TestPatient4458:
    """Good prognosis — state cycling, no seizures."""

    @pytest.fixture(scope="class")
    def result(self):
        return _run_patient("4458", rosc_time_str="2025-04-05 01:00:00")

    def test_parses(self, result):
        assert result.epochs.shape[0] == 172800

    def test_no_seizures(self, result):
        assert result.seizure_report.seizure_burden_pct < 1.0
        assert result.seizure_report.has_status_epilepticus is False

    def test_clean_recording(self, result):
        # Low artifact rate expected
        assert result.artifact_result.artifact_pct < 30.0


class TestPatient4682:
    """Mixed pattern with edge cases: 15 leading zeros, timestamp gap, bad quality values."""

    @pytest.fixture(scope="class")
    def result(self):
        return _run_patient("4682", rosc_time_str="2025-05-12 01:20:00")

    def test_parses(self, result):
        # Pipeline trims 15 leading zero rows → 172800 - 15 = 172785
        assert result.epochs.shape[0] == 172800 - result.validation.leading_zero_rows

    def test_seizure_detection_requires_config(self, result):
        # Default seizure mode is "none" — no seizure epochs counted.
        # But max_seizure_probability captures the peak from raw data.
        assert result.seizure_report.max_seizure_probability > 0.3
        # To actually detect seizures, must run with seizure_mode="probability"

    @pytest.fixture(scope="class")
    def result_with_seizures(self):
        from qeeg.config import PipelineConfig, SeizureConfig
        config = PipelineConfig(seizure=SeizureConfig(exclusion_mode="probability"))
        return _run_patient("4682", rosc_time_str="2025-05-12 01:20:00", config=config)

    def test_seizures_with_probability_mode(self, result_with_seizures):
        # With probability mode, seizure probability peaks exist
        assert result_with_seizures.seizure_report.max_seizure_probability > 0.3

    def test_rosc_alignment_edge(self, result):
        # 10h gap: ROSC 01:20 → EEG 11:20
        assert result.time_info.reference == "rosc"

    def test_leading_zeros_detected(self, result):
        # Validation should detect leading zeros (capped at 15, under the 50 limit)
        assert result.validation.leading_zero_rows > 0

    def test_timestamp_gap_detected(self, result):
        assert len(result.validation.timestamp_gaps) > 0

    def test_phi_stripped_by_parser(self, result):
        # Parser strips patient_name in _extract_metadata (always clears it).
        # So data_checks.validate_export never sees the name → phi_detected = False.
        # This is actually the parser protecting PHI proactively, but
        # data_checks.strip_phi_metadata (bug #4) is still incomplete.
        assert result.validation.phi_detected is False


# -----------------------------------------------------------------------
# Cross-patient tests
# -----------------------------------------------------------------------

class TestBatchAllPatients:
    """Verify all 5 patients process without crashing."""

    @pytest.fixture(scope="class")
    def all_results(self):
        from qeeg.config import PipelineConfig, SeizureConfig
        config = PipelineConfig(seizure=SeizureConfig(exclusion_mode="probability"))
        rosc_times = {
            "2046": "2025-01-10 09:30:00",
            "3640": "2025-02-15 06:30:00",
            "3848": "2025-03-20 05:00:00",
            "4458": "2025-04-05 01:00:00",
            "4682": "2025-05-12 01:20:00",
        }
        results = {}
        for pid, rosc in rosc_times.items():
            results[pid] = _run_patient(pid, rosc_time_str=rosc, config=config)
        return results

    def test_all_five_complete(self, all_results):
        assert len(all_results) == 5
        for pid, r in all_results.items():
            assert r is not None, f"Patient {pid} returned None"
            # Row count may differ due to leading zero trimming
            assert r.epochs.shape[0] > 170000, f"Patient {pid} too few rows"

    def test_se_in_seizure_patients(self, all_results):
        # 2046 (heavy seizures) should have SE
        assert all_results["2046"].seizure_report.has_status_epilepticus is True
        # 3640 (no seizures) and 4458 (no seizures) should NOT have SE
        assert all_results["3640"].seizure_report.has_status_epilepticus is False
        assert all_results["4458"].seizure_report.has_status_epilepticus is False


# -----------------------------------------------------------------------
# Folder scan test
# -----------------------------------------------------------------------

def test_folder_scan():
    """quick_scan finds all 5 CSVs correctly."""
    from qeeg.ingestion.quick_scan import quick_scan

    for pid in ["2046", "3640", "3848", "4458", "4682"]:
        csv_path = STRESS_DIR / pid / f"{pid}_1.csv"
        result = quick_scan(csv_path)
        assert result.patient_id == pid
        assert result.n_data_rows > 100000
        assert result.duration_hours is not None
        assert result.duration_hours > 40  # ~48h expected


# -----------------------------------------------------------------------
# Clinical metadata test
# -----------------------------------------------------------------------

def test_clinical_metadata_load():
    """Load clinical_data.csv via SubjectRegistry."""
    from qeeg.alignment.subject_registry import SubjectRegistry

    registry = SubjectRegistry()
    count = registry.load_from_csv(
        STRESS_DIR / "clinical_data.csv",
        id_column="patient_id",
    )
    assert count == 5

    p2046 = registry.get_patient("2046")
    assert p2046 is not None
    assert p2046.patient_id == "2046"
