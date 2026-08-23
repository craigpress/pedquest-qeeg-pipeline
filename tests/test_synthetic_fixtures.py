"""Frozen synthetic fixtures for the publication fact-check loop.

Each test pins the pipeline's behavior on a specific edge case called out in
``docs/RESEARCH_READINESS_REVIEW_2026-04-24.md``. They are deterministic and
in-memory — no on-disk binary fixtures — so a reviewer can read the test, see
the inputs, and verify the expected behavior.

Scenarios covered:

* partial first ROSC bin
* within-bin timestamp gap
* non-1s timestamp spacing
* seizure overlapping artifact
* CSV stem differing from the embedded ``.dat`` stem
* semantic merge threads an MMX through multi-segment input
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from qeeg.analysis.seizure import compute_seizure_report
from qeeg.analysis.time_binning import (
    aggregate_by_bins,
    infer_epoch_durations_hours,
)


# ---------------------------------------------------------------------------
# Fixture 1 — partial first ROSC bin
# ---------------------------------------------------------------------------
def test_partial_first_rosc_bin_reports_expected_observed_fraction():
    """EEG starts 3 hours into the [0, 6h) bin. Expected bin-width is still 6 h,
    but observed wall-clock support should be ~3 h and the clean-of-expected
    fraction should be roughly 0.5, not 1.0."""
    # 1 Hz data starting at hours=3.0 for 3 hours
    n = 3 * 3600
    hours = pd.Series(np.linspace(3.0, 6.0 - 1 / 3600.0, n))
    df = pd.DataFrame({
        "_hours_relative": hours,
        "feat": np.linspace(1.0, 2.0, n),
    })
    durations = infer_epoch_durations_hours(hours)
    bins = aggregate_by_bins(
        df,
        hours_relative=hours,
        variables=["feat"],
        edges=[0, 6, 12],
        usable_mask=pd.Series([True] * n),
        epoch_durations_hours=durations,
    )
    first = bins.iloc[0]
    assert first["bin_label"] == "0-6h"
    assert first["bin_expected_hours"] == 6.0
    assert 2.5 <= float(first["observed_wall_clock_hours"]) <= 3.5
    assert 0.4 <= float(first["clean_fraction_of_expected"]) <= 0.6
    # clean_fraction_of_observed should be ~1 because every epoch is artifact-clean.
    assert float(first["clean_fraction_of_observed"]) >= 0.95


# ---------------------------------------------------------------------------
# Fixture 2 — within-bin timestamp gap
# ---------------------------------------------------------------------------
def test_within_bin_gap_is_capped_and_visible_in_observed_hours():
    """Two 30-minute segments separated by a 4-hour gap inside [0, 6h).
    The gap must not become "observed EEG" — cap should keep observed
    wall-clock near 1 h, not 5 h."""
    seg_rows = 30 * 60  # 1 Hz × 30 min
    before = np.linspace(0.0, 0.5 - 1 / 3600.0, seg_rows)
    after = np.linspace(4.5, 5.0 - 1 / 3600.0, seg_rows)
    hours = pd.Series(np.concatenate([before, after]))
    df = pd.DataFrame({
        "_hours_relative": hours,
        "feat": np.linspace(1.0, 2.0, len(hours)),
    })
    durations = infer_epoch_durations_hours(hours)
    # Total summed durations must be approximately the two segment widths, not
    # include the 4-h gap.
    total = float(durations.sum())
    assert total < 1.5, f"gap leaked into observed support: total={total:.3f}h"

    bins = aggregate_by_bins(
        df,
        hours_relative=hours,
        variables=["feat"],
        edges=[0, 6, 12],
        usable_mask=pd.Series([True] * len(hours)),
        epoch_durations_hours=durations,
    )
    first = bins.iloc[0]
    # observed_wall_clock_hours should be near the two-segment total (~1 h),
    # not the wall-clock span (5 h).
    assert float(first["observed_wall_clock_hours"]) < 1.5


# ---------------------------------------------------------------------------
# Fixture 3 — non-1s timestamp spacing
# ---------------------------------------------------------------------------
def test_non_1s_timestamp_spacing_uses_actual_time_support():
    """If the trend cadence is 10 s, 360 rows cover 1 h, not 360 s. The coverage
    in hours must be driven by the timestamp deltas, not row count."""
    n = 360  # 10-s epochs for 1 hour
    hours = pd.Series(np.linspace(0.0, 1.0 - 10 / 3600.0, n))
    durations = infer_epoch_durations_hours(hours)

    # Each step should be ~10/3600 h, summed to ~1 h.
    per_epoch = float(durations.median())
    assert 9 / 3600.0 < per_epoch < 11 / 3600.0
    assert 0.95 <= float(durations.sum()) <= 1.05


# ---------------------------------------------------------------------------
# Fixture 4 — seizure overlapping artifact
# ---------------------------------------------------------------------------
def test_seizure_overlapping_artifact_splits_raw_and_clean_metrics():
    """Some seizure epochs coincide with artifact. Raw metrics count them;
    artifact-clean metrics do not."""
    n = 600
    df = pd.DataFrame({"_hours_relative": np.linspace(0.0, 10.0 / 60.0, n)})

    # Seizure from epoch 100-200 (100 epochs total)
    seizure = pd.Series([False] * 100 + [True] * 100 + [False] * (n - 200))
    # Artifact covers epochs 150-250 — first 50 of the seizure overlap.
    artifact_clean = pd.Series([True] * 150 + [False] * 100 + [True] * (n - 250))

    report = compute_seizure_report(
        df, {}, seizure,
        usable_mask=artifact_clean,
        epoch_duration_sec=1.0,
    )

    assert report.total_seizure_epochs == 100
    # 50 of the 100 seizure epochs overlap artifact and must be excluded.
    assert report.total_seizure_epochs_artifact_clean == 50
    # Events: raw = 1 continuous run. Artifact-clean seizure: epochs 100-149 contiguous → 1 event.
    assert report.seizure_events == 1
    assert report.seizure_events_artifact_clean == 1


# ---------------------------------------------------------------------------
# Fixture 5 — CSV stem differs from embedded .dat stem
# ---------------------------------------------------------------------------
def test_csv_stem_differs_from_dat_stem_and_corrections_key_on_dat_stem(tmp_path: Path):
    """Persyst exports often have a CSV filename like 20260422_2006__.csv
    while the embedded 'File,' row names the underlying dat file
    (4290-10_b884347.dat). Corrections must be keyed by the dat stem."""
    from api.services.pipeline_service import PipelineService

    csv_path = tmp_path / "20260422_2006__.csv"
    csv_path.write_text(
        "Patient,Anon\n"
        "File,C:\\\\studies\\\\4290-10_b884347.dat\n"
        "ClockDateTime,I1_1\n"
        "44000.0,0.0\n",
        encoding="utf-8",
    )

    dat_stem = PipelineService._dat_stem_from_csv(csv_path)
    assert dat_stem == "4290-10_b884347"
    # CSV stem is different — confirms the lookup key must not be csv_path.stem.
    assert csv_path.stem != dat_stem


# ---------------------------------------------------------------------------
# Fixture 6 — segment_merge accepts and threads an MMX config
# ---------------------------------------------------------------------------
def test_merge_segments_with_same_csv_descriptions_merge_semantically_without_mmx():
    """Generic semantic merge without MMX still collapses identical CSV trend
    descriptions onto one slug, but this does NOT prove MMX-backed semantics."""
    from qeeg.ingestion.segment_merge import merge_segments_by_semantic_name
    from qeeg.ingestion.parser import ParsedExport, ExportMetadata

    trend = "FFT Power, 1 - 4 Hz, Left Hemisphere"

    def _seg(code: str, t0_unix: float, values: list[float]) -> ParsedExport:
        df = pd.DataFrame({
            "ClockDateTime": pd.to_datetime(
                [t0_unix + i for i in range(len(values))], unit="s", origin="unix",
            ),
            code: values,
        })
        return ParsedExport(
            data=df,
            code_to_description={code: trend},
            description_to_codes={trend: [code]},
            metadata=ExportMetadata(file_path="syn"),
            code_row_index=0, trend_row_index=0,
        )

    # Same trend exported under two different I-codes across segments.
    parsed_a = _seg("I50_1", 0.0, [1.0, 2.0])
    parsed_b = _seg("I80_1", 100.0, [3.0, 4.0])

    merged, _schema = merge_segments_by_semantic_name([parsed_a, parsed_b])

    fft_cols = [c for c in merged.data.columns if c.startswith("fft_")]
    assert len(fft_cols) == 1, f"expected single semantic column, got {fft_cols}"
    col = fft_cols[0]
    values = merged.data.sort_values("ClockDateTime")[col].dropna().tolist()
    assert values == [1.0, 2.0, 3.0, 4.0]
    # Raw I-codes must not leak through.
    assert "I50_1" not in merged.data.columns
    assert "I80_1" not in merged.data.columns


def test_merge_segments_with_mmx_uses_mmx_as_semantic_reference():
    """Ambiguous CSV trend labels omit the channel location, so the generic
    mapper can only produce ``fft_delta``. Passing MMX must upgrade both
    segments onto the authoritative MMX-derived slug ``fft_delta_left_anterior``.

    This test is intentionally written so removing ``mmx=...`` makes it fail:
    the merged column still exists, but under the wrong generic slug.
    """
    from qeeg.ingestion.mmx_parser import InstrumentDef, MMXConfig
    from qeeg.ingestion.segment_merge import merge_segments_by_semantic_name
    from qeeg.ingestion.parser import ParsedExport, ExportMetadata

    def _seg(code: str, trend: str, t0_unix: float, values: list[float]) -> ParsedExport:
        df = pd.DataFrame({
            "ClockDateTime": pd.to_datetime(
                [t0_unix + i for i in range(len(values))], unit="s", origin="unix",
            ),
            code: values,
        })
        return ParsedExport(
            data=df,
            code_to_description={code: trend},
            description_to_codes={trend: [code]},
            metadata=ExportMetadata(file_path="syn"),
            code_row_index=0,
            trend_row_index=0,
        )

    trend_a = "FFT Power, 1 - 4 Hz"
    trend_b = "FFT_Power 1 - 4 Hz"
    parsed_a = _seg("I50_1", trend_a, 0.0, [1.0, 2.0])
    parsed_b = _seg("I80_1", trend_b, 100.0, [3.0, 4.0])

    mmx = MMXConfig(
        engines={},
        engines_by_ref={},
        instruments={
            trend_a: InstrumentDef(
                name=trend_a,
                instance_id="inst-a",
                channels="Left Anterior",
                graph_title="FFT Power",
                freq_min=1.0,
                freq_max=4.0,
                engine=None,
                family="fft_power",
            ),
            trend_b: InstrumentDef(
                name=trend_b,
                instance_id="inst-b",
                channels="Left Anterior",
                graph_title="FFT Power",
                freq_min=1.0,
                freq_max=4.0,
                engine=None,
                family="fft_power",
            ),
        },
        instance_index={},
        panels={},
        mmx_version="synthetic",
        mmx_path="synthetic",
    )

    merged, schema = merge_segments_by_semantic_name([parsed_a, parsed_b], mmx=mmx)

    semantic_cols = [c for c in merged.data.columns if c != "ClockDateTime"]
    assert semantic_cols == ["fft_delta_left_anterior"]
    values = merged.data.sort_values("ClockDateTime")["fft_delta_left_anterior"].dropna().tolist()
    assert values == [1.0, 2.0, 3.0, 4.0]

    entry = next(e for e in schema if e.code == "fft_delta_left_anterior")
    assert entry.family == "fft_power"
    assert entry.hemisphere == "left"
    assert entry.region == "anterior"

    # Raw I-codes and the generic no-MMX fallback slug must not leak through.
    assert "I50_1" not in merged.data.columns
    assert "I80_1" not in merged.data.columns
    assert "fft_delta" not in merged.data.columns
