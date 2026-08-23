from __future__ import annotations
import pandas as pd
import numpy as np

from typing import TYPE_CHECKING

from qeeg.constants import FFT_UPDATE_INTERVAL
from qeeg.ingestion.cadence import get_family_cadence

if TYPE_CHECKING:
    from qeeg.ingestion.mmx_parser import EngineConfig


def compute_total_power(*bands: pd.Series) -> pd.Series:
    """Sum power across all provided frequency bands.

    Pass any number of Series/arrays. Do not assume fixed delta/theta/alpha/beta.
    """
    if not bands:
        raise ValueError("At least one frequency band required")
    result = bands[0].copy()
    for b in bands[1:]:
        result = result + b
    return result


def compute_relative_power(band_power: pd.Series, total_power: pd.Series) -> pd.Series:
    """Relative power = band / total. Returns NaN where total is 0."""
    return band_power / total_power.replace(0, np.nan)


def compute_band_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Band ratio (e.g., alpha/delta). Returns NaN where denominator is 0."""
    return numerator / denominator.replace(0, np.nan)


def compute_log_band_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Log10(num/denom). Symmetric around 0, approximately normal.

    Clips both to 1e-6 to avoid log(0). Values:
    - 0 means equal power
    - positive means numerator dominates
    - negative means denominator dominates
    """
    safe_num = numerator.clip(lower=1e-6)
    safe_den = denominator.clip(lower=1e-6)
    return np.log10(safe_num / safe_den)


def compute_all_derived(df: pd.DataFrame, region: str) -> pd.DataFrame:
    """Compute all derived features for a region (anterior or posterior).

    Expects columns: fft_delta_{region}, fft_theta_{region}, fft_alpha_{region}, fft_beta_{region}

    Produces:
    - total_power_{region}
    - rel_delta_{region}, rel_theta_{region}, rel_alpha_{region}, rel_beta_{region}
    - theta_delta_ratio_{region}, alpha_delta_ratio_{region}
    - log_theta_delta_ratio_{region}, log_alpha_delta_ratio_{region}

    Persyst-native precedence: relative-power columns (``rel_{band}_{region}``)
    are skipped when a same-named Persyst-native value is already present
    (V8+ emits ``FFT PowerRatio, {band}/1-30 Hz, {region}``). Note the two are
    computed differently — the native denominator is the 1-30 Hz broadband total,
    while the computed fallback uses the δ+θ+α+β band-sum. The native value wins
    when available; older exports fall back to the computed band-sum.
    """
    delta = df.get(f"fft_delta_{region}")
    theta = df.get(f"fft_theta_{region}")
    alpha = df.get(f"fft_alpha_{region}")
    beta = df.get(f"fft_beta_{region}")

    if delta is None or theta is None or alpha is None or beta is None:
        return pd.DataFrame(index=df.index)

    result = pd.DataFrame(index=df.index)
    total = compute_total_power(delta, theta, alpha, beta)
    result[f"total_power_{region}"] = total
    # Relative power: skip any band whose Persyst-native column already exists.
    for band, series in (("delta", delta), ("theta", theta), ("alpha", alpha), ("beta", beta)):
        name = f"rel_{band}_{region}"
        if name in df.columns:
            continue
        result[name] = compute_relative_power(series, total)
    result[f"theta_delta_ratio_{region}"] = compute_band_ratio(theta, delta)
    result[f"alpha_delta_ratio_{region}"] = compute_band_ratio(alpha, delta)
    # Log-transformed ratios (symmetric, ~normal for parametric models)
    result[f"log_theta_delta_ratio_{region}"] = compute_log_band_ratio(theta, delta)
    result[f"log_alpha_delta_ratio_{region}"] = compute_log_band_ratio(alpha, delta)

    return result


def downsample_to_independent(df: pd.DataFrame, columns: list[str],
                               interval: int = 8) -> pd.DataFrame:
    """Downsample columns that update at a slower rate (e.g., FFT every 8 seconds).

    Detects value transitions and keeps only the first row of each constant block.
    Falls back to fixed stride when no transition is detected within `interval` rows.
    """
    if not columns or interval <= 1:
        return df

    existing = [c for c in columns if c in df.columns]
    if not existing:
        return df

    df = df.copy()
    df["_is_independent_fft"] = get_independent_mask(df, existing, interval)
    return df


def get_independent_mask(
    df: pd.DataFrame,
    fft_columns: list[str],
    interval: int = FFT_UPDATE_INTERVAL,
    engines: dict[str, "EngineConfig"] | None = None,
) -> pd.Series:
    """Return boolean mask where True = independent FFT observation.

    Uses transition detection (value changes in FFT columns) with a fixed-interval
    fallback for constant-value epochs (common in suppressed/isoelectric EEG).
    NaN-aware: NaN→NaN transitions are NOT counted as changes.

    If engines are provided, the interval is derived from the MMX file's
    FFTEngine01 cadence via get_family_cadence() instead of the default.
    """
    if engines is not None:
        interval = get_family_cadence("fft_power", engines)
    if not fft_columns:
        return pd.Series(True, index=df.index)

    existing = [c for c in fft_columns if c in df.columns]
    if not existing:
        return pd.Series(True, index=df.index)

    # An empty frame reaches here when upstream trimming removes every row — e.g.
    # a ROSC time that postdates the whole recording, which happens with
    # de-identified exports whose dates have not been corrected. `changed.iloc[0]`
    # would raise "iloc cannot enlarge its target object"; return the empty mask
    # and let the caller report the real problem.
    if df.empty:
        return pd.Series(dtype=bool, index=df.index)

    shifted = df[existing].shift(1)
    # NaN-aware comparison: NaN != NaN should NOT be a transition
    changed = (
        (df[existing] != shifted) & df[existing].notna() & shifted.notna()
    ).any(axis=1)
    changed.iloc[0] = True  # First row is always independent

    # Fixed-interval fallback: if no transition detected within `interval` rows,
    # force an independent observation. This handles constant-value epochs
    # (burst-suppression, isoelectric) where FFT values genuinely don't change.
    mask = changed.values.copy()
    last_true = 0
    for i in range(1, len(mask)):
        if mask[i]:
            last_true = i
        elif (i - last_true) >= interval:
            mask[i] = True
            last_true = i

    return pd.Series(mask, index=df.index)
