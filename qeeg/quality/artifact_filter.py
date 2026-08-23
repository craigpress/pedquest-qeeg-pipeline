from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass

@dataclass
class FilterResult:
    mask: pd.Series  # True = keep, False = exclude
    total_epochs: int
    excluded_epochs: int
    artifact_pct: float
    method: str

def apply_artifact_filter(df: pd.DataFrame, artifact_columns: dict[str, list[str]],
                          mode: str = "combined",
                          # intensity_threshold: Persyst 0-30+ scale; typical artifact 5-15; default 10 = conservative-clinical
                          intensity_threshold: float = 10.0,
                          # quality_threshold: user-facing percentage (0-100).
                          # Persyst "Electrode Signal Quality" data is on a 0-1 scale (median ~0.0006 for clean signal).
                          # quality_threshold is divided by 100 internally to convert to the data scale.
                          # Example: quality_threshold=50 → rejects electrodes with quality_data > 0.5 (severely degraded).
                          quality_threshold: float = 50.0,
                          min_clean_electrodes: int = 10) -> FilterResult:
    """Apply configurable artifact filtering.

    artifact_columns should have keys: 'intensity' and 'quality'
    with lists of column names for each.
    """
    n = len(df)
    mask = pd.Series(True, index=df.index)

    if mode == "none":
        return FilterResult(mask=mask, total_epochs=n, excluded_epochs=0,
                          artifact_pct=0.0, method="none")

    # Intensity filter
    if mode in ("intensity", "combined") and artifact_columns.get("intensity"):
        intensity_cols = [c for c in artifact_columns["intensity"] if c in df.columns]
        if intensity_cols:
            # Use max intensity across all intensity columns
            max_intensity = df[intensity_cols].max(axis=1)
            mask &= max_intensity < intensity_threshold

    # Quality filter
    # Persyst "Electrode Signal Quality" is a degradation metric:
    # low values = clean signal, high values = poor quality / artifact.
    # An electrode is "clean" when its quality value is BELOW the threshold.
    if mode in ("quality", "combined") and artifact_columns.get("quality"):
        quality_cols = [c for c in artifact_columns["quality"] if c in df.columns]
        if quality_cols:
            quality_data = df[quality_cols]
            # Convert user-facing percentage threshold to Persyst data scale (0-1).
            # Data median is ~0.0006 for clean signal; severely degraded electrodes approach 1.0.
            effective_threshold = quality_threshold / 100.0
            clean_count = (quality_data <= effective_threshold).sum(axis=1)
            mask &= clean_count >= min_clean_electrodes

    excluded = int((~mask).sum())
    rejection_frac = (~mask).sum() / len(mask) if len(mask) > 0 else 0
    if rejection_frac > 0.8:
        import warnings
        warnings.warn(
            f"Artifact filter rejected {rejection_frac:.0%} of epochs. "
            f"Check intensity_threshold ({intensity_threshold}) against your data scale (Persyst: 0-30+).",
            stacklevel=2,
        )
    return FilterResult(
        mask=mask, total_epochs=n, excluded_epochs=excluded,
        artifact_pct=100.0 * excluded / n if n > 0 else 0.0, method=mode
    )
