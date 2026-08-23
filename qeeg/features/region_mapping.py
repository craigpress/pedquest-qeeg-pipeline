from __future__ import annotations

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _sides_contributing(left: pd.Series, right: pd.Series) -> pd.Series:
    """Count how many hemispheres contributed a non-null value for each epoch."""
    return pd.Series(
        (left.notna().astype(int) + right.notna().astype(int)).values,
        index=left.index,
    )


def _nan_tolerant_bilateral_mean(left: pd.Series, right: pd.Series) -> pd.Series:
    """Average left/right values while keeping all-missing rows as NaN."""
    stacked = np.column_stack([left.values, right.values])
    valid = ~np.isnan(stacked)
    counts = valid.sum(axis=1)
    totals = np.nansum(stacked, axis=1)
    mean = np.full(len(stacked), np.nan, dtype=float)
    np.divide(totals, counts, out=mean, where=counts > 0)
    return pd.Series(mean, index=left.index)


def compute_anterior(
    left_anterior: pd.Series,
    right_anterior: pd.Series,
    require_bilateral: bool = True,
) -> pd.Series:
    """Compute bilateral Anterior as the mean of Left and Right Anterior.

    Default (``require_bilateral=True``) returns NaN whenever one hemisphere
    is missing — unilateral survivor values are not treated as bilateral
    physiology. PedQuEST/POCCA decision: bilateral features must require
    both sides for publication-grade analysis.

    Set ``require_bilateral=False`` to fall back to the legacy NaN-tolerant
    mean (kept for diagnostic exploration only). The
    ``fft_{band}_{region}_sides_contributing`` companion column always
    records the per-epoch contribution count regardless of this flag.
    """
    mean = _nan_tolerant_bilateral_mean(left_anterior, right_anterior)
    if require_bilateral:
        both = left_anterior.notna().values & right_anterior.notna().values
        mean = mean.where(both, np.nan)
    return mean


def compute_posterior(
    left_posterior: pd.Series,
    right_posterior: pd.Series,
    require_bilateral: bool = True,
) -> pd.Series:
    """Compute bilateral Posterior as the mean of Left and Right Posterior.

    Default (``require_bilateral=True``) returns NaN when one hemisphere
    is missing. See ``compute_anterior`` for the full rationale."""
    mean = _nan_tolerant_bilateral_mean(left_posterior, right_posterior)
    if require_bilateral:
        both = left_posterior.notna().values & right_posterior.notna().values
        mean = mean.where(both, np.nan)
    return mean


def compute_regional_features(
    df: pd.DataFrame,
    fft_columns: dict[str, dict[str, str]],
    bands: list[str] | None = None,
    require_bilateral: bool = True,
) -> pd.DataFrame:
    """Compute bilateral Anterior/Posterior features from Left/Right columns.

    Args:
        df: DataFrame with epoch data
        fft_columns: Nested dict from column_mapper.get_fft_power_columns()
                     {band: {region: code}}
        bands: Which bands to compute (default: all in fft_columns)
        require_bilateral: when True, bilateral features return NaN unless
            both hemispheres contributed a value.

    Returns:
        DataFrame with new columns: ``fft_{band}_anterior``, ``fft_{band}_posterior``,
        and side-contribution counts ``fft_{band}_anterior_sides_contributing``,
        ``fft_{band}_posterior_sides_contributing`` (values 0/1/2 per epoch).

    Persyst-native precedence: when the MMX already emits a native Anterior /
    Posterior channel power (V8+ ``fft_{band}_anterior`` is present in ``df``),
    the computed bilateral aggregate is skipped — the native value is the single
    source of truth. Older exports without native regional channels still get
    the computed bilateral mean.
    """
    if bands is None:
        bands = list(fft_columns.keys())

    result = pd.DataFrame(index=df.index)

    for band in bands:
        regions = fft_columns.get(band, {})
        la = regions.get("Left Anterior")
        ra = regions.get("Right Anterior")
        lp = regions.get("Left Posterior")
        rp = regions.get("Right Posterior")

        native_ant = f"fft_{band}_anterior"
        if native_ant in df.columns:
            logger.debug("Using Persyst-native %s; skipping computed bilateral aggregate", native_ant)
        elif la and ra and la in df.columns and ra in df.columns:
            result[native_ant] = compute_anterior(
                df[la], df[ra], require_bilateral=require_bilateral,
            )
            result[f"fft_{band}_anterior_sides_contributing"] = _sides_contributing(
                df[la], df[ra],
            )
        else:
            logger.debug("Skipping fft_%s_anterior: missing Left/Right Anterior columns", band)

        native_post = f"fft_{band}_posterior"
        if native_post in df.columns:
            logger.debug("Using Persyst-native %s; skipping computed bilateral aggregate", native_post)
        elif lp and rp and lp in df.columns and rp in df.columns:
            result[native_post] = compute_posterior(
                df[lp], df[rp], require_bilateral=require_bilateral,
            )
            result[f"fft_{band}_posterior_sides_contributing"] = _sides_contributing(
                df[lp], df[rp],
            )
        else:
            logger.debug("Skipping fft_%s_posterior: missing Left/Right Posterior columns", band)

    return result
