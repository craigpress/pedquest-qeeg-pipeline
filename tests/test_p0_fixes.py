"""Regression tests for the Phase-2 P0 fix set (behavior-changing, authorized).

Each test would have FAILED before its fix and documents the corrected behavior.
See docs/review/SHIP_READINESS_REPORT.md for the full change set.
"""
from __future__ import annotations

import pytest

import numpy as np
import pandas as pd

from qeeg.analysis.seizure import _is_seizure_column
from qeeg.analysis.time_binning import aggregate_by_bins
from qeeg.storage.export import _FAMILY_UNITS


# --- P0-2: seizure-column detector must match REAL Persyst labels ------------
# The prior singular, word-bounded regex matched only synthetic singular labels
# and silently produced no seizures on real (plural / MMX-Name) exports.
@pytest.mark.parametrize("label", [
    "Seizure Detections (red) and Notifications (gray)",  # CSV ref §3.22
    "Seizure Notifications (P14)",
    "SeizureProbabilityP14 Probability",
    "SeizureProbabilityP14 Detections",
    "Seizure Detection P14",          # singular synthetic form must still match
    "Seizure Probability",
])
def test_seizure_pattern_matches_real_and_synthetic_labels(label):
    assert _is_seizure_column(label), f"seizure detector missed {label!r}"


@pytest.mark.parametrize("label", [
    "FFT Power, 1-4 Hz",
    "aEEG Left Hemisphere",
    "Artifact Intensity",
])
def test_seizure_pattern_does_not_overmatch(label):
    assert not _is_seizure_column(label), f"seizure detector false-positive on {label!r}"


# --- P0-7: asymmetry unit is percent, not a (-1..+1) index -------------------
def test_asymmetry_unit_is_percent_not_index():
    unit = _FAMILY_UNITS["asymmetry"]
    assert "%" in unit, f"asymmetry unit should be percent, got {unit!r}"
    assert "index (−1" not in unit and "-1 to +1" not in unit, (
        f"asymmetry still mislabeled as a -1..+1 index: {unit!r}"
    )


# --- P0-4: native ADR + V8 status/burden families reach analysis selection ---
def test_keep_families_includes_native_ratio_and_v8_metrics():
    import inspect
    from qeeg import pipeline
    src = inspect.getsource(pipeline._select_analysis_variables)
    for fam in ("adr", "relative_power", "status_epilepticus", "seizure_burden"):
        assert f'"{fam}"' in src, f"{fam} missing from analysis-variable selection"


# --- P0-3: seizure burden must not collapse to 0 when seizure exclusion is on -
def _burden_setup():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    hours = pd.Series([0.5, 1.5, 2.5, 3.5])
    edges = [0, 6]  # one bin
    durations = pd.Series([1.0, 1.0, 1.0, 1.0])  # 1 h/epoch
    seizure = pd.Series([False, True, False, False])  # epoch 1 is seizure
    artifact_clean = pd.Series([True, True, True, True])
    return df, hours, edges, durations, seizure, artifact_clean


def test_seizure_burden_survives_exclusion_with_artifact_clean_mask():
    df, hours, edges, durations, seizure, artifact_clean = _burden_setup()
    # Analysis mask excludes the seizure epoch (exclusion_mode != "none").
    usable = artifact_clean & ~seizure
    result = aggregate_by_bins(
        df, hours, ["x"], edges,
        usable_mask=usable,
        seizure_mask=seizure,
        artifact_clean_mask=artifact_clean,
        epoch_durations_hours=durations,
        min_coverage_hours=0.0,
    )
    # One artifact-clean seizure epoch of 1 h → burden must be 1.0, not 0.
    assert result.iloc[0]["seizure_burden_hours"] == pytest.approx(1.0)


def test_seizure_burden_counts_all_seizure_bin():
    # An all-seizure bin has n_usable == 0 yet is the highest-burden case.
    df, hours, edges, durations, _, artifact_clean = _burden_setup()
    seizure = pd.Series([True, True, True, True])
    usable = artifact_clean & ~seizure  # all False
    result = aggregate_by_bins(
        df, hours, ["x"], edges,
        usable_mask=usable,
        seizure_mask=seizure,
        artifact_clean_mask=artifact_clean,
        epoch_durations_hours=durations,
        min_coverage_hours=0.0,
    )
    assert result.iloc[0]["seizure_burden_hours"] == pytest.approx(4.0)


# --- P0-1: V8 Suppression Ratio is 0–100 percent, not a 0–1 fraction ---------
# Resolved against the real subject-1_rec V8 export (research-trends panel):
# Suppression Ratio column max = 30.97 > 1, which rules out a 0–1 fraction.
def test_suppression_threshold_default_is_acns_continuity_boundary():
    # ACNS 2021: <10% suppression = continuous/nearly-continuous; 10-49% = discontinuous.
    import inspect
    sig = inspect.signature(aggregate_by_bins)
    default = sig.parameters["suppression_threshold"].default
    assert default == 10.0, (
        f"BCI default threshold should be 10 (ACNS continuity boundary), got {default!r}"
    )


def test_bci_uses_acns_10pct_boundary():
    # Suppression in PERCENT: 5% and 8% are continuous (<10); 30% is discontinuous.
    df = pd.DataFrame({"suppression_left": [5.0, 8.0, 30.0]})
    hours = pd.Series([0.0, 1 / 3600, 2 / 3600])
    result = aggregate_by_bins(
        df, hours, ["suppression_left"], [0, 1],
        min_coverage_hours=0.0,
        suppression_columns=["suppression_left"],  # uses the 10.0 ACNS default
    )
    assert result.iloc[0]["background_continuity_index"] == pytest.approx(2 / 3)


def test_median_suppression_not_double_scaled():
    # The QC median-suppression report must NOT ×100 a value that is already percent.
    import inspect
    from qeeg import pipeline
    src = inspect.getsource(pipeline.run_pipeline) if hasattr(pipeline, "run_pipeline") else ""
    if not src:
        # Fall back to scanning the module source for the QC line.
        src = inspect.getsource(pipeline)
    assert "median_val * 100" not in src, "median suppression still ×100 (P0-1 regression)"
    assert "round(median_val, 1)" in src, "median suppression should be reported un-scaled"
