"""Pipeline configuration models (Pydantic v2)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ArtifactConfig(BaseModel):
    """Artifact rejection settings."""

    mode: Literal["none", "intensity", "quality", "combined"] = "quality"
    intensity_threshold: float = Field(default=5.0, ge=0.0)
    quality_threshold: float = Field(default=50.0, ge=0.0, le=100.0)
    min_clean_electrodes: int = Field(default=10, ge=0)

    # Persyst writes 0 rather than blank when Artifact Reduction cannot produce a
    # value, so those zeros are missing data, not measurements. Defaults ON: it
    # corrects the recorded values rather than changing an analysis policy, and
    # leaving it off silently biases every mean and ratio downward. Disable only
    # to reproduce a pre-2026-08 result.
    ar_rejection: bool = True
    # Exclude epochs where AR rejected every region — nothing was analysable.
    exclude_all_region_rejected: bool = True


class SeizureConfig(BaseModel):
    """Seizure exclusion settings."""

    exclusion_mode: Literal["none", "detected", "probability"] = "none"
    probability_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class BinningConfig(BaseModel):
    """Time-bin settings."""

    bin_edges_hours: list[float] = Field(default=[0, 6, 12, 18, 24, 48, 72])
    min_coverage_hours: float = Field(default=1.0, gt=0)
    # Background-continuity-index cutoff. An epoch counts as "continuous"
    # (non-suppressed) when its burst-suppression ratio is BELOW this value.
    # BSR is PERCENT (0-100), NOT a 0-1 fraction (Persyst CSV §3.18 /
    # PERSYST_V10_REFERENCE §3a). Default 10.0 → <10% suppression = continuous
    # background (clinically chosen cutoff, PI-approved 2026-06-11).
    suppression_continuity_threshold_pct: float = Field(default=10.0, ge=0.0, le=100.0)
    include_extended_bins: bool = Field(default=False)
    extended_bin_width_hours: float = Field(default=24.0)
    max_hours: float = Field(default=168.0)  # 7 days

    @field_validator("bin_edges_hours")
    @classmethod
    def validate_bin_edges(cls, v: list[float]) -> list[float]:
        if len(v) < 2:
            raise ValueError("bin_edges_hours must have at least 2 values to define 1 bin")
        if any(x < 0 for x in v):
            raise ValueError("bin_edges_hours must be non-negative")
        if not all(v[i] < v[i + 1] for i in range(len(v) - 1)):
            raise ValueError("bin_edges_hours must be strictly increasing")
        return v


class FeatureConfig(BaseModel):
    """Derived-feature settings."""

    # When True, bilateral anterior/posterior features return NaN unless both
    # hemispheres contributed — prevents unilateral survivor values from being
    # interpreted as bilateral physiology. Default False preserves the existing
    # NaN-tolerant-mean behavior; flip to True for publication runs.
    require_bilateral_hemispheres: bool = Field(default=False)


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration."""

    artifact: ArtifactConfig = Field(default_factory=ArtifactConfig)
    seizure: SeizureConfig = Field(default_factory=SeizureConfig)
    binning: BinningConfig = Field(default_factory=BinningConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    frequency_bands: dict[str, tuple[float, float]] = Field(default=None)  # None = use constants
    rosc_time: Optional[str] = None
    patient_age_days: Optional[float] = None

    def get_frequency_bands(self) -> dict:
        """Return configured frequency bands, falling back to defaults."""
        from .constants import FREQUENCY_BANDS

        return self.frequency_bands or FREQUENCY_BANDS
