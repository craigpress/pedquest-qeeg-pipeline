"""Tests for qeeg.features.region_mapping — bilateral side-contribution metadata.

Covers the research-readiness requirement that bilateral anterior/posterior
features advertise how many hemispheres contributed, and that the
``require_bilateral`` gate suppresses unilateral survivor values when callers
want strict two-side coverage.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from qeeg.features.region_mapping import (
    compute_anterior,
    compute_posterior,
    compute_regional_features,
)


def test_sides_contributing_counts_reflect_non_null_inputs():
    df = pd.DataFrame({
        "la": [1.0, 2.0, np.nan, np.nan],
        "ra": [3.0, np.nan, 5.0, np.nan],
        "lp": [np.nan, 4.0, 6.0, np.nan],
        "rp": [7.0, 8.0, np.nan, np.nan],
    })
    fft_cols = {
        "delta": {
            "Left Anterior": "la", "Right Anterior": "ra",
            "Left Posterior": "lp", "Right Posterior": "rp",
        }
    }
    result = compute_regional_features(df, fft_cols)

    # Both sides valid → 2; one side valid → 1; neither → 0
    assert result["fft_delta_anterior_sides_contributing"].tolist() == [2, 1, 1, 0]
    assert result["fft_delta_posterior_sides_contributing"].tolist() == [1, 2, 1, 0]


def test_default_requires_bilateral_contribution():
    """Default (require_bilateral=True): NaN when one hemisphere is missing.

    PedQuEST/POCCA publication policy: bilateral features must have both
    sides; unilateral survivor values are not treated as bilateral
    physiology. Callers can opt out via require_bilateral=False for
    diagnostic exploration.
    """
    la = pd.Series([1.0, np.nan])
    ra = pd.Series([3.0, 5.0])
    bilateral = compute_anterior(la, ra)
    assert bilateral.iloc[0] == 2.0          # both sides → mean
    assert np.isnan(bilateral.iloc[1])       # unilateral → NaN

    # Opt-out path still works
    relaxed = compute_anterior(la, ra, require_bilateral=False)
    assert relaxed.iloc[1] == 5.0


def test_all_nan_rows_return_nan_without_runtime_warning():
    la = pd.Series([np.nan, 2.0, np.nan])
    ra = pd.Series([np.nan, np.nan, 6.0])
    lp = pd.Series([np.nan, 8.0, np.nan])
    rp = pd.Series([np.nan, np.nan, 10.0])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        anterior = compute_anterior(la, ra, require_bilateral=False)
        posterior = compute_posterior(lp, rp, require_bilateral=False)

    assert np.isnan(anterior.iloc[0])
    assert anterior.iloc[1:].tolist() == [2.0, 6.0]
    assert np.isnan(posterior.iloc[0])
    assert posterior.iloc[1:].tolist() == [8.0, 10.0]
    assert not [warning for warning in caught if issubclass(warning.category, RuntimeWarning)]


def test_require_bilateral_drops_unilateral_survivor():
    la = pd.Series([1.0, np.nan])
    ra = pd.Series([3.0, 5.0])
    bilateral = compute_anterior(la, ra, require_bilateral=True)
    assert bilateral.iloc[0] == 2.0
    assert np.isnan(bilateral.iloc[1])


def test_require_bilateral_flag_threads_through_compute_regional_features():
    df = pd.DataFrame({
        "la": [1.0, np.nan],
        "ra": [3.0, 5.0],
        "lp": [7.0, 9.0],
        "rp": [11.0, np.nan],
    })
    fft_cols = {
        "delta": {
            "Left Anterior": "la", "Right Anterior": "ra",
            "Left Posterior": "lp", "Right Posterior": "rp",
        }
    }
    relaxed = compute_regional_features(df, fft_cols, require_bilateral=False)
    strict = compute_regional_features(df, fft_cols, require_bilateral=True)

    assert relaxed["fft_delta_anterior"].iloc[1] == 5.0
    assert np.isnan(strict["fft_delta_anterior"].iloc[1])
    assert relaxed["fft_delta_posterior"].iloc[1] == 9.0
    assert np.isnan(strict["fft_delta_posterior"].iloc[1])
    # Side counts do not change with the strict flag — they always report
    # the factual number of contributing sides.
    assert relaxed["fft_delta_anterior_sides_contributing"].tolist() == strict["fft_delta_anterior_sides_contributing"].tolist()


def test_compute_regional_features_all_nan_rows_return_nan_without_runtime_warning():
    df = pd.DataFrame({
        "la": [np.nan, 2.0],
        "ra": [np.nan, np.nan],
        "lp": [np.nan, np.nan],
        "rp": [np.nan, 10.0],
    })
    fft_cols = {
        "delta": {
            "Left Anterior": "la", "Right Anterior": "ra",
            "Left Posterior": "lp", "Right Posterior": "rp",
        }
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        result = compute_regional_features(df, fft_cols, require_bilateral=False)

    assert np.isnan(result["fft_delta_anterior"].iloc[0])
    assert result["fft_delta_anterior"].iloc[1] == 2.0
    assert np.isnan(result["fft_delta_posterior"].iloc[0])
    assert result["fft_delta_posterior"].iloc[1] == 10.0
    assert result["fft_delta_anterior_sides_contributing"].tolist() == [0, 1]
    assert result["fft_delta_posterior_sides_contributing"].tolist() == [0, 1]
    assert not [warning for warning in caught if issubclass(warning.category, RuntimeWarning)]
