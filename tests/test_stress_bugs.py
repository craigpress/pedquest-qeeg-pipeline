"""Bug verification tests — confirm all 10 bugs from the hostile review are FIXED.

Each test asserts the corrected behavior after the bug fix.
"""
from __future__ import annotations

import inspect
import tempfile
from pathlib import Path

import pandas as pd
import numpy as np
import pytest


# -----------------------------------------------------------------------
# Bug 1 (FIXED): alignment_check.py:65 — dead pd.datetime code removed
# -----------------------------------------------------------------------
def test_bug1_strptime_uses_stdlib_datetime():
    """parse_rosc_time no longer uses pd.datetime (removed in pandas 2.0).

    Uses stdlib datetime.strptime as fallback after pd.Timestamp.
    """
    assert not hasattr(pd, "datetime"), "pd.datetime exists — pandas < 2.0?"

    from qeeg.validation.alignment_check import parse_rosc_time
    for date_str in ["03/15/25 10:30", "03/15/2025 10:30", "2025-03-15 10:30:00"]:
        result = parse_rosc_time(date_str)
        assert result is not None, f"Failed to parse '{date_str}'"


# -----------------------------------------------------------------------
# Bug 2 (FIXED): subject_registry.py:61 — ROSC stored as ISO on ingest
# -----------------------------------------------------------------------
def test_bug2_rosc_json_roundtrip_fixed():
    """ROSC time is converted to ISO at ingest, survives JSON round-trip."""
    from qeeg.alignment.subject_registry import SubjectRegistry, PatientRecord
    from qeeg.validation.alignment_check import parse_rosc_time

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        tmp = Path(f.name)

    try:
        registry = SubjectRegistry()
        record = PatientRecord(patient_id="test", rosc_time="2024-03-15T10:30:00")
        registry.add_patient(record)
        registry.save(tmp)

        registry2 = SubjectRegistry(tmp)
        loaded = registry2.get_patient("test")

        # FIXED: ISO string survives JSON round-trip
        parsed = parse_rosc_time(loaded.rosc_time)
        assert parsed is not None
        assert parsed.year == 2024
    finally:
        tmp.unlink(missing_ok=True)


def test_bug2_excel_serial_string_now_parsed():
    """parse_rosc_time now handles numeric strings (Excel serial from JSON)."""
    from qeeg.validation.alignment_check import parse_rosc_time

    # Excel serial 45366.395833 ≈ 2024-03-15 ~09:30
    result = parse_rosc_time("45366.395833")
    assert result is not None
    assert result.year == 2024


# -----------------------------------------------------------------------
# Bug 3 (FIXED): data_checks.py:19 — PHI now fails is_valid
# -----------------------------------------------------------------------
def test_bug3_phi_fails_validation():
    """PHI detection now causes is_valid to return False."""
    from qeeg.validation.data_checks import ValidationReport

    report = ValidationReport()
    report.phi_detected = True
    report.warnings.append("Warning: Possible PHI detected in patient name")

    # FIXED: is_valid returns False when PHI detected
    assert report.is_valid is False


# -----------------------------------------------------------------------
# Bug 4 (FIXED): strip_phi_metadata clears all PHI fields
# -----------------------------------------------------------------------
def test_bug4_strip_phi_complete():
    """strip_phi_metadata now clears patient_name, patient_id, test_date, test_time."""
    from qeeg.ingestion.parser import ExportMetadata
    from qeeg.validation.data_checks import strip_phi_metadata

    meta = ExportMetadata(
        patient_name="John Doe",
        patient_id="MRN12345",
        test_date="03/15/2025",
        test_time="10:00:00",
    )
    strip_phi_metadata(meta)

    assert meta.patient_name == ""
    assert meta.patient_id == ""
    assert meta.test_date == ""
    assert meta.test_time == ""


# -----------------------------------------------------------------------
# Bug 5 (UPDATED 2026-04-24): bilateral now requires both sides by default.
# Original "NaN-tolerant" behavior is preserved as the require_bilateral=False
# opt-out for diagnostic exploration; PedQuEST/POCCA publication policy is
# require_bilateral=True so unilateral survivors do not become bilateral.
# -----------------------------------------------------------------------
def test_bug5_bilateral_requires_both_sides_by_default():
    """Default require_bilateral=True: NaN when one hemisphere is missing."""
    from qeeg.features.region_mapping import compute_anterior

    left = pd.Series([10.0, float("nan"), 30.0])
    right = pd.Series([20.0, 40.0, 50.0])
    result = compute_anterior(left, right)

    assert result.iloc[0] == 15.0   # both sides → (10+20)/2
    assert pd.isna(result.iloc[1])  # one side missing → NaN
    assert result.iloc[2] == 40.0   # both sides → (30+50)/2

    # Opt-out path preserves the legacy NaN-tolerant behavior.
    relaxed = compute_anterior(left, right, require_bilateral=False)
    assert relaxed.iloc[1] == 40.0


# -----------------------------------------------------------------------
# Bug 6a (FIXED): artifact_intensity range corrected to (0, 50)
# -----------------------------------------------------------------------
def test_bug6a_artifact_range_fixed():
    """artifact_intensity validation now uses (0, 50) matching Persyst 0-30+ scale."""
    from qeeg.validation.data_checks import check_value_ranges

    # Value 80 is implausible on 0-30+ scale and should be flagged
    df = pd.DataFrame({"art1": [25.0, 50.0, 80.0]})
    families = {"artifact_intensity": ["art1"]}
    result = check_value_ranges(df, families)

    # FIXED: 80 exceeds the (0, 50) range → flagged
    assert "artifact_intensity" in result
    assert result["artifact_intensity"] == 1  # only 80 is out of range


# -----------------------------------------------------------------------
# Bug 6b (FIXED): electrode_quality range corrected to (0, 1)
# -----------------------------------------------------------------------
def test_bug6b_quality_range_fixed():
    """electrode_quality validation now uses (0, 1) matching Persyst degradation scale."""
    from qeeg.validation.data_checks import check_value_ranges

    df = pd.DataFrame({"eq1": [0.5, 2.0, 5.0]})
    families = {"electrode_quality": ["eq1"]}
    result = check_value_ranges(df, families)

    # FIXED: 2.0 and 5.0 exceed the (0, 1) range → flagged
    assert "electrode_quality" in result
    assert result["electrode_quality"] == 2


# -----------------------------------------------------------------------
# Bug 7 (FIXED): leading zeros no longer capped at 50
# -----------------------------------------------------------------------
def test_bug7_leading_zeros_uncapped():
    """detect_leading_zeros now scans all rows, not just first 50."""
    from qeeg.validation.data_checks import detect_leading_zeros

    df = pd.DataFrame({"fft1": [0.0] * 100 + [10.0] * 50})
    result = detect_leading_zeros(df, ["fft1"])

    # FIXED: returns 100, not 50
    assert result == 100


# -----------------------------------------------------------------------
# Bug 8 (FIXED): timestamp gaps use positional indexing
# -----------------------------------------------------------------------
def test_bug8_noninteger_index_works():
    """detect_timestamp_gaps now works with any index type."""
    from qeeg.validation.data_checks import detect_timestamp_gaps

    ts = pd.Series(pd.date_range("2025-01-01", periods=10, freq="1s"))
    ts.index = [f"row_{i}" for i in range(10)]
    ts.iloc[5] = ts.iloc[4] + pd.Timedelta(seconds=120)

    # FIXED: no TypeError — uses positional indexing
    gaps = detect_timestamp_gaps(ts)
    assert len(gaps) > 0
    assert gaps[0]["start_idx"] == 4
    assert gaps[0]["end_idx"] == 5


# -----------------------------------------------------------------------
# Bug 9 (FIXED): atomic JSON write with temp + os.replace
# -----------------------------------------------------------------------
def test_bug9_atomic_write():
    """project_store._save() now uses temp file + os.replace for atomic writes."""
    from qeeg.storage.project_store import ProjectStore

    source = inspect.getsource(ProjectStore._save)
    assert "replace" in source
    assert ".tmp" in source or "tmp" in source


# -----------------------------------------------------------------------
# Bug 10 (FIXED): missing columns now logged instead of silent skip
# -----------------------------------------------------------------------
def test_bug10_missing_columns_logged(caplog):
    """compute_regional_features logs when columns are missing."""
    import logging
    from qeeg.features.region_mapping import compute_regional_features

    df = pd.DataFrame({"I10_1": [1.0, 2.0, 3.0]})
    fft_cols = {"delta": {"Left Anterior": "I10_1"}}

    with caplog.at_level(logging.DEBUG, logger="qeeg.features.region_mapping"):
        result = compute_regional_features(df, fft_cols)

    assert "fft_delta_anterior" not in result.columns
    assert any("Skipping" in r.message for r in caplog.records)
