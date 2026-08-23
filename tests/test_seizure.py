"""Tests for qeeg.analysis.seizure — mask computation, report generation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qeeg.analysis.seizure import (
    SeizureReport,
    compute_seizure_mask,
    compute_seizure_report,
    detect_seizure_columns,
)


class TestDetectSeizureColumns:
    def test_finds_probability(self):
        cols = ["I121_1", "I122_1"]
        c2d = {"I121_1": "Seizure Probability P14", "I122_1": "Seizure Detection P14"}
        result = detect_seizure_columns(cols, c2d)
        assert result["probability"] == "I121_1"

    def test_finds_detection(self):
        cols = ["I122_1"]
        c2d = {"I122_1": "Seizure Detection P14"}
        result = detect_seizure_columns(cols, c2d)
        assert result["detections"] == "I122_1"

    def test_empty_when_no_seizure_cols(self):
        cols = ["I1_1"]
        c2d = {"I1_1": "Artifact Intensity"}
        result = detect_seizure_columns(cols, c2d)
        assert result == {}

    def test_skips_cols_not_in_df(self):
        cols = ["I1_1"]  # I121_1 not in column list
        c2d = {"I121_1": "Seizure Probability P14"}
        result = detect_seizure_columns(cols, c2d)
        assert "probability" not in result


class TestComputeSeizureMask:
    def test_mode_none_all_false(self):
        df = pd.DataFrame({"I121_1": [0.8, 0.9, 0.7]})
        mask = compute_seizure_mask(df, {"probability": "I121_1"}, mode="none")
        assert mask.sum() == 0

    def test_mode_detected(self):
        df = pd.DataFrame({"I122_1": [0.0, 1.0, 0.0, 1.0]})
        mask = compute_seizure_mask(df, {"detections": "I122_1"}, mode="detected")
        assert list(mask) == [False, True, False, True]

    def test_mode_probability_with_threshold(self):
        df = pd.DataFrame({"I121_1": [0.1, 0.5, 0.9, 0.3]})
        mask = compute_seizure_mask(
            df, {"probability": "I121_1"},
            mode="probability", probability_threshold=0.5,
        )
        assert list(mask) == [False, True, True, False]

    def test_mode_probability_custom_threshold(self):
        df = pd.DataFrame({"I121_1": [0.1, 0.3, 0.5, 0.7]})
        mask = compute_seizure_mask(
            df, {"probability": "I121_1"},
            mode="probability", probability_threshold=0.4,
        )
        assert list(mask) == [False, False, True, True]

    def test_missing_column_returns_false(self):
        df = pd.DataFrame({"other": [1.0, 2.0]})
        mask = compute_seizure_mask(df, {"probability": "I121_1"}, mode="probability")
        assert mask.sum() == 0

    def test_nan_treated_as_zero(self):
        df = pd.DataFrame({"I122_1": [np.nan, 1.0, np.nan]})
        mask = compute_seizure_mask(df, {"detections": "I122_1"}, mode="detected")
        assert list(mask) == [False, True, False]


class TestComputeSeizureReport:
    def test_no_seizures(self):
        df = pd.DataFrame({"I121_1": [0.0, 0.0, 0.0]})
        mask = pd.Series([False, False, False])
        report = compute_seizure_report(df, {"probability": "I121_1"}, mask)
        assert report.total_seizure_epochs == 0
        assert report.seizure_burden_pct == 0.0
        assert report.seizure_events == 0

    def test_with_seizures(self):
        df = pd.DataFrame({"I121_1": [0.0, 0.8, 0.9, 0.0, 0.7]})
        mask = pd.Series([False, True, True, False, True])
        report = compute_seizure_report(df, {"probability": "I121_1"}, mask)
        assert report.total_seizure_epochs == 3
        assert report.seizure_burden_pct == pytest.approx(60.0)
        assert report.seizure_events == 2  # two transitions: F→T and F→T
        assert report.max_seizure_probability == 0.9

    def test_seizure_event_at_first_epoch_is_counted(self):
        df = pd.DataFrame({"x": range(4)})
        mask = pd.Series([True, True, False, True])
        report = compute_seizure_report(df, {}, mask)
        assert report.seizure_events == 2

    def test_artifact_clean_event_metrics_are_separate(self):
        df = pd.DataFrame({"x": range(5)})
        seizure = pd.Series([True, True, False, True, False])
        usable = pd.Series([False, True, True, True, True])
        report = compute_seizure_report(df, {}, seizure, usable_mask=usable)
        assert report.total_seizure_epochs == 3
        assert report.total_seizure_epochs_artifact_clean == 2
        assert report.seizure_events == 2
        assert report.seizure_events_artifact_clean == 2

    def test_longest_seizure(self):
        # 5 consecutive seizure epochs at 1 sec each = 5/60 minutes
        mask = pd.Series([False] + [True] * 5 + [False])
        df = pd.DataFrame({"x": range(7)})
        report = compute_seizure_report(df, {}, mask, epoch_duration_sec=1.0)
        assert report.longest_seizure_minutes == pytest.approx(5.0 / 60.0)

    def test_status_epilepticus_by_duration(self):
        # 1800 continuous seizure epochs at 1 sec = 30 minutes
        n = 3600
        mask = pd.Series([False] * 100 + [True] * 1800 + [False] * (n - 1900))
        df = pd.DataFrame({"x": range(n)})
        report = compute_seizure_report(df, {}, mask, epoch_duration_sec=1.0)
        assert report.has_status_epilepticus is True
        # Canonical screen-flag alias must mirror the legacy field.
        assert report.status_epilepticus_screen_flag is True
        assert report.longest_seizure_minutes == 30.0

    def test_status_flag_dual_emit_in_to_dict(self):
        """Both names must appear in to_dict() with the same value until the
        deprecation window closes; consumers may read either."""
        report = SeizureReport()
        report.has_status_epilepticus = True
        d = report.to_dict()
        assert d["has_status_epilepticus"] is True
        assert d["status_epilepticus_screen_flag"] is True

    def test_usable_mask_affects_burden(self):
        df = pd.DataFrame({"x": range(10)})
        seizure = pd.Series([True] * 5 + [False] * 5)
        usable = pd.Series([True] * 5 + [False] * 5)  # only seizure epochs are usable
        report = compute_seizure_report(df, {}, seizure, usable_mask=usable)
        assert report.seizure_burden_pct == 100.0  # 5 seizure out of 5 usable

    def test_time_to_first_seizure(self):
        df = pd.DataFrame({"x": range(5)})
        mask = pd.Series([False, False, True, False, False])
        hours = pd.Series([0.0, 1.0, 2.0, 3.0, 4.0])
        report = compute_seizure_report(df, {}, mask, hours_relative=hours)
        assert report.time_to_first_seizure_hours == 2.0

    def test_to_dict(self):
        report = SeizureReport(total_seizure_epochs=5, seizure_burden_pct=10.0)
        d = report.to_dict()
        assert d["total_seizure_epochs"] == 5
        assert d["seizure_burden_pct"] == 10.0
        assert "per_bin_burden" in d
