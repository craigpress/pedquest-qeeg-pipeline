"""Tests for qeeg.pipeline — end-to-end processing on synthetic data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qeeg.config import PipelineConfig
from qeeg.pipeline import PatientResult, concatenate_and_process, process_patient


class TestProcessPatient:
    def test_returns_patient_result(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert isinstance(result, PatientResult)

    def test_patient_id(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert result.patient_id == "SYNTH001_1"  # derived from filename stem

    def test_custom_patient_id(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv, patient_id="CUSTOM_ID")
        assert result.patient_id == "CUSTOM_ID"

    def test_epochs_dataframe(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert isinstance(result.epochs, pd.DataFrame)
        assert len(result.epochs) == 50

    def test_pipeline_columns_added(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        expected_cols = [
            "_timestamp", "_hours_relative", "_artifact_clean",
            "_seizure_flag", "_usable",
        ]
        for col in expected_cols:
            assert col in result.epochs.columns, f"Missing column: {col}"

    def test_usable_mask_is_boolean(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert result.epochs["_usable"].dtype == bool

    def test_bin_summary_dataframe(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert isinstance(result.bin_summary, pd.DataFrame)
        assert "bin_label" in result.bin_summary.columns
        assert "coverage_hours" in result.bin_summary.columns

    def test_schema_populated(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert len(result.schema) > 0
        assert result.schema[0].family != ""

    def test_validation_report(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert result.validation.total_rows == 50

    def test_time_info(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert result.time_info.reference in ("rosc", "recording_start")
        assert result.time_info.reference_time is not None

    def test_artifact_result(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert result.artifact_result.total_epochs == 50
        assert 0 <= result.artifact_result.artifact_pct <= 100

    def test_seizure_report(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert result.seizure_report.total_seizure_epochs >= 0

    def test_qc_report(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert hasattr(result.qc, "to_dict")

    def test_warnings_is_list(self, synthetic_csv: Path):
        result = process_patient(synthetic_csv)
        assert isinstance(result.warnings, list)

    def test_progress_callback(self, synthetic_csv: Path):
        stages = []

        def cb(stage: str, frac: float):
            stages.append((stage, frac))

        process_patient(synthetic_csv, progress_cb=cb)
        assert len(stages) > 0
        # Last callback should be near 1.0
        assert stages[-1][1] >= 0.9

    def test_custom_config(self, synthetic_csv: Path):
        config = PipelineConfig(
            artifact={"mode": "none"},
            seizure={"exclusion_mode": "none"},
            binning={"bin_edges_hours": [0, 3, 6], "min_coverage_hours": 0.001},
        )
        result = process_patient(synthetic_csv, config=config)
        # With artifact mode "none", all epochs should be usable
        assert result.artifact_result.artifact_pct == 0.0
        assert result.epochs["_usable"].all()

    def test_nonexistent_file_raises(self, tmp_path: Path):
        with pytest.raises(Exception):
            process_patient(tmp_path / "does_not_exist.csv")


class TestConcatenateAndProcess:
    def test_single_file(self, synthetic_csv: Path):
        result = concatenate_and_process([synthetic_csv])
        assert isinstance(result, PatientResult)
        assert len(result.epochs) == 50

    def test_multi_file(self, synthetic_csv_pair: tuple[Path, Path]):
        p1, p2 = synthetic_csv_pair
        result = concatenate_and_process([p1, p2])
        assert isinstance(result, PatientResult)
        # Fixture emits two CSVs with identical timestamps and identical
        # semantic columns — the semantic-name merge correctly dedupes
        # overlapping rows rather than doubling the data. 50 unique epochs.
        assert len(result.epochs) == 50

    def test_uses_first_file_metadata(self, synthetic_csv_pair: tuple[Path, Path]):
        p1, p2 = synthetic_csv_pair
        result = concatenate_and_process([p1, p2])
        assert result.patient_id == "SYNTH001_1"  # derived from first filename stem
