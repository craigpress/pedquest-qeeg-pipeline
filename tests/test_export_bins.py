"""Tests for export bin handling — low-coverage bins must be present."""
import json
import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
from qeeg.storage.export import export_patient_bins_long, export_patient_semi_long
from qeeg.storage.export import build_provenance


def test_semi_long_export_includes_low_coverage_bins():
    """F3 regression: semi-long must include all bins with NA for low-coverage features."""
    bins = pd.DataFrame([
        {
            "bin_label": "0-6h", "bin_start_hours": 0, "bin_end_hours": 6,
            "n_total_epochs": 21600, "n_usable_epochs": 20000,
            "n_effective_fft": 2500, "coverage_hours": 5.6,
            "coverage_fraction": 0.93, "meets_minimum": True,
            "missingness_flag": "complete",
            "var1_median": 1.5, "var1_mean": 1.6, "var1_sd": 0.3,
            "var1_iqr": 0.4, "var1_min": 0.5, "var1_max": 3.0, "var1_n": 20000,
        },
        {
            "bin_label": "6-12h", "bin_start_hours": 6, "bin_end_hours": 12,
            "n_total_epochs": 21600, "n_usable_epochs": 500,
            "n_effective_fft": 60, "coverage_hours": 0.14,
            "coverage_fraction": 0.02, "meets_minimum": False,
            "missingness_flag": "low_data",
            "var1_median": np.nan, "var1_mean": np.nan, "var1_sd": np.nan,
            "var1_iqr": np.nan, "var1_min": np.nan, "var1_max": np.nan, "var1_n": 0,
        },
    ])

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "semi.csv"
        export_patient_semi_long({"P001": bins}, {"P001": {}}, path)
        result = pd.read_csv(path)
        bin_labels = result["time_bin"].tolist()
        assert "6-12h" in bin_labels, (
            "Low-coverage bin 6-12h was silently dropped from semi-long export"
        )


def test_long_export_uses_n_observed_and_optional_n_effective():
    """Long export must separate observed row counts from effective FFT counts."""
    bins = pd.DataFrame([
        {
            "bin_label": "0-6h",
            "bin_start_hours": 0,
            "bin_end_hours": 6,
            "coverage_hours": 5.6,
            "n_effective_fft": 2500,
            "fft_delta_left_median": 1.5,
            "fft_delta_left_mean": 1.6,
            "fft_delta_left_sd": 0.3,
            "fft_delta_left_iqr": 0.4,
            "fft_delta_left_min": 0.5,
            "fft_delta_left_max": 3.0,
            "fft_delta_left_n": 20000,
            "fft_delta_left_n_observed": 20000,
            "fft_delta_left_n_effective": 2500,
            "fft_delta_left_effective_basis": "fft_power_cadence_adjusted",
            "suppression_left_median": 0.2,
            "suppression_left_mean": 0.25,
            "suppression_left_sd": 0.1,
            "suppression_left_iqr": 0.05,
            "suppression_left_min": 0.0,
            "suppression_left_max": 0.6,
            "suppression_left_n": 20000,
            "suppression_left_n_observed": 20000,
            "suppression_left_n_effective": 2000,
            "suppression_left_effective_basis": "suppression_ratio_cadence_adjusted",
        }
    ])

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "long.csv"
        export_patient_bins_long({"P001": bins}, {"P001": {}}, path)
        result = pd.read_csv(path)

    assert "n_observed" in result.columns
    assert "n_independent" not in result.columns
    assert "n_effective" in result.columns
    assert "n_effective_basis" in result.columns

    fft_row = result[result["feature_name"] == "fft_delta_left"].iloc[0]
    assert fft_row["n_observed"] == 20000
    assert fft_row["n_effective"] == 2500
    assert fft_row["n_effective_basis"] == "fft_power_cadence_adjusted"

    suppression_row = result[result["feature_name"] == "suppression_left"].iloc[0]
    assert suppression_row["n_observed"] == 20000
    assert suppression_row["n_effective"] == 2000
    assert suppression_row["n_effective_basis"] == "suppression_ratio_cadence_adjusted"


def test_provenance_preserves_config_and_source_hashes():
    prov = build_provenance(
        config={"artifact": {"mode": "quality"}},
        source_files=["patient.csv"],
        source_file_hashes={"patient.csv": "abc123"},
    )
    assert prov["config"]["artifact"]["mode"] == "quality"
    assert prov["source_file_hashes"]["patient.csv"] == "abc123"


def test_provenance_includes_audit_hashes_and_stage_row_counts():
    """Provenance must carry MMX / clinical / corrections hashes and stage row counts for publication audit."""
    prov = build_provenance(
        config={"artifact": {"mode": "quality"}},
        source_files=["patient.csv"],
        source_file_hashes={"patient.csv": "abc123"},
        mmx_file_hash="deadbeef",
        clinical_metadata_hash="c0ffee",
        corrections_hash=None,
        stage_row_counts={"parsed": 100, "usable": 80, "binned_rows": 4},
        hash_strategy="full_sha256",
    )
    assert prov["mmx_file_hash"] == "deadbeef"
    assert prov["clinical_metadata_hash"] == "c0ffee"
    assert prov["corrections_hash"] is None
    assert prov["stage_row_counts"]["parsed"] == 100
    assert prov["stage_row_counts"]["usable"] == 80
    assert prov["stage_row_counts"]["binned_rows"] == 4
    assert prov["hash_strategy"] == "full_sha256"


def test_provenance_carries_clinical_metadata_and_corrections_rows():
    """Reviewers should see the actual ROSC anchor and the correction row(s)
    that produced the timing — not just their hash."""
    clinical = {
        "patient_id": "subject-10",
        "rosc_date": "2026-04-01",
        "rosc_time": "12:34:56",
        "age_at_arrest_days": 365,
    }
    corrections = {
        "subject-10_rec": {
            "new_name": "subject-10_rec",
            "age_in_days_at_time_of_eeg": 365,
            "eeg_start_time": "12:35:01",
            "eeg_duration": "11:32:00",
        }
    }
    prov = build_provenance(
        config={},
        clinical_metadata=clinical,
        eeg_corrections=corrections,
    )
    assert prov["clinical_metadata"]["rosc_time"] == "12:34:56"
    assert prov["clinical_metadata"]["age_at_arrest_days"] == 365
    assert "subject-10_rec" in prov["eeg_corrections"]
    assert prov["eeg_corrections"]["subject-10_rec"]["eeg_start_time"] == "12:35:01"


def test_research_package_includes_manifest_and_epoch_parquet(tmp_path):
    """Audit bundle must include MANIFEST.sha256 with one SHA-256 per non-manifest member,
    and the epoch parquet must be present so independent recomputation is possible."""
    import hashlib
    import zipfile
    from qeeg.storage.export import build_research_package

    # Minimal inputs that exercise the code paths without requiring a full run.
    epochs = pd.DataFrame({
        "_hours_relative": [0.0, 1.0, 2.0],
        "_usable": [True, True, False],
        "fft_delta_left": [1.0, 1.1, np.nan],
    })
    bins = pd.DataFrame([{
        "bin_label": "0-6h",
        "bin_start_hours": 0,
        "bin_end_hours": 6,
        "coverage_hours": 2.0,
        "coverage_fraction": 0.67,
        "bin_expected_hours": 6.0,
        "observed_wall_clock_hours": 3.0,
        "artifact_clean_hours": 2.0,
        "clean_fraction_of_observed": 0.67,
        "clean_fraction_of_expected": 0.33,
        "n_observed": 3,
        "n_effective_fft": 2,
        "background_continuity_index": np.nan,
        "missingness_flag": "moderate_artifact",
        "meets_minimum": True,
        "fft_delta_left_median": 1.05,
        "fft_delta_left_mean": 1.05,
        "fft_delta_left_sd": 0.05,
        "fft_delta_left_iqr": 0.05,
        "fft_delta_left_min": 1.0,
        "fft_delta_left_max": 1.1,
        "fft_delta_left_n": 2,
    }])

    buf = build_research_package(
        patient_id="TEST-001",
        epochs=epochs,
        bin_summary=bins,
        schema=[],
        config={"artifact": {"mode": "quality"}},
        qc_dict={},
        seizure_dict={},
        source_files=[],
        source_file_hashes={},
        mmx_file_hash="m" * 64,
        clinical_metadata_hash=None,
        corrections_hash=None,
        stage_row_counts={"parsed": 3, "binned_rows": 1},
    )

    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        assert "TEST-001_epochs.parquet" in names, "epoch parquet missing from package"
        assert "MANIFEST.sha256" in names, "MANIFEST.sha256 missing from package"
        manifest = zf.read("MANIFEST.sha256").decode()
        # Every non-manifest member must have exactly one matching manifest line.
        for n in names:
            if n == "MANIFEST.sha256":
                continue
            expected = hashlib.sha256(zf.read(n)).hexdigest()
            assert f"{expected}  {n}" in manifest, f"{n} missing or hash mismatch in MANIFEST.sha256"
        prov = json.loads(zf.read("provenance.json"))
        assert prov["mmx_file_hash"] == "m" * 64
        assert prov["stage_row_counts"]["parsed"] == 3


def test_research_package_data_dictionary_uses_mmx_engine_summary():
    """Packaged data dictionary must reflect the actual MMX engine metadata, not only defaults."""
    import json
    import zipfile
    from qeeg.ingestion.column_mapper import ColumnEntry
    from qeeg.storage.export import build_research_package

    schema = [
        ColumnEntry(
            col_index=0,
            code="I1_1",
            i_group=1,
            sub_index=1,
            trend_name="Suppression Left",
            family="suppression_ratio",
            frequency_band="",
            freq_min_hz=None,
            freq_max_hz=None,
            hemisphere="left",
            region="hemisphere",
            electrode="",
            common_name="suppression_left",
        )
    ]
    epochs = pd.DataFrame({"_hours_relative": [0.0], "suppression_left": [0.1]})
    bins = pd.DataFrame([{
        "bin_label": "0-6h",
        "bin_start_hours": 0,
        "bin_end_hours": 6,
        "coverage_hours": 0.001,
        "coverage_fraction": 1.0,
        "missingness_flag": "low_data",
        "suppression_left_median": 0.1,
        "suppression_left_n": 1,
    }])
    buf = build_research_package(
        patient_id="TEST-ENG",
        epochs=epochs,
        bin_summary=bins,
        schema=schema,
        config={},
        qc_dict={},
        seizure_dict={},
        mmx_engines_summary={"Amplitude01": {"epoch_duration": 12.0, "epoch_step": 6.0}},
    )
    with zipfile.ZipFile(buf, "r") as zf:
        dictionary = json.loads(zf.read("data_dictionary.json"))
    suppression = next(e for e in dictionary if e["variable_name"] == "suppression_left")
    assert suppression["persyst_engine"] == "Amplitude01"
    assert suppression["window_seconds"] == 12.0
    assert suppression["cadence_seconds"] == 6
    assert "EpochStep=6s" in suppression["n_effective_definition"]
