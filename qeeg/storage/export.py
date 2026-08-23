"""Export formats for downstream analysis: wide, long, semi-long, parquet, provenance."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import platform
import subprocess
import zipfile
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

from qeeg.__version__ import __version__ as PIPELINE_VERSION
from qeeg.__version__ import COLUMN_SCHEMA_VERSION
from qeeg.ingestion.cadence import (
    get_family_cadence,
    get_family_effective_basis,
    get_family_engine_name,
    get_engine_window,
    get_effective_basis_values,
    FAMILY_ENGINE_MAP,
)


_FFT_EFFECTIVE_PREFIXES = ("fft_", "adr_", "tdr_", "rav_", "rel_")

# Canonical unit string per Persyst feature family. Used to populate the
# data-dictionary `unit` field for schema-derived entries so downstream
# codebooks carry physical units (µV²/Hz, µV, spikes/s, etc.) rather than
# blank strings. Values match the descriptions in
# docs/TREND_ENGINE_REFERENCE.md and the panel `units` strings in _PANEL_DEFS.
#
# UNITS FOLLOW THE MMX ``PowerType`` SETTING, NOT AN ASSUMPTION. The Persyst
# Power Scale selector is an enum — 0=µV², 1=µV, 2=dB, 3=sqrt(µV) — and the
# export writes the configured scale. The V10 template sets PowerType=1 (µV) on
# FFT Power / PowerRatio / SEF / Asymmetry and PowerType=3 (sqrt(µV)) on the FFT
# Spectrogram. These strings previously claimed µV² for FFT Power, which was
# wrong for 54 columns. Confirmed: Persyst (Mike), email to C. Press,
# 2026-08-20/21, plus the Power Scale dialog screenshot.
def _resolve_variant_unit(variable_name: str, family: str, unit: str) -> str:
    """Narrow a family-level unit to the specific variant this column carries.

    Three families ship variants with different units under one family name, so
    the family-level string would otherwise read "binary (0/1) or % (0-100)" —
    an ambiguity the analyst has to resolve by hand for every column.

    * ``status_epilepticus`` — 3 methods x {binary, percent}
    * ``seizure_burden``     — percentage vs category code
    * ``sleep``              — ``SleepStages`` carries the 0-5 stage code, but the
      six per-stage ``Sleep-Wake Stage <stage>`` columns are Threshold trends on
      it (``Operator "="``, ``Cutoff`` = that stage) and are therefore binary
      one-hot indicators, not stage codes.
    """
    v = (variable_name or "").lower()
    if family in ("status_epilepticus", "seizure_burden"):
        if v.endswith("_binary") or "_binary_" in v:
            return "binary (0/1)"
        if v.endswith("_percent") or "_percent_" in v or v.endswith("_pct"):
            return "% (0–100)"
        if "categor" in v:
            return "category code"
    if family == "sleep":
        # The undifferentiated stage-code column keeps the code map; every
        # per-stage column is a one-hot flag.
        if "stage_display" in v or "rate_display" in v or v.endswith("sleepstages"):
            return "sleep stage code (0=indeterminate, 1=N3, 2=N2, 3=N1, 4=REM, 5=wake)"
        return "binary (0/1) — one-hot flag for this stage"
    return unit


_FAMILY_UNITS: dict[str, str] = {
    "fft_power": "µV (amplitude; MMX PowerType=1 — NOT µV² power)",
    "fft_power_ratio": "ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10",
    "adr": ("ratio of µV amplitudes (dimensionless); clamped at Ratio Max 10. "
            "NOT a power ratio — equals the square root of a conventional "
            "power-based ADR, so do not compare directly to published values."),
    "relative_power": ("band/broadband ratio of µV amplitudes (dimensionless); "
                       "clamped at Ratio Max 10. NOT conventional relative power "
                       "(band power ÷ total power) — equals its square root."),
    "alpha_variability": ("RAV: 6–14/1–20 Hz ratio of µV amplitudes "
                          "(dimensionless); clamped at Ratio Max 10"),
    "fft_spectrogram": "µV/√Hz (amplitude spectral density = √(µV²/Hz); Persyst label 'sqrt(µV)/Hz'; square to get PSD µV²/Hz)",
    "asymmetry_spectrogram": "% (−100 to +100) per bin",
    "rhythmicity_spectrogram": "rhythmic spectral amplitude (µV/Hz)",
    "spectral_edge": "Hz",
    "asymmetry": "% (EASI 0–100 magnitude; REASI −100 to +100, + = right>left)",
    "suppression_ratio": "% (0–100)",
    "rhythmicity": "rhythmicity index",
    "rda": "rhythmicity index",
    "rhythmic_delta": "boolean (0/1)",
    # Sub-column 1 muscle (units pending vendor confirmation — Persyst help says
    # "average power (µV²)", Mike's 2026-08-20 note says µV); sub-columns 2 and 3
    # are vertical and lateral eye-movement PROBABILITY scores, 0.0–1.0 (P-COMM).
    "artifact_intensity": ("muscle: µV (per Persyst 2026-08-20; help text says µV² — "
                           "unconfirmed). V-Eye / L-Eye: probability 0.0–1.0"),
    # Persyst (Mike, 2026-08-20): 0.0 clean → 1.0, values above 1.0 indicate an
    # electrode above the impedance disconnect threshold. The 1.2 ceiling seen in
    # exports is the MMX display Maximum (Autoscale off), so values are CLAMPED to
    # it — 1.2 means "at or beyond the configured maximum", not a Persyst sentinel.
    "electrode_quality": ("dimensionless, 0=clean → 1.0; >1.0 = above impedance "
                          "disconnect threshold. Clamped at the MMX display "
                          "Maximum (1.2 in this template)"),
    "aeeg": "µV (peak-to-peak)",
    "peak_envelope": "µV",
    "seizure_probability": "probability (0–1)",
    "seizure_detection": "boolean (0/1)",
    "seizure_notification": "boolean (0/1)",
    # Two vendor behaviours an analyst must know before modelling these, both
    # confirmed in the raw CSV across 16 real exports (7 patients):
    #   * the Advanced and Combined PERCENT variants are byte-identical on every
    #     row — one variable under two names, perfectly collinear;
    #   * they never reach 0. Their resting output is a floor of 0.050331, so
    #     `> 0` is true on every epoch of every recording and a reported mean of
    #     "0.05%" is that floor, not a detection. Threshold above it, not at 0.
    #   * the ACNS percent variant was exactly 0 in all 16 exports.
    # Faithfully transported, not repaired; qeeg.quality.constant_columns
    # surfaces them per recording in the QC report.
    "status_epilepticus": ("binary (0/1) or % (0–100) per variant. PERCENT "
                           "variants floor at 0.050331, never 0; advanced and "
                           "combined are identical — see docs/DATA_DICTIONARY_v4.md"),
    "seizure_burden": "% (0–100) or category code per variant",
    "spike_density": "spikes/sec",
    "coherence_spectrogram": "coherence (0–1)",
    "sleep": "sleep stage code",
    "heart_rate": "bpm",
    "annotation": "text",
    "time_display": "timestamp",
}

_MISSINGNESS_FLAG_VALUES = [
    {"code": "complete", "label": ">=95% usable coverage"},
    {"code": "high_artifact", "label": "50-94% usable coverage"},
    {"code": "moderate_artifact", "label": "10-49% usable coverage"},
    {"code": "low_data", "label": "<10% usable coverage"},
    {"code": "no_data", "label": "0 usable rows available"},
]

# Columns always kept regardless of group filter (bin metadata).
_METADATA_COLS: frozenset[str] = frozenset({
    "bin_label", "bin_start_hours", "bin_end_hours",
    "n_total_epochs", "n_usable_epochs", "n_observed", "n_effective_fft",
    "n_effective_cadence_adjusted",
    "coverage_hours", "coverage_fraction", "meets_minimum",
    "bin_expected_hours", "observed_wall_clock_hours", "artifact_clean_hours",
    "clean_fraction_of_observed", "clean_fraction_of_expected",
    "background_continuity_index", "seizure_burden_hours", "missingness_flag",
})

# Stat suffixes used in bin_summary column names.
_BIN_STAT_SUFFIXES = (
    "_median", "_mean", "_sd", "_iqr", "_min", "_max", "_n",
    "_log_mean", "_log_sd", "_trimmed_mean", "_cv", "_slope",
)

# Family names that belong to each export group.
_GROUP_FAMILIES: dict[str, frozenset[str]] = {
    "core": frozenset({
        "fft_power", "fft_power_ratio", "adr", "relative_power", "aeeg",
        "seizure_probability", "seizure_detection", "seizure_notification",
        "status_epilepticus", "seizure_burden",
        "suppression_ratio", "spike_density", "alpha_variability", "heart_rate",
        "spectral_edge", "rda", "rhythmic_delta", "sleep", "peak_envelope",
    }),
    "electrode_detail": frozenset({
        "electrode_quality", "artifact_intensity",
    }),
    "fft_spectrogram": frozenset({"fft_spectrogram"}),
    "asymmetry_spectrogram": frozenset({"asymmetry"}),
    "coherence_spectrogram": frozenset({"coherence_spectrogram"}),
    "rhythmicity": frozenset({"rhythmicity"}),
}

# Derived feature prefixes (computed in pipeline.py, not in schema).
# These are always core.
_DERIVED_PREFIXES = (
    "fft_delta_", "fft_theta_", "fft_alpha_", "fft_beta_",
    "total_power_", "rel_delta_", "rel_theta_", "rel_alpha_", "rel_beta_",
    "theta_delta_ratio_", "alpha_delta_ratio_",
    "log_theta_delta_ratio_", "log_alpha_delta_ratio_",
    "aeeg_",
)

# Asymmetry spectrogram bases end with _1 … _40 (freq-bin sub-columns).
# Single-value EASI/REASI (no numeric suffix) stay in core.
import re as _re
_ASYM_SPEC_RE = _re.compile(r"_\d+$")


def _base_name(col: str) -> str:
    """Strip the trailing stat suffix from a bin_summary column name."""
    for sfx in _BIN_STAT_SUFFIXES:
        if col.endswith(sfx):
            return col[: -len(sfx)]
    return col


def _is_asymmetry_spectrogram(base: str, common_name: str) -> bool:
    """True when the base represents a per-freq-bin asymmetry column (not EASI/REASI)."""
    return bool(_ASYM_SPEC_RE.search(base)) and "easi" not in common_name.lower()


def _resolve_enabled_bases(
    include_groups: list[str],
    schema: list,
    bin_summary_cols: list[str],
) -> set[str]:
    """Return the set of variable base names that should appear in the export.

    *include_groups* is a list of group keys: core, electrode_detail,
    fft_spectrogram, asymmetry_spectrogram, coherence_spectrogram, rhythmicity.
    Core is always implicitly included.
    """
    groups = set(include_groups) | {"core"}

    # Build a lookup from I-code → (family, common_name) from schema.
    code_meta: dict[str, tuple[str, str]] = {
        e.code: (e.family, e.common_name or "") for e in schema
    }

    enabled: set[str] = set()

    for col in bin_summary_cols:
        base = _base_name(col)
        if base in _METADATA_COLS:
            continue

        # Derived features (not in schema) → always core.
        if any(base.startswith(p) for p in _DERIVED_PREFIXES):
            enabled.add(base)
            continue

        family, common_name = code_meta.get(base, ("", ""))

        # EASI/REASI: asymmetry family but common_name contains "easi" → core.
        if family == "asymmetry" and "easi" in common_name.lower():
            enabled.add(base)
            continue

        # Asymmetry spectrogram: asymmetry family with freq-bin suffix → group.
        if family == "asymmetry" and _is_asymmetry_spectrogram(base, common_name):
            if "asymmetry_spectrogram" in groups:
                enabled.add(base)
            continue

        # Match family to group.
        matched = False
        for group_key, families in _GROUP_FAMILIES.items():
            if family in families:
                if group_key in groups:
                    enabled.add(base)
                matched = True
                break

        # Unknown family → include by default (future-proof).
        if not matched:
            enabled.add(base)

    return enabled


def _filter_bin_summary(
    df: pd.DataFrame,
    include_groups: list[str] | None,
    schema: list,
) -> pd.DataFrame:
    """Drop stat columns for variable families not in *include_groups*.

    Metadata columns are always kept.  When *include_groups* is None the
    default is core-only.
    """
    groups = include_groups if include_groups is not None else ["core"]
    enabled_bases = _resolve_enabled_bases(groups, schema, list(df.columns))

    keep_cols = []
    for col in df.columns:
        base = _base_name(col)
        if base in _METADATA_COLS or col in _METADATA_COLS:
            keep_cols.append(col)
        elif base in enabled_bases:
            keep_cols.append(col)
    return df[keep_cols]


def _feature_has_fft_effective_n(feature_name: str) -> bool:
    """Return True when the current cadence-adjusted effective N applies.

    The live pipeline only derives effective independent observations for FFT-like
    families. Other families still report row counts and must not be labelled as
    independent until family-specific cadence handling exists.
    """
    return feature_name.startswith(_FFT_EFFECTIVE_PREFIXES)


def _feature_effective_n(bin_row: pd.Series, feature_name: str) -> tuple[Any, str]:
    """Return feature-specific effective N and basis with legacy fallback."""
    observed = bin_row.get(f"{feature_name}_n_observed", bin_row.get(f"{feature_name}_n", 0))
    effective = bin_row.get(f"{feature_name}_n_effective", np.nan)
    basis = bin_row.get(f"{feature_name}_effective_basis", None)
    if basis is not None and not pd.isna(basis):
        return effective, str(basis)
    if _feature_has_fft_effective_n(feature_name):
        return bin_row.get("n_effective_fft", np.nan), "fft_cadence_adjusted"
    return np.nan, "not_estimated"


def _engines_from_summary(summary: dict | None) -> dict | None:
    """Rehydrate MMX engine summaries into EngineConfig-like objects."""
    if not summary:
        return None
    from qeeg.ingestion.mmx_parser import EngineConfig

    engines = {}
    for name, values in summary.items():
        try:
            engines[name] = EngineConfig(
                name=name,
                epoch_duration=float(values["epoch_duration"]),
                epoch_step=float(values["epoch_step"]),
            )
        except Exception:
            continue
    return engines or None


def _normalize_for_csv(value: Any) -> Any:
    """Flatten list/dict metadata for CSV codebooks."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _enrich_entry(
    entry: dict[str, Any],
    engines: dict | None = None,
) -> dict[str, Any]:
    """Add cadence, window, and definition fields to a dictionary entry."""
    family = entry.get("family", "")
    is_eeg_feature = family in FAMILY_ENGINE_MAP
    is_categorical = entry.get("is_categorical", False)

    # Timing + observation-count definitions — only for EEG feature families
    if is_eeg_feature:
        cadence = get_family_cadence(family, engines)
        window = get_engine_window(family, engines)
        engine_name = get_family_engine_name(family)
        effective_basis = get_family_effective_basis(family, engines)
        entry["cadence_seconds"] = cadence
        entry["window_seconds"] = window
        entry["persyst_engine"] = engine_name

        var_name = entry.get("variable_name", "")
        entry["n_observed_definition"] = (
            "Count of non-null usable rows for this feature in the time bin."
        )
        if effective_basis != "row_count":
            entry["n_effective_definition"] = (
                f"Cadence-adjusted independent observation count for {family} "
                f"from {engine_name} (EpochStep={cadence}s, EpochDuration={window}s); "
                f"reported with n_effective_basis={effective_basis}."
            )
        else:
            entry["n_effective_definition"] = (
                f"Engine {engine_name} updates every exported row "
                f"(EpochStep={cadence}s, EpochDuration={window}s); "
                "n_effective equals n_observed and n_effective_basis=row_count."
            )
    else:
        entry["cadence_seconds"] = None
        entry["window_seconds"] = None
        entry["persyst_engine"] = None
        entry["n_observed_definition"] = None
        entry["n_effective_definition"] = None

    # Populate canonical units for schema-derived family entries that came in
    # with empty units (build_data_dictionary leaves `unit=""` on raw schema
    # entries since unit is family-level, not column-level).
    if not entry.get("unit") and family in _FAMILY_UNITS:
        entry["unit"] = _FAMILY_UNITS[family]

    # Families where Persyst ships several variants of the same measure under one
    # family, each with a DIFFERENT unit. A family-level "binary or percent"
    # string is useless to an analyst — resolve it per column from the variable
    # name so every row states one unit.
    entry["unit"] = _resolve_variant_unit(
        entry.get("variable_name", ""), family, entry.get("unit", ""))

    # Categorical fields
    if is_categorical:
        cats = entry.get("categories", [])
        entry["category_code_map"] = (
            {c["code"]: c["label"] for c in cats} if cats else {}
        )
        entry["allowed_values"] = [c["code"] for c in cats] if cats else []
    else:
        entry["category_code_map"] = {}
        entry["allowed_values"] = None

    return entry


def _statistic_dictionary_entries() -> list[dict[str, Any]]:
    """Definitions for long-export statistic columns and bin-summary suffixes."""
    missing_policy = {
        "csv": "blank field",
        "parquet": "null/NaN",
        "allowed_sentinel_codes": [],
    }
    stats: list[tuple[str, str, str, str]] = [
        ("median", "Feature median", "Median of usable, non-null feature values after the feature-specific effective-N mask is applied.", "feature units"),
        ("mean", "Feature arithmetic mean", "Arithmetic mean of usable, non-null feature values after the feature-specific effective-N mask is applied.", "feature units"),
        ("sd", "Feature standard deviation", "Sample standard deviation of usable, non-null feature values; 0.0 when only one value contributes.", "feature units"),
        ("p05", "Feature 5th percentile", "Empirical 5th percentile of usable, non-null feature values.", "feature units"),
        ("p10", "Feature 10th percentile", "Empirical 10th percentile of usable, non-null feature values.", "feature units"),
        ("p25", "Feature 25th percentile", "Empirical 25th percentile of usable, non-null feature values.", "feature units"),
        ("p75", "Feature 75th percentile", "Empirical 75th percentile of usable, non-null feature values.", "feature units"),
        ("p90", "Feature 90th percentile", "Empirical 90th percentile of usable, non-null feature values.", "feature units"),
        ("p95", "Feature 95th percentile", "Empirical 95th percentile of usable, non-null feature values.", "feature units"),
        ("iqr", "Feature interquartile range", "p75 minus p25 for usable, non-null feature values.", "feature units"),
        ("min", "Feature minimum", "Minimum usable, non-null feature value.", "feature units"),
        ("max", "Feature maximum", "Maximum usable, non-null feature value.", "feature units"),
        ("trimmed_mean_20pct", "Feature 20 percent trimmed mean", "Mean after trimming 10 percent from each tail; for fewer than four observations, equals the arithmetic mean.", "feature units"),
        ("cv", "Feature coefficient of variation", "SD divided by mean for strictly positive mean values; NaN for zero, near-zero, or negative means.", "unitless"),
        ("log_mean", "Feature geometric mean", "exp(mean(log(x))) for positive spectral-power values only.", "feature units"),
        ("log_sd", "Feature log standard deviation", "Sample SD of log-transformed positive spectral-power values.", "log units"),
        ("slope", "Feature trajectory slope", "Linear regression slope of bin midpoint versus feature median across bins meeting minimum coverage.", "feature units per hour"),
    ]
    entries = [
        {
            "variable_name": name,
            "label": label,
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": unit,
            "family": "statistic",
            "original_code": "",
            "source_columns": [f"*_{name}"],
            "derivation_formula": formula,
            "missing_value_policy": missing_policy,
            "notes": "In bin-summary exports this appears as {feature}_" + name + "; in long exports this appears as a statistic column when included.",
        }
        for name, label, formula, unit in stats
    ]
    entries.extend([
        {
            "variable_name": "coverage_hours",
            "label": "Artifact-clean EEG support",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "hours",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["artifact_clean_hours"],
            "derivation_formula": "Sum of timestamp-derived durations for artifact-clean usable rows in the bin.",
            "missing_value_policy": missing_policy,
            "notes": "Same value as artifact_clean_hours; retained for backward compatibility.",
        },
        {
            "variable_name": "bin_expected_hours",
            "label": "Configured bin width",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "hours",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["bin_start_hours", "bin_end_hours"],
            "derivation_formula": "bin_end_hours - bin_start_hours.",
            "missing_value_policy": missing_policy,
            "notes": "The intended wall-clock width of the configured analysis bin.",
        },
        {
            "variable_name": "observed_wall_clock_hours",
            "label": "Observed EEG support",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "hours",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["_hours_relative"],
            "derivation_formula": "Sum of timestamp-derived row durations in the bin with large gaps capped.",
            "missing_value_policy": missing_policy,
            "notes": "Represents observed exported EEG support, not the full configured bin width.",
        },
        {
            "variable_name": "artifact_clean_hours",
            "label": "Artifact-clean EEG support",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "hours",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["_artifact_clean", "_hours_relative"],
            "derivation_formula": "Sum of timestamp-derived row durations for rows passing the artifact-clean mask.",
            "missing_value_policy": missing_policy,
            "notes": "Primary numerator for coverage calculations.",
        },
        {
            "variable_name": "clean_fraction_of_observed",
            "label": "Proportion clean (of observed EEG support)",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "proportion (0–1)",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["artifact_clean_hours", "observed_wall_clock_hours"],
            "derivation_formula": "artifact_clean_hours / observed_wall_clock_hours.",
            "missing_value_policy": missing_policy,
            "notes": (
                "PROPORTION CLEAN: of the EEG actually recorded in this bin, "
                "what fraction was artifact-clean? Numerator = artifact-clean "
                "hours; denominator = observed wall-clock hours of EEG. "
                "Equals 1.0 when all recorded EEG was clean, regardless of "
                "whether the recording covered the full bin width. "
                "Same value as the deprecated `coverage_fraction` alias."
            ),
        },
        {
            "variable_name": "clean_fraction_of_expected",
            "label": "Proportion of bin (clean coverage of configured bin width)",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "proportion (0–1)",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["artifact_clean_hours", "bin_expected_hours"],
            "derivation_formula": "artifact_clean_hours / bin_expected_hours.",
            "missing_value_policy": missing_policy,
            "notes": (
                "PROPORTION OF BIN: of the configured bin width "
                "(e.g. 6.0 h), what fraction was both recorded AND "
                "artifact-clean? Numerator = artifact-clean hours; "
                "denominator = bin_expected_hours. Equals 0.5 when half "
                "the bin width was covered with clean EEG. Drives "
                "`missingness_flag` buckets."
            ),
        },
        {
            "variable_name": "coverage_fraction",
            "label": "DEPRECATED alias of `clean_fraction_of_observed` (proportion clean)",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "proportion (0–1)",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["clean_fraction_of_observed"],
            "derivation_formula": "Alias of clean_fraction_of_observed. DEPRECATED.",
            "missing_value_policy": missing_policy,
            "notes": (
                "DEPRECATED. The name suggests proportion of the configured bin "
                "width that was covered, but the value is proportion of observed "
                "EEG that was clean — different denominators. Use the explicit "
                "pair instead: `clean_fraction_of_observed` (proportion clean) "
                "and `clean_fraction_of_expected` (proportion of bin). Retained "
                "for backward compatibility; will be removed at the next "
                "CACHE_SCHEMA_VERSION bump."
            ),
        },
        {
            "variable_name": "background_continuity_index",
            "label": "Background continuity index",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "proportion",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["suppression_*"],
            "derivation_formula": "Proportion of usable epochs with non-missing suppression values below threshold.",
            "missing_value_policy": missing_policy,
            "notes": "NaN when suppression values are unavailable.",
        },
        {
            "variable_name": "seizure_burden_hours",
            "label": "Artifact-clean seizure burden in bin",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": "hours",
            "family": "seizure",
            "original_code": "",
            "source_columns": ["_artifact_clean", "_hours_relative", "seizure_mask"],
            "derivation_formula": "Sum of timestamp-derived row durations for rows that are both artifact-clean and seizure-positive within the bin.",
            "missing_value_policy": missing_policy,
            "notes": "NaN when no usable rows exist in the bin or when no seizure mask was computed.",
        },
        {
            "variable_name": "n_effective_cadence_adjusted",
            "label": "Bin-level cadence-adjusted effective N",
            "data_type": "integer",
            "is_categorical": False,
            "categories": [],
            "unit": "observations",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["_usable", "_is_independent_<engine>"],
            "derivation_formula": "Minimum across feature families of cadence-adjusted independent-observation counts within the bin; equals n_effective_fft when only FFT cadence is present.",
            "missing_value_policy": missing_policy,
            "notes": "Per-feature n_effective is preferred for analysis; this bin-level summary is retained for backward compatibility with audit workflows.",
        },
    ])
    return entries


# ---------------------------------------------------------------------------
# Derived features (computed in pipeline, not emitted as schema entries)
# ---------------------------------------------------------------------------

# Regions over which derived features are computed (compute_all_derived,
# compute_regional_features). Kept as a constant so tests can introspect.
_DERIVED_REGIONS: tuple[str, ...] = ("anterior", "posterior")
_DERIVED_BANDS: tuple[str, ...] = ("delta", "theta", "alpha", "beta")


def _derived_feature_entries() -> list[dict[str, Any]]:
    """Dictionary entries for pipeline-derived features.

    These columns are produced in `qeeg.features.region_mapping` and
    `qeeg.features.derived_features` and are not present in the parsed
    Persyst schema, so they require explicit dictionary rows. All inherit
    the FFT engine cadence/window from their source columns.
    """
    missing_policy = {
        "csv": "blank field",
        "parquet": "null/NaN",
        "allowed_sentinel_codes": [],
    }

    entries: list[dict[str, Any]] = []

    for region in _DERIVED_REGIONS:
        # Bilateral band-power aggregates (compute_regional_features).
        for band in _DERIVED_BANDS:
            entries.append({
                "variable_name": f"fft_{band}_{region}",
                "label": f"Bilateral {region} {band}-band FFT power",
                "data_type": "float",
                "is_categorical": False,
                "categories": [],
                "unit": _FAMILY_UNITS["fft_power"],
                "family": "fft_power",
                "original_code": "",
                "source_columns": [
                    f"FFT_Power Left {region.capitalize()} {band}",
                    f"FFT_Power Right {region.capitalize()} {band}",
                ],
                "derivation_formula": (
                    f"NaN-tolerant mean of left- and right-{region} "
                    f"FFT {band}-band power across hemispheres."
                ),
                "missing_value_policy": missing_policy,
                "notes": (
                    "Defaults to NaN-tolerant mean (require_bilateral=False); "
                    "see fft_{band}_{region}_sides_contributing for the "
                    "per-epoch hemisphere-contribution count."
                ),
            })
            entries.append({
                "variable_name": f"fft_{band}_{region}_sides_contributing",
                "label": (
                    f"Hemispheres contributing to fft_{band}_{region} "
                    f"per epoch"
                ),
                "data_type": "integer",
                "is_categorical": True,
                "categories": [
                    {"code": 0, "label": "Neither hemisphere contributed"},
                    {"code": 1, "label": "One hemisphere contributed (unilateral fallback)"},
                    {"code": 2, "label": "Both hemispheres contributed (true bilateral mean)"},
                ],
                "unit": "count",
                "family": "fft_power",
                "original_code": "",
                "source_columns": [
                    f"FFT_Power Left {region.capitalize()} {band}",
                    f"FFT_Power Right {region.capitalize()} {band}",
                ],
                "derivation_formula": (
                    "Count of left.notna() + right.notna() per epoch."
                ),
                "missing_value_policy": missing_policy,
                "notes": (
                    "0 = both NaN, 1 = unilateral survivor (potential "
                    "asymmetric-encephalopathy bias), 2 = true bilateral mean."
                ),
            })

        # Total + relative band power, ratios, log ratios (compute_all_derived).
        entries.append({
            "variable_name": f"total_power_{region}",
            "label": f"Bilateral {region} total FFT power",
            "data_type": "float",
            "is_categorical": False,
            "categories": [],
            "unit": _FAMILY_UNITS["fft_power"],
            "family": "fft_power",
            "original_code": "",
            "source_columns": [
                f"fft_delta_{region}",
                f"fft_theta_{region}",
                f"fft_alpha_{region}",
                f"fft_beta_{region}",
            ],
            "derivation_formula": (
                f"fft_delta_{region} + fft_theta_{region} + "
                f"fft_alpha_{region} + fft_beta_{region}."
            ),
            "missing_value_policy": missing_policy,
            "notes": "Log-transformed summary statistics (log_mean, log_sd) are emitted for positive values.",
        })
        for band in _DERIVED_BANDS:
            entries.append({
                "variable_name": f"rel_{band}_{region}",
                "label": f"Relative {band}-band power, {region}",
                "data_type": "float",
                "is_categorical": False,
                "categories": [],
                "unit": "proportion",
                "family": "fft_power_ratio",
                "original_code": "",
                "source_columns": [f"fft_{band}_{region}", f"total_power_{region}"],
                "derivation_formula": f"fft_{band}_{region} / total_power_{region}; NaN where total_power is 0.",
                "missing_value_policy": missing_policy,
                "notes": "Sum of rel_delta+rel_theta+rel_alpha+rel_beta within a region equals 1 by construction.",
            })
        for ratio_band in ("theta", "alpha"):
            entries.append({
                "variable_name": f"{ratio_band}_delta_ratio_{region}",
                "label": f"{ratio_band.capitalize()}/Delta ratio, {region}",
                "data_type": "float",
                "is_categorical": False,
                "categories": [],
                "unit": _FAMILY_UNITS["fft_power_ratio"],
                "family": "fft_power_ratio",
                "original_code": "",
                "source_columns": [f"fft_{ratio_band}_{region}", f"fft_delta_{region}"],
                "derivation_formula": f"fft_{ratio_band}_{region} / fft_delta_{region}; NaN where delta is 0.",
                "missing_value_policy": missing_policy,
                "notes": (
                    "Ratio is plausibly log-normal; consider analyzing on log scale "
                    "via log_{ratio}_delta_ratio_{region}."
                ),
            })
            entries.append({
                "variable_name": f"log_{ratio_band}_delta_ratio_{region}",
                "label": f"log10({ratio_band}/delta) ratio, {region}",
                "data_type": "float",
                "is_categorical": False,
                "categories": [],
                "unit": "log10 ratio",
                "family": "fft_power_ratio",
                "original_code": "",
                "source_columns": [f"fft_{ratio_band}_{region}", f"fft_delta_{region}"],
                "derivation_formula": (
                    f"log10(clip(fft_{ratio_band}_{region}, 1e-6) / "
                    f"clip(fft_delta_{region}, 1e-6)); 0 = equal power."
                ),
                "missing_value_policy": missing_policy,
                "notes": "Symmetric around 0; positive = numerator dominates. Approximately normal for parametric models.",
            })

    return entries


# Per-column clarifications appended to the data-dictionary `notes` field.
# Keyed by common_name. These record where an identifier is faithful to the
# vendor but could be read differently by a clinical audience, so the caveat
# travels with the exported dataset rather than living only in a commit message.
_COMMON_NAME_NOTES: dict[str, str] = {
    "rda_generalized": (
        "Persyst's own legend labels this channel 'gen'. Mechanically it is the "
        "conjunction of two independent regional detectors (left AND right), so "
        "it establishes that both hemispheres are concurrently positive. It does "
        "NOT establish the bilaterally synchronous and symmetric distribution "
        "that the ACNS 2021 'G' (generalized) modifier requires, and it cannot "
        "exclude bilateral-independent rhythmic delta. Read as 'both hemispheres "
        "active', not as ACNS GRDA. Companion channels rda_left and rda_right "
        "are the mutually exclusive one-sided detectors; across a real recording "
        "the three partition cleanly, with no epoch positive for more than one."
    ),
}


def column_resolution_summary(schema: list | None) -> dict:
    """How this export's columns were resolved, for the provenance block.

    A dataset stamped with a column_schema_version implies its columns were
    resolved by panel ordinal. That only holds when the export panel could be
    identified -- several panels share an instrument count, and when
    resolve_export_panel cannot decide, resolution silently degrades to
    name/regex while the version stamp stays the same. Recording the mix makes
    the difference visible in the data rather than only in a log line.
    """
    counts: dict[str, int] = {}
    for e in schema or []:
        counts[getattr(e, "resolution", "") or "unknown"] = \
            counts.get(getattr(e, "resolution", "") or "unknown", 0) + 1
    total = sum(counts.values())
    non_ordinal = total - counts.get("ordinal", 0) - counts.get("tail", 0)
    return {
        "by_method": dict(sorted(counts.items())),
        "fully_ordinal": non_ordinal == 0 and total > 0,
        "non_ordinal_columns": non_ordinal,
    }

def build_data_dictionary(
    schema: list | None = None,
    engines: dict | None = None,
) -> list[dict[str, Any]]:
    """Build a machine-readable data dictionary for exports and raw schema fields."""
    entries: list[dict[str, Any]] = [
        {
            "variable_name": "patient_id",
            "label": "Patient identifier",
            "data_type": "string",
            "is_categorical": True,
            "categories": [],
            "unit": "",
            "family": "identifier",
            "original_code": "",
            "source_columns": [],
            "derivation_formula": "",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Opaque patient/study identifier used for joins across exports.",
        },
        {
            "variable_name": "time_bin",
            "label": "Time bin label",
            "data_type": "string",
            "is_categorical": True,
            "categories": [],
            "unit": "",
            "family": "time",
            "original_code": "",
            "source_columns": ["bin_label"],
            "derivation_formula": "Derived from configured time-bin edges.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Ordered categorical label such as 0-6h or 6-12h.",
        },
        {
            "variable_name": "feature_name",
            "label": "Feature identifier",
            "data_type": "string",
            "is_categorical": True,
            "categories": [],
            "unit": "",
            "family": "export",
            "original_code": "",
            "source_columns": [],
            "derivation_formula": "Feature stem from *_median, *_mean, *_sd, *_iqr, *_min, *_max, *_n columns.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Only present in long-format exports.",
        },
        {
            "variable_name": "n_observed",
            "label": "Observed row count contributing to feature summary",
            "data_type": "integer",
            "is_categorical": False,
            "categories": [],
            "unit": "rows",
            "family": "export",
            "original_code": "",
            "source_columns": ["*_n_observed", "*_n"],
            "derivation_formula": "Copied from feature-specific *_n_observed when present; otherwise falls back to *_n for legacy bin summaries.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Observed usable rows, not a guaranteed effective independent sample size.",
        },
        {
            "variable_name": "n_effective",
            "label": "Effective independent observation count when cadence-adjusted",
            "data_type": "integer",
            "is_categorical": False,
            "categories": [],
            "unit": "observations",
            "family": "export",
            "original_code": "",
            "source_columns": ["*_n_effective", "n_effective_fft"],
            "derivation_formula": "Copied from feature-specific *_n_effective when present; otherwise falls back to legacy n_effective_fft for FFT-like features.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Use with n_effective_basis. Row-count families have n_effective equal to n_observed; slower engines use their family-specific cadence-adjusted count.",
        },
        {
            "variable_name": "n_effective_basis",
            "label": "Interpretation of n_effective",
            "data_type": "string",
            "is_categorical": True,
            "categories": [
                {"code": code, "label": (
                    "n_effective equals n_observed"
                    if code == "row_count"
                    else "Effective observation count not estimated for this feature family"
                    if code == "not_estimated"
                    else f"Cadence-adjusted effective observation count for {code.removesuffix('_cadence_adjusted')}"
                )}
                for code in get_effective_basis_values()
            ],
            "unit": "",
            "family": "export",
            "original_code": "",
            "source_columns": ["*_effective_basis"],
            "derivation_formula": "row_count when the producing engine updates every exported row; otherwise {family}_cadence_adjusted from the feature family's Persyst engine cadence.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Use with n_observed and n_effective to distinguish raw row counts from engine-cadence adjusted denominators.",
        },
        {
            "variable_name": "n_independent_obs",
            "label": "Legacy bin-level effective observation count",
            "data_type": "integer",
            "is_categorical": False,
            "categories": [],
            "unit": "observations",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["n_effective_fft", "n_effective_cadence_adjusted"],
            "derivation_formula": "Legacy compatibility field. Prefer per-feature n_effective and n_effective_basis.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Retained for older exports. Do not use as a universal denominator when per-feature n_effective is available.",
        },
        {
            "variable_name": "missingness_flag",
            "label": "Coverage/artifact status heuristic",
            "data_type": "string",
            "is_categorical": True,
            "categories": _MISSINGNESS_FLAG_VALUES,
            "unit": "",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["coverage_fraction", "n_usable_epochs", "n_total_epochs"],
            "derivation_formula": "Bucketed heuristic from usable coverage, not a formal MCAR/MAR/MNAR missingness model.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Categorical coverage flag for QC and filtering; should not be interpreted as a statistical missing-data mechanism.",
        },
        {
            "variable_name": "meets_minimum",
            "label": "Bin passes minimum coverage threshold",
            "data_type": "boolean",
            "is_categorical": True,
            "categories": [
                {"code": False, "label": "Bin retained but below minimum coverage threshold"},
                {"code": True, "label": "Bin meets configured minimum coverage threshold"},
            ],
            "unit": "",
            "family": "time_binning",
            "original_code": "",
            "source_columns": ["coverage_hours"],
            "derivation_formula": "coverage_hours >= configured minimum threshold.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Boolean QC gate used to distinguish analyzable from low-coverage bins.",
        },
        {
            "variable_name": "has_status_epilepticus",
            "label": "Status-epilepticus screen flag (deprecated name)",
            "data_type": "boolean",
            "is_categorical": True,
            "categories": [
                {"code": False, "label": "Algorithmic screen criterion not met"},
                {"code": True, "label": "Algorithmic screen criterion met"},
            ],
            "unit": "",
            "family": "seizure",
            "original_code": "",
            "source_columns": ["seizure_burden_pct", "longest_seizure_minutes", "seizure_events"],
            "derivation_formula": "Derived from Persyst seizure-trend output (>=30 min continuous or >=50% hourly burden or repeated close onsets).",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Deprecated name. The label implies ILAE status epilepticus but the value is algorithmic only. Prefer `status_epilepticus_screen_flag`; this alias will be removed in a future release.",
        },
        {
            "variable_name": "status_epilepticus_screen_flag",
            "label": "Status-epilepticus screen flag (algorithmic)",
            "data_type": "boolean",
            "is_categorical": True,
            "categories": [
                {"code": False, "label": "Algorithmic screen criterion not met"},
                {"code": True, "label": "Algorithmic screen criterion met"},
            ],
            "unit": "",
            "family": "seizure",
            "original_code": "",
            "source_columns": ["seizure_burden_pct", "longest_seizure_minutes", "seizure_events"],
            "derivation_formula": "Algorithmic screen: >=30 min continuous seizure, OR >=50% burden in any 1-hour sliding window, OR repeated seizures with <5 min inter-onset interval. Not an ILAE diagnosis.",
            "missing_value_policy": {
                "csv": "blank field",
                "parquet": "null",
                "allowed_sentinel_codes": [],
            },
            "notes": "Canonical name; mirrors `has_status_epilepticus` during deprecation window.",
        },
    ]

    entries.extend(_statistic_dictionary_entries())

    # Derived features (FFT-derived bilateral aggregates, ratios, log ratios,
    # side-contribution counts) are computed in pipeline.py and not present
    # in the parsed schema, so we emit explicit dictionary rows. They flow
    # through _enrich_entry below for cadence/window/engine population.
    entries.extend(_derived_feature_entries())

    if schema:
        # Where Persyst exports a column the derived-feature block also describes,
        # the native value wins at compute time (see
        # derived_features.compute_all_derived) — so drop the derived row rather
        # than emit two dictionary entries for one variable_name, one of which is
        # wrong. This bites rel_{band}_{region}: from column_schema_version 3 the
        # mapper emits exactly those names, so the guard finally fires, but the
        # derived row still declared family fft_power_ratio, unit "proportion",
        # and a fft_{band}/total_power formula. The native column is
        # band / 1-30 Hz, and the schema row below describes it correctly.
        native = {e.common_name for e in schema if getattr(e, "common_name", "")}
        entries = [x for x in entries if x["variable_name"] not in native]

        for e in schema:
            if not getattr(e, "common_name", ""):
                continue
            entries.append({
                "variable_name": e.common_name,
                "label": e.trend_name,
                "data_type": "numeric",
                "is_categorical": False,
                "categories": [],
                "unit": "",
                "family": e.family,
                # source_code holds the Persyst I-code once `code` has been
                # replaced by the semantic slug; fall back for older schemas.
                "original_code": getattr(e, "source_code", "") or e.code,
                "source_columns": [e.code],
                "derivation_formula": "Direct Persyst export column after schema mapping.",
                "missing_value_policy": {
                    "csv": "blank field",
                    "parquet": "null/NaN",
                    "allowed_sentinel_codes": [],
                },
                "frequency_band": e.frequency_band or "",
                "freq_min_hz": e.freq_min_hz,
                "freq_max_hz": e.freq_max_hz,
                "hemisphere": e.hemisphere or "",
                "region": e.region or "",
                "electrode": e.electrode or "",
                "notes": " ".join(filter(None, [
                    "Raw mapped Persyst trend column. Numeric values remain nullable; canonical exports do not replace missing numeric values with sentinel codes.",
                    _COMMON_NAME_NOTES.get(e.common_name, ""),
                ])),
            })

    return [_enrich_entry(e, engines) for e in entries]


def data_dictionary_dataframe(
    schema: list | None = None,
    engines: dict | None = None,
) -> pd.DataFrame:
    """Return a flattened DataFrame representation of the data dictionary."""
    entries = build_data_dictionary(schema, engines)
    return pd.DataFrame([{k: _normalize_for_csv(v) for k, v in entry.items()} for entry in entries])


_PANEL_DEFS: list[dict[str, Any]] = [
    {
        "panel_id": "band_power_anterior",
        "display_name": "Band Power (Anterior)",
        "description": "FFT spectral power in standard frequency bands for anterior electrodes.",
        "source_families": ["fft_power"],
        "_region": "anterior",
        "units": "\u00b5V\u00b2/Hz",
        "derivation": "FFT power (4s Hanning window, 8s epoch step) in delta/theta/alpha/beta bands.",
        "filtering": "Artifact-excluded epochs removed before aggregation.",
    },
    {
        "panel_id": "band_power_posterior",
        "display_name": "Band Power (Posterior)",
        "description": "FFT spectral power in standard frequency bands for posterior electrodes.",
        "source_families": ["fft_power"],
        "_region": "posterior",
        "units": "\u00b5V\u00b2/Hz",
        "derivation": "FFT power (4s Hanning window, 8s epoch step) in delta/theta/alpha/beta bands.",
        "filtering": "Artifact-excluded epochs removed before aggregation.",
    },
    {
        "panel_id": "adr_hemisphere",
        "display_name": "ADR — Hemisphere",
        "description": "Alpha/delta ratio (ADR) for left and right hemispheres. ADR tracks background EEG reactivity and encephalopathy severity — higher = more awake/reactive, lower = more encephalopathic.",
        "source_families": ["fft_power_ratio"],
        "_region": "hemisphere",
        "units": "ratio (dimensionless)",
        "derivation": "ADR = alpha (8\u201313 Hz) / delta (1\u20134 Hz) power ratio, Persyst FFT engine. Per-electrode ratios averaged across hemisphere (Jensen's inequality applies).",
        "filtering": "Artifact-excluded epochs removed before aggregation. 2-min running-average display variants excluded.",
    },
    {
        "panel_id": "adr_tdr_anterior",
        "display_name": "ADR / TDR — Anterior",
        "description": "Anterior alpha/delta ratio (ADR) per hemisphere, plus bilateral anterior theta/delta ratio (TDR). TDR is more sensitive than ADR for detecting moderate encephalopathy.",
        "source_families": ["fft_power_ratio", "fft_power"],
        "_region": "anterior",
        "units": "ratio (dimensionless)",
        "derivation": "ADR = alpha (8\u201313 Hz) / delta (1\u20134 Hz), Persyst FFT engine, anterior electrodes. TDR = theta (4\u20138 Hz) / delta (1\u20134 Hz) derived from FFT power band averages.",
        "filtering": "Artifact-excluded epochs removed before aggregation.",
    },
    {
        "panel_id": "adr_tdr_posterior",
        "display_name": "ADR / TDR — Posterior",
        "description": "Posterior alpha/delta ratio (ADR) per hemisphere, plus bilateral posterior theta/delta ratio (TDR). Posterior ADR reflects occipital background and is sensitive to post-anoxic encephalopathy.",
        "source_families": ["fft_power_ratio", "fft_power"],
        "_region": "posterior",
        "units": "ratio (dimensionless)",
        "derivation": "ADR = alpha (8\u201313 Hz) / delta (1\u20134 Hz), Persyst FFT engine, posterior electrodes. TDR = theta (4\u20138 Hz) / delta (1\u20134 Hz) derived from FFT power band averages.",
        "filtering": "Artifact-excluded epochs removed before aggregation.",
    },
    {
        "panel_id": "seizure_probability",
        "display_name": "Seizure Probability",
        "description": "Persyst seizure detection probability score.",
        "source_families": ["seizure_probability"],
        "units": "probability (0\u20131)",
        "derivation": "Persyst SeizureProbabilityP1401 engine, 1s window, 1s updates.",
        "filtering": "Raw probability values; threshold applied for seizure event detection.",
    },
    {
        "panel_id": "suppression_ratio",
        "display_name": "Suppression Ratio",
        "description": "EEG burst-suppression ratio from amplitude analysis.",
        "source_families": ["suppression_ratio"],
        "units": "ratio (0\u20131)",
        "derivation": "Persyst Amplitude01 engine, 10s window, 10s epoch step.",
        "filtering": "Artifact-excluded epochs removed.",
    },
    {
        "panel_id": "artifact_intensity",
        "display_name": "Artifact Intensity",
        "description": "Composite artifact intensity across electrode channels.",
        "source_families": ["artifact_intensity"],
        "units": "arbitrary (0\u201330+ scale)",
        "derivation": "Persyst Artifact01 engine, 1.2s window, 1s updates.",
        "filtering": "Used as quality gate; quality mode thresholds artifact quality sub-columns.",
    },
    {
        "panel_id": "spike_density",
        "display_name": "Spike Density",
        "description": "Interictal spike rate by laterality. Displayed: left-hemisphere (blue), right-hemisphere (red), and generalized (green) spikes per second. Persyst SpikeDensityV101 engine.",
        "source_families": ["spike_density"],
        "units": "spikes/sec",
        "derivation": "Persyst SpikeDensityV101 engine, 1s epoch, 1s step. Left = spike_left_per_sec; Right = spike_right_per_sec; Generalized = spike_generalized_per_sec. Threshold, display, and burst columns excluded from display.",
        "filtering": "Artifact-excluded epochs removed.",
        "_exclude_name_fragments": ["threshold", "rate_display", "vertex", "all_foci", "burst"],
    },
    {
        "panel_id": "aeeg",
        "display_name": "aEEG (Amplitude-Integrated EEG)",
        "description": "Amplitude-integrated EEG for background pattern assessment.",
        "source_families": ["aeeg"],
        "units": "\u00b5V",
        "derivation": "Persyst aEEG01 engine, 1s window, 1s updates.",
        "filtering": "Artifact-excluded epochs removed.",
    },
    {
        "panel_id": "fft_spectrogram_left",
        "display_name": "FFT Spectrogram (Left)",
        "description": "Time-frequency power spectrogram for left hemisphere.",
        "source_families": ["fft_spectrogram"],
        "_hemisphere": "left",
        "units": "\u00b5V\u00b2/Hz",
        "derivation": "FFT spectrogram, 0\u201320 Hz, 0.5 Hz resolution, 40 frequency bins.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "fft_spectrogram_right",
        "display_name": "FFT Spectrogram (Right)",
        "description": "Time-frequency power spectrogram for right hemisphere.",
        "source_families": ["fft_spectrogram"],
        "_hemisphere": "right",
        "units": "\u00b5V\u00b2/Hz",
        "derivation": "FFT spectrogram, 0\u201320 Hz, 0.5 Hz resolution, 40 frequency bins.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "asymmetry_spectrogram_hemi",
        "display_name": "Asymmetry Spectrogram — Hemisphere",
        "description": "Relative hemispheric asymmetry across 0–20 Hz: positive (red) = right > left power, negative (blue) = left > right power. Hemisphere-level average (all left vs all right electrodes).",
        "source_families": ["asymmetry"],
        "_spectrogram": True,
        "_name_must_contain": "hemi",
        "units": "asymmetry index (\u22121 to +1)",
        "derivation": "Asymmetry spectrogram, 0\u201320 Hz, 0.5 Hz resolution. (Left \u2212 Right) / (Left + Right) per frequency bin, hemisphere-level electrode averages.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "asymmetry_spectrogram_ant",
        "display_name": "Asymmetry Spectrogram — Anterior",
        "description": "Relative frontal asymmetry across 0–20 Hz: left vs right anterior electrodes.",
        "source_families": ["asymmetry"],
        "_spectrogram": True,
        "_name_must_contain": "ant",
        "units": "asymmetry index (\u22121 to +1)",
        "derivation": "Asymmetry spectrogram, 0\u201320 Hz, 0.5 Hz resolution, anterior electrode pairs.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "asymmetry_spectrogram_post",
        "display_name": "Asymmetry Spectrogram — Posterior",
        "description": "Relative posterior asymmetry across 0–20 Hz: left vs right posterior electrodes.",
        "source_families": ["asymmetry"],
        "_spectrogram": True,
        "_name_must_contain": "post",
        "units": "asymmetry index (\u22121 to +1)",
        "derivation": "Asymmetry spectrogram, 0\u201320 Hz, 0.5 Hz resolution, posterior electrode pairs.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "asymmetry_spectrogram_temp",
        "display_name": "Asymmetry Spectrogram — Temporal",
        "description": "Relative temporal asymmetry across 0–20 Hz: left vs right temporal electrodes.",
        "source_families": ["asymmetry"],
        "_spectrogram": True,
        "_name_must_contain": "temporal",
        "units": "asymmetry index (\u22121 to +1)",
        "derivation": "Asymmetry spectrogram, 0\u201320 Hz, 0.5 Hz resolution, temporal electrode pairs.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "asymmetry_spectrogram_parasag",
        "display_name": "Asymmetry Spectrogram — Parasagittal",
        "description": "Relative parasagittal asymmetry across 0–20 Hz: left vs right parasagittal electrodes.",
        "source_families": ["asymmetry"],
        "_spectrogram": True,
        "_name_must_contain": "parasag",
        "units": "asymmetry index (\u22121 to +1)",
        "derivation": "Asymmetry spectrogram, 0\u201320 Hz, 0.5 Hz resolution, parasagittal electrode pairs.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "reasi",
        "display_name": "REASI — Hemisphere (Delta Band)",
        "description": "Relative hemispheric EEG asymmetry index (REASI), delta band (0\u20135 Hz). Positive = right hemisphere dominant, negative = left hemisphere dominant. Single broadband summary of background laterality.",
        "source_families": ["asymmetry"],
        "_spectrogram": False,
        "_name_must_contain": "reasi",
        "units": "asymmetry index (\u22121 to +1)",
        "derivation": "REASI = (Left \u2212 Right) / (Left + Right) power, 0\u20135 Hz (delta band), hemisphere-level electrode average. Persyst asymmetry engine.",
        "filtering": "Artifact-excluded epochs removed.",
    },
    {
        "panel_id": "rhythmicity_spectrogram",
        "display_name": "Rhythmicity Spectrogram",
        "description": "P2D2 rhythmicity index across frequency bands over time — quantifies regularity/periodicity of EEG activity per derivation.",
        "source_families": ["rhythmicity"],
        "_spectrogram": True,
        "units": "rhythmicity index (0\u20131)",
        "derivation": "Persyst rhythmicity spectrogram, 1\u201325 Hz, 0.25 Hz resolution, 97 frequency bins per electrode derivation.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
    {
        "panel_id": "coherence_spectrogram",
        "display_name": "Coherence Spectrogram",
        "description": "Inter-hemispheric EEG coherence across frequency bands over time — measures synchrony between electrode pairs.",
        "source_families": ["coherence_spectrogram"],
        "_spectrogram": True,
        "units": "coherence (0\u20131)",
        "derivation": "Persyst coherence spectrogram, 0.5\u201332 Hz, 0.5 Hz resolution, 63 frequency bins per electrode pair.",
        "filtering": "Peak-preserving downsampling to 2000 time points for display.",
    },
]


_ELECTRODE_CHAIN_RE = _re.compile(r'[a-z]{1,3}\d{1,2}[a-z]{1,3}\d{1,2}')


def _match_panel_variables(
    panel_def: dict[str, Any],
    schema: list,
) -> list[str]:
    """Return common_names from *schema* that belong to this panel.

    Electrode-chain variants (e.g. adr_f3c3p3) and rolling-average display
    overlays (adr_avg_*) are excluded — only regional/hemisphere summaries shown.
    """
    families = set(panel_def["source_families"])
    region_filter = panel_def.get("_region")
    hemi_filter = panel_def.get("_hemisphere")
    is_spectrogram = panel_def.get("_spectrogram")
    exclude_fragments = panel_def.get("_exclude_name_fragments", [])
    name_must_contain = panel_def.get("_name_must_contain", "")

    seen: set[str] = set()
    matched: list[str] = []
    for e in schema:
        name = getattr(e, "common_name", "")
        if not name or e.family not in families:
            continue
        if region_filter and getattr(e, "region", "") != region_filter:
            continue
        if hemi_filter and getattr(e, "hemisphere", "") != hemi_filter:
            continue
        # For hemisphere-level spectrogram panels (fft_spectrogram_left/right), exclude
        # sub-regional variants (anterior, posterior) — those have a non-empty region attribute.
        if is_spectrogram is True and hemi_filter and getattr(e, "region", ""):
            continue
        # Distinguish spectrogram vs non-spectrogram asymmetry columns
        if is_spectrogram is True and "spectrogram" not in name:
            continue
        if is_spectrogram is False and "spectrogram" in name:
            continue
        # Exclude electrode-chain variants and rolling-average display overlays (avg64s, avg2m, etc.)
        if _ELECTRODE_CHAIN_RE.search(name) or "_avg_" in name or name.endswith("_avg") or _re.search(r'_avg\d', name):
            continue
        # Exclude panel-specific unwanted sub-columns (e.g. spike threshold/rate_display columns)
        if any(frag in name for frag in exclude_fragments):
            continue
        # Require name contains a specific substring (e.g. regional asymmetry panels)
        if name_must_contain and name_must_contain not in name:
            continue
        if name not in seen:
            seen.add(name)
            matched.append(name)

    if not is_spectrogram:
        return sorted(matched)

    # For spectrogram panels: strip per-frequency-bin suffixes and return
    # unique channel-group column prefixes (e.g. "fft_spec_left_hemisphere",
    # "asymmetry_spec_anterior"). This collapses 120 freq-bin entries into
    # 3–5 readable column-prefix names that match the actual data columns.
    _FREQ_SUFFIX = _re.compile(r'_[\d.]+(?:-[\d.]+)?hz$', _re.IGNORECASE)
    groups: dict[str, bool] = {}
    for name in matched:
        group = _FREQ_SUFFIX.sub("", name)
        groups[group] = True
    return sorted(groups)


def build_chart_metadata(
    schema: list | None = None,
    config: dict | None = None,
    engines: dict | None = None,
) -> list[dict[str, Any]]:
    """Map dashboard panel IDs to displayed variables, units, and derivation info.

    Args:
        schema: Column schema entries for the patient (filters variables to those present).
        config: Pipeline config dict (artifact thresholds, etc.) for filtering descriptions.
        engines: Engine configs from MMX for accurate cadence/window values.

    Returns:
        List of panel metadata dicts, one per dashboard panel.
    """
    panels: list[dict[str, Any]] = []
    for pdef in _PANEL_DEFS:
        primary_family = pdef["source_families"][0]
        cadence = get_family_cadence(primary_family, engines)
        window = get_engine_window(primary_family, engines)

        variables = _match_panel_variables(pdef, schema) if schema else []

        panel = {
            "panel_id": pdef["panel_id"],
            "display_name": pdef["display_name"],
            "description": pdef["description"],
            "source_families": pdef["source_families"],
            "variables": variables,
            "units": pdef["units"],
            "derivation": pdef["derivation"],
            "cadence_seconds": cadence,
            "window_seconds": window,
            "filtering": pdef["filtering"],
        }

        # Augment filtering description with config thresholds if available
        if config and pdef["panel_id"] == "artifact_intensity":
            mode = config.get("artifact_mode", "quality")
            thresh = config.get("artifact_quality_threshold")
            if thresh is not None:
                panel["filtering"] += f" Current: {mode} mode, threshold={thresh}."

        if config and pdef["panel_id"] == "seizure_probability":
            thresh = config.get("seizure_probability_threshold")
            if thresh is not None:
                panel["filtering"] += f" Current threshold={thresh}."

        panels.append(panel)

    return panels


def export_patient_wide(
    bin_summaries: dict[str, pd.DataFrame],
    qc_reports: dict[str, dict],
    output_path: Path,
    outcomes: pd.DataFrame | None = None,
) -> Path:
    """Export patient-level feature matrix (one row per patient).

    Suitable for: ML, clustering, logistic regression, random forests.

    Args:
        bin_summaries: {patient_id: bin_summary_df from time_binning}
        qc_reports: {patient_id: qc_report dict}
        output_path: path to write CSV
    """
    rows = []
    for pid, bins_df in bin_summaries.items():
        row: dict = {"patient_id": pid}

        # QC columns
        qc = qc_reports.get(pid, {})
        row["total_epochs"] = qc.get("total_epochs", 0)
        row["usable_epochs"] = qc.get("usable_epochs", 0)
        row["artifact_pct"] = qc.get("artifact_pct", 0.0)
        row["recording_duration_hours"] = qc.get("recording_duration_hours", 0.0)
        row["usable_hours"] = qc.get("usable_hours", 0.0)
        row["seizure_pct_of_total"] = qc.get("seizure_pct_of_total", 0.0)

        # Pivot bin data to wide: one column per variable per bin
        for _, bin_row in bins_df.iterrows():
            label = bin_row.get("bin_label", "")
            prefix = label.replace("-", "_").replace("h", "h_")
            for col in bins_df.columns:
                if col.endswith(("_median", "_mean", "_sd", "_iqr", "_min", "_max", "_n")):
                    wide_col = f"{col}_{prefix}".rstrip("_")
                    row[wide_col] = bin_row[col]
            row[f"n_effective_fft_{prefix}".rstrip("_")] = bin_row.get("n_effective_fft", 0)
            row[f"coverage_hours_{prefix}".rstrip("_")] = bin_row.get("coverage_hours", 0.0)

        rows.append(row)

    result = pd.DataFrame(rows)

    # Merge outcomes if provided
    if outcomes is not None and "patient_id" in outcomes.columns:
        result = result.merge(outcomes, on="patient_id", how="left")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return output_path


def export_patient_bins_long(
    bin_summaries: dict[str, pd.DataFrame],
    patient_info: dict[str, dict],
    output_path: Path,
) -> Path:
    """Export bin-level data in long format (one row per patient x bin x feature).

    Suitable for: mixed-effects models, repeated-measures ANOVA, GEE.
    """
    rows = []
    for pid, bins_df in bin_summaries.items():
        info = patient_info.get(pid, {})
        for _, bin_row in bins_df.iterrows():
            bin_label = bin_row["bin_label"]
            bin_start = bin_row["bin_start_hours"]
            bin_end = bin_row["bin_end_hours"]
            coverage = bin_row.get("coverage_hours", 0.0)
            # Extract feature names from columns ending in _median
            for col in bins_df.columns:
                if col.endswith("_median"):
                    feature = col[: -len("_median")]
                    n_effective, n_effective_basis = _feature_effective_n(bin_row, feature)
                    # Parse feature family/region/band from name
                    row = {
                        "patient_id": pid,
                        "time_bin": bin_label,
                        "bin_start_hours": bin_start,
                        "bin_end_hours": bin_end,
                        "feature_name": feature,
                        "median": bin_row.get(f"{feature}_median", np.nan),
                        "mean": bin_row.get(f"{feature}_mean", np.nan),
                        "sd": bin_row.get(f"{feature}_sd", np.nan),
                        "iqr": bin_row.get(f"{feature}_iqr", np.nan),
                        "min": bin_row.get(f"{feature}_min", np.nan),
                        "max": bin_row.get(f"{feature}_max", np.nan),
                        "n_observed": bin_row.get(f"{feature}_n_observed", bin_row.get(f"{feature}_n", 0)),
                        "n_effective": n_effective,
                        "n_effective_basis": n_effective_basis,
                        "coverage_hours": coverage,
                        # Patient-level covariates
                        "age_days": info.get("age_days"),
                        "sex": info.get("sex"),
                        "diagnosis_category": info.get("diagnosis_category"),
                    }
                    rows.append(row)

    result = pd.DataFrame(rows)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return output_path


def export_epochs_parquet(
    epoch_data: pd.DataFrame,
    output_path: Path,
    patient_id: str = "",
) -> Path:
    """Export full epoch-level data as Parquet.

    Suitable for: LSTM, transformer, CNN time-series models.
    """
    from qeeg.storage.parquet_io import save_epochs

    return save_epochs(epoch_data, output_path, patient_id=patient_id)


def export_patient_semi_long(
    bin_summaries: dict[str, pd.DataFrame],
    patient_info: dict[str, dict],
    output_path: Path,
    include_groups: list[str] | None = None,
    schema: list | None = None,
) -> Path:
    """Export semi-long format: 1 row per patient x bin, features as columns.

    This is what lme4/geepack expect: each row is one observation (patient x time),
    with features spread across columns rather than melted into rows.
    """
    rows = []
    for pid, bins_df in bin_summaries.items():
        info = patient_info.get(pid, {})
        if schema is not None:
            bins_df = _filter_bin_summary(bins_df, include_groups, schema)
        # Drop bins with no EEG data (no epochs fell in this time range)
        bins_with_data = bins_df[bins_df["missingness_flag"] != "no_data"] if "missingness_flag" in bins_df.columns else bins_df
        for _, bin_row in bins_with_data.iterrows():
            row: dict = {
                "patient_id": pid,
                "time_bin": bin_row["bin_label"],
                "bin_start_hours": bin_row["bin_start_hours"],
                "bin_end_hours": bin_row["bin_end_hours"],
                "coverage_hours": bin_row.get("coverage_hours", 0.0),
                "coverage_fraction": bin_row.get("coverage_fraction", 0.0),
                "bin_expected_hours": bin_row.get("bin_expected_hours", np.nan),
                "observed_wall_clock_hours": bin_row.get("observed_wall_clock_hours", np.nan),
                "artifact_clean_hours": bin_row.get("artifact_clean_hours", np.nan),
                "clean_fraction_of_observed": bin_row.get("clean_fraction_of_observed", np.nan),
                "clean_fraction_of_expected": bin_row.get("clean_fraction_of_expected", np.nan),
                "n_observed": bin_row.get("n_observed", 0),
                "n_effective_fft": bin_row.get("n_effective_fft", 0),
                "background_continuity_index": bin_row.get("background_continuity_index", np.nan),
                "missingness_flag": bin_row.get("missingness_flag", ""),
                # Patient-level covariates
                "age_days": info.get("age_days"),
                "sex": info.get("sex"),
                "diagnosis_category": info.get("diagnosis_category"),
            }

            # Extract all feature medians as individual columns
            for col in bins_df.columns:
                if col.endswith("_median"):
                    feature = col[: -len("_median")]
                    row[feature] = bin_row.get(col, np.nan)
                    # Also include log-transformed if available
                    log_col = f"{feature}_log_mean"
                    if log_col in bins_df.columns:
                        row[f"{feature}_log"] = bin_row.get(log_col, np.nan)
                    # Include n_independent for this feature
                    n_col = f"{feature}_n"
                    if n_col in bins_df.columns:
                        row[f"{feature}_n"] = bin_row.get(n_col, 0)
                    # Include trimmed mean if available
                    tm_col = f"{feature}_trimmed_mean"
                    if tm_col in bins_df.columns:
                        row[f"{feature}_trimmed"] = bin_row.get(tm_col, np.nan)
                    # Include CV if available
                    cv_col = f"{feature}_cv"
                    if cv_col in bins_df.columns:
                        row[f"{feature}_cv"] = bin_row.get(cv_col, np.nan)
                # Include slope columns (trajectory features)
                elif col.endswith("_slope"):
                    row[col] = bin_row.get(col, np.nan)

            rows.append(row)

    result = pd.DataFrame(rows)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return output_path


def _get_git_hash() -> str:
    """Try to get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def build_provenance(
    config: dict,
    persyst_version: str = "",
    source_files: list[str] | None = None,
    source_file_hashes: dict[str, str] | None = None,
    artifact_rejection_counts: dict[str, int] | None = None,
    column_mapping_version: str = "",
    mmx_fingerprint: str = "",
    mmx_engines_summary: dict[str, dict] | None = None,
    alignment_info: dict | None = None,
    mmx_file_hash: str | None = None,
    clinical_metadata_hash: str | None = None,
    corrections_hash: str | None = None,
    stage_row_counts: dict[str, int] | None = None,
    hash_strategy: str = "full_sha256",
    clinical_metadata: dict | None = None,
    eeg_corrections: dict | None = None,
    schema: list | None = None,
) -> dict:
    """Build comprehensive provenance metadata dict.

    *alignment_info* — optional dict describing ROSC alignment. Keys: ``time_reference``
    ("rosc" | "recording_start"), ``rosc_datetime``, ``hours_from_rosc_to_eeg``,
    ``is_aligned``, ``has_pre_rosc_data``, ``pre_rosc_hours``, ``alignment_warning``.
    When absent, exports still load but downstream code cannot tell whether
    ``bin_start_hours`` is ROSC-anchored or recording-start-anchored.

    *mmx_file_hash*, *clinical_metadata_hash*, *corrections_hash* — SHA-256 hashes
    of the auxiliary input files used to interpret the raw CSVs. ``None`` means
    the file was not available at export time (e.g. study has no corrections).
    *stage_row_counts* records row counts at each pipeline stage for audit.
    *hash_strategy* documents which hashing method produced the hash values
    ("full_sha256" is authoritative; "fingerprint_stat_head_tail" is the fast
    cache-keying fingerprint and should be flagged as provisional in audit
    bundles).
    *clinical_metadata* — the actual clinical metadata row for this patient
    (ROSC datetime, age-at-arrest, site, etc.) so reviewers can reconstruct
    the timing anchor without re-reading the study CSV.
    *eeg_corrections* — {dat_stem: correction_row} for every segment in this
    patient. Records what de-identified timing was applied.
    """
    prov = {
        "pipeline_version": PIPELINE_VERSION,
        "column_schema_version": COLUMN_SCHEMA_VERSION,
        "column_resolution": column_resolution_summary(schema),
        "git_commit": _get_git_hash(),
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "persyst_version": persyst_version,
        "source_files": source_files or [],
        "source_file_hashes": source_file_hashes or {},
        "hash_strategy": hash_strategy,
        "config": config,
        "artifact_rejection_counts": artifact_rejection_counts or {},
        "column_mapping_version": column_mapping_version,
        "mmx_file_hash": mmx_file_hash,
        "clinical_metadata_hash": clinical_metadata_hash,
        "corrections_hash": corrections_hash,
        "stage_row_counts": stage_row_counts or {},
        "clinical_metadata": clinical_metadata,
        "eeg_corrections": eeg_corrections or {},
    }
    if mmx_fingerprint:
        prov["mmx_fingerprint"] = mmx_fingerprint
    if mmx_engines_summary:
        prov["mmx_engines"] = mmx_engines_summary
    if alignment_info is not None:
        prov["alignment"] = alignment_info
    return prov


def build_alignment_info(time_info, alignment_result=None) -> dict:
    """Compose the ``alignment`` provenance block from pipeline outputs.

    *time_info* is the ``TimeAxisInfo`` from ``build_time_axis``; *alignment_result*
    is the ``AlignmentResult`` from ``check_rosc_alignment`` (may be ``None`` when
    the caller never had ROSC data).  Missing values become ``None`` / ``False``
    so the schema is stable across patients.
    """
    reference = getattr(time_info, "reference", "recording_start") if time_info else "recording_start"
    reference_time = getattr(time_info, "reference_time", None) if time_info else None
    info: dict = {
        "time_reference": reference,
        "reference_time": reference_time.isoformat() if reference_time is not None and hasattr(reference_time, "isoformat") else None,
        "is_aligned": False,
        "rosc_datetime": None,
        "hours_from_rosc_to_eeg": None,
        "has_pre_rosc_data": False,
        "pre_rosc_hours": 0.0,
        "alignment_warning": "",
    }
    if alignment_result is not None:
        rosc_time = getattr(alignment_result, "rosc_time", None)
        info["is_aligned"] = bool(getattr(alignment_result, "is_aligned", False))
        info["rosc_datetime"] = rosc_time.isoformat() if rosc_time is not None and hasattr(rosc_time, "isoformat") else None
        info["hours_from_rosc_to_eeg"] = getattr(alignment_result, "hours_from_rosc_to_eeg", None)
        info["has_pre_rosc_data"] = bool(getattr(alignment_result, "has_pre_rosc_data", False))
        info["pre_rosc_hours"] = float(getattr(alignment_result, "pre_rosc_hours", 0.0) or 0.0)
        info["alignment_warning"] = str(getattr(alignment_result, "warning", "") or "")
    return info


def export_metadata(
    output_dir: Path,
    config: dict,
    column_descriptions: dict[str, str],
    persyst_version: str = "",
    source_files: list[str] | None = None,
    source_file_hashes: dict[str, str] | None = None,
    artifact_rejection_counts: dict[str, int] | None = None,
    feature_stats: dict[str, dict] | None = None,
    missing_summary: dict[str, list[str]] | None = None,
) -> Path:
    """Write comprehensive provenance JSON for exports."""
    meta = build_provenance(
        config=config,
        persyst_version=persyst_version,
        source_files=source_files,
        source_file_hashes=source_file_hashes,
        artifact_rejection_counts=artifact_rejection_counts,
        schema=schema,
    )
    meta["column_descriptions"] = column_descriptions
    if feature_stats:
        meta["feature_scaling"] = feature_stats
    if missing_summary:
        meta["missing_data"] = missing_summary
    meta["missing_value_policy"] = {
        "canonical_exports": {
            "csv": "blank fields for missing values",
            "parquet": "typed null/NaN values",
        },
        "sentinel_codes_used": False,
        "notes": "Canonical exports preserve nullable numeric/string values rather than replacing them with legacy sentinel codes.",
    }
    meta["data_dictionary"] = build_data_dictionary()

    output_path = Path(output_dir) / "provenance.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(meta, indent=2, default=str))
    return output_path


def export_column_mapping(
    schema: list,
    output_path: Path,
) -> Path:
    """Export column mapping CSV: I-code -> common_name, family, hemisphere, etc."""
    rows = []
    for e in schema:
        rows.append({
            "i_code": e.code,
            "common_name": e.common_name or "",
            "family": e.family,
            "trend_name": e.trend_name,
            "hemisphere": e.hemisphere or "",
            "region": e.region or "",
            "electrode": e.electrode or "",
            "frequency_band": e.frequency_band or "",
            "freq_min_hz": e.freq_min_hz,
            "freq_max_hz": e.freq_max_hz,
        })
    df = pd.DataFrame(rows)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def build_research_package(
    patient_id: str,
    epochs: pd.DataFrame,
    bin_summary: pd.DataFrame,
    schema: list,
    config: dict,
    qc_dict: dict,
    seizure_dict: dict,
    persyst_version: str = "",
    source_files: list[str] | None = None,
    source_file_hashes: dict[str, str] | None = None,
    artifact_rejection_counts: dict[str, int] | None = None,
    col_map: dict[str, str] | None = None,
    mmx_fingerprint: str = "",
    mmx_engines_summary: dict | None = None,
    include_groups: list[str] | None = None,
    alignment_info: dict | None = None,
    mmx_file_hash: str | None = None,
    clinical_metadata_hash: str | None = None,
    corrections_hash: str | None = None,
    stage_row_counts: dict[str, int] | None = None,
    hash_strategy: str = "full_sha256",
    include_epoch_parquet: bool = True,
    clinical_metadata: dict | None = None,
    eeg_corrections: dict | None = None,
) -> io.BytesIO:
    """Build a ZIP research export package containing all export artifacts.

    Returns a BytesIO buffer containing the ZIP file.

    *include_groups* controls which column families appear in the bin_summary
    and semi-long outputs.  Default (None) includes core analysis only.
    Epoch-level Parquet is not exported; use the cache for deep-learning use.
    """
    # Apply family group filter once; all outputs share the filtered view.
    filtered_bins = _filter_bin_summary(bin_summary, include_groups, schema)
    data_dictionary_engines = _engines_from_summary(mmx_engines_summary)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Binned summary Parquet (replaces epoch-level Parquet)
        bin_pq = filtered_bins.copy()
        if "missingness_flag" in bin_pq.columns:
            bin_pq = bin_pq[bin_pq["missingness_flag"] != "no_data"]
        bin_pq.insert(0, "patient_id", patient_id)
        pq_buf = io.BytesIO()
        pq.write_table(
            pa.Table.from_pandas(bin_pq, preserve_index=False),
            pq_buf,
            compression="zstd",
        )
        pq_buf.seek(0)
        zf.writestr(f"{patient_id}_bin_summary.parquet", pq_buf.read())

        # 2. Bin summary CSV (with readable names, filtered)
        bin_df = filtered_bins.copy()
        rename: dict[str, str] = {}
        if col_map:
            for col in bin_df.columns:
                for suffix in _BIN_STAT_SUFFIXES:
                    if col.endswith(suffix):
                        base = col[: -len(suffix)]
                        if base in col_map:
                            rename[col] = f"{col_map[base]}{suffix}"
                        break
            if rename:
                bin_df = bin_df.rename(columns=rename)
        csv_buf = io.StringIO()
        # Drop bins with no EEG data
        if "missingness_flag" in bin_df.columns:
            bin_df = bin_df[bin_df["missingness_flag"] != "no_data"]
        bin_df.to_csv(csv_buf, index=False)
        zf.writestr(f"{patient_id}_bin_summary.csv", csv_buf.getvalue())

        # 3. Semi-long CSV (filtered)
        semi_buf = io.StringIO()
        bins_with_data = (
            filtered_bins[filtered_bins["missingness_flag"] != "no_data"]
            if "missingness_flag" in filtered_bins.columns
            else filtered_bins
        )
        semi_rows = []
        for _, row in bins_with_data.iterrows():
            sr: dict = {
                "patient_id": patient_id,
                "time_bin": row["bin_label"],
                "bin_start_hours": row["bin_start_hours"],
                "bin_end_hours": row["bin_end_hours"],
                "coverage_hours": row.get("coverage_hours", 0),
                "coverage_fraction": row.get("coverage_fraction", 0),
                "bin_expected_hours": row.get("bin_expected_hours", np.nan),
                "observed_wall_clock_hours": row.get("observed_wall_clock_hours", np.nan),
                "artifact_clean_hours": row.get("artifact_clean_hours", np.nan),
                "clean_fraction_of_observed": row.get("clean_fraction_of_observed", np.nan),
                "clean_fraction_of_expected": row.get("clean_fraction_of_expected", np.nan),
                "n_observed": row.get("n_observed", 0),
                "n_effective_fft": row.get("n_effective_fft", 0),
                "background_continuity_index": row.get("background_continuity_index", np.nan),
                "missingness_flag": row.get("missingness_flag", ""),
            }
            for col in filtered_bins.columns:
                if col.endswith("_median"):
                    feature = col[: -len("_median")]
                    readable = col_map.get(feature, feature) if col_map else feature
                    sr[readable] = row.get(col, np.nan)
                    log_col = f"{feature}_log_mean"
                    if log_col in filtered_bins.columns:
                        sr[f"{readable}_log"] = row.get(log_col, np.nan)
                elif col.endswith("_slope"):
                    feature = col[: -len("_slope")]
                    readable = col_map.get(feature, feature) if col_map else feature
                    sr[f"{readable}_slope"] = row.get(col, np.nan)
            semi_rows.append(sr)
        if semi_rows:
            pd.DataFrame(semi_rows).to_csv(semi_buf, index=False)
        zf.writestr(f"{patient_id}_semi_long.csv", semi_buf.getvalue())

        # 4. Provenance JSON with column descriptions
        provenance = build_provenance(
            config=config,
            persyst_version=persyst_version,
            source_files=source_files,
            source_file_hashes=source_file_hashes,
            artifact_rejection_counts=artifact_rejection_counts,
            mmx_fingerprint=mmx_fingerprint,
            mmx_engines_summary=mmx_engines_summary,
            alignment_info=alignment_info,
            mmx_file_hash=mmx_file_hash,
            clinical_metadata_hash=clinical_metadata_hash,
            corrections_hash=corrections_hash,
            stage_row_counts=stage_row_counts,
            hash_strategy=hash_strategy,
            clinical_metadata=clinical_metadata,
            eeg_corrections=eeg_corrections,
            schema=schema,
        )
        provenance["qc_summary"] = qc_dict
        provenance["seizure_summary"] = seizure_dict

        # Build column descriptions for all variables (raw + calculated)
        column_descriptions = {}

        # Raw Persyst columns from schema
        for e in schema:
            if e.common_name:
                column_descriptions[e.common_name] = f"Persyst I-code: {e.code}, family: {e.family}, hemisphere: {e.hemisphere or 'bilateral'}"

        # Calculated bin-level variables
        calculated_vars = {
            "bin_label": "Time bin identifier (e.g., '0-6h', '6-12h')",
            "bin_start_hours": "Start time of bin, hours from the reference event recorded in provenance.alignment.time_reference ('rosc' → hours from ROSC; 'recording_start' → hours from EEG start)",
            "bin_end_hours": "End time of bin, hours from the reference event recorded in provenance.alignment.time_reference",
            "coverage_hours": "Estimated artifact-clean EEG time support in bin (hours), derived from timestamp spacing.",
            "coverage_fraction": "Artifact-clean fraction of observed EEG time support (same value as clean_fraction_of_observed).",
            "bin_expected_hours": "Configured bin width in wall-clock hours.",
            "observed_wall_clock_hours": "Estimated observed EEG time support in the bin, derived from timestamp spacing with large gaps capped.",
            "artifact_clean_hours": "Estimated artifact-clean EEG time support in the bin.",
            "clean_fraction_of_observed": "artifact_clean_hours / observed_wall_clock_hours.",
            "clean_fraction_of_expected": "artifact_clean_hours / bin_expected_hours.",
            "n_total_epochs": "Total 1-second epochs in bin (including artifact)",
            "n_usable_epochs": "Number of 1-second epochs passing artifact threshold",
            "n_independent_obs": "Legacy effective independent observations field. Prefer per-feature n_observed, n_effective, and n_effective_basis in long exports.",
            "background_continuity_index": "Proportion of usable epochs with suppression below threshold; indicates continuous background activity",
            "missingness_flag": "Coverage/artifact heuristic: complete (>=95%), high_artifact (50-94%), moderate_artifact (10-49%), low_data (<10%), no_data (0%). Not an MCAR/MAR/MNAR missing-data mechanism.",
            "meets_minimum": "Binary: whether bin has ≥ minimum required coverage hours",
            "has_status_epilepticus": "Deprecated alias for status_epilepticus_screen_flag. Algorithmic screening flag from Persyst seizure trend output (>=30 min OR >=50% hourly burden OR repeated close onsets); not a clinically adjudicated ILAE diagnosis.",
            "status_epilepticus_screen_flag": "Algorithmic screening flag from Persyst seizure trend output (>=30 min OR >=50% hourly burden OR repeated close onsets); not a clinically adjudicated ILAE diagnosis.",
            "seizure_burden_pct": "Percentage of artifact-clean time containing seizure activity",
            "longest_seizure_minutes": "Duration of longest continuous seizure episode (minutes)",
            "time_to_first_seizure_hours": "Time from reference event (ROSC/recording start) to first seizure (hours)",
            "seizure_events": "Count of distinct seizure episodes (transitions from non-seizure to seizure)",
            "alpha_delta_ratio": "Ratio of alpha (8-13 Hz) to delta (1-4 Hz) band power",
            "theta_delta_ratio": "Ratio of theta (4-8 Hz) to delta (1-4 Hz) band power",
        }
        column_descriptions.update(calculated_vars)

        provenance["column_descriptions"] = column_descriptions
        provenance["missing_value_policy"] = {
            "canonical_exports": {
                "csv": "blank fields for missing values",
                "parquet": "typed null/NaN values",
            },
            "sentinel_codes_used": False,
            "notes": "Canonical exports preserve nullable values. If a legacy stats package requires sentinels, generate a compatibility export separately and document the codes.",
        }
        zf.writestr("provenance.json", json.dumps(provenance, indent=2, default=str))

        # 5. Data dictionary + column mapping CSV
        dict_csv = io.StringIO()
        data_dictionary_dataframe(schema, engines=data_dictionary_engines).to_csv(dict_csv, index=False)
        zf.writestr("data_dictionary.csv", dict_csv.getvalue())
        zf.writestr(
            "data_dictionary.json",
            json.dumps(build_data_dictionary(schema, engines=data_dictionary_engines), indent=2, default=str),
        )

        col_rows = []
        for e in schema:
            col_rows.append({
                "i_code": e.code,
                "common_name": e.common_name or "",
                "family": e.family,
                "trend_name": e.trend_name,
                "hemisphere": e.hemisphere or "",
                "region": e.region or "",
            })
        col_df = pd.DataFrame(col_rows)
        col_csv = io.StringIO()
        col_df.to_csv(col_csv, index=False)
        zf.writestr("column_mapping.csv", col_csv.getvalue())

        # 6. README
        readme = f"""# Research Export Package — {patient_id}
Generated: {datetime.now(timezone.utc).isoformat()}
Pipeline version: {PIPELINE_VERSION}

## Contents

| File | Description |
|------|-------------|
| `{patient_id}_bin_summary.parquet` | Binned summary statistics (Parquet, zstd compression) — preferred for R/Python |
| `{patient_id}_bin_summary.csv` | Time-binned summary statistics (median, mean, SD, IQR, trimmed mean, CV, slopes) |
| `{patient_id}_semi_long.csv` | Semi-long format: 1 row per time bin, features as columns (for lme4/geepack) |
| `{patient_id}_epochs.parquet` | Epoch-level features + QC flags for independent recomputation |
| `provenance.json` | Full processing provenance (pipeline version, config, library versions, Persyst version, source/MMX/clinical/corrections hashes, stage row counts) |
| `data_dictionary.csv` | Machine-readable codebook: variable names, types, categories, units, derivations |
| `data_dictionary.json` | Same codebook in JSON for programmatic access |
| `column_mapping.csv` | I-code to human-readable name mapping with family, hemisphere, region |
| `MANIFEST.sha256` | Per-file SHA-256 digests of every other member of this package |
| `README.md` | This file |

---

## Quick Start — Load Data in 3 Lines

### R
```r
library(arrow)
dat <- read_parquet("{patient_id}_bin_summary.parquet")  # or: read_csv("{patient_id}_semi_long.csv")
str(dat)
```

### Python
```python
import pandas as pd
dat = pd.read_parquet("{patient_id}_bin_summary.parquet")  # or: pd.read_csv("{patient_id}_semi_long.csv")
dat.info()
```

### Stata
```stata
import delimited "{patient_id}_semi_long.csv", clear
describe
```

---

## Detailed Import Guides

### R / RStudio

#### Loading data
```r
library(arrow)
library(readr)
library(jsonlite)
library(dplyr)

# --- Parquet (preferred: preserves types, categoricals, nulls) ---
bins_pq <- read_parquet("{patient_id}_bin_summary.parquet")
cat("Schema:\\n"); print(schema(bins_pq))

# --- CSV fallback ---
semi_long <- read_csv("{patient_id}_semi_long.csv",
                       show_col_types = FALSE)
bins <- read_csv("{patient_id}_bin_summary.csv",
                  show_col_types = FALSE)

# --- Metadata ---
provenance <- fromJSON("provenance.json")
codebook   <- fromJSON("data_dictionary.json")

# Inspect codebook
codebook_df <- read_csv("data_dictionary.csv", show_col_types = FALSE)
head(codebook_df[, c("variable_name", "label", "data_type", "unit")])
```

#### Label variables from codebook
```r
# Create a named vector of labels from the codebook
labels <- setNames(codebook_df$label, codebook_df$variable_name)
# Apply to matching columns
for (v in intersect(names(semi_long), names(labels))) {{
  attr(semi_long[[v]], "label") <- labels[[v]]
}}
```

#### Mixed-effects model (lme4)
```r
library(lme4)

# Semi-long format has 1 row per patient x time bin, features as columns.
# Example: FFT delta anterior power across time bins
mod <- lmer(fft_delta_anterior ~ bin_start_hours + (1 | patient_id),
            data = semi_long,
            REML = TRUE)
summary(mod)
confint(mod)

# With log-transformed outcome (if available):
# mod_log <- lmer(fft_delta_anterior_log ~ bin_start_hours + (1 | patient_id),
#                 data = semi_long, REML = TRUE)
```

#### GEE model (geepack)
```r
library(geepack)

# Sort by patient and time (required for GEE)
semi_long <- semi_long[order(semi_long$patient_id, semi_long$bin_start_hours), ]

# Exchangeable correlation within patient
gee_mod <- geeglm(fft_delta_anterior ~ bin_start_hours,
                   id = patient_id,
                   data = semi_long,
                   family = gaussian,
                   corstr = "exchangeable")
summary(gee_mod)
```

### Python (pandas + pyarrow)

```python
import pandas as pd
import pyarrow.parquet as pq
import json

# --- Load data ---
epochs = pd.read_parquet("{patient_id}_epochs.parquet")
semi_long = pd.read_csv("{patient_id}_semi_long.csv")
bins = pd.read_csv("{patient_id}_bin_summary.csv")

# --- Inspect Parquet metadata (pipeline version, codebook hash, etc.) ---
pf = pq.read_metadata("{patient_id}_epochs.parquet")
for key in pf.schema.to_arrow_schema().metadata:
    print(key.decode(), "=", pf.schema.to_arrow_schema().metadata[key].decode()[:80])

# --- Load provenance and codebook ---
with open("provenance.json") as f:
    provenance = json.load(f)
with open("data_dictionary.json") as f:
    codebook = json.load(f)

# Programmatic codebook access
codebook_df = pd.DataFrame(codebook)
print(codebook_df[["variable_name", "label", "data_type", "unit"]].head(10))

# --- Use codebook to label columns ---
label_map = codebook_df.set_index("variable_name")["label"].to_dict()
for col in semi_long.columns:
    if col in label_map:
        semi_long[col].attrs["label"] = label_map[col]
```

#### Mixed-effects model (statsmodels)
```python
import statsmodels.formula.api as smf

# Linear mixed-effects model: random intercept per patient
me = smf.mixedlm("fft_delta_anterior ~ bin_start_hours", semi_long,
                  groups=semi_long["patient_id"])
me_fit = me.fit()
print(me_fit.summary())
```

#### GEE model (statsmodels)
```python
import statsmodels.api as sm

gee = sm.GEE.from_formula(
    "fft_delta_anterior ~ bin_start_hours",
    groups="patient_id", data=semi_long,
    family=sm.families.Gaussian(),
    cov_struct=sm.cov_struct.Exchangeable(),
)
gee_fit = gee.fit()
print(gee_fit.summary())
```

### Stata

```stata
* --- CSV import ---
import delimited "{patient_id}_semi_long.csv", clear
describe
summarize

* --- Parquet import (Stata 18+ via Python bridge) ---
* Requires: python set exec /path/to/python
frames create parquet_data
frames change parquet_data
python:
import pandas as pd
df = pd.read_parquet("{patient_id}_epochs.parquet")
from sfi import Data, Macro
Data.setObsTotal(len(df))
for i, col in enumerate(df.columns):
    try:
        Data.addVarFloat(col)
        Data.store(col, None, df[col].values.tolist())
    except:
        Data.addVarStr(col, max(df[col].astype(str).str.len().max(), 1))
        Data.store(col, None, df[col].astype(str).values.tolist())
end
frames change default

* --- Alternative: haven (R) to .dta ---
* In R: haven::write_dta(semi_long, "{patient_id}_semi_long.dta")
* Then in Stata: use "{patient_id}_semi_long.dta", clear

* --- Encode categoricals from codebook ---
* missingness_flag: complete=1, high_artifact=2, moderate_artifact=3, low_data=4, no_data=5
encode missingness_flag, gen(missingness_cat)
label define miss_lbl 1 "complete" 2 "high_artifact" 3 "moderate_artifact" 4 "low_data" 5 "no_data"
label values missingness_cat miss_lbl

* --- Mixed-effects model ---
mixed fft_delta_anterior bin_start_hours || patient_id:
estimates store m1
```

---

## Data Format Notes

- **Semi-long format**: 1 row per time bin, features as columns. This is the expected input
  for `lme4::lmer()`, `geepack::geeglm()`, and Stata `mixed`.
- **Log-transformed columns** (suffix `_log`): geometric means of spectral power (log-normal distribution).
- **Slope columns** (suffix `_slope`): linear regression slope of median values across bins (rate of change per hour).
- **`n_effective_fft`**: legacy cadence-adjusted independent observation count for FFT-family features.
  Prefer per-feature `n_effective` and `n_effective_basis`, which can reflect the specific MMX engine cadence for each instrument family.
- **`coverage_fraction`**: artifact-clean fraction of observed timestamp support; same as `clean_fraction_of_observed`.
- **`clean_fraction_of_expected`**: artifact-clean timestamp support divided by configured bin width; this drives missingness buckets.
- **`background_continuity_index`**: proportion of usable epochs with suppression below threshold.
- **`missingness_flag`**: `complete` (>=95%), `high_artifact` (50-94%), `moderate_artifact` (10-49%),
  `low_data` (<10%), `no_data` (0%). These are coverage heuristics, not MCAR/MAR/MNAR tests.
- **Parquet categorical columns**: `missingness_flag` and `n_effective_basis` are stored as ordered
  categoricals; `meets_minimum`, `has_status_epilepticus`, and `status_epilepticus_screen_flag` as boolean categoricals.
  R `arrow::read_parquet()` reads these as factors automatically.

## Reproducibility

The Parquet file embeds a `codebook_hash` in its schema metadata — a SHA-256 digest of the
structural data dictionary at export time. To verify that two exports used the same variable
definitions, compare their codebook hashes:

```python
import pyarrow.parquet as pq
meta = pq.read_schema("{patient_id}_epochs.parquet").metadata
print("codebook_hash:", meta[b"codebook_hash"].decode())
```

If the hash differs between exports, the data dictionary structure changed (new variables,
renamed columns, or modified categories). Re-export the earlier dataset with the current
pipeline version before pooling.
"""
        zf.writestr("README.md", readme)

        # 7. Epoch-level parquet (per research package README promise)
        if include_epoch_parquet and epochs is not None and not epochs.empty:
            ep_buf = io.BytesIO()
            try:
                ep_pq = epochs.copy()
                if "patient_id" not in ep_pq.columns:
                    ep_pq.insert(0, "patient_id", patient_id)
                pq.write_table(
                    pa.Table.from_pandas(ep_pq, preserve_index=False),
                    ep_buf,
                    compression="zstd",
                )
                ep_buf.seek(0)
                zf.writestr(f"{patient_id}_epochs.parquet", ep_buf.read())
            except Exception as exc:
                log.warning("Could not serialize epochs.parquet for %s: %s", patient_id, exc)

        # 8. MANIFEST.sha256 — per-member SHA-256 of every other file in the zip.
        # Written last so it records every other member. Not self-referential.
        import hashlib as _hashlib
        manifest_lines = []
        for name in zf.namelist():
            data = zf.read(name)
            member_hash = _hashlib.sha256(data).hexdigest()
            manifest_lines.append(f"{member_hash}  {name}")
        zf.writestr("MANIFEST.sha256", "\n".join(manifest_lines) + "\n")

    buf.seek(0)
    return buf


log = logging.getLogger(__name__)


def _compute_codebook_hash(schema: list | None = None) -> str:
    """SHA-256 of the structural data dictionary for reproducibility tracking."""
    entries = build_data_dictionary(schema=schema, engines=None)
    canonical = json.dumps(entries, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def export_cohort_semi_long(
    results: dict[str, Any],
    col_map: dict[str, str] | None = None,
    include_groups: list[str] | None = None,
    schema_by_patient: dict[str, list] | None = None,
) -> pd.DataFrame:
    """Concatenate semi-long frames across patients into a single tidy table.

    One row per patient × time-bin with ``patient_id`` as the first column.
    This is the "one file for R" shape the user has asked for: load once with
    ``readr::read_csv()`` and pass directly to ``lme4`` or ``geepack``.

    *results* — ``{patient_id: PatientResult}``
    *col_map* — optional I-code → common-name mapping applied uniformly.
    *include_groups* — family filter (same semantics as ``build_research_package``).
    *schema_by_patient* — optional per-patient schema override; otherwise read from the result.
    """
    rows: list[dict] = []
    for pid, result in results.items():
        schema_for_patient = (schema_by_patient or {}).get(pid, getattr(result, "schema", []))
        bin_summary = getattr(result, "bin_summary", None)
        if bin_summary is None or bin_summary.empty:
            continue
        filtered = _filter_bin_summary(bin_summary, include_groups, schema_for_patient)
        bins_with_data = (
            filtered[filtered["missingness_flag"] != "no_data"]
            if "missingness_flag" in filtered.columns
            else filtered
        )
        align = build_alignment_info(
            getattr(result, "time_info", None),
            getattr(result, "alignment", None),
        )
        for _, row in bins_with_data.iterrows():
            sr: dict = {
                "patient_id": pid,
                "time_reference": align["time_reference"],
                "rosc_aligned": align["is_aligned"],
                "time_bin": row["bin_label"],
                "bin_start_hours": row["bin_start_hours"],
                "bin_end_hours": row["bin_end_hours"],
                "coverage_hours": row.get("coverage_hours", 0),
                "coverage_fraction": row.get("coverage_fraction", 0),
                "bin_expected_hours": row.get("bin_expected_hours", np.nan),
                "observed_wall_clock_hours": row.get("observed_wall_clock_hours", np.nan),
                "artifact_clean_hours": row.get("artifact_clean_hours", np.nan),
                "clean_fraction_of_observed": row.get("clean_fraction_of_observed", np.nan),
                "clean_fraction_of_expected": row.get("clean_fraction_of_expected", np.nan),
                "n_observed": row.get("n_observed", 0),
                "n_effective_fft": row.get("n_effective_fft", 0),
                "background_continuity_index": row.get("background_continuity_index", np.nan),
                "missingness_flag": row.get("missingness_flag", ""),
            }
            for col in filtered.columns:
                if col.endswith("_median"):
                    feature = col[: -len("_median")]
                    readable = col_map.get(feature, feature) if col_map else feature
                    sr[readable] = row.get(col, np.nan)
                    log_col = f"{feature}_log_mean"
                    if log_col in filtered.columns:
                        sr[f"{readable}_log"] = row.get(log_col, np.nan)
                elif col.endswith("_slope"):
                    feature = col[: -len("_slope")]
                    readable = col_map.get(feature, feature) if col_map else feature
                    sr[f"{readable}_slope"] = row.get(col, np.nan)
            rows.append(sr)
    return pd.DataFrame(rows)


def export_cohort_dataset(
    results: dict[str, Any],
    output_dir: Path,
    config: dict | None = None,
    mmx_identity: dict | None = None,
) -> Path:
    """Write a partitioned Parquet dataset with Arrow sidecar files and manifest.

    Args:
        results: {patient_id: PatientResult} dict of processed patients.
        output_dir: Directory to write the partitioned dataset into.
        config: Processing config dict for the manifest.
        mmx_identity: {study_name, fingerprint} if MMX was used.

    Returns:
        Path to the output directory.
    """
    from qeeg.storage.parquet_io import _prepare_dataframe_for_parquet, _merge_metadata
    from qeeg.storage.result_cache import CACHE_SCHEMA_VERSION

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    schemas: list[pa.Schema] = []
    parquet_paths: list[str] = []
    patient_recordings: dict[str, list[str]] = {}

    for patient_id, result in results.items():
        # Write per-patient Parquet into partition directory
        part_dir = output_dir / f"patient_id={patient_id}"
        part_dir.mkdir(parents=True, exist_ok=True)
        parquet_file = part_dir / "data.parquet"

        prepared, metadata = _prepare_dataframe_for_parquet(
            result.epochs, patient_id=patient_id,
        )
        metadata["codebook_hash"] = _compute_codebook_hash()
        table = pa.Table.from_pandas(prepared, preserve_index=False)
        table = table.replace_schema_metadata(
            _merge_metadata(table.schema.metadata, metadata),
        )

        pq.write_table(
            table, parquet_file,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
            data_page_version="2.0",
            version="2.6",
        )

        schemas.append(table.schema.remove_metadata())
        rel_path = f"patient_id={patient_id}/data.parquet"
        parquet_paths.append(rel_path)

        # Record source files for manifest
        meta = result.parsed.metadata
        if isinstance(meta, dict):
            src = meta.get("source_path", "")
        else:
            src = getattr(meta, "source_path", "") or ""
        patient_recordings[patient_id] = [str(src)] if src else []

        log.info("Wrote cohort partition: %s", rel_path)

    # Unify schemas and write Arrow sidecar files
    if schemas:
        unified = pa.unify_schemas(schemas, promote_options="permissive")
        # _common_metadata: schema only (no row groups)
        pq.write_metadata(unified, output_dir / "_common_metadata")
        # _metadata: references all row groups in all files
        metadata_collector: list[pq.FileMetaData] = []
        for rel_path in parquet_paths:
            file_meta = pq.read_metadata(output_dir / rel_path)
            file_meta.set_file_path(rel_path)
            metadata_collector.append(file_meta)
        if metadata_collector:
            merged = metadata_collector[0]
            for m in metadata_collector[1:]:
                merged.append_row_groups(m)
            merged.write_metadata_file(output_dir / "_metadata")

    # Write per-patient bin_summary.csv
    patient_summaries: list[dict] = []
    for patient_id, result in results.items():
        part_dir = output_dir / f"patient_id={patient_id}"
        csv_buf = io.StringIO()
        bs = result.bin_summary
        bs_export = bs[bs["missingness_flag"] != "no_data"] if "missingness_flag" in bs.columns else bs
        bs_export.to_csv(csv_buf, index=False)
        (part_dir / "bin_summary.csv").write_text(csv_buf.getvalue(), encoding="utf-8")

        n_epochs = len(result.epochs)
        duration_hours = 0.0
        if "_hours_relative" in result.epochs.columns and n_epochs > 0:
            duration_hours = float(
                result.epochs["_hours_relative"].iloc[-1]
                - result.epochs["_hours_relative"].iloc[0]
            )

        patient_summaries.append({
            "patient_id": patient_id,
            "n_epochs": n_epochs,
            "duration_hours": round(duration_hours, 2),
            "has_corrections": patient_id in patient_recordings and bool(patient_recordings[patient_id]),
            "has_mmx": mmx_identity is not None,
            "alignment": build_alignment_info(
                getattr(result, "time_info", None),
                getattr(result, "alignment", None),
            ),
        })

    # Generate manifest.json
    manifest = {
        "format": "hive_partitioned_parquet",
        "parquet_files": parquet_paths,
        "schema_version": CACHE_SCHEMA_VERSION,
        "codebook_hash": _compute_codebook_hash(),
        "mmx_identity": mmx_identity,
        "processing_config": config or {},
        "patient_recordings": patient_recordings,
        "patients": patient_summaries,
        "patient_count": len(results),
        "n_patients": len(results),
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_version": PIPELINE_VERSION,
        "column_schema_version": COLUMN_SCHEMA_VERSION,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    # Generate cohort README
    cohort_readme = _build_cohort_readme(len(results), parquet_paths)
    (output_dir / "cohort_README.md").write_text(cohort_readme)

    log.info(
        "Cohort dataset exported: %d patients, %d files",
        len(results), len(parquet_paths),
    )
    return output_dir


def _build_cohort_readme(n_patients: int, parquet_paths: list[str]) -> str:
    """Generate a README for the cohort partitioned Parquet dataset."""
    return f"""# Cohort Dataset — Partitioned Parquet Export
Generated: {datetime.now(timezone.utc).isoformat()}
Pipeline version: {PIPELINE_VERSION}
Patients: {n_patients}

This directory contains a Hive-partitioned Parquet dataset with one partition per
patient (`patient_id=<id>/data.parquet`). Arrow sidecar files (`_common_metadata`,
`_metadata`) provide a unified schema for the entire dataset.

## Quick Start

### R (arrow)
```r
library(arrow)
ds <- open_dataset("{str(Path('.'))}", format = "parquet", partitioning = "hive")
cohort <- ds |> collect()
str(cohort)
# Filter to one patient:
one_pt <- ds |> filter(patient_id == "3848") |> collect()
```

### Python (pyarrow)
```python
import pyarrow.dataset as ds
dataset = ds.dataset(".", format="parquet", partitioning="hive")
table = dataset.to_table()
df = table.to_pandas()
# Filter to one patient:
one_pt = dataset.to_table(filter=ds.field("patient_id") == "3848").to_pandas()
```

### Python (pandas)
```python
import pandas as pd
df = pd.read_parquet(".", engine="pyarrow")
```

## Manifest
See `manifest.json` for:
- List of all patient Parquet file paths
- Schema version and codebook hash for reproducibility
- MMX configuration identity (if used)
- Processing configuration
- Patient-to-recording mapping

## Notes
- Each patient partition contains epoch-level data (1-second rows).
- Column names are cleaned for R/Python/Stata compatibility (lowercase, no spaces).
- Missing values are native null/NaN — no sentinel codes.
- The `_common_metadata` sidecar provides the unified schema across all patients.
"""
