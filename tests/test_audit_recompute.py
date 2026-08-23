"""Tests for scripts/audit_recompute.py.

These tests build synthetic cache directories and verify that the audit script
recomputes the bin summary directly from epoch parquet, catches mismatches, and
reports missing audit inputs explicitly as ``not checked``.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = Path(__file__).parent.parent / "scripts" / "audit_recompute.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_recompute", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_recompute"] = module
    spec.loader.exec_module(module)
    return module


def _trimmed_mean_20pct(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(clean) == 0:
        return float("nan")
    if len(clean) < 4:
        return float(clean.mean())
    ordered = np.sort(clean)
    cut = int(np.floor(len(ordered) * 0.1))
    if cut <= 0:
        return float(ordered.mean())
    trimmed = ordered[cut: len(ordered) - cut]
    if len(trimmed) == 0:
        return float(ordered.mean())
    return float(trimmed.mean())


def _infer_epoch_durations_hours(hours_relative: pd.Series, fallback_epoch_seconds: float = 1.0) -> pd.Series:
    fallback = max(float(fallback_epoch_seconds), 0.0) / 3600.0
    hours = pd.to_numeric(hours_relative, errors="coerce")
    if len(hours) == 0:
        return pd.Series(dtype=float, index=hours_relative.index)
    diffs = hours.shift(-1) - hours
    positive = diffs[(diffs > 0) & np.isfinite(diffs)]
    median_step = float(positive.median()) if len(positive) else fallback
    if not np.isfinite(median_step) or median_step <= 0:
        median_step = fallback if fallback > 0 else 1.0 / 3600.0
    gap_cap = max(median_step * 3.0, median_step)
    durations = diffs.fillna(median_step)
    durations = durations.where((durations > 0) & np.isfinite(durations), median_step)
    durations = durations.clip(upper=gap_cap)
    return pd.Series(durations.astype(float), index=hours_relative.index)


def _stat_block(values: list[float]) -> dict[str, float | int]:
    series = pd.Series(values, dtype=float).dropna()
    if len(series) == 0:
        return {
            "median": float("nan"),
            "mean": float("nan"),
            "sd": float("nan"),
            "p05": float("nan"),
            "p10": float("nan"),
            "p25": float("nan"),
            "p75": float("nan"),
            "p90": float("nan"),
            "p95": float("nan"),
            "iqr": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "n": 0,
            "trimmed_mean_20pct": float("nan"),
            "cv": float("nan"),
            "log_mean": float("nan"),
            "log_sd": float("nan"),
        }

    q05, q10, q25, q75, q90, q95 = series.quantile([0.05, 0.10, 0.25, 0.75, 0.90, 0.95])
    mean_val = float(series.mean())
    sd_val = float(series.std()) if len(series) > 1 else 0.0
    positive = series[series > 0]

    return {
        "median": float(series.median()),
        "mean": mean_val,
        "sd": sd_val,
        "p05": float(q05),
        "p10": float(q10),
        "p25": float(q25),
        "p75": float(q75),
        "p90": float(q90),
        "p95": float(q95),
        "iqr": float(q75 - q25),
        "min": float(series.min()),
        "max": float(series.max()),
        "n": int(len(series)),
        "trimmed_mean_20pct": _trimmed_mean_20pct(series),
        "cv": float(sd_val / mean_val) if abs(mean_val) > 1e-10 and mean_val > 0 else float("nan"),
        "log_mean": float(np.exp(np.log(positive).mean())) if len(positive) else float("nan"),
        "log_sd": float(np.log(positive).std()) if len(positive) > 1 else (0.0 if len(positive) == 1 else float("nan")),
    }


def _build_expected_bins(epochs: pd.DataFrame, include_fft_mask: bool) -> pd.DataFrame:
    rows: list[dict[str, float | int | bool | str]] = []
    hours = pd.to_numeric(epochs["_hours_relative"], errors="coerce")
    durations = _infer_epoch_durations_hours(hours)
    usable = epochs["_usable"].fillna(False).astype(bool)
    artifact = epochs["_artifact_clean"].fillna(False).astype(bool)
    seizure = epochs["_seizure_flag"].fillna(False).astype(bool)
    ind_mask = epochs["_is_independent_fft"].fillna(False).astype(bool) if include_fft_mask else None

    for start, end in [(0.0, 2.0), (2.0, 4.0)]:
        bin_mask = (hours >= start) & (hours < end)
        usable_in_bin = bin_mask & usable
        artifact_hours = float(durations[usable_in_bin].sum())
        observed_hours = float(durations[bin_mask].sum())
        clean_fraction_observed = artifact_hours / observed_hours if observed_hours else 0.0
        clean_fraction_expected = artifact_hours / (end - start) if (end - start) else 0.0
        suppression_cols = ["suppression_left"]
        suppression = epochs.loc[usable_in_bin, suppression_cols]
        valid = suppression.notna().all(axis=1)
        below = (suppression < 0.5).all(axis=1)

        row = {
            "bin_label": f"{int(start)}-{int(end)}h",
            "bin_start_hours": start,
            "bin_end_hours": end,
            "n_total_epochs": int(bin_mask.sum()),
            "n_usable_epochs": int(usable_in_bin.sum()),
            "n_observed": int(usable_in_bin.sum()),
            "n_effective_fft": int((usable_in_bin & ind_mask).sum()) if ind_mask is not None else 0,
            "coverage_hours": artifact_hours,
            "bin_expected_hours": end - start,
            "observed_wall_clock_hours": observed_hours,
            "artifact_clean_hours": artifact_hours,
            "clean_fraction_of_observed": clean_fraction_observed,
            "clean_fraction_of_expected": clean_fraction_expected,
            "coverage_fraction": clean_fraction_observed,
            "meets_minimum": artifact_hours >= 0.001,
            "background_continuity_index": float((below & valid).sum()) / float(valid.sum()) if int(valid.sum()) > 0 else float("nan"),
            "seizure_burden_hours": float(len(epochs.loc[bin_mask & usable & seizure]) / 3600.0),
            "missingness_flag": (
                "no_data" if int(bin_mask.sum()) == 0 else
                "complete" if clean_fraction_expected >= 0.95 else
                "high_artifact" if clean_fraction_expected >= 0.5 else
                "moderate_artifact" if clean_fraction_expected >= 0.1 else
                "low_data"
            ),
        }

        fft_values = epochs.loc[usable_in_bin & (ind_mask if ind_mask is not None else True), "fft_delta_x"] if "fft_delta_x" in epochs.columns and ind_mask is not None else []
        if len(fft_values) == 0 and "fft_delta_x" in epochs.columns and ind_mask is None:
            fft_values = []
        elif len(fft_values) == 0 and "fft_delta_x" in epochs.columns:
            fft_values = epochs.loc[usable_in_bin, "fft_delta_x"]
        y_values = epochs.loc[usable_in_bin, "feat_y"]

        fft_stats = _stat_block(list(fft_values))
        y_stats = _stat_block(list(y_values))
        for feature, stats in {"fft_delta_x": fft_stats, "feat_y": y_stats}.items():
            for key, value in stats.items():
                if key == "trimmed_mean_20pct":
                    row[f"{feature}_trimmed_mean_20pct"] = value
                elif key == "median":
                    row[f"{feature}_median"] = value
                elif key == "mean":
                    row[f"{feature}_mean"] = value
                elif key == "sd":
                    row[f"{feature}_sd"] = value
                elif key == "p05":
                    row[f"{feature}_p05"] = value
                elif key == "p10":
                    row[f"{feature}_p10"] = value
                elif key == "p25":
                    row[f"{feature}_p25"] = value
                elif key == "p75":
                    row[f"{feature}_p75"] = value
                elif key == "p90":
                    row[f"{feature}_p90"] = value
                elif key == "p95":
                    row[f"{feature}_p95"] = value
                elif key == "iqr":
                    row[f"{feature}_iqr"] = value
                elif key == "min":
                    row[f"{feature}_min"] = value
                elif key == "max":
                    row[f"{feature}_max"] = value
                elif key == "n":
                    row[f"{feature}_n"] = value
                elif key == "cv":
                    row[f"{feature}_cv"] = value
                elif key == "log_mean":
                    row[f"{feature}_log_mean"] = value
                elif key == "log_sd":
                    row[f"{feature}_log_sd"] = value

        rows.append(row)

    result = pd.DataFrame(rows)
    valid_bins = result["meets_minimum"]
    midpoints = (result["bin_start_hours"] + result["bin_end_hours"]) / 2.0
    for feature in ["fft_delta_x", "feat_y"]:
        mask = valid_bins & result[f"{feature}_median"].notna()
        slope = np.nan
        if int(mask.sum()) >= 2:
            x = midpoints[mask].to_numpy(dtype=float)
            y = result.loc[mask, f"{feature}_median"].to_numpy(dtype=float)
            x_mean = x.mean()
            y_mean = y.mean()
            var_x = ((x - x_mean) ** 2).sum()
            slope = ((x - x_mean) * (y - y_mean)).sum() / var_x
        result[f"{feature}_slope"] = slope

    return result


def _build_cache(tmp_path: Path, include_fft_mask: bool = True) -> Path:
    cache_dir = tmp_path / "abc123_TEST"
    cache_dir.mkdir()

    hours = np.array([0, 1, 2, 3, 4, 5, 6, 7, 2 * 3600, 2 * 3600 + 1, 2 * 3600 + 2, 2 * 3600 + 3, 2 * 3600 + 4, 2 * 3600 + 5, 2 * 3600 + 6, 2 * 3600 + 7], dtype=float) / 3600.0
    artifact_clean = np.array([True, True, True, True, False, True, True, True, True, True, True, True, True, True, True, True])
    seizure = np.array([False, False, True, False, False, False, False, False, False, False, False, False, False, False, False, False])
    usable = np.array([True, True, False, True, False, True, True, True, True, True, True, True, True, True, True, True])
    independent_fft = np.array([True, False, False, True, False, False, True, False, True, False, False, True, False, False, True, False])
    fft_delta_x = np.array([1, 1, 2, 2, 3, 3, 4, 4, 2, 2, 3, 3, 4, 4, 5, 5], dtype=float)
    feat_y = np.array([10, 20, 30, 40, 50, 60, 70, 80, 15, 25, 35, 45, 55, 65, 75, 85], dtype=float)
    suppression_left = np.array([0.1, 0.2, 0.6, 0.4, 0.8, 0.3, 0.2, 0.9, 0.6, 0.7, 0.8, 0.4, 0.5, 0.2, 0.1, 0.9], dtype=float)

    epochs = pd.DataFrame({
        "_hours_relative": hours,
        "_artifact_clean": artifact_clean,
        "_seizure_flag": seizure,
        "_usable": usable,
        "fft_delta_x": fft_delta_x,
        "feat_y": feat_y,
        "suppression_left": suppression_left,
    })
    if include_fft_mask:
        epochs["_is_independent_fft"] = independent_fft

    epochs.to_parquet(cache_dir / "epochs.parquet")

    bin_summary = _build_expected_bins(epochs, include_fft_mask=include_fft_mask)
    bin_summary.to_parquet(cache_dir / "bin_summary.parquet")

    (cache_dir / "meta.json").write_text(json.dumps({
        "patient_id": "TEST",
        "cache_key": "fakekey",
        "config": {
            "binning": {
                "min_coverage_hours": 0.001,
                "bin_edges_hours": [0, 2, 4],
            },
            "seizure": {
                "exclusion_mode": "detected",
            },
        },
    }))
    return cache_dir


@pytest.fixture
def synthetic_cache(tmp_path) -> Path:
    return _build_cache(tmp_path, include_fft_mask=True)


@pytest.fixture
def synthetic_cache_without_fft_mask(tmp_path) -> Path:
    return _build_cache(tmp_path, include_fft_mask=False)


def test_audit_passes_on_consistent_cache(synthetic_cache):
    mod = _load_module()
    result = mod.audit_patient(synthetic_cache, dict(mod.DEFAULT_TOLERANCES))
    assert result.passed
    assert result.mismatches == []
    assert result.not_checked == []


def test_audit_detects_exact_usable_count_mismatch_when_usable_changes(synthetic_cache):
    mod = _load_module()
    epochs = pd.read_parquet(synthetic_cache / "epochs.parquet")
    epochs.loc[epochs.index[2], "_usable"] = True
    epochs.to_parquet(synthetic_cache / "epochs.parquet")

    result = mod.audit_patient(synthetic_cache, dict(mod.DEFAULT_TOLERANCES))
    assert any(m.field == "n_usable_epochs" for m in result.mismatches)


def test_audit_detects_extended_feature_stat_mismatches(synthetic_cache):
    mod = _load_module()
    bins = pd.read_parquet(synthetic_cache / "bin_summary.parquet")
    bins.loc[0, "feat_y_sd"] = 123.0
    bins.loc[0, "feat_y_p95"] = 456.0
    bins.loc[0, "feat_y_trimmed_mean_20pct"] = 789.0
    bins.loc[0, "feat_y_cv"] = 1.5
    bins.loc[0, "feat_y_log_sd"] = 2.0
    bins.to_parquet(synthetic_cache / "bin_summary.parquet")

    result = mod.audit_patient(synthetic_cache, dict(mod.DEFAULT_TOLERANCES))
    fields = {m.field for m in result.mismatches}
    assert {"feat_y_sd", "feat_y_p95", "feat_y_trimmed_mean_20pct", "feat_y_cv", "feat_y_log_sd"} <= fields


def test_audit_detects_coverage_bci_n_effective_and_slope_mismatches(synthetic_cache):
    mod = _load_module()
    bins = pd.read_parquet(synthetic_cache / "bin_summary.parquet")
    bins.loc[0, "clean_fraction_of_observed"] = 0.1
    bins.loc[0, "background_continuity_index"] = 0.0
    bins.loc[0, "n_effective_fft"] = 99
    bins.loc[0, "feat_y_slope"] = 999.0
    bins.to_parquet(synthetic_cache / "bin_summary.parquet")

    result = mod.audit_patient(synthetic_cache, dict(mod.DEFAULT_TOLERANCES))
    fields = {m.field for m in result.mismatches}
    assert {"clean_fraction_of_observed", "background_continuity_index", "n_effective_fft", "feat_y_slope"} <= fields


def test_audit_reports_n_effective_fft_not_checked_without_mask(synthetic_cache_without_fft_mask):
    mod = _load_module()
    result = mod.audit_patient(synthetic_cache_without_fft_mask, dict(mod.DEFAULT_TOLERANCES))
    assert any(item.field == "n_effective_fft" for item in result.not_checked)
    assert any("_is_independent_fft" in item.reason for item in result.not_checked if item.field == "n_effective_fft")
