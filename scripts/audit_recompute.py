"""Independent audit recomputation for the publication fact-check loop.

This script reads a single patient cache directory containing:

    - epochs.parquet
    - bin_summary.parquet
    - meta.json

It recomputes bin-level summary statistics directly from the epoch parquet and
compares them against the exported bin summary. The implementation is kept
separate from ``qeeg.analysis.time_binning`` so the audit does not inherit the
pipeline's binning code path.

Usage:
    python scripts/audit_recompute.py --cache-dir .qeeg_cache/<hash>_<patient_id>
    python scripts/audit_recompute.py --cache-dir ... --tolerance tolerances.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_TOLERANCES = {
    "count": 0,        # counts must match exactly
    "fraction": 1e-6,  # coverage fractions are deterministic
    "numeric": 1e-6,   # medians/means are deterministic from the same rows
    "percent": 1e-4,   # seizure burden allowed small float drift
}

_TRIM_PROPORTION = 0.1
_FFT_MASK_PREFIXES = (
    "fft_",
    "adr_",
    "rav_",
    "total_power_",
    "rel_delta_",
    "rel_theta_",
    "rel_alpha_",
    "rel_beta_",
    "theta_delta_ratio_",
    "alpha_delta_ratio_",
    "log_theta_delta_ratio_",
    "log_alpha_delta_ratio_",
)

_SOURCELESS_NOT_CHECKED_REASON = (
    "epoch parquet does not contain enough source information to recompute this "
    "field independently"
)


def _engine_independence_marker(basis: str, epochs: pd.DataFrame) -> str | None:
    """Return the epoch-column name carrying the per-engine independence
    boolean for the given ``n_effective_basis`` string, or None if absent.

    Basis strings have the form ``"{family}_cadence_adjusted"``. The pipeline
    persists ``_is_independent_<engine>`` (lowercase engine name) alongside
    ``_is_independent_fft``. We discover the engine name lazily without
    importing the pipeline here, by scanning the epoch columns.
    """
    if not basis or not basis.endswith("_cadence_adjusted"):
        return None
    family = basis[: -len("_cadence_adjusted")]
    family_to_engine = {
        "fft_power": "fftengine01",
        "fft_power_ratio": "fftengine01",
        "alpha_variability": "fftengine01",
        "fft_spectrogram": "fftengine01",
        "spectral_edge": "fftengine01",
        "asymmetry": "fftengine01",
        "suppression_ratio": "amplitude01",
        "rhythmicity": "rhythmicityengine01",
        "rda": "rhythmicityengine01",
        "rhythmic_delta": "rhythmicityengine01",
    }
    engine_lower = family_to_engine.get(family)
    if engine_lower is None:
        return None
    candidate = f"_is_independent_{engine_lower}"
    if candidate in epochs.columns:
        return candidate
    if engine_lower == "fftengine01" and "_is_independent_fft" in epochs.columns:
        return "_is_independent_fft"
    return None


@dataclass
class Mismatch:
    bin_label: str
    field: str
    exported: Any
    recomputed: Any
    tolerance: float

    def __str__(self) -> str:
        return (
            f"[{self.bin_label}] {self.field}: exported={self.exported!r} "
            f"recomputed={self.recomputed!r} tolerance={self.tolerance}"
        )


@dataclass
class NotChecked:
    bin_label: str
    field: str
    reason: str

    def __str__(self) -> str:
        return f"[{self.bin_label}] {self.field}: not checked ({self.reason})"


@dataclass
class AuditResult:
    mismatches: list[Mismatch]
    not_checked: list[NotChecked]

    @property
    def passed(self) -> bool:
        return not self.mismatches


def _close(a: Any, b: Any, tol: float) -> bool:
    """NaN-safe closeness check for scalars."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False

    if isinstance(a, (bool, np.bool_)) or isinstance(b, (bool, np.bool_)):
        return bool(a) is bool(b)

    if isinstance(a, (int, np.integer)) and isinstance(b, (int, np.integer)):
        return abs(int(a) - int(b)) <= tol

    try:
        af = float(a)
        bf = float(b)
    except Exception:
        return a == b

    if math.isnan(af) and math.isnan(bf):
        return True
    if math.isnan(af) or math.isnan(bf):
        return False
    return abs(af - bf) <= tol


def _load_cache(cache_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    epochs = pd.read_parquet(cache_dir / "epochs.parquet")
    bins = pd.read_parquet(cache_dir / "bin_summary.parquet")
    meta = json.loads((cache_dir / "meta.json").read_text(encoding="utf-8"))
    return epochs, bins, meta


def _bin_mask(hours_relative: pd.Series, start: float, end: float) -> pd.Series:
    """Right-exclusive bin membership matching ``pd.cut(..., right=False)``."""
    return (hours_relative >= start) & (hours_relative < end)


def _series_to_bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


def _get_nested(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cursor: Any = mapping
    for key in keys:
        if not isinstance(cursor, dict) or key not in cursor:
            return default
        cursor = cursor[key]
    return cursor


def _resolve_usable_mask(epochs: pd.DataFrame, meta: dict[str, Any]) -> tuple[pd.Series | None, str]:
    """Return the usable epoch mask if the cache carries enough information."""
    if "_usable" in epochs.columns:
        return _series_to_bool(epochs["_usable"]), "_usable"

    if "_artifact_clean" not in epochs.columns:
        return None, "missing _artifact_clean"

    artifact_clean = _series_to_bool(epochs["_artifact_clean"])
    seizure_mode = _get_nested(meta, "config", "seizure", "exclusion_mode", default="none")

    if seizure_mode == "none":
        return artifact_clean, "_artifact_clean"

    if "_seizure_flag" in epochs.columns:
        seizure = _series_to_bool(epochs["_seizure_flag"])
        return artifact_clean & ~seizure, "_artifact_clean + _seizure_flag"

    return None, "seizure exclusion is configured but _usable/_seizure_flag is missing"


def _infer_epoch_durations_hours(
    hours_relative: pd.Series,
    fallback_epoch_seconds: float = 1.0,
) -> pd.Series:
    """Estimate per-row time support from the timestamp axis.

    This mirrors the pipeline's observed-support logic so coverage fields can be
    recomputed independently.
    """
    fallback = max(float(fallback_epoch_seconds), 0.0) / 3600.0
    if len(hours_relative) == 0:
        return pd.Series(dtype=float, index=hours_relative.index)

    hours = pd.to_numeric(hours_relative, errors="coerce")
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


def _trimmed_mean_20pct(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(clean) == 0:
        return float("nan")
    if len(clean) < 4:
        return float(clean.mean())

    ordered = np.sort(clean)
    cut = int(math.floor(len(ordered) * _TRIM_PROPORTION))
    if cut <= 0:
        return float(ordered.mean())
    trimmed = ordered[cut: len(ordered) - cut]
    if len(trimmed) == 0:
        return float(ordered.mean())
    return float(trimmed.mean())


def _linregress_slope(x: pd.Series, y: pd.Series) -> float:
    x_vals = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
    y_vals = pd.to_numeric(y, errors="coerce").to_numpy(dtype=float)
    mask = np.isfinite(x_vals) & np.isfinite(y_vals)
    x_vals = x_vals[mask]
    y_vals = y_vals[mask]
    if len(x_vals) < 2:
        return float("nan")
    if np.allclose(x_vals, x_vals[0]):
        return float("nan")
    x_mean = float(x_vals.mean())
    y_mean = float(y_vals.mean())
    var_x = float(((x_vals - x_mean) ** 2).sum())
    if var_x == 0.0:
        return float("nan")
    cov_xy = float(((x_vals - x_mean) * (y_vals - y_mean)).sum())
    return cov_xy / var_x


def _feature_needs_fft_mask(feature: str) -> bool:
    return feature.startswith(_FFT_MASK_PREFIXES)


def _feature_mask_series(
    epochs: pd.DataFrame,
    usable_mask: pd.Series | None,
    feature: str,
) -> tuple[pd.Series | None, str | None]:
    """Return the series subset that should be summarized for a feature."""
    if feature not in epochs.columns:
        return None, f"missing source column {feature}"

    mask = usable_mask
    if _feature_needs_fft_mask(feature):
        if "_is_independent_fft" not in epochs.columns:
            return None, "missing _is_independent_fft mask"
        ind_mask = _series_to_bool(epochs["_is_independent_fft"])
        mask = ind_mask if mask is None else (mask & ind_mask)

    series = epochs.loc[mask, feature] if mask is not None else epochs[feature]
    return pd.to_numeric(series, errors="coerce").dropna(), None


def _compare_or_note(
    result: AuditResult,
    bin_label: str,
    field: str,
    exported: Any,
    recomputed: Any,
    tolerance: float,
    source_reason: str | None = None,
) -> None:
    if source_reason is not None:
        result.not_checked.append(NotChecked(bin_label, field, source_reason))
        return
    if not _close(exported, recomputed, tolerance):
        result.mismatches.append(Mismatch(bin_label, field, exported, recomputed, tolerance))


def _check_feature_stats(
    result: AuditResult,
    bin_label: str,
    row: pd.Series,
    epochs: pd.DataFrame,
    usable_mask: pd.Series | None,
    feature: str,
    tolerances: dict[str, float],
) -> None:
    values, reason = _feature_mask_series(epochs, usable_mask, feature)

    stat_fields = {
        "median": f"{feature}_median",
        "mean": f"{feature}_mean",
        "sd": f"{feature}_sd",
        "p05": f"{feature}_p05",
        "p10": f"{feature}_p10",
        "p25": f"{feature}_p25",
        "p75": f"{feature}_p75",
        "p90": f"{feature}_p90",
        "p95": f"{feature}_p95",
        "iqr": f"{feature}_iqr",
        "min": f"{feature}_min",
        "max": f"{feature}_max",
        "n": f"{feature}_n",
        "trimmed_mean": f"{feature}_trimmed_mean_20pct",
        "cv": f"{feature}_cv",
        "log_mean": f"{feature}_log_mean",
        "log_sd": f"{feature}_log_sd",
    }

    exported_fields = [field for field in stat_fields.values() if field in row.index and not pd.isna(row[field])]
    if not exported_fields:
        return

    if values is None:
        for field in exported_fields:
            result.not_checked.append(NotChecked(bin_label, field, reason or _SOURCELESS_NOT_CHECKED_REASON))
        return

    if len(values) == 0:
        computed = {
            stat_fields["median"]: float("nan"),
            stat_fields["mean"]: float("nan"),
            stat_fields["sd"]: float("nan"),
            stat_fields["p05"]: float("nan"),
            stat_fields["p10"]: float("nan"),
            stat_fields["p25"]: float("nan"),
            stat_fields["p75"]: float("nan"),
            stat_fields["p90"]: float("nan"),
            stat_fields["p95"]: float("nan"),
            stat_fields["iqr"]: float("nan"),
            stat_fields["min"]: float("nan"),
            stat_fields["max"]: float("nan"),
            stat_fields["n"]: 0,
            stat_fields["trimmed_mean"]: float("nan"),
            stat_fields["cv"]: float("nan"),
            stat_fields["log_mean"]: float("nan"),
            stat_fields["log_sd"]: float("nan"),
        }
    else:
        q05, q10, q25, q75, q90, q95 = values.quantile([0.05, 0.10, 0.25, 0.75, 0.90, 0.95])
        mean_val = float(values.mean())
        sd_val = float(values.std()) if len(values) > 1 else 0.0
        computed = {
            stat_fields["median"]: float(values.median()),
            stat_fields["mean"]: mean_val,
            stat_fields["sd"]: sd_val,
            stat_fields["p05"]: float(q05),
            stat_fields["p10"]: float(q10),
            stat_fields["p25"]: float(q25),
            stat_fields["p75"]: float(q75),
            stat_fields["p90"]: float(q90),
            stat_fields["p95"]: float(q95),
            stat_fields["iqr"]: float(q75 - q25),
            stat_fields["min"]: float(values.min()),
            stat_fields["max"]: float(values.max()),
            stat_fields["n"]: int(len(values)),
            stat_fields["trimmed_mean"]: _trimmed_mean_20pct(values),
            stat_fields["cv"]: float(sd_val / mean_val) if abs(mean_val) > 1e-10 and mean_val > 0 else float("nan"),
        }
        positive = values[values > 0]
        if len(positive) > 0:
            computed[stat_fields["log_mean"]] = float(np.exp(np.log(positive).mean()))
            computed[stat_fields["log_sd"]] = float(np.log(positive).std()) if len(positive) > 1 else 0.0
        else:
            computed[stat_fields["log_mean"]] = float("nan")
            computed[stat_fields["log_sd"]] = float("nan")

    for logical_name, field in stat_fields.items():
        if field not in row.index or pd.isna(row[field]):
            continue
        _compare_or_note(
            result,
            bin_label,
            field,
            row[field],
            computed[field],
            tolerances["numeric"] if logical_name not in {"n"} else tolerances["count"],
        )

    observed_field = f"{feature}_n_observed"
    effective_field = f"{feature}_n_effective"
    basis_field = f"{feature}_effective_basis"
    if observed_field in row.index and not pd.isna(row[observed_field]):
        observed_n = 0 if values is None else int(len(values))
        _compare_or_note(
            result,
            bin_label,
            observed_field,
            row[observed_field],
            observed_n,
            tolerances["count"],
        )

    if effective_field in row.index and not pd.isna(row[effective_field]):
        basis = str(row.get(basis_field, "") or "")
        if values is None:
            result.not_checked.append(NotChecked(bin_label, effective_field, reason or _SOURCELESS_NOT_CHECKED_REASON))
        elif basis == "row_count":
            _compare_or_note(
                result,
                bin_label,
                effective_field,
                row[effective_field],
                int(len(values)),
                tolerances["count"],
            )
        elif "fft" in basis and "_is_independent_fft" in epochs.columns:
            ind_mask = _series_to_bool(epochs["_is_independent_fft"])
            effective_values = pd.to_numeric(
                epochs.loc[usable_in_bin & ind_mask, feature],
                errors="coerce",
            ).dropna()
            _compare_or_note(
                result,
                bin_label,
                effective_field,
                row[effective_field],
                int(len(effective_values)),
                tolerances["count"],
            )
        else:
            # Non-FFT cadence-adjusted basis: look up the per-engine
            # independence marker that pipeline.py persists alongside
            # _is_independent_fft. Basis strings look like
            # "{family}_cadence_adjusted"; the engine name comes from the
            # family→engine map.
            engine_marker = _engine_independence_marker(basis, epochs)
            if engine_marker is not None:
                ind_mask = _series_to_bool(epochs[engine_marker])
                effective_values = pd.to_numeric(
                    epochs.loc[usable_in_bin & ind_mask, feature],
                    errors="coerce",
                ).dropna()
                _compare_or_note(
                    result,
                    bin_label,
                    effective_field,
                    row[effective_field],
                    int(len(effective_values)),
                    tolerances["count"],
                )
            else:
                result.not_checked.append(
                    NotChecked(
                        bin_label,
                        effective_field,
                        f"cannot reconstruct per-feature effective N for basis {basis!r}: missing per-engine independence marker in epoch parquet",
                    )
                )


def _check_bin_row(
    result: AuditResult,
    epochs: pd.DataFrame,
    bins: pd.DataFrame,
    row: pd.Series,
    usable_mask: pd.Series | None,
    tolerances: dict[str, float],
    min_coverage_hours: float,
    features_to_check: list[str] | None,
) -> None:
    label = str(row["bin_label"])
    start = float(row["bin_start_hours"])
    end = float(row["bin_end_hours"])
    hours = pd.to_numeric(epochs["_hours_relative"], errors="coerce")
    bin_all_mask = _bin_mask(hours, start, end)

    expected_n_total = int(bin_all_mask.sum())
    _compare_or_note(
        result,
        label,
        "n_total_epochs",
        row.get("n_total_epochs"),
        expected_n_total,
        tolerances["count"],
    )

    if usable_mask is None:
        result.not_checked.append(NotChecked(label, "n_usable_epochs", "usable mask could not be reconstructed"))
        return

    usable_in_bin = bin_all_mask & usable_mask
    expected_n_usable = int(usable_in_bin.sum())

    _compare_or_note(
        result,
        label,
        "n_usable_epochs",
        row.get("n_usable_epochs"),
        expected_n_usable,
        tolerances["count"],
    )
    if "n_observed" in row.index and not pd.isna(row["n_observed"]):
        _compare_or_note(
            result,
            label,
            "n_observed",
            row.get("n_observed"),
            expected_n_usable,
            tolerances["count"],
        )

    if "_artifact_clean" in epochs.columns:
        artifact_clean = _series_to_bool(epochs["_artifact_clean"])
    else:
        artifact_clean = usable_mask.copy()

    if "n_effective_fft" in row.index and not pd.isna(row["n_effective_fft"]):
        if "_is_independent_fft" in epochs.columns:
            ind_mask = _series_to_bool(epochs["_is_independent_fft"])
            actual_n_effective = int((usable_in_bin & ind_mask).sum())
            _compare_or_note(
                result,
                label,
                "n_effective_fft",
                row["n_effective_fft"],
                actual_n_effective,
                tolerances["count"],
            )
        else:
            result.not_checked.append(
                NotChecked(label, "n_effective_fft", "missing _is_independent_fft mask; cadence-adjusted FFT N cannot be reconstructed from epoch parquet alone")
            )

    durations_all = _infer_epoch_durations_hours(hours)
    artifact_clean_hours = float(durations_all[usable_in_bin].sum())
    observed_wall_clock_hours = float(durations_all[bin_all_mask].sum())
    bin_expected_hours = float(end - start)
    clean_fraction_of_observed = artifact_clean_hours / observed_wall_clock_hours if observed_wall_clock_hours > 0 else 0.0
    clean_fraction_of_expected = artifact_clean_hours / bin_expected_hours if bin_expected_hours > 0 else 0.0
    coverage_fraction = clean_fraction_of_observed

    coverage_fields = {
        "coverage_hours": artifact_clean_hours,
        "artifact_clean_hours": artifact_clean_hours,
        "observed_wall_clock_hours": observed_wall_clock_hours,
        "bin_expected_hours": bin_expected_hours,
        "clean_fraction_of_observed": clean_fraction_of_observed,
        "clean_fraction_of_expected": clean_fraction_of_expected,
        "coverage_fraction": coverage_fraction,
    }
    for field, actual in coverage_fields.items():
        if field in row.index and not pd.isna(row[field]):
            _compare_or_note(
                result,
                label,
                field,
                row[field],
                actual,
                tolerances["fraction"] if "fraction" in field or field.endswith("_hours") else tolerances["numeric"],
            )

    if "meets_minimum" in row.index and not pd.isna(row["meets_minimum"]):
        _compare_or_note(
            result,
            label,
            "meets_minimum",
            row["meets_minimum"],
            artifact_clean_hours >= min_coverage_hours,
            tolerances["count"],
        )

    if "missingness_flag" in row.index and not pd.isna(row["missingness_flag"]):
        missingness = (
            "no_data" if expected_n_total == 0 else
            "complete" if clean_fraction_of_expected >= 0.95 else
            "high_artifact" if clean_fraction_of_expected >= 0.5 else
            "moderate_artifact" if clean_fraction_of_expected >= 0.1 else
            "low_data"
        )
        _compare_or_note(result, label, "missingness_flag", row["missingness_flag"], missingness, tolerances["count"])

    if "background_continuity_index" in row.index and not pd.isna(row["background_continuity_index"]):
        suppression_cols = [col for col in epochs.columns if col.startswith("suppression_")]
        if suppression_cols:
            df_bin = epochs.loc[usable_in_bin, suppression_cols]
            valid = df_bin.notna().all(axis=1)
            if int(valid.sum()) > 0:
                below = (df_bin < 0.5).all(axis=1)
                actual_bci = float((below & valid).sum()) / float(valid.sum())
                _compare_or_note(
                    result,
                    label,
                    "background_continuity_index",
                    row["background_continuity_index"],
                    actual_bci,
                    tolerances["fraction"],
                )
            else:
                result.not_checked.append(
                    NotChecked(label, "background_continuity_index", "suppression columns exist but no valid values were present")
                )
        else:
            result.not_checked.append(
                NotChecked(label, "background_continuity_index", "no suppression_* columns present in epochs.parquet")
            )

    if "seizure_burden_hours" in row.index and not pd.isna(row["seizure_burden_hours"]):
        if "_seizure_flag" in epochs.columns:
            seizure = _series_to_bool(epochs["_seizure_flag"])
            actual_hours = float(durations_all[seizure & usable_in_bin].sum())
            _compare_or_note(
                result,
                label,
                "seizure_burden_hours",
                row["seizure_burden_hours"],
                actual_hours,
                tolerances["fraction"],
            )
        else:
            result.not_checked.append(NotChecked(label, "seizure_burden_hours", "missing _seizure_flag"))

    if "seizure_burden_pct_bin" in row.index and not pd.isna(row["seizure_burden_pct_bin"]):
        if "_seizure_flag" in epochs.columns:
            seizure = _series_to_bool(epochs["_seizure_flag"])
            actual_pct = 100.0 * float((seizure & usable_in_bin).sum()) / max(expected_n_usable, 1)
            _compare_or_note(
                result,
                label,
                "seizure_burden_pct_bin",
                row["seizure_burden_pct_bin"],
                actual_pct,
                tolerances["percent"],
            )
        else:
            result.not_checked.append(NotChecked(label, "seizure_burden_pct_bin", "missing _seizure_flag"))

    # Side-contribution sanity: fft_{band}_{region}_sides_contributing columns
    # are emitted per epoch and carry values in {0, 1, 2}. Audit each bin's
    # values are non-null and within that range; out-of-range = corrupted.
    sides_cols = [c for c in epochs.columns if c.endswith("_sides_contributing")]
    for sc_col in sides_cols:
        vals = pd.to_numeric(epochs.loc[bin_all_mask, sc_col], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        bad = vals[(vals < 0) | (vals > 2) | (vals != vals.astype(int))]
        if len(bad) > 0:
            result.mismatches.append(
                Mismatch(label, sc_col, "values in {0,1,2}", f"{int(len(bad))} out-of-range", 0)
            )

    # Feature-specific checks.
    if features_to_check is not None:
        feature_stems = [feature for feature in features_to_check if any(f"{feature}_{suffix}" in row.index for suffix in ("median", "mean", "sd", "p05", "p10", "p25", "p75", "p90", "p95", "iqr", "min", "max", "n", "trimmed_mean_20pct", "cv", "log_mean", "log_sd"))]
    else:
        feature_stems = []
        for col in bins.columns:
            if col.endswith("_median"):
                stem = col[: -len("_median")]
                if stem not in feature_stems:
                    feature_stems.append(stem)
        if not feature_stems:
            for col in bins.columns:
                if col.endswith("_mean"):
                    stem = col[: -len("_mean")]
                    if stem not in feature_stems:
                        feature_stems.append(stem)

    for feature in feature_stems:
        _check_feature_stats(result, label, row, epochs, usable_in_bin, feature, tolerances)


def _check_slopes(
    result: AuditResult,
    bins: pd.DataFrame,
    tolerances: dict[str, float],
) -> None:
    slope_cols = [col for col in bins.columns if col.endswith("_slope")]
    if not slope_cols:
        return

    midpoints = (pd.to_numeric(bins["bin_start_hours"], errors="coerce") + pd.to_numeric(bins["bin_end_hours"], errors="coerce")) / 2.0
    meets_minimum = _series_to_bool(bins["meets_minimum"]) if "meets_minimum" in bins.columns else pd.Series(True, index=bins.index)

    for slope_col in slope_cols:
        if slope_col not in bins.columns:
            continue
        exported = pd.to_numeric(bins[slope_col], errors="coerce")
        if exported.notna().sum() == 0:
            continue
        stem = slope_col[: -len("_slope")]
        median_col = f"{stem}_median"
        if median_col not in bins.columns:
            continue
        mask = meets_minimum & bins[median_col].notna()
        if int(mask.sum()) < 2:
            result.not_checked.append(NotChecked(str(bins.iloc[0]["bin_label"]), slope_col, "fewer than two minimum-coverage bins with non-null medians"))
            continue

        actual = _linregress_slope(midpoints[mask], bins.loc[mask, median_col])
        _compare_or_note(
            result,
            str(bins.iloc[0]["bin_label"]),
            slope_col,
            float(exported.dropna().iloc[0]),
            actual,
            tolerances["numeric"],
        )


def audit_patient(
    cache_dir: Path,
    tolerances: dict[str, float],
    features_to_check: list[str] | None = None,
) -> AuditResult:
    """Recompute bin-summary columns and compare them to the export."""
    epochs, bins, meta = _load_cache(cache_dir)
    result = AuditResult(mismatches=[], not_checked=[])

    if "_hours_relative" not in epochs.columns:
        raise SystemExit("epochs.parquet missing _hours_relative column")

    usable_mask, usable_source = _resolve_usable_mask(epochs, meta)
    if usable_mask is None:
        result.not_checked.append(
            NotChecked("*", "n_usable_epochs", f"usable mask unavailable ({usable_source})")
        )

    min_coverage_hours = float(_get_nested(meta, "config", "binning", "min_coverage_hours", default=1.0))

    for _, row in bins.iterrows():
        _check_bin_row(
            result,
            epochs,
            bins,
            row,
            usable_mask,
            tolerances,
            min_coverage_hours,
            features_to_check,
        )

    _check_slopes(result, bins, tolerances)

    if features_to_check:
        missing = [feature for feature in features_to_check if feature not in epochs.columns]
        for feature in missing:
            result.not_checked.append(NotChecked("*", feature, "source column missing from epochs.parquet"))

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cache-dir",
        type=Path,
        required=True,
        help="Path to a single patient cache directory (e.g. .qeeg_cache/<hash>_<pid>)",
    )
    ap.add_argument(
        "--tolerance",
        type=Path,
        default=None,
        help="Optional JSON file with tolerance overrides (keys: count, fraction, numeric, percent)",
    )
    ap.add_argument(
        "--features",
        nargs="*",
        help="Restrict feature-level checks to these column stems (e.g. fft_delta_left_anterior)",
    )
    args = ap.parse_args()

    tolerances = dict(DEFAULT_TOLERANCES)
    if args.tolerance and args.tolerance.exists():
        tolerances.update(json.loads(args.tolerance.read_text(encoding="utf-8")))

    if not args.cache_dir.exists():
        print(f"cache dir not found: {args.cache_dir}", file=sys.stderr)
        return 2

    result = audit_patient(args.cache_dir, tolerances, features_to_check=args.features)
    if result.passed:
        print(f"[audit_recompute] PASS {args.cache_dir.name}")
    else:
        print(f"[audit_recompute] FAIL {args.cache_dir.name} ({len(result.mismatches)} mismatch(es))")
        for m in result.mismatches[:25]:
            print(f"  - {m}")
        if len(result.mismatches) > 25:
            print(f"  ... and {len(result.mismatches) - 25} more")

    if result.not_checked:
        print(f"[audit_recompute] NOT CHECKED ({len(result.not_checked)} item(s))")
        for item in result.not_checked[:25]:
            print(f"  - {item}")
        if len(result.not_checked) > 25:
            print(f"  ... and {len(result.not_checked) - 25} more")

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
