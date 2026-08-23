"""Tests for qeeg.analysis.time_binning — bin edges, coverage, independent obs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qeeg.analysis.time_binning import (
    _is_fft_variable,
    _should_log_transform,
    aggregate_by_bins,
    assign_bins,
    build_bin_labels,
    summarize_bin,
)


class TestBuildBinLabels:
    def test_default_bins(self):
        labels = build_bin_labels([0, 6, 12, 18, 24])
        assert labels == ["0-6h", "6-12h", "12-18h", "18-24h"]

    def test_single_bin(self):
        assert build_bin_labels([0, 24]) == ["0-24h"]

    def test_uneven_bins(self):
        labels = build_bin_labels([0, 6, 24, 72])
        assert labels == ["0-6h", "6-24h", "24-72h"]


class TestAssignBins:
    def test_assigns_correctly(self):
        hours = pd.Series([1.0, 7.0, 13.0, 25.0])
        edges = [0, 6, 12, 24, 48]
        bins = assign_bins(hours, edges)
        assert str(bins.iloc[0]) == "0-6h"
        assert str(bins.iloc[1]) == "6-12h"
        assert str(bins.iloc[2]) == "12-24h"
        assert str(bins.iloc[3]) == "24-48h"

    def test_out_of_range_is_nan(self):
        hours = pd.Series([100.0])
        edges = [0, 6, 12]
        bins = assign_bins(hours, edges)
        assert pd.isna(bins.iloc[0])

    def test_edge_value_inclusive(self):
        hours = pd.Series([0.0, 6.0])
        edges = [0, 6, 12]
        bins = assign_bins(hours, edges)
        assert str(bins.iloc[0]) == "0-6h"
        assert str(bins.iloc[1]) == "6-12h"


class TestIsFftVariable:
    def test_fft_variables(self):
        assert _is_fft_variable("fft_delta_left_anterior") is True
        assert _is_fft_variable("total_power_left") is True

    def test_non_fft_variables(self):
        assert _is_fft_variable("aeeg_left_max") is False
        assert _is_fft_variable("seizure_probability_p14") is False
        assert _is_fft_variable("suppression_left") is False
        assert _is_fft_variable("spike_generalized") is False
        assert _is_fft_variable("heart_rate") is False


class TestShouldLogTransform:
    def test_power_variables(self):
        assert _should_log_transform("fft_delta_left_anterior") is True
        assert _should_log_transform("total_power_left") is True

    def test_non_power_variables(self):
        assert _should_log_transform("aeeg_left_max") is False
        assert _should_log_transform("suppression_left") is False


class TestSummarizeBin:
    def test_basic_stats(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = summarize_bin(df, ["x"])
        assert result["x_median"] == 3.0
        assert result["x_mean"] == 3.0
        assert result["x_min"] == 1.0
        assert result["x_max"] == 5.0
        assert result["x_n"] == 5
        assert result["x_iqr"] == pytest.approx(2.0)

    def test_empty_bin(self):
        df = pd.DataFrame({"x": pd.Series([], dtype=float)})
        result = summarize_bin(df, ["x"])
        assert np.isnan(result["x_median"])
        assert result["x_n"] == 0

    def test_nan_values_excluded(self):
        df = pd.DataFrame({"x": [1.0, np.nan, 3.0]})
        result = summarize_bin(df, ["x"])
        assert result["x_n"] == 2
        assert result["x_mean"] == 2.0

    def test_independent_mask_applied_to_fft(self):
        df = pd.DataFrame({"fft_delta_x": [10.0, 20.0, 30.0, 40.0, 50.0]})
        mask = pd.Series([True, False, True, False, True])
        result = summarize_bin(
            df, ["fft_delta_x"],
            independent_mask=mask,
            fft_columns={"fft_delta_x"},
        )
        # Only values at index 0, 2, 4 used
        assert result["fft_delta_x_n"] == 3
        assert result["fft_delta_x_mean"] == pytest.approx(30.0)

    def test_independent_mask_not_applied_to_aeeg(self):
        df = pd.DataFrame({"aeeg_left": [10.0, 20.0, 30.0, 40.0, 50.0]})
        mask = pd.Series([True, False, True, False, True])
        result = summarize_bin(
            df, ["aeeg_left"],
            independent_mask=mask,
            fft_columns={"fft_delta_x"},  # aeeg_left NOT in fft_columns
        )
        # All 5 values used — mask not applied to non-FFT
        assert result["aeeg_left_n"] == 5

    def test_per_variable_engine_mask_applies_to_non_fft_slow_engine(self):
        df = pd.DataFrame({
            "suppression_left": [0.1, 0.2, 0.3, 0.4, 0.5],
            "aeeg_left": [10.0, 20.0, 30.0, 40.0, 50.0],
        })
        suppression_mask = pd.Series([True, False, True, False, True])
        result = summarize_bin(
            df,
            ["suppression_left", "aeeg_left"],
            independent_masks={"suppression_left": suppression_mask},
            effective_basis={
                "suppression_left": "suppression_ratio_cadence_adjusted",
                "aeeg_left": "row_count",
            },
        )
        assert result["suppression_left_n_observed"] == 5
        assert result["suppression_left_n_effective"] == 3
        assert result["suppression_left_effective_basis"] == "suppression_ratio_cadence_adjusted"
        assert result["aeeg_left_n_observed"] == 5
        assert result["aeeg_left_n_effective"] == 5
        assert result["aeeg_left_effective_basis"] == "row_count"

    def test_log_transform_for_power(self):
        df = pd.DataFrame({"fft_delta_x": [1.0, 10.0, 100.0]})
        result = summarize_bin(df, ["fft_delta_x"])
        assert "fft_delta_x_log_mean" in result
        assert "fft_delta_x_log_sd" in result
        # Geometric mean of [1, 10, 100] = (1*10*100)^(1/3) = 10
        assert result["fft_delta_x_log_mean"] == pytest.approx(10.0, rel=0.01)

    def test_no_log_transform_for_non_power(self):
        df = pd.DataFrame({"aeeg_left": [1.0, 2.0, 3.0]})
        result = summarize_bin(df, ["aeeg_left"])
        assert "aeeg_left_log_mean" not in result

    def test_missing_column_skipped(self):
        df = pd.DataFrame({"x": [1.0, 2.0]})
        result = summarize_bin(df, ["x", "nonexistent"])
        assert "x_median" in result
        assert "nonexistent_median" not in result


class TestAggregateByBins:
    def test_basic_aggregation(self):
        n = 7200  # 2 hours of 1-second epochs
        df = pd.DataFrame({"x": np.random.RandomState(42).randn(n)})
        hours = pd.Series(np.linspace(0, 2, n))
        edges = [0, 1, 2]

        result = aggregate_by_bins(df, hours, ["x"], edges, min_coverage_hours=0.1)
        assert len(result) == 2
        assert list(result["bin_label"]) == ["0-1h", "1-2h"]
        assert all(result["meets_minimum"])

    def test_bin_metadata_columns(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
        hours = pd.Series([0.5, 1.5, 2.5])
        edges = [0, 3]

        result = aggregate_by_bins(df, hours, ["x"], edges, min_coverage_hours=0.0)
        assert "bin_label" in result.columns
        assert "bin_start_hours" in result.columns
        assert "bin_end_hours" in result.columns
        assert "n_total_epochs" in result.columns
        assert "n_effective_fft" in result.columns
        assert "coverage_hours" in result.columns
        assert "bin_expected_hours" in result.columns
        assert "observed_wall_clock_hours" in result.columns
        assert "artifact_clean_hours" in result.columns
        assert "clean_fraction_of_expected" in result.columns
        assert "clean_fraction_of_observed" in result.columns
        assert "meets_minimum" in result.columns

    def test_usable_mask_filters(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
        hours = pd.Series([0.5, 1.5, 2.5, 3.5])
        edges = [0, 6]
        usable = pd.Series([True, False, True, True])

        result = aggregate_by_bins(df, hours, ["x"], edges, usable_mask=usable)
        # n_total_epochs stores true total of all epochs (including filtered)
        assert result.iloc[0]["n_total_epochs"] == 4
        # n_usable_epochs stores count of epochs passing usable_mask
        assert result.iloc[0]["n_usable_epochs"] == 3

    def test_low_coverage_fills_nan(self):
        df = pd.DataFrame({"x": [1.0, 2.0]})
        hours = pd.Series([0.5, 0.5 + 1 / 3600])
        edges = [0, 6]

        result = aggregate_by_bins(df, hours, ["x"], edges, min_coverage_hours=1.0)
        assert not result.iloc[0]["meets_minimum"]
        assert np.isnan(result.iloc[0]["x_median"])

    def test_multiple_bins(self):
        n = 14400  # 4 hours
        df = pd.DataFrame({"x": np.ones(n)})
        hours = pd.Series(np.linspace(0, 4, n))
        edges = [0, 2, 4]

        result = aggregate_by_bins(df, hours, ["x"], edges, min_coverage_hours=0.5)
        assert len(result) == 2
        assert result.iloc[0]["bin_start_hours"] == 0
        assert result.iloc[0]["bin_end_hours"] == 2
        assert result.iloc[1]["bin_start_hours"] == 2
        assert result.iloc[1]["bin_end_hours"] == 4

    def test_wall_clock_coverage_distinguishes_partial_bin(self):
        df = pd.DataFrame({"x": [1.0, 2.0]})
        hours = pd.Series([0.5, 0.5002777778])  # two 1-second rows in a 1h bin
        result = aggregate_by_bins(df, hours, ["x"], [0, 1], min_coverage_hours=0.0)
        row = result.iloc[0]
        assert row["bin_expected_hours"] == 1
        assert row["artifact_clean_hours"] < 0.01
        assert row["clean_fraction_of_expected"] < 0.01
        assert row["clean_fraction_of_observed"] == pytest.approx(1.0)

    def test_bci_excludes_missing_suppression_values(self):
        # BSR is PERCENT (0-100). With the default 10% continuity cutoff: a 2%
        # epoch is continuous, a 40% epoch is not, and the NaN epoch is excluded
        # from the denominator -> BCI = 1 continuous / 2 valid = 0.5.
        df = pd.DataFrame({"suppression_left": [2.0, np.nan, 40.0]})
        hours = pd.Series([0.0, 1 / 3600, 2 / 3600])
        result = aggregate_by_bins(
            df,
            hours,
            ["suppression_left"],
            [0, 1],
            min_coverage_hours=0.0,
            suppression_columns=["suppression_left"],
            suppression_threshold=10.0,  # ACNS percent-scale continuity cutoff
        )
        assert result.iloc[0]["background_continuity_index"] == pytest.approx(0.5)

    def test_aggregate_uses_per_variable_engine_masks(self):
        df = pd.DataFrame({
            "suppression_left": [0.1, 0.2, 0.3, 0.4],
            "fft_delta_left": [1.0, 2.0, 3.0, 4.0],
        })
        hours = pd.Series([0.0, 1 / 3600, 2 / 3600, 3 / 3600])
        masks = {
            "suppression_left": pd.Series([True, False, False, False]),
            "fft_delta_left": pd.Series([True, False, True, False]),
        }
        result = aggregate_by_bins(
            df,
            hours,
            ["suppression_left", "fft_delta_left"],
            [0, 1],
            min_coverage_hours=0.0,
            independent_masks=masks,
            effective_basis={
                "suppression_left": "suppression_ratio_cadence_adjusted",
                "fft_delta_left": "fft_power_cadence_adjusted",
            },
        )
        row = result.iloc[0]
        assert row["suppression_left_n_observed"] == 4
        assert row["suppression_left_n_effective"] == 1
        assert row["suppression_left_effective_basis"] == "suppression_ratio_cadence_adjusted"
        assert row["fft_delta_left_n_observed"] == 4
        assert row["fft_delta_left_n_effective"] == 2
        assert row["fft_delta_left_effective_basis"] == "fft_power_cadence_adjusted"
