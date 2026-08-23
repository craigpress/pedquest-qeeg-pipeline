"""Tests for seizure burden computation — especially under seizure exclusion."""
import pandas as pd
import numpy as np
import pytest
from qeeg.analysis.seizure import compute_seizure_report


def test_seizure_burden_nonzero_under_exclusion():
    """F2 regression: seizure burden must NOT collapse to zero when
    the usable mask excludes seizure epochs.

    The bug: pipeline.py built usable = artifact_clean & ~seizure_mask,
    then passed that as usable_mask to compute_seizure_report.
    seizure_in_usable = (seizure_mask & usable_mask).sum() was always 0.
    """
    n = 1000
    df = pd.DataFrame({"I121_1": np.random.rand(n)})

    # 10% seizure epochs (indices 100-199)
    seizure_mask = pd.Series(False, index=range(n))
    seizure_mask.iloc[100:200] = True

    # Artifact-clean mask: 90% clean
    artifact_clean = pd.Series(True, index=range(n))
    artifact_clean.iloc[900:1000] = False  # 10% artifact at end

    # This is the CORRECT mask for seizure burden: artifact-only, NOT excluding seizures
    report = compute_seizure_report(
        df,
        seizure_columns={"probability": "I121_1"},
        seizure_mask=seizure_mask,
        usable_mask=artifact_clean,  # artifact-only denominator
        hours_relative=pd.Series(np.linspace(0, 1, n)),
    )

    # 100 seizure epochs out of 900 artifact-clean epochs = 11.1%
    assert report.seizure_burden_pct > 0, "Seizure burden must not collapse to zero"
    assert abs(report.seizure_burden_pct - 11.11) < 1.0, (
        f"Expected ~11.1%, got {report.seizure_burden_pct:.1f}%"
    )


def test_seizure_burden_artifact_only_denominator():
    """Seizure burden denominator should be artifact-clean time,
    not artifact-clean-minus-seizure time."""
    n = 3600  # 1 hour
    df = pd.DataFrame({"I121_1": np.zeros(n)})

    seizure_mask = pd.Series(False, index=range(n))
    seizure_mask.iloc[0:360] = True  # 10% seizure

    artifact_clean = pd.Series(True, index=range(n))  # 100% clean

    report = compute_seizure_report(
        df,
        seizure_columns={"probability": "I121_1"},
        seizure_mask=seizure_mask,
        usable_mask=artifact_clean,
        hours_relative=pd.Series(np.linspace(0, 1, n)),
    )

    # 360 / 3600 = 10.0%
    assert abs(report.seizure_burden_pct - 10.0) < 0.1
