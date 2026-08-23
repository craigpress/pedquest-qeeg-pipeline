from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass
from scipy import stats as sp_stats

MIN_BIN_COVERAGE_HOURS = 1.0

# Families where log-transform statistics (geometric mean, log SD) are meaningful
LOG_TRANSFORM_PREFIXES = (
    "fft_delta_", "fft_theta_", "fft_alpha_", "fft_beta_",
    "total_power_",
)

@dataclass
class BinSummary:
    bin_label: str
    bin_start: float  # hours
    bin_end: float    # hours
    n_total_epochs: int
    n_usable_epochs: int
    n_effective_fft: int
    coverage_hours: float
    meets_minimum: bool


def build_bin_labels(edges: list[float]) -> list[str]:
    """Create human-readable bin labels from edges. E.g., [0,6,12] -> ['0-6h', '6-12h']"""
    labels = []
    for i in range(len(edges) - 1):
        labels.append(f"{edges[i]:.0f}-{edges[i+1]:.0f}h")
    return labels


def assign_bins(hours_relative: pd.Series, edges: list[float]) -> pd.Series:
    """Assign each epoch to a time bin. Returns bin labels (or NaN if outside all bins)."""
    labels = build_bin_labels(edges)
    return pd.cut(hours_relative, bins=edges, labels=labels, right=False, include_lowest=True)


def _is_fft_variable(var: str) -> bool:
    """Backward-compatible helper for FFT-derived feature names."""
    return var.startswith((
        "fft_", "total_power_", "rel_delta_", "rel_theta_", "rel_alpha_", "rel_beta_",
        "theta_delta_ratio_", "alpha_delta_ratio_",
        "log_theta_delta_ratio_", "log_alpha_delta_ratio_",
    ))


def _should_log_transform(var: str) -> bool:
    """Check if a variable should get log-transform statistics."""
    return any(var.startswith(p) for p in LOG_TRANSFORM_PREFIXES)


def infer_epoch_durations_hours(
    hours_relative: pd.Series,
    fallback_epoch_seconds: float = 1.0,
) -> pd.Series:
    """Estimate per-row time support from the timestamp axis.

    Uses the forward difference for each row and caps large gaps at 3x the
    median positive step so acquisition gaps do not become falsely observed EEG
    time. The last row receives the median step. Returned values are hours.
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


def summarize_bin(df_bin: pd.DataFrame, variables: list[str],
                  independent_mask: pd.Series | None = None,
                  fft_columns: set[str] | None = None,
                  independent_masks: dict[str, pd.Series] | None = None,
                  effective_basis: dict[str, str] | None = None) -> dict:
    """Compute summary statistics for a single bin.

    Args:
        df_bin: Epoch data for this bin (already filtered to usable).
        variables: Columns to summarize.
        independent_mask: legacy boolean mask for independent FFT observations.
        fft_columns: legacy set of columns that should use ``independent_mask``.
        independent_masks: optional per-variable masks keyed by variable name. This
            is the preferred engine-aware path because each Persyst instrument family
            can have a different MMX engine cadence.
        effective_basis: optional per-variable label describing the effective-N rule.
    """
    result = {}
    for var in variables:
        if var not in df_bin.columns:
            continue

        raw_series = df_bin[var]
        observed_clean = raw_series.dropna()

        var_mask = None
        basis = "row_count"
        if independent_masks is not None and var in independent_masks:
            var_mask = independent_masks[var]
            basis = (effective_basis or {}).get(var, "engine_cadence_adjusted")
        elif independent_mask is not None and fft_columns is not None and var in fft_columns:
            var_mask = independent_mask
            basis = "fft_cadence_adjusted"

        series = raw_series
        if var_mask is not None:
            # fill_value=False: unknown independence status defaults to excluded (conservative)
            series = series[var_mask.reindex(df_bin.index, fill_value=False)]

        clean = series.dropna()
        if len(clean) == 0:
            result[f"{var}_median"] = np.nan
            result[f"{var}_mean"] = np.nan
            result[f"{var}_sd"] = np.nan
            result[f"{var}_p05"] = np.nan
            result[f"{var}_p10"] = np.nan
            result[f"{var}_p25"] = np.nan
            result[f"{var}_p75"] = np.nan
            result[f"{var}_p90"] = np.nan
            result[f"{var}_p95"] = np.nan
            result[f"{var}_iqr"] = np.nan
            result[f"{var}_min"] = np.nan
            result[f"{var}_max"] = np.nan
            result[f"{var}_n"] = 0
            result[f"{var}_n_observed"] = len(observed_clean)
            result[f"{var}_n_effective"] = 0
            result[f"{var}_effective_basis"] = basis
            continue

        result[f"{var}_median"] = float(clean.median())
        mean_val = float(clean.mean())
        sd_val = float(clean.std()) if len(clean) > 1 else 0.0
        result[f"{var}_mean"] = mean_val
        result[f"{var}_sd"] = sd_val
        p05, p10, p25, p75, p90, p95 = clean.quantile([0.05, 0.10, 0.25, 0.75, 0.90, 0.95])
        result[f"{var}_p05"] = float(p05)
        result[f"{var}_p10"] = float(p10)
        result[f"{var}_p25"] = float(p25)
        result[f"{var}_p75"] = float(p75)
        result[f"{var}_p90"] = float(p90)
        result[f"{var}_p95"] = float(p95)
        result[f"{var}_iqr"] = float(p75 - p25)
        result[f"{var}_min"] = float(clean.min())
        result[f"{var}_max"] = float(clean.max())
        result[f"{var}_n"] = len(clean)
        result[f"{var}_n_observed"] = len(observed_clean)
        result[f"{var}_n_effective"] = len(clean)
        result[f"{var}_effective_basis"] = basis

        # Trimmed mean: trims 10% from each tail (20% total), leaving the middle 80%.
        if len(clean) >= 4:
            result[f"{var}_trimmed_mean_20pct"] = float(sp_stats.trim_mean(clean.values, 0.1))
        else:
            result[f"{var}_trimmed_mean_20pct"] = mean_val

        # CV only valid for strictly positive ratio-scale data (e.g. band power). Returns NaN for
        # zero, near-zero, or negative means (asymmetry/log-ratio variables can be negative).
        result[f"{var}_cv"] = float(sd_val / mean_val) if abs(mean_val) > 1e-10 and mean_val > 0 else np.nan

        # Log-transform statistics for spectral power variables (log-normally distributed).
        # log_mean = geometric mean = exp(E[ln X]).
        # log_sd   = SD of ln-transformed values (σ_ln).
        # Geometric 95% CI: [log_mean * exp(-1.96 * log_sd), log_mean * exp(+1.96 * log_sd)]
        if _should_log_transform(var):
            positive = clean[clean > 0]
            if len(positive) > 0:
                mu_log = float(np.log(positive).mean())
                result[f"{var}_log_mean"] = float(np.exp(mu_log))  # geometric mean
                result[f"{var}_log_sd"] = float(np.log(positive).std()) if len(positive) > 1 else 0.0

    return result


def aggregate_by_bins(df: pd.DataFrame, hours_relative: pd.Series,
                      variables: list[str], edges: list[float],
                      usable_mask: pd.Series | None = None,
                      independent_mask: pd.Series | None = None,
                      fft_columns: list[str] | None = None,
                      independent_masks: dict[str, pd.Series] | None = None,
                      effective_basis: dict[str, str] | None = None,
                      min_coverage_hours: float = MIN_BIN_COVERAGE_HOURS,
                      suppression_columns: list[str] | None = None,
                      suppression_threshold: float = 10.0,
                      seizure_mask: pd.Series | None = None,
                      artifact_clean_mask: pd.Series | None = None,
                      epoch_duration_sec: float = 1.0,
                      epoch_durations_hours: pd.Series | None = None) -> pd.DataFrame:
    """Aggregate data into time bins with summary statistics.

    Args:
        df: DataFrame with epoch data
        hours_relative: hours from reference (ROSC or recording start)
        variables: columns to summarize
        edges: bin edges in hours
        usable_mask: True = usable epoch (passed artifact filter)
        independent_mask: legacy True = independent FFT observation
        fft_columns: legacy columns that use independent_mask
        independent_masks: preferred per-variable masks derived from the MMX engine
            used by each instrument family.
        effective_basis: per-variable labels for the effective observation rule.
        min_coverage_hours: minimum hours of data to include bin
        suppression_columns: columns used to compute background continuity index
        suppression_threshold: suppression % below which epochs count as continuous
            background. Default 10 on the 0–100 percent scale, per ACNS 2021
            critical-care EEG continuity: <10% = continuous/nearly-continuous,
            10–49% = discontinuous. (P0-1)
        seizure_mask: True = seizure epoch (from seizure detection, before exclusion)
        artifact_clean_mask: True = artifact-clean epoch BEFORE seizure exclusion;
            used as the seizure-burden denominator so burden is not zeroed out when
            usable_mask excludes seizures. Falls back to usable_mask if None. (P0-3)
        epoch_duration_sec: duration of each epoch in seconds (default 1.0 for Persyst)

    Returns:
        DataFrame with one row per bin, columns = variable summary stats
    """
    labels = build_bin_labels(edges)

    # Pre-filter bins: record total epochs per bin BEFORE usable mask
    bins_all = assign_bins(hours_relative, edges)
    durations_all = (
        epoch_durations_hours.reindex(df.index).astype(float)
        if epoch_durations_hours is not None
        else infer_epoch_durations_hours(hours_relative, epoch_duration_sec).reindex(df.index).astype(float)
    )
    total_per_bin = {}
    observed_hours_per_bin = {}
    for label in labels:
        mask = bins_all == label
        total_per_bin[label] = int(mask.sum())
        observed_hours_per_bin[label] = float(durations_all[mask].sum())

    fft_col_set = set(fft_columns) if fft_columns else None

    # Apply usable mask
    df_full = df  # keep reference to full df for BCI computation
    if usable_mask is not None:
        df = df[usable_mask].copy()
        bins_usable = bins_all[usable_mask]
        hours_relative = hours_relative[usable_mask]
        durations_usable = durations_all[usable_mask]
        if independent_mask is not None:
            independent_mask = independent_mask[usable_mask]
        if independent_masks is not None:
            independent_masks = {
                name: mask[usable_mask]
                for name, mask in independent_masks.items()
            }
    else:
        bins_usable = bins_all
        durations_usable = durations_all

    results = []
    for label in labels:
        bin_mask = bins_usable == label
        df_bin = df[bin_mask]

        n_usable = len(df_bin)
        artifact_clean_hours = float(durations_usable[bin_mask].sum())
        coverage = artifact_clean_hours

        meets_min = coverage >= min_coverage_hours

        # Get edge values for this bin
        idx = labels.index(label)
        bin_start = edges[idx]
        bin_end = edges[idx + 1]

        ind_mask_bin = independent_mask[bin_mask] if independent_mask is not None else None
        masks_bin = (
            {name: mask[bin_mask] for name, mask in independent_masks.items()}
            if independent_masks is not None else None
        )

        if meets_min and n_usable > 0:
            stats = summarize_bin(
                df_bin, variables, ind_mask_bin, fft_col_set,
                independent_masks=masks_bin,
                effective_basis=effective_basis,
            )
        else:
            # Fill with NaN
            stats = {}
            for var in variables:
                for suffix in ["_median", "_mean", "_sd", "_p05", "_p10", "_p25", "_p75", "_p90", "_p95", "_iqr", "_min", "_max", "_n"]:
                    stats[f"{var}{suffix}"] = np.nan
                stats[f"{var}_n_observed"] = 0
                stats[f"{var}_n_effective"] = 0
                stats[f"{var}_effective_basis"] = (effective_basis or {}).get(var, "not_estimated")

        n_independent = int(ind_mask_bin.sum()) if ind_mask_bin is not None else n_usable
        cadence_adjusted_counts = [
            int(mask.sum()) for name, mask in (masks_bin or {}).items()
            if (effective_basis or {}).get(name, "").endswith("_cadence_adjusted")
        ]
        n_effective_cadence_adjusted = (
            min(cadence_adjusted_counts) if cadence_adjusted_counts else n_independent
        )

        # Coverage fractions are timestamp-support based, not raw row fractions.
        n_total_bin = total_per_bin[label]
        bin_expected_hours = float(bin_end - bin_start)
        observed_wall_clock_hours = observed_hours_per_bin[label]
        clean_fraction_of_observed = (
            artifact_clean_hours / observed_wall_clock_hours
            if observed_wall_clock_hours > 0 else 0.0
        )
        clean_fraction_of_expected = (
            artifact_clean_hours / bin_expected_hours
            if bin_expected_hours > 0 else 0.0
        )
        coverage_fraction = clean_fraction_of_observed

        # Background continuity index: proportion of usable epochs with
        # suppression below threshold (continuous background activity).
        # Threshold is the ACNS 2021 continuous/discontinuous boundary (10%).
        bci = np.nan
        if suppression_columns and n_usable > 0:
            valid = pd.Series(True, index=df_bin.index)
            below = pd.Series(True, index=df_bin.index)
            for col in suppression_columns:
                if col in df_bin.columns:
                    valid = valid & df_bin[col].notna()
                    below = below & (df_bin[col] < suppression_threshold)
            valid_n = int(valid.sum())
            bci = float((below & valid).sum()) / valid_n if valid_n > 0 else np.nan

        # Seizure burden: hours of seizure within artifact-clean epochs in this
        # bin. P0-3: this MUST use the artifact-clean mask taken BEFORE seizure
        # exclusion. `usable_mask` excludes seizure epochs for feature analysis,
        # so `seizure_mask & usable_mask` is empty and burden collapses to 0
        # whenever seizure exclusion is enabled. Fall back to usable_mask only
        # when no separate artifact-clean mask is supplied. No n_usable guard:
        # an all-seizure bin has n_usable == 0 yet is exactly the high-burden case.
        seizure_burden_hours = np.nan
        if seizure_mask is not None:
            burden_denom_mask = (
                artifact_clean_mask if artifact_clean_mask is not None else usable_mask
            )
            bin_all_mask = bins_all == label
            clean_in_bin = (
                burden_denom_mask & bin_all_mask
                if burden_denom_mask is not None else bin_all_mask
            )
            seizure_in_bin = seizure_mask & clean_in_bin
            seizure_burden_hours = float(durations_all[seizure_in_bin].sum())

        row = {
            "bin_label": label,
            "bin_start_hours": bin_start,
            "bin_end_hours": bin_end,
            "n_total_epochs": n_total_bin,
            "n_usable_epochs": n_usable,
            "n_observed": n_usable,
            "n_effective_fft": n_independent,
            "n_effective_cadence_adjusted": n_effective_cadence_adjusted,
            "coverage_hours": coverage,
            "coverage_fraction": coverage_fraction,
            "bin_expected_hours": bin_expected_hours,
            "observed_wall_clock_hours": observed_wall_clock_hours,
            "artifact_clean_hours": artifact_clean_hours,
            "clean_fraction_of_observed": clean_fraction_of_observed,
            "clean_fraction_of_expected": clean_fraction_of_expected,
            "meets_minimum": meets_min,
            "background_continuity_index": bci,
            "seizure_burden_hours": seizure_burden_hours,
            **stats
        }
        results.append(row)

    result_df = pd.DataFrame(results)

    # ── Trajectory features: slope of key metrics across bins ──────────
    # Computed via linear regression of bin midpoint (hours) vs metric median.
    # Slopes are patient-level trajectory metrics, broadcast to every bin row for export convenience.
    if len(result_df) >= 2:
        midpoints = (result_df["bin_start_hours"] + result_df["bin_end_hours"]) / 2
        valid_bins = result_df["meets_minimum"]
        slopes: dict[str, float] = {}
        for col in result_df.columns:
            if col.endswith("_median") and valid_bins.sum() >= 2:
                vals = result_df[col]
                mask = valid_bins & vals.notna()
                if mask.sum() >= 2:
                    x = midpoints[mask].values
                    y = vals[mask].values
                    slope, _, _, _, _ = sp_stats.linregress(x, y)
                    slopes[col.replace("_median", "_slope")] = slope
        if slopes:
            result_df = pd.concat([result_df, pd.DataFrame(slopes, index=result_df.index)], axis=1)

    # ── Missingness classification per bin ──────────────────────────────
    n_total = result_df.get("n_total_epochs", pd.Series(0, index=result_df.index))
    frac = result_df.get("clean_fraction_of_expected", result_df.get("coverage_fraction", pd.Series(0, index=result_df.index)))
    result_df["missingness_flag"] = np.where(
        n_total == 0, "no_data",
        np.where(frac >= 0.95, "complete",
        np.where(frac >= 0.5, "high_artifact",
        np.where(frac >= 0.1, "moderate_artifact", "low_data"))))

    return result_df
