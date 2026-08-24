"""Artifact-Reduction rejection: turn suppressed zeros into NaN.

Persyst writes ``0``, not blank, when Artifact Reduction cannot produce a value
for a channel in an epoch. Those zeros are missing data. Treating them as
measurements biases every mean, ratio and spectral summary downward, and because
they cluster in the most artifacted stretches the bias is systematic rather than
random.

Proven by toggling AR on one recording (subject-4, full Research panel): with AR off
every region is zero exactly 0.12% of the time — uniformly, because that is one
real 37-second recording gap. With AR on the rate ranges 0.10%–24.5% by region.
Only 1.7% of AR-on zeros are also zero without AR, so 98.3% are AR rejections.

Two properties drive the design:

* **Rejection is regional, not global.** All regions are rejected together in only
  ~0.1% of rows while ~27% are partial, so a whole-row rule both over-nulls good
  regions and under-nulls bad ones.
* **Zero means different things in different families.** Suppression Ratio is
  legitimately 0 in 74% of *clean* rows and binary detectors are legitimately 0
  most of the time. A rule that nulls any measure on its own zero destroys real
  data, so the mask is built only from measures that cannot physically be zero.

See docs/_project/plans/NULL_ZERO_AND_METADATA_SPEC.md §2 for the evidence.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Physically positive-definite families: an exact 0 cannot be a measurement, so a
# 0 here IS the rejection signal. Only these seed the mask.
ZERO_IMPOSSIBLE: frozenset[str] = frozenset({
    "fft_spectrogram", "fft_power", "aeeg", "peak_envelope",
    "rhythmicity", "coherence_spectrogram",
})

# Continuous, but legitimately zero. Never inferred from their own value — nulled
# only where the mask says their region was rejected.
ZERO_LEGITIMATE: frozenset[str] = frozenset({
    "suppression_ratio", "asymmetry", "spectral_edge",
    "adr", "relative_power", "alpha_variability",
})

# Binary, count and categorical families. A 0 is a real "no event" and must
# survive — but only while some region was actually analysable. See _apply().
NEVER_NULL: frozenset[str] = frozenset({
    "rhythmic_delta", "rda", "sleep", "spike_density",
    "seizure_detection", "seizure_probability", "seizure_notification",
    "seizure_burden", "status_epilepticus",
    "artifact_intensity", "electrode_quality",
    "heart_rate", "annotation", "time_display",
})

# Longest first so "Left Anterior" wins over "Anterior".
_REGIONS: tuple[str, ...] = (
    "Left Anterior", "Right Anterior", "Left Posterior", "Right Posterior",
    "Left Hemisphere", "Right Hemisphere",
    "Asym Anterior", "Asym Posterior", "Asym Parasagittal", "Asym Temporal",
    "Asym Hemi", "All 10-20", "Anterior", "Posterior",
)

# Asymmetry trends are defined on "Asym *" regions, and no positive-definite
# family is exported on those regions — so they have no mask of their own and
# would never be nulled, even though REASI is 100% zero inside a rejected epoch.
# Fall back to the anatomically-equivalent region the mask does cover.
_REGION_FALLBACK: dict[str, tuple[str, ...]] = {
    "Asym Hemi": ("All 10-20", "Left Hemisphere", "Right Hemisphere"),
    "Asym Anterior": ("Anterior", "All 10-20"),
    "Asym Posterior": ("Posterior", "All 10-20"),
    "Asym Parasagittal": ("All 10-20",),
    "Asym Temporal": ("All 10-20",),
}

# A reference measure that is zero in ≥95% of rows carries no information about
# when rejection happened, so it cannot seed the mask.
_DEAD_REFERENCE = 0.95


@dataclass
class ARRejectionResult:
    """Outcome of applying the rejection mask."""

    region_reject_pct: dict[str, float] = field(default_factory=dict)
    all_regions_mask: pd.Series | None = None      # True = every region rejected
    n_regions: int = 0
    n_mask_sources: int = 0
    cells_nulled: int = 0
    columns_touched: int = 0
    rows_all_rejected: int = 0
    rows_partial: int = 0
    segment_empty: bool = False
    warnings: list[str] = field(default_factory=list)


def region_of(trend_name: str) -> str:
    """Return the regional token in *trend_name*, or "" if it names no region."""
    low = (trend_name or "").lower()
    for r in _REGIONS:
        if r.lower() in low:
            return r
    return ""


def apply_ar_rejection(
    df: pd.DataFrame,
    schema: list,
    *,
    dead_reference_frac: float = _DEAD_REFERENCE,
) -> tuple[pd.DataFrame, ARRejectionResult]:
    """Replace AR-suppressed zeros with NaN, in place on a copy of *df*.

    ``schema`` is the list of ColumnEntry produced by the column mapper; column
    identity in *df* is the Persyst ``I{n}_{k}`` code.

    Returns the modified frame and a result describing what was nulled. The frame
    is copied, never mutated in place — the raw export stays intact.
    """
    res = ARRejectionResult()
    entries = [e for e in schema if getattr(e, "code", None) in df.columns]
    if not entries:
        res.warnings.append("AR rejection skipped: no schema columns present in frame")
        return df, res

    # Group columns by instrument so an instrument is rejected only when ALL of
    # its sub-columns are zero — a single zero bin in a spectrogram is normal.
    by_instrument: dict[int, list] = {}
    for e in entries:
        by_instrument.setdefault(e.i_group, []).append(e)

    # ── build the mask, from ZERO_IMPOSSIBLE instruments only ──────────
    region_masks: dict[str, list[pd.Series]] = {}
    for cols in by_instrument.values():
        fam = cols[0].family
        reg = region_of(cols[0].trend_name)
        if fam not in ZERO_IMPOSSIBLE or not reg:
            continue
        codes = [c.code for c in cols]
        null = (df[codes] == 0).all(axis=1)
        if null.mean() >= dead_reference_frac:
            continue                      # dead channel: cannot inform the mask
        region_masks.setdefault(reg, []).append(null)

    if not region_masks:
        res.segment_empty = True
        res.warnings.append(
            "AR rejection skipped: every positive-definite reference measure is "
            f">={dead_reference_frac:.0%} zero — this segment is empty, not rejected"
        )
        return df, res

    regions = sorted(region_masks)
    rejected = {r: pd.concat(m, axis=1).all(axis=1) for r, m in region_masks.items()}
    stacked = pd.concat([rejected[r] for r in regions], axis=1)
    n_rejected = stacked.sum(axis=1)
    all_regions = n_rejected == len(regions)

    res.n_regions = len(regions)
    res.n_mask_sources = sum(len(v) for v in region_masks.values())
    res.region_reject_pct = {r: round(100 * float(rejected[r].mean()), 3) for r in regions}
    res.all_regions_mask = all_regions
    res.rows_all_rejected = int(all_regions.sum())
    res.rows_partial = int(((n_rejected > 0) & ~all_regions).sum())

    # ── apply ─────────────────────────────────────────────────────────
    out = df.copy()
    nulled = 0
    touched = 0
    for cols in by_instrument.values():
        fam = cols[0].family
        codes = [c.code for c in cols]
        reg = region_of(cols[0].trend_name)

        if fam in ZERO_IMPOSSIBLE:
            # Its own zero is the signal — including for instruments with no
            # region (whole-head aggregates carry their own validity).
            mask = (out[codes] == 0).all(axis=1)
        elif fam in ZERO_LEGITIMATE:
            # Never inferred from its own value; nulled only where its region was
            # rejected. Without a region there is nothing to key on, so leave it.
            src = reg if reg in rejected else next(
                (f for f in _REGION_FALLBACK.get(reg, ()) if f in rejected), "")
            if not src:
                continue
            mask = rejected[src]
        elif fam in NEVER_NULL:
            # A binary 0 only means "no event" if there was signal to detect in.
            # When every region is rejected there was none, so those epochs are
            # not true negatives and must not inflate any rate denominator.
            mask = all_regions
        else:
            continue

        if not mask.any():
            continue
        n = int(mask.sum()) * len(codes)
        out.loc[mask, codes] = np.nan
        nulled += n
        touched += len(codes)

    res.cells_nulled = nulled
    res.columns_touched = touched
    log.info(
        "AR rejection: %d regions from %d reference measures; %d rows all-rejected, "
        "%d partial; nulled %d cells across %d columns",
        res.n_regions, res.n_mask_sources, res.rows_all_rejected,
        res.rows_partial, nulled, touched,
    )
    return out, res
