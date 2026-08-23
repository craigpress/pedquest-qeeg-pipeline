"""Tests for qeeg.quality.ar_rejection — AR-suppressed zeros become NaN.

The behaviour that matters is asymmetric, so each class gets its own test: a rule
that nulls every zero destroys real data (Suppression Ratio is legitimately 0 in
74% of clean rows), and a rule that nulls none of them leaves suppressed epochs
masquerading as measurements.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from qeeg.quality.ar_rejection import apply_ar_rejection, region_of


@dataclass
class _Entry:
    """Minimal stand-in for ColumnEntry."""
    code: str
    i_group: int
    family: str
    trend_name: str


def _fixture():
    """8 rows. Rows 2-3: Left Hemisphere rejected. Row 6: every region rejected."""
    n = 8
    left_rej = [False, False, True, True, False, False, True, False]
    right_rej = [False, False, False, False, False, False, True, False]

    def sig(rej):
        return [0.0 if r else 5.0 for r in rej]

    df = pd.DataFrame({
        # ZERO_IMPOSSIBLE — seeds the mask
        "fft_left": sig(left_rej),
        "fft_right": sig(right_rej),
        # ZERO_LEGITIMATE — genuinely 0 in rows 0,1,4 as well as when rejected
        "supp_left": [0.0, 0.0, 0.0, 0.0, 0.0, 12.0, 0.0, 3.0],
        # NEVER_NULL - a real "no event" everywhere except the fully-rejected row
        "boolean_left": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    })
    schema = [
        _Entry("fft_left", 1, "fft_power", "FFT Power, 1 - 4 Hz, Left Hemisphere"),
        _Entry("fft_right", 2, "fft_power", "FFT Power, 1 - 4 Hz, Right Hemisphere"),
        _Entry("supp_left", 3, "suppression_ratio", "Suppression Ratio, Left Hemisphere"),
        _Entry("boolean_left", 4, "rhythmic_delta", "Boolean LAD+, Left Hemisphere"),
    ]
    return df, schema


def test_region_extraction_prefers_the_longer_token():
    assert region_of("FFT Power, 1 - 4 Hz, Left Anterior") == "Left Anterior"
    assert region_of("Suppression Ratio, Anterior") == "Anterior"
    assert region_of("Artifact Intensity") == ""


def test_zero_impossible_is_nulled_on_its_own_zero():
    df, schema = _fixture()
    out, res = apply_ar_rejection(df, schema)
    # Left is rejected in rows 2, 3, 6.
    assert out["fft_left"].isna().tolist() == [False, False, True, True,
                                               False, False, True, False]
    assert (out["fft_left"] == 0).sum() == 0, "no suppressed zero may survive"
    assert res.n_regions == 2


def test_zero_legitimate_keeps_its_real_zeros():
    """The whole point: Suppression Ratio is validly 0 outside rejected epochs."""
    df, schema = _fixture()
    out, _ = apply_ar_rejection(df, schema)
    # Nulled only where Left Hemisphere was rejected (rows 2, 3, 6) …
    assert out["supp_left"].isna().tolist() == [False, False, True, True,
                                                False, False, True, False]
    # … and rows 0, 1, 4 keep their genuine zeros.
    assert out.loc[[0, 1, 4], "supp_left"].eq(0.0).all()


def test_never_null_survives_partial_rejection_but_not_total():
    """A binary 0 is a real negative only if some region was analysable."""
    df, schema = _fixture()
    out, _ = apply_ar_rejection(df, schema)
    # Row 6 is the only row where every region is rejected.
    assert out["boolean_left"].isna().tolist() == [False, False, False, False,
                                                   False, False, True, False]
    # Rows 2 and 3 are partially rejected — the binary keeps its real 0 there.
    assert out.loc[[2, 3], "boolean_left"].eq(0.0).all()


def test_all_regions_mask_marks_only_the_total_rejection():
    df, schema = _fixture()
    _, res = apply_ar_rejection(df, schema)
    assert res.all_regions_mask.tolist() == [False, False, False, False,
                                             False, False, True, False]
    assert res.rows_all_rejected == 1
    assert res.rows_partial == 2


def test_empty_segment_is_reported_not_masked():
    """Every reference >=95% zero means the segment is empty, not rejected."""
    n = 40
    df = pd.DataFrame({
        "fft_left": [0.0] * n,
        "supp_left": [0.0] * n,
    })
    schema = [
        _Entry("fft_left", 1, "fft_power", "FFT Power, 1 - 4 Hz, Left Hemisphere"),
        _Entry("supp_left", 2, "suppression_ratio", "Suppression Ratio, Left Hemisphere"),
    ]
    out, res = apply_ar_rejection(df, schema)
    assert res.segment_empty
    assert res.cells_nulled == 0
    assert out["supp_left"].notna().all(), "an empty segment must not be silently nulled"
    assert any("empty" in w for w in res.warnings)


def test_input_frame_is_not_mutated():
    df, schema = _fixture()
    before = df.copy()
    apply_ar_rejection(df, schema)
    pd.testing.assert_frame_equal(df, before)


def test_asymmetry_falls_back_to_an_anatomical_region():
    """Asym* regions carry no positive-definite measure of their own."""
    df, schema = _fixture()
    df["reasi"] = [0.0, 3.0, 0.0, 0.0, 1.0, 2.0, 0.0, 4.0]
    schema.append(_Entry("reasi", 5, "asymmetry",
                         "Asymmetry, Relative Index (REASI), 0 - 20 Hz, Asym Hemi"))
    out, _ = apply_ar_rejection(df, schema)
    # Asym Hemi falls back to Left/Right Hemisphere, so row 6 (all rejected) nulls.
    assert bool(out["reasi"].isna().iloc[6])
    # Row 0's zero is a genuine "symmetric" reading and must survive.
    assert out["reasi"].iloc[0] == 0.0
