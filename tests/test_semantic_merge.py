"""Regression tests for semantic-name multi-segment merge.

Covers the bug where two Persyst CSV segments exported from different MMX
panel configurations assigned the same ``I{group}_{sub}`` code to DIFFERENT
trends. The old raw-concat merge silently mixed those signals; the
``segment_merge`` module resolves each I-code to a semantic ``common_name``
slug before stitching so contributors line up on meaning, not on index.

Three scenarios:
1. Two segments where the same semantic trend is encoded under different
   I-group numbers — one merged column with values from both.
2. Two segments covering disjoint time windows for the same semantic trend
   — rows concatenate in time order.
3. Two segments with overlapping time windows — the denser contributor
   wins per row; lower-density contributor fills remaining NaNs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qeeg.ingestion.parser import ExportMetadata, ParsedExport
from qeeg.ingestion.segment_merge import merge_segments_by_semantic_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment(
    code_to_description: dict[str, str],
    data: dict[str, list],
    clock: list[float] | None = None,
) -> ParsedExport:
    """Build a minimal ParsedExport from a column→trend dict and row data.

    Any ``code_to_description`` entries missing from ``data`` get NaN rows.
    """
    cols: dict[str, list] = {}
    if clock is not None:
        cols["ClockDateTime"] = list(clock)
    for code in code_to_description:
        cols[code] = list(data.get(code, []))
    # Pad short columns to match max length
    n = max((len(v) for v in cols.values()), default=0)
    for c, v in cols.items():
        if len(v) < n:
            v.extend([np.nan] * (n - len(v)))
    df = pd.DataFrame(cols)
    if "ClockDateTime" in df.columns:
        df["ClockDateTime"] = pd.to_datetime(df["ClockDateTime"], unit="s", origin="unix")
    desc_to_codes: dict[str, list[str]] = {}
    for code, desc in code_to_description.items():
        desc_to_codes.setdefault(desc, []).append(code)
    return ParsedExport(
        data=df,
        code_to_description=dict(code_to_description),
        description_to_codes=desc_to_codes,
        metadata=ExportMetadata(file_path="syn"),
        code_row_index=0,
        trend_row_index=0,
    )


# ---------------------------------------------------------------------------
# Case 1: same semantic trend, different I-group numbers per segment
# ---------------------------------------------------------------------------

def test_same_semantic_trend_different_igroups_merges_to_single_column():
    """Seg A puts rhythmicity::Cz::1Hz at I100_1; seg B puts the same
    semantic trend at I200_1. The merged DataFrame must have exactly ONE
    column for that trend, populated from both segments."""
    seg_a = _make_segment(
        code_to_description={
            "I100_1": "Rhythmicity Spectrogram, Cz",  # sub_index=1 → 0-0.25Hz bin
        },
        data={"I100_1": [1.0, 2.0, 3.0]},
        clock=[0.0, 1.0, 2.0],
    )
    seg_b = _make_segment(
        code_to_description={
            "I200_1": "Rhythmicity Spectrogram, Cz",  # same trend, different I-group
        },
        data={"I200_1": [10.0, 20.0, 30.0]},
        clock=[3.0, 4.0, 5.0],
    )

    merged, schema = merge_segments_by_semantic_name([seg_a, seg_b])

    # Exactly one rhythmicity column for Cz / bin 1
    rhythm_cols = [c for c in merged.data.columns if c.startswith("rhythmicity")]
    assert len(rhythm_cols) == 1, f"Expected 1 rhythmicity col, got {rhythm_cols}"
    col = rhythm_cols[0]

    # Values from both segments must survive
    vals = merged.data.sort_values("ClockDateTime")[col].dropna().tolist()
    assert vals == [1.0, 2.0, 3.0, 10.0, 20.0, 30.0], vals

    # No raw I-codes in output columns
    assert "I100_1" not in merged.data.columns
    assert "I200_1" not in merged.data.columns

    # Schema uses semantic name as code
    codes = {e.code for e in schema}
    assert col in codes


# ---------------------------------------------------------------------------
# Case 2: disjoint time windows → stitch by time
# ---------------------------------------------------------------------------

def test_disjoint_time_windows_concat_in_time_order():
    """Same trend present in both segments, non-overlapping timestamps.
    Merged column should contain ALL rows from both, in time order."""
    trend = "FFT Power, 1 - 4 Hz, Left Hemisphere"
    seg_early = _make_segment(
        code_to_description={"I50_1": trend},
        data={"I50_1": [100.0, 200.0]},
        clock=[0.0, 1.0],
    )
    seg_late = _make_segment(
        code_to_description={"I80_1": trend},
        data={"I80_1": [300.0, 400.0, 500.0]},
        clock=[10.0, 11.0, 12.0],
    )

    merged, _schema = merge_segments_by_semantic_name([seg_early, seg_late])

    # Expect one fft_power column — both I-codes resolved to same common_name
    candidate_cols = [
        c for c in merged.data.columns if c.startswith("fft_") and c != "ClockDateTime"
    ]
    assert len(candidate_cols) == 1, f"Expected 1 FFT column, got {candidate_cols}"
    col = candidate_cols[0]

    sorted_df = merged.data.sort_values("ClockDateTime")
    assert sorted_df[col].tolist() == [100.0, 200.0, 300.0, 400.0, 500.0]
    # 5 unique timestamps from 2 disjoint segments
    assert len(sorted_df) == 5


# ---------------------------------------------------------------------------
# Case 3: overlapping time windows → highest non-NaN density wins
# ---------------------------------------------------------------------------

def test_overlapping_windows_highest_density_wins():
    """Two segments cover the same timestamps for the same trend. The
    segment with denser (fewer-NaN) data wins; sparser segment fills only
    the winner's NaN gaps.

    Seg A (dense): every row populated.
    Seg B (sparse): only rows 0 and 2 populated, rest NaN.
    Merged values at t=0,1,2 should come from Seg A entirely.
    """
    trend = "FFT Power, 1 - 4 Hz, Left Hemisphere"
    seg_dense = _make_segment(
        code_to_description={"I50_1": trend},
        data={"I50_1": [1.0, 2.0, 3.0]},
        clock=[0.0, 1.0, 2.0],
    )
    seg_sparse = _make_segment(
        code_to_description={"I80_1": trend},
        data={"I80_1": [99.0, np.nan, 99.0]},
        clock=[0.0, 1.0, 2.0],
    )

    merged, _schema = merge_segments_by_semantic_name([seg_dense, seg_sparse])

    fft_cols = [c for c in merged.data.columns if c.startswith("fft_")]
    assert len(fft_cols) == 1
    col = fft_cols[0]
    sorted_df = merged.data.sort_values("ClockDateTime")
    # Dense segment values must win every row
    assert sorted_df[col].tolist() == [1.0, 2.0, 3.0]


def test_overlapping_windows_sparse_fills_dense_gaps():
    """When the denser segment has occasional NaN gaps, sparser segments
    fill only those gaps. No cross-contamination."""
    trend = "FFT Power, 1 - 4 Hz, Left Hemisphere"
    # Dense segment has a NaN at t=1
    seg_a = _make_segment(
        code_to_description={"I50_1": trend},
        data={"I50_1": [1.0, np.nan, 3.0, 4.0]},
        clock=[0.0, 1.0, 2.0, 3.0],
    )
    # Sparse segment has a value at t=1 only
    seg_b = _make_segment(
        code_to_description={"I80_1": trend},
        data={"I80_1": [np.nan, 42.0, np.nan, np.nan]},
        clock=[0.0, 1.0, 2.0, 3.0],
    )

    merged, _schema = merge_segments_by_semantic_name([seg_a, seg_b])
    fft_cols = [c for c in merged.data.columns if c.startswith("fft_")]
    col = fft_cols[0]
    sorted_df = merged.data.sort_values("ClockDateTime")
    assert sorted_df[col].tolist() == [1.0, 42.0, 3.0, 4.0]


# ---------------------------------------------------------------------------
# Case 4: collision prevention — different trends, same I-code
# ---------------------------------------------------------------------------

def test_same_icode_different_trends_across_segments_no_cross_contamination():
    """Reproduces the subject-1 root cause: two segments with the same
    ``I288_1`` but DIFFERENT semantic meanings. The merged DataFrame must
    keep them as DISTINCT columns (one per semantic name), never mixing
    values across meanings.
    """
    seg_a = _make_segment(
        code_to_description={
            # Same I-code, but FreqPow regional summary in this segment
            "I288_1": "Rhythmicity Spectrogram FreqPow LA, 1 - 25 Hz, Left Anterior",
        },
        data={"I288_1": [1.1, 1.2, 1.3]},
        clock=[0.0, 1.0, 2.0],
    )
    seg_b = _make_segment(
        code_to_description={
            # Same I-code, but full rhythmicity spectrogram bin in this segment
            "I288_1": "Rhythmicity Spectrogram, Cz",
        },
        data={"I288_1": [99.1, 99.2]},
        clock=[3.0, 4.0],
    )

    merged, schema = merge_segments_by_semantic_name([seg_a, seg_b])

    # Must produce TWO distinct semantic columns — one per trend.
    freqpow_cols = [c for c in merged.data.columns if "freqpow" in c]
    spec_cols = [
        c for c in merged.data.columns
        if c.startswith("rhythmicity_") and "freqpow" not in c
    ]
    assert len(freqpow_cols) == 1, f"Expected 1 freqpow col, got {freqpow_cols}"
    assert len(spec_cols) == 1, f"Expected 1 rhythmicity spec col, got {spec_cols}"

    # Values must NOT cross-contaminate
    sorted_df = merged.data.sort_values("ClockDateTime")
    fp_vals = sorted_df[freqpow_cols[0]].dropna().tolist()
    sp_vals = sorted_df[spec_cols[0]].dropna().tolist()
    assert fp_vals == [1.1, 1.2, 1.3], fp_vals
    assert sp_vals == [99.1, 99.2], sp_vals

    # Schema should have two entries with different families
    freqpow_entry = next(e for e in schema if e.code == freqpow_cols[0])
    spec_entry = next(e for e in schema if e.code == spec_cols[0])
    assert freqpow_entry.family == "rhythmicity"
    assert spec_entry.family == "rhythmicity"
    # And the common_name encodes the region/electrode distinction
    assert freqpow_entry.common_name == freqpow_cols[0]
    assert spec_entry.common_name == spec_cols[0]


def test_single_segment_passthrough():
    """Single-segment input should still produce a valid merged ParsedExport
    with semantic-name columns and a matching schema."""
    trend = "FFT Power, 1 - 4 Hz, Left Hemisphere"
    seg = _make_segment(
        code_to_description={"I50_1": trend},
        data={"I50_1": [1.0, 2.0, 3.0]},
        clock=[0.0, 1.0, 2.0],
    )
    merged, schema = merge_segments_by_semantic_name([seg])
    assert "I50_1" not in merged.data.columns
    assert any(c.startswith("fft_") for c in merged.data.columns)
    assert len(schema) == 1
    # Schema code is the semantic slug, not the raw I-code
    assert not schema[0].code.startswith("I")
